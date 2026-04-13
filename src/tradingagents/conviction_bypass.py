"""
TICKET-068: Conviction Threshold Bypass

When Research Manager has high conviction (≥ 8) and research signal agrees,
bypass Risk Judge to execute trade immediately.
"""

import re
from typing import Optional


def _get_thresholds(target_deployment_pct: float | None = None) -> tuple[float, float]:
    """Get bypass thresholds relative to target deployment.

    Args:
        target_deployment_pct: Optional target. If None, loads from config.

    Returns:
        Tuple of (cash_low_threshold, aggressive_threshold)
    """
    if target_deployment_pct is None:
        try:
            from .deployment_config import get_target_deployment_pct
            target_deployment_pct = get_target_deployment_pct()
        except ImportError:
            # Fallback to legacy hardcoded values
            return 0.70, 0.85

    target_cash = 1.0 - target_deployment_pct
    # Low threshold: when we stop bypassing (below target cash - buffer)
    cash_low = target_cash - 0.10
    # Aggressive threshold: when we lower conviction requirement (above target + extra)
    aggressive = target_cash + 0.20
    return cash_low, aggressive


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
    has_position: bool,
    target_deployment_pct: float | None = None
) -> tuple[bool, str]:
    """Determine if high-conviction signal should bypass Risk Judge.

    Args:
        investment_plan: Research Manager output text
        research_signal: Research signal dict (from parse_research_signals)
        portfolio_context: Dict with cash_ratio, etc.
        has_position: Whether we currently hold a position in this ticker
        target_deployment_pct: Optional target deployment for threshold calculation.

    Returns:
        (should_bypass, reason)
    """
    rm_signal, rm_conviction = extract_signal_and_conviction(investment_plan)
    cash_ratio = portfolio_context.get("cash_ratio", 0)
    research_decision = research_signal.get("decision", "HOLD") if research_signal else "HOLD"

    # Get dynamic thresholds based on target deployment
    cash_low_threshold, aggressive_threshold = _get_thresholds(target_deployment_pct)

    # Conviction thresholds:
    # - conviction >= 8: bypass always (if signals agree)
    # - conviction == 7 + cash above aggressive threshold: bypass for BUYs
    min_conviction = 8
    if rm_signal == "BUY" and cash_ratio > aggressive_threshold:
        min_conviction = 7  # Lower bar when capital urgently needs deployment

    if rm_conviction < min_conviction:
        return False, f"conviction_too_low ({rm_conviction}, need {min_conviction})"

    # Signals must agree (research + RM both say BUY or both say SELL)
    # REDUCE counts as SELL agreement for bypass purposes
    effective_research = research_decision
    if effective_research == "REDUCE":
        effective_research = "SELL"
    if rm_signal != effective_research:
        return False, "signal_mismatch"

    # BUY: need enough cash to deploy
    if rm_signal == "BUY":
        if cash_ratio <= cash_low_threshold:
            return False, "cash_too_low"
        return True, f"high_conviction_buy (conv={rm_conviction}, cash={cash_ratio:.0%})"

    # SELL: need position
    if rm_signal == "SELL":
        if not has_position:
            return False, "no_position_to_sell"
        return True, f"high_conviction_sell (conv={rm_conviction})"

    return False, "default_hold"


def format_bypass_message(ticker: str, signal: str, conviction: int, reason: str) -> str:
    """Format bypass notification message."""
    emoji = "🚀" if signal == "BUY" else "🔻"
    return (
        f"{emoji} BYPASS: {ticker} {signal} (conviction {conviction}) - "
        f"high conviction signal, skipping Risk Judge ({reason})"
    )
