"""
TICKET-068: Conviction Threshold Bypass

When Research Manager has high conviction (≥ 8) and research signal agrees,
bypass Risk Judge to execute trade immediately.
"""

import re
from typing import Optional


def extract_signal_and_conviction(text: str) -> tuple[str, int]:
    """Extract signal (BUY/SELL/HOLD) and conviction (1-10) from agent output."""
    signal = "HOLD"
    conviction = 5

    # Extract signal
    signal_match = re.search(
        r'RECOMMENDATION:\s*(BUY|SELL|HOLD)',
        text,
        re.IGNORECASE
    )
    if not signal_match:
        # Try alternative format
        signal_match = re.search(
            r'FINAL DECISION:\s*\*?(BUY|SELL|HOLD)\*?',
            text,
            re.IGNORECASE
        )

    if signal_match:
        signal = signal_match.group(1).upper()

    # Extract conviction
    conv_match = re.search(r'CONVICTION:\s*(\d+)', text, re.IGNORECASE)
    if conv_match:
        conviction = int(conv_match.group(1))

    return signal, conviction


def should_bypass_risk_judge(
    investment_plan: str,
    research_signal: Optional[dict],
    portfolio_context: dict,
    has_position: bool
) -> tuple[bool, str]:
    """Determine if high-conviction signal should bypass Risk Judge.

    Args:
        investment_plan: Research Manager output text
        research_signal: Research signal dict (from parse_research_signals)
        portfolio_context: Dict with cash_ratio, etc.
        has_position: Whether we currently hold a position in this ticker

    Returns:
        (should_bypass, reason)
    """
    rm_signal, rm_conviction = extract_signal_and_conviction(investment_plan)
    cash_ratio = portfolio_context.get("cash_ratio", 0)
    research_decision = research_signal.get("decision", "HOLD") if research_signal else "HOLD"

    # Must have high conviction
    if rm_conviction < 8:
        return False, f"conviction_too_low ({rm_conviction})"

    # Signals must agree
    if rm_signal != research_decision:
        return False, "signal_mismatch"

    # BUY: need high cash
    if rm_signal == "BUY":
        if cash_ratio <= 0.80:
            return False, "cash_too_low"
        return True, "high_conviction_buy_high_cash"

    # SELL: need position
    if rm_signal == "SELL":
        if not has_position:
            return False, "no_position_to_sell"
        return True, "high_conviction_sell_has_position"

    return False, "default_hold"


def format_bypass_message(ticker: str, signal: str, conviction: int, reason: str) -> str:
    """Format bypass notification message."""
    emoji = "🚀" if signal == "BUY" else "🔻"
    return (
        f"{emoji} BYPASS: {ticker} {signal} (conviction {conviction}) - "
        f"high conviction signal, skipping Risk Judge ({reason})"
    )
