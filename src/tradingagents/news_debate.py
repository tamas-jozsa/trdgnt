"""News-specific debate pipeline with graduated response.

Assesses news impact against existing position theses. Unlike the discovery
pipeline (which evaluates from scratch), this asks: "Does this news affect
why we hold this stock?"

Four severity levels with different response depths:
- LOW: log only
- MEDIUM: 2-agent quick assessment
- HIGH: full 12-agent debate
- CRITICAL: immediate Risk Judge decision

TICKET-111
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class NewsSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TriageResult:
    """Result from LLM triage of a single news item."""

    headline: str
    source: str = ""
    affected_tickers: list[str] = field(default_factory=list)
    severity: NewsSeverity = NewsSeverity.LOW
    sentiment: str = "neutral"  # positive | negative | mixed | neutral
    reasoning: str = ""


@dataclass
class NewsTradeDecision:
    """Final trade decision from the news reaction pipeline."""

    ticker: str
    action: str  # BUY | SELL | HOLD
    conviction: int  # 1-10
    reasoning: str
    severity: NewsSeverity = NewsSeverity.LOW
    should_execute: bool = False  # True only when conviction >= threshold


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------


TRIAGE_SYSTEM_PROMPT = """You are a news triage analyst for an investment portfolio.

CURRENT PORTFOLIO:
{portfolio_summary}

NEWS ITEMS TO TRIAGE:
{news_items}

For EACH news item, classify:
1. Which portfolio tickers are DIRECTLY affected (only tickers we hold)
2. Severity: LOW (routine, no impact) | MEDIUM (potentially relevant) | HIGH (likely thesis impact) | CRITICAL (clear and immediate threat/opportunity)
3. Sentiment: positive | negative | mixed | neutral

OUTPUT FORMAT (one block per news item):
---
HEADLINE: <headline>
AFFECTED: <comma-separated tickers, or NONE>
SEVERITY: LOW | MEDIUM | HIGH | CRITICAL
SENTIMENT: positive | negative | mixed | neutral
REASONING: <1 sentence>
---

SEVERITY GUIDE:
- LOW: Routine analyst note, minor filing, no thesis impact
- MEDIUM: Sector signal, competitor news, possible indirect impact
- HIGH: Earnings miss/beat, guidance change, upgrade/downgrade, regulatory action
- CRITICAL: Fraud allegation, FDA rejection, war/sanctions, flash crash, CEO departure
"""


def triage_news(
    news_items: list[dict],
    portfolio_theses: dict,
    conviction_threshold: int = 8,
) -> list[TriageResult]:
    """Classify news items by severity and identify affected portfolio tickers.

    Args:
        news_items: List of {headline, source, summary} dicts.
        portfolio_theses: {ticker: ThesisRecord dict} of current holdings.
        conviction_threshold: Minimum conviction for trade execution.

    Returns:
        List of TriageResult, one per news item.
    """
    if not news_items:
        return []

    from .llm_clients.factory import create_llm_client

    # Build portfolio summary for context
    portfolio_lines = []
    for ticker, thesis in portfolio_theses.items():
        t = thesis.get("thesis", {})
        rationale = t.get("rationale", "")[:100]
        portfolio_lines.append(f"- {ticker}: {rationale}")

    portfolio_summary = "\n".join(portfolio_lines) if portfolio_lines else "Portfolio is EMPTY"

    # Build news items text
    news_text_lines = []
    for i, item in enumerate(news_items[:20], 1):  # cap at 20
        headline = item.get("headline", item.get("title", ""))
        summary = item.get("summary", "")[:200]
        source = item.get("source", "")
        news_text_lines.append(f"{i}. [{source}] {headline}")
        if summary:
            news_text_lines.append(f"   {summary}")

    prompt = TRIAGE_SYSTEM_PROMPT.format(
        portfolio_summary=portfolio_summary,
        news_items="\n".join(news_text_lines),
    )

    model = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
    provider = os.getenv("LLM_PROVIDER", "openai")

    try:
        client = create_llm_client(provider=provider, model=model)
        response = client.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("News triage LLM call failed: %s", exc)
        # Fallback: mark everything as LOW
        return [
            TriageResult(
                headline=item.get("headline", ""),
                source=item.get("source", ""),
                severity=NewsSeverity.LOW,
                reasoning=f"Triage failed: {exc}",
            )
            for item in news_items
        ]

    return _parse_triage_results(text, news_items)


def _parse_triage_results(text: str, news_items: list[dict]) -> list[TriageResult]:
    """Parse LLM triage output into TriageResult list."""
    results = []
    current = {}

    for line in text.split("\n"):
        line = line.strip()
        if line == "---":
            if current.get("headline"):
                results.append(_build_triage_result(current))
            current = {}
            continue

        upper = line.upper()
        if upper.startswith("HEADLINE:"):
            current["headline"] = line.split(":", 1)[1].strip()
        elif upper.startswith("AFFECTED:"):
            val = line.split(":", 1)[1].strip()
            if val.upper() != "NONE":
                current["affected"] = [t.strip().upper() for t in val.split(",") if t.strip()]
            else:
                current["affected"] = []
        elif upper.startswith("SEVERITY:"):
            current["severity"] = line.split(":", 1)[1].strip().lower()
        elif upper.startswith("SENTIMENT:"):
            current["sentiment"] = line.split(":", 1)[1].strip().lower()
        elif upper.startswith("REASONING:"):
            current["reasoning"] = line.split(":", 1)[1].strip()

    # Don't forget the last block
    if current.get("headline"):
        results.append(_build_triage_result(current))

    return results


def _build_triage_result(data: dict) -> TriageResult:
    severity_map = {"low": NewsSeverity.LOW, "medium": NewsSeverity.MEDIUM,
                    "high": NewsSeverity.HIGH, "critical": NewsSeverity.CRITICAL}
    return TriageResult(
        headline=data.get("headline", ""),
        affected_tickers=data.get("affected", []),
        severity=severity_map.get(data.get("severity", "low"), NewsSeverity.LOW),
        sentiment=data.get("sentiment", "neutral"),
        reasoning=data.get("reasoning", ""),
    )


# ---------------------------------------------------------------------------
# Graduated responses
# ---------------------------------------------------------------------------


def assess_medium(
    ticker: str,
    thesis_record: dict,
    news_summary: str,
) -> dict:
    """MEDIUM severity: quick 2-agent assessment.

    Returns assessment dict with net_impact and severity_reassessment.
    """
    from .review_agents import run_quick_assessment

    result = run_quick_assessment(ticker, thesis_record, news_summary)
    return {
        "ticker": ticker,
        "severity": "medium",
        "bull_view": result.bull_view,
        "bear_view": result.bear_view,
        "net_impact": result.net_impact,
        "severity_reassessment": result.severity_reassessment,
        "reasoning": result.reasoning,
    }


def debate_high(
    ticker: str,
    thesis_record: dict,
    news_summary: str,
    trade_date: str = "",
) -> NewsTradeDecision:
    """HIGH severity: full 12-agent debate with thesis context.

    Returns trade decision with conviction score.
    """
    from .graph.trading_graph import TradingAgentsGraph
    from .default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["deep_think_llm"] = os.getenv("DEEP_LLM_MODEL", "gpt-4o")
    config["quick_think_llm"] = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
    config["max_debate_rounds"] = 1  # single round for speed
    config["max_risk_discuss_rounds"] = 1

    thesis = thesis_record.get("thesis", {})

    # Build position context with thesis
    position_context = (
        f"CURRENT POSITION in {ticker}.\n"
        f"THESIS: {thesis.get('rationale', 'No rationale')}\n"
        f"KEY CATALYSTS: {', '.join(thesis.get('key_catalysts', []))}\n"
        f"INVALIDATION: {', '.join(thesis.get('invalidation_conditions', []))}\n"
        f"\nNEWS EVENT TRIGGERING THIS REVIEW:\n{news_summary}\n"
        f"\nAssess whether this news affects our investment thesis."
    )

    if not trade_date:
        from datetime import datetime
        trade_date = datetime.now().strftime("%Y-%m-%d")

    try:
        ta = TradingAgentsGraph(config=config)
        final_state, decision = ta.propagate(
            ticker, trade_date,
            position_context=position_context,
        )

        decision = (decision or "HOLD").upper().strip()
        if decision not in ("BUY", "SELL", "HOLD"):
            decision = "HOLD"

        # Extract conviction from agent text
        agent_text = str(final_state.get("final_trade_decision", ""))
        conviction = _extract_conviction(agent_text)

        threshold = int(os.getenv("NEWS_CONVICTION_THRESHOLD", "8"))

        return NewsTradeDecision(
            ticker=ticker,
            action=decision,
            conviction=conviction,
            reasoning=agent_text[:500],
            severity=NewsSeverity.HIGH,
            should_execute=(conviction >= threshold),
        )

    except Exception as exc:
        logger.error("News debate failed for %s: %s", ticker, exc)
        return NewsTradeDecision(
            ticker=ticker,
            action="HOLD",
            conviction=0,
            reasoning=f"Debate failed: {exc}",
            severity=NewsSeverity.HIGH,
            should_execute=False,
        )


def assess_critical(
    ticker: str,
    thesis_record: dict,
    news_summary: str,
) -> NewsTradeDecision:
    """CRITICAL severity: immediate Risk Judge decision.

    Single LLM call to the decision-tier model. No full debate.
    """
    from .llm_clients.factory import create_llm_client

    thesis = thesis_record.get("thesis", {})

    prompt = f"""CRITICAL NEWS EVENT — IMMEDIATE ASSESSMENT REQUIRED

POSITION: {ticker}
THESIS: {thesis.get('rationale', 'Unknown')}
KEY CATALYSTS: {', '.join(thesis.get('key_catalysts', []))}
INVALIDATION CONDITIONS: {', '.join(thesis.get('invalidation_conditions', []))}

CRITICAL NEWS:
{news_summary}

You are a Risk Judge making an immediate decision. This news is CRITICAL — 
it may require an immediate position change.

Assess the impact and decide:

DECISION: BUY | SELL | HOLD
CONVICTION: 1-10 (how confident are you in this decision?)
REASONING: 2-3 sentences explaining your decision
THESIS_IMPACT: Does this news invalidate the investment thesis? (yes/no/partially)
"""

    model = os.getenv("DEEP_LLM_MODEL", "gpt-4o")
    provider = os.getenv("LLM_PROVIDER", "openai")

    try:
        client = create_llm_client(provider=provider, model=model)
        response = client.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("Critical assessment failed for %s: %s", ticker, exc)
        return NewsTradeDecision(
            ticker=ticker,
            action="HOLD",
            conviction=0,
            reasoning=f"Critical assessment failed: {exc}",
            severity=NewsSeverity.CRITICAL,
            should_execute=False,
        )

    # Parse response
    decision = "HOLD"
    conviction = 0
    reasoning = ""

    for line in text.split("\n"):
        line = line.strip()
        upper = line.upper()

        if upper.startswith("DECISION:"):
            val = line.split(":", 1)[1].strip().upper()
            if "SELL" in val:
                decision = "SELL"
            elif "BUY" in val:
                decision = "BUY"
            else:
                decision = "HOLD"
        elif upper.startswith("CONVICTION:"):
            import re
            match = re.search(r"\d+", line.split(":", 1)[1])
            if match:
                conviction = max(1, min(10, int(match.group())))
        elif upper.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    threshold = int(os.getenv("NEWS_CONVICTION_THRESHOLD", "8"))

    return NewsTradeDecision(
        ticker=ticker,
        action=decision,
        conviction=conviction,
        reasoning=reasoning,
        severity=NewsSeverity.CRITICAL,
        should_execute=(conviction >= threshold),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_conviction(text: str) -> int:
    """Extract conviction score from agent output text."""
    import re

    patterns = [
        r"CONVICTION[:\s]*(\d+)",
        r"conviction[:\s]*(\d+)",
        r"Conviction[:\s]*(\d+)/10",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, min(10, int(match.group(1))))
    return 5  # default moderate conviction
