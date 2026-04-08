"""
news_monitor_triage.py
======================
LLM-based news triage for the real-time news monitor.

Uses OpenAI's structured output to analyze batches of news articles
and identify material events that could affect stock prices.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    OpenAI = None

from news_monitor_config import (
    TRIAGE_LLM_MODEL,
    TRIAGE_MAX_TOKENS,
    TRIAGE_TEMPERATURE,
    URGENCY_HIGH,
    URGENCY_MEDIUM,
    URGENCY_LOW,
)

logger = logging.getLogger(__name__)

# Initialize OpenAI client (lazy initialization)
_client: Optional[OpenAI] = None

def get_openai_client() -> Optional[OpenAI]:
    """Get or create OpenAI client."""
    global _client
    if not HAS_OPENAI:
        return None
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        _client = OpenAI(api_key=api_key)
    return _client


@dataclass
class TriageResult:
    """Result of triaging a single news item."""
    news_index: int
    affected_tickers: list[str]
    urgency: str
    sentiment: str
    reasoning: str
    action_recommended: bool


# The JSON schema for structured output
TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "news_index": {
                        "type": "integer",
                        "description": "Index of the news item in the input batch"
                    },
                    "affected_tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Stock ticker symbols that could be materially affected by this news"
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["HIGH", "MEDIUM", "LOW"],
                        "description": "HIGH = breaking news that could move stock 2%+ immediately; MEDIUM = notable but not urgent; LOW = routine"
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["BULLISH", "BEARISH", "NEUTRAL"],
                        "description": "Expected market reaction direction"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "One-sentence explanation of why these tickers are affected"
                    },
                    "action_recommended": {
                        "type": "boolean",
                        "description": "True if immediate analysis/trading action is warranted (HIGH urgency with clear ticker impact)"
                    }
                },
                "required": ["news_index", "affected_tickers", "urgency", "sentiment", "reasoning", "action_recommended"],
                "additionalProperties": False
            }
        }
    },
    "required": ["events"],
    "additionalProperties": False
}


# System prompt for the triage LLM
TRIAGE_SYSTEM_PROMPT = """You are a financial news triage system for an algorithmic trading bot.

Your job is to analyze breaking news and identify which stocks could be materially affected.

Key principles:
1. Focus on PRICE-MOVING events: earnings, M&A, FDA decisions, major contract wins/losses, executive changes, regulatory actions, significant analyst upgrades/downgrades
2. Urgency levels:
   - HIGH: Breaking news that could move a stock 2%+ within minutes (earnings beats/misses, M&A announcements, FDA approvals/rejections, major contract wins)
   - MEDIUM: Noteworthy but not immediately price-moving (sector trends, minor analyst changes, routine product launches)
   - LOW: Background noise (general market commentary, historical analysis, non-specific industry news)
3. Ticker extraction:
   - Explicit mentions: If news says "NVDA beats earnings", include NVDA
   - Implicit impacts: If news says "TSMC cuts chip output", include AMD, NVDA, AVGO (chip designers who rely on TSMC)
   - Sector plays: If major oil discovery, include XOM, CVX, etc.
   - Reddit/meme potential: For high-retail-interest news (short squeezes, viral stories), note potential meme stocks
4. Sentiment:
   - BULLISH: Expected to drive price up (earnings beat, contract win, upgrade)
   - BEARISH: Expected to drive price down (earnings miss, investigation, downgrade)
   - NEUTRAL: Mixed or unclear impact
5. Action recommendation:
   - Only recommend action for HIGH urgency events with clear, specific ticker impact
   - If you're unsure about the impact, don't recommend action
   - Err on the side of caution - better to miss a trade than fire on false signals

Available watchlist for reference (analyze these plus any new tickers you identify):
{watchlist}

Return your analysis in the exact JSON schema provided."""


def build_watchlist_context(watchlist_tickers: list[str]) -> str:
    """Build watchlist context string for the prompt."""
    if not watchlist_tickers:
        return "No current watchlist."
    return ", ".join(sorted(watchlist_tickers))


def format_news_batch(news_items: list[dict]) -> str:
    """
    Format a batch of news items for the LLM.

    Each item should have: source, title, summary, tickers_mentioned
    """
    lines = []
    for i, item in enumerate(news_items):
        lines.append(f"[{i}] Source: {item['source']}")
        lines.append(f"    Title: {item['title']}")
        if item.get('summary'):
            lines.append(f"    Summary: {item['summary'][:200]}")
        if item.get('tickers_mentioned'):
            lines.append(f"    Tickers mentioned: {', '.join(item['tickers_mentioned'])}")
        lines.append("")
    return "\n".join(lines)


def triage_news_batch(
    news_items: list[dict],
    watchlist_tickers: list[str],
) -> list[TriageResult]:
    """
    Triage a batch of news items using LLM.

    Args:
        news_items: List of news item dicts with source, title, summary, tickers_mentioned
        watchlist_tickers: Current watchlist for context

    Returns:
        List of TriageResult objects
    """
    if not news_items:
        return []

    client = get_openai_client()
    if not client:
        logger.warning("OpenAI not available or OPENAI_API_KEY not set, falling back to basic triage")
        return _fallback_triage(news_items)

    try:
        # Build prompt
        system_prompt = TRIAGE_SYSTEM_PROMPT.format(
            watchlist=build_watchlist_context(watchlist_tickers)
        )
        user_prompt = f"Analyze these {len(news_items)} news items:\n\n{format_news_batch(news_items)}"

        # Call OpenAI with structured output
        response = client.chat.completions.create(
            model=TRIAGE_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": {"name": "news_triage", "schema": TRIAGE_SCHEMA}},
            max_tokens=TRIAGE_MAX_TOKENS,
            temperature=TRIAGE_TEMPERATURE,
        )

        # Parse response
        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty LLM response")
            return _fallback_triage(news_items)

        result = json.loads(content)
        events = result.get("events", [])

        # Convert to TriageResult objects
        triage_results = []
        for event in events:
            try:
                triage_results.append(TriageResult(
                    news_index=event["news_index"],
                    affected_tickers=[t.upper() for t in event.get("affected_tickers", [])],
                    urgency=event.get("urgency", URGENCY_LOW),
                    sentiment=event.get("sentiment", "NEUTRAL"),
                    reasoning=event.get("reasoning", ""),
                    action_recommended=event.get("action_recommended", False),
                ))
            except (KeyError, TypeError) as e:
                logger.warning(f"Invalid triage event: {e}")
                continue

        # Log cost
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = (input_tokens * 0.00015 + output_tokens * 0.00060) / 1000  # gpt-4o-mini pricing
        logger.info(f"Triage batch: {len(news_items)} items, {input_tokens} in / {output_tokens} out, ${cost:.4f}")

        return triage_results

    except Exception as e:
        logger.exception(f"LLM triage failed: {e}")
        return _fallback_triage(news_items)


def _fallback_triage(news_items: list[dict]) -> list[TriageResult]:
    """
    Fallback keyword-based triage when LLM is unavailable.

    This is a simplified version that catches obvious high-urgency events.
    """
    results = []

    high_urgency_keywords = [
        "earnings", "beat", "miss", "guidance", "outlook",
        "acquisition", "merger", "buyout", "acquire", "merging",
        "fda", "approval", "rejection", "clinical trial",
        "bankruptcy", "layoff", "layoffs", "restructuring",
        "cyberattack", "hack", "breach", "data breach",
        "investigation", "lawsuit", "sec investigation",
        "upgrade", "downgrade", "price target", "analyst",
        "short squeeze", "gamma squeeze",
        "ceo resigns", "ceo departure", "executive departure",
        "contract win", "major contract", "billion contract",
    ]

    bearish_keywords = ["miss", "layoff", "layoffs", "bankruptcy", "investigation", "lawsuit", "rejection", "downgrade", "bearish", "sell"]
    bullish_keywords = ["beat", "approval", "contract win", "upgrade", "bullish", "buy", "strong buy"]

    for i, item in enumerate(news_items):
        title_lower = item.get("title", "").lower()
        summary_lower = item.get("summary", "").lower()
        full_text = title_lower + " " + summary_lower

        # Check urgency
        urgency = URGENCY_LOW
        for kw in high_urgency_keywords:
            if kw in full_text:
                urgency = URGENCY_HIGH
                break

        # Determine sentiment
        sentiment = "NEUTRAL"
        bearish_count = sum(1 for kw in bearish_keywords if kw in full_text)
        bullish_count = sum(1 for kw in bullish_keywords if kw in full_text)
        if bullish_count > bearish_count:
            sentiment = "BULLISH"
        elif bearish_count > bullish_count:
            sentiment = "BEARISH"

        # Get tickers
        tickers = [t.upper() for t in item.get("tickers_mentioned", [])]

        # Recommend action only for HIGH urgency with tickers
        action_recommended = (urgency == URGENCY_HIGH and len(tickers) > 0)

        results.append(TriageResult(
            news_index=i,
            affected_tickers=tickers,
            urgency=urgency,
            sentiment=sentiment,
            reasoning=f"Keyword-based triage (LLM unavailable)",
            action_recommended=action_recommended,
        ))

    return results


def estimate_triage_cost(num_articles: int) -> float:
    """
    Estimate the cost of triaging a batch of articles.

    Rough estimate based on average token counts:
    - Input: ~200 tokens per article (title + summary + formatting)
    - Output: ~50 tokens per article (JSON response)
    """
    input_tokens = num_articles * 200
    output_tokens = num_articles * 50
    return (input_tokens * 0.00015 + output_tokens * 0.00060) / 1000
