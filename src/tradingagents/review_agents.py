"""Lightweight review agents for portfolio thesis checking.

Unlike the full 12-agent debate pipeline, these agents focus on verifying
whether an existing investment thesis still holds. Used by the portfolio
review process and the news reaction pipeline's MEDIUM-severity path.

TICKET-109
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass
class ReviewResult:
    """Output from the thesis review pipeline."""

    ticker: str
    verdict: Literal["intact", "weakening", "broken"]
    confidence: int  # 1-10
    reasoning: str
    thesis_update: str | None = None
    action: str = "HOLD"  # HOLD | TIGHTEN_STOP | FLAG_FOR_DEBATE | SELL
    stop_loss_update: float | None = None


@dataclass
class AssessmentResult:
    """Output from a quick 2-agent news assessment."""

    ticker: str
    bull_view: str
    bear_view: str
    net_impact: str  # "positive" | "negative" | "neutral"
    severity_reassessment: str  # may upgrade MEDIUM → HIGH
    reasoning: str


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------


THESIS_ASSESSOR_SYSTEM_PROMPT = """You are a portfolio review analyst. Your job is to assess whether an existing investment thesis still holds.

You are NOT re-debating the investment from scratch. You are checking if the ORIGINAL thesis is still valid given recent data.

BIAS: Default to INTACT unless there is clear evidence of deterioration. Most holdings don't change materially day-to-day.

ORIGINAL THESIS:
{rationale}

KEY CATALYSTS WE ARE WATCHING:
{catalysts}

CONDITIONS THAT WOULD INVALIDATE THIS THESIS:
{invalidation_conditions}

POSITION DATA:
- Ticker: {ticker}
- Entry: ${entry_price:.2f} on {entry_date} ({days_held} days ago)
- Current: ${current_price:.2f} ({pnl_pct:+.1f}% P&L)
- Category: {category} (expected hold: {expected_hold_months} months)
- Trailing high since entry: ${trailing_high:.2f}

MARKET ANALYST UPDATE:
{market_update}

FUNDAMENTALS ANALYST UPDATE:
{fundamentals_update}

RECENT NEWS EVENTS:
{news_summary}

OUTPUT (you MUST follow this exact format):
VERDICT: INTACT | WEAKENING | BROKEN
CONFIDENCE: <1-10>
REASONING: <2-3 sentences explaining your verdict>
THESIS_UPDATE: <any modifications to the thesis, or "none">
ACTION: HOLD | TIGHTEN_STOP | FLAG_FOR_DEBATE | SELL
STOP_LOSS_UPDATE: <new stop price if tightening, or "none">

VERDICT CRITERIA:
- INTACT: Fundamentals on track, catalysts still ahead, no invalidation condition triggered
- WEAKENING: Some invalidation conditions partially met, key catalyst delayed or uncertain, technicals deteriorating
- BROKEN: Invalidation condition fully met, fundamental thesis destroyed, or position down significantly with no recovery thesis
"""


QUICK_ASSESSMENT_SYSTEM_PROMPT = """You are assessing the impact of a specific news event on an existing investment position.

POSITION THESIS:
We hold {ticker} because: {rationale}
Key catalysts: {catalysts}
Thesis would be invalidated if: {invalidation_conditions}

NEWS EVENT:
{news_summary}

Provide two perspectives:

BULL VIEW: How does this news SUPPORT or not affect our thesis? (2-3 sentences)
BEAR VIEW: How does this news THREATEN our thesis? (2-3 sentences)
NET IMPACT: positive | negative | neutral
SEVERITY: Should this be escalated? (keep_medium | upgrade_to_high | upgrade_to_critical)
REASONING: Overall assessment in 1-2 sentences
"""


# ---------------------------------------------------------------------------
# Thesis Assessor
# ---------------------------------------------------------------------------


def run_thesis_review(
    ticker: str,
    thesis_record: dict,
    current_price: float = 0.0,
    trailing_high: float = 0.0,
    market_update: str = "",
    fundamentals_update: str = "",
    news_summary: str = "",
    config: dict | None = None,
) -> ReviewResult:
    """Run the thesis assessor on a single holding.

    Args:
        ticker: Stock ticker symbol.
        thesis_record: ThesisRecord as a dict (from thesis.py).
        current_price: Current stock price.
        trailing_high: Highest price since entry.
        market_update: Output from Market Analyst.
        fundamentals_update: Output from Fundamentals Analyst.
        news_summary: Recent news events summary.
        config: Optional config override.

    Returns:
        ReviewResult with verdict, confidence, and recommended action.
    """
    from .llm_clients.factory import create_llm_client

    # Extract thesis fields
    thesis = thesis_record.get("thesis", {})
    targets = thesis_record.get("targets", {})
    review = thesis_record.get("review", {})

    entry_price = thesis_record.get("entry_price", 0)
    entry_date = thesis_record.get("entry_date", "unknown")
    category = thesis_record.get("category", "TACTICAL")
    expected_hold = thesis_record.get("expected_hold_months", 6)

    # Calculate derived values
    if current_price <= 0 and entry_price > 0:
        current_price = entry_price  # fallback
    if trailing_high <= 0:
        trailing_high = max(current_price, entry_price)

    pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
    days_held = 0
    try:
        from datetime import datetime
        entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
        days_held = (datetime.now() - entry_dt).days
    except Exception:
        pass

    # Build prompt
    catalysts = thesis.get("key_catalysts", [])
    invalidation = thesis.get("invalidation_conditions", [])

    prompt = THESIS_ASSESSOR_SYSTEM_PROMPT.format(
        ticker=ticker,
        rationale=thesis.get("rationale", "No rationale recorded"),
        catalysts="\n".join(f"- {c}" for c in catalysts) if catalysts else "None recorded",
        invalidation_conditions="\n".join(f"- {c}" for c in invalidation) if invalidation else "None recorded",
        entry_price=entry_price,
        entry_date=entry_date,
        days_held=days_held,
        current_price=current_price,
        pnl_pct=pnl_pct,
        category=category,
        expected_hold_months=expected_hold,
        trailing_high=trailing_high,
        market_update=market_update or "No market update available",
        fundamentals_update=fundamentals_update or "No fundamentals update available",
        news_summary=news_summary or "No recent news events",
    )

    # Call LLM
    model = os.getenv("DEEP_LLM_MODEL", "gpt-4o")
    provider = os.getenv("LLM_PROVIDER", "openai")

    try:
        client = create_llm_client(provider=provider, model=model)
        response = client.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("Thesis assessor LLM call failed for %s: %s", ticker, exc)
        return ReviewResult(
            ticker=ticker,
            verdict="intact",
            confidence=3,
            reasoning=f"LLM call failed: {exc}. Defaulting to INTACT.",
            action="HOLD",
        )

    return _parse_review_result(ticker, text)


def _parse_review_result(ticker: str, text: str) -> ReviewResult:
    """Parse the structured output from the thesis assessor LLM."""
    verdict = "intact"
    confidence = 5
    reasoning = ""
    thesis_update = None
    action = "HOLD"
    stop_loss_update = None

    for line in text.split("\n"):
        line = line.strip()
        upper = line.upper()

        if upper.startswith("VERDICT:"):
            val = line.split(":", 1)[1].strip().upper()
            if "BROKEN" in val:
                verdict = "broken"
            elif "WEAKENING" in val:
                verdict = "weakening"
            else:
                verdict = "intact"

        elif upper.startswith("CONFIDENCE:"):
            try:
                confidence = int(re.search(r"\d+", line.split(":", 1)[1]).group())
                confidence = max(1, min(10, confidence))
            except Exception:
                confidence = 5

        elif upper.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

        elif upper.startswith("THESIS_UPDATE:"):
            val = line.split(":", 1)[1].strip()
            if val.lower() not in ("none", "n/a", ""):
                thesis_update = val

        elif upper.startswith("ACTION:"):
            val = line.split(":", 1)[1].strip().upper()
            for a in ("SELL", "FLAG_FOR_DEBATE", "TIGHTEN_STOP", "HOLD"):
                if a in val:
                    action = a
                    break

        elif upper.startswith("STOP_LOSS_UPDATE:"):
            val = line.split(":", 1)[1].strip()
            if val.lower() not in ("none", "n/a", ""):
                try:
                    stop_loss_update = float(val.replace("$", "").replace(",", ""))
                except ValueError:
                    pass

    return ReviewResult(
        ticker=ticker,
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        thesis_update=thesis_update,
        action=action,
        stop_loss_update=stop_loss_update,
    )


# ---------------------------------------------------------------------------
# Quick assessment (for news MEDIUM severity)
# ---------------------------------------------------------------------------


def run_quick_assessment(
    ticker: str,
    thesis_record: dict,
    news_summary: str,
    config: dict | None = None,
) -> AssessmentResult:
    """Run a quick bull/bear assessment of news impact on a thesis.

    Used by the news reaction pipeline for MEDIUM-severity events.
    Cheaper and faster than the full thesis review.
    """
    from .llm_clients.factory import create_llm_client

    thesis = thesis_record.get("thesis", {})

    prompt = QUICK_ASSESSMENT_SYSTEM_PROMPT.format(
        ticker=ticker,
        rationale=thesis.get("rationale", "No rationale recorded"),
        catalysts=", ".join(thesis.get("key_catalysts", [])) or "None",
        invalidation_conditions=", ".join(thesis.get("invalidation_conditions", [])) or "None",
        news_summary=news_summary,
    )

    model = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
    provider = os.getenv("LLM_PROVIDER", "openai")

    try:
        client = create_llm_client(provider=provider, model=model)
        response = client.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("Quick assessment LLM call failed for %s: %s", ticker, exc)
        return AssessmentResult(
            ticker=ticker,
            bull_view="Assessment failed",
            bear_view="Assessment failed",
            net_impact="neutral",
            severity_reassessment="keep_medium",
            reasoning=f"LLM call failed: {exc}",
        )

    return _parse_assessment_result(ticker, text)


def _parse_assessment_result(ticker: str, text: str) -> AssessmentResult:
    """Parse the quick assessment LLM output."""
    bull_view = ""
    bear_view = ""
    net_impact = "neutral"
    severity = "keep_medium"
    reasoning = ""

    current_section = None
    for line in text.split("\n"):
        line = line.strip()
        upper = line.upper()

        if upper.startswith("BULL VIEW:"):
            bull_view = line.split(":", 1)[1].strip()
            current_section = "bull"
        elif upper.startswith("BEAR VIEW:"):
            bear_view = line.split(":", 1)[1].strip()
            current_section = "bear"
        elif upper.startswith("NET IMPACT:"):
            val = line.split(":", 1)[1].strip().lower()
            if "negative" in val:
                net_impact = "negative"
            elif "positive" in val:
                net_impact = "positive"
            else:
                net_impact = "neutral"
            current_section = None
        elif upper.startswith("SEVERITY:"):
            val = line.split(":", 1)[1].strip().lower()
            if "critical" in val:
                severity = "upgrade_to_critical"
            elif "high" in val:
                severity = "upgrade_to_high"
            else:
                severity = "keep_medium"
            current_section = None
        elif upper.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()
            current_section = None
        elif current_section == "bull" and line:
            bull_view += " " + line
        elif current_section == "bear" and line:
            bear_view += " " + line

    return AssessmentResult(
        ticker=ticker,
        bull_view=bull_view.strip(),
        bear_view=bear_view.strip(),
        net_impact=net_impact,
        severity_reassessment=severity,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Analyst update helpers
# ---------------------------------------------------------------------------


def run_market_update(ticker: str, config: dict | None = None) -> str:
    """Run the Market Analyst's tools to get current technicals.

    Returns a text summary of current technical indicators.
    """
    try:
        from .dataflows.interface import get_stock_data, get_indicators

        price_data = get_stock_data(ticker, config=config)
        indicators = get_indicators(ticker, config=config)

        parts = []
        if price_data:
            parts.append(f"Price data (recent):\n{str(price_data)[:1000]}")
        if indicators:
            parts.append(f"Technical indicators:\n{str(indicators)[:1000]}")

        return "\n\n".join(parts) if parts else "No market data available"

    except Exception as exc:
        logger.warning("Market update for %s failed: %s", ticker, exc)
        return f"Market data fetch failed: {exc}"


def run_fundamentals_update(ticker: str, config: dict | None = None) -> str:
    """Run the Fundamentals Analyst's tools to get latest data.

    Returns a text summary of current fundamentals.
    """
    try:
        from .dataflows.interface import get_fundamentals

        fundamentals = get_fundamentals(ticker, config=config)

        if fundamentals:
            return f"Fundamentals:\n{str(fundamentals)[:1500]}"
        return "No fundamentals data available"

    except Exception as exc:
        logger.warning("Fundamentals update for %s failed: %s", ticker, exc)
        return f"Fundamentals fetch failed: {exc}"
