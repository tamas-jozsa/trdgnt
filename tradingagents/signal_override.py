"""
TICKET-067: Risk Judge Override Detection, Logging, and Enforcement

Detects when Risk Judge overrides strong upstream signals.
For critical overrides with high cash ratio, can revert the decision
to the upstream signal (enforcement mode).
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

OVERRIDE_LOG_FILE = Path("trading_loop_logs/signal_overrides.json")


def extract_signal_and_conviction(text: str) -> tuple[str, int]:
    """Extract signal (BUY/SELL/HOLD) and conviction (1-10) from agent output.

    Returns:
        (signal, conviction) - defaults to ("HOLD", 5) if not found
    """
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


def detect_signal_override(
    ticker: str,
    investment_plan: str,
    risk_judge_decision: str,
    portfolio_context: dict,
    research_signal: Optional[dict] = None
) -> Optional[dict]:
    """Detect when Risk Judge overrides strong upstream signals.

    Args:
        ticker: Stock symbol
        investment_plan: Research Manager output text
        risk_judge_decision: Risk Judge output text
        portfolio_context: Dict with portfolio info (cash_ratio, etc.)
        research_signal: Optional research signal dict

    Returns:
        Override info dict if override detected, None otherwise
    """
    # Extract upstream (Research Manager) signal
    rm_signal, rm_conviction = extract_signal_and_conviction(investment_plan)

    # Extract Risk Judge signal
    rj_signal, rj_conviction = extract_signal_and_conviction(risk_judge_decision)

    # No override if signals match
    if rm_signal == rj_signal:
        return None

    # Only consider high-conviction upstream signals
    if rm_conviction < 7:
        return None

    # Determine severity
    if rm_conviction >= 9:
        severity = "critical"
    elif rm_conviction >= 8:
        severity = "high"
    else:
        severity = "medium"

    # Extract reason from Risk Judge output
    reason = "unknown"
    reason_match = re.search(
        r'OVERRIDE REASON:\s*(.+?)(?:\n|$)',
        risk_judge_decision,
        re.IGNORECASE
    )
    if reason_match:
        reason = reason_match.group(1).strip()
    else:
        # Try to infer from reasoning section
        reasoning_match = re.search(
            r'REASONING:\s*(.+?)(?:\n\n|\Z)',
            risk_judge_decision,
            re.DOTALL | re.IGNORECASE
        )
        if reasoning_match:
            reason = reasoning_match.group(1).strip()[:100] + "..."

    return {
        "timestamp": datetime.now().isoformat(),
        "ticker": ticker,
        "upstream_signal": rm_signal,
        "upstream_conviction": rm_conviction,
        "final_signal": rj_signal,
        "final_conviction": rj_conviction,
        "cash_ratio": portfolio_context.get("cash_ratio", 0),
        "severity": severity,
        "reason": reason,
        "research_signal": research_signal.get("decision") if research_signal else None,
    }


def log_override(override_info: dict):
    """Log override to file.

    Args:
        override_info: Dict from detect_signal_override()
    """
    OVERRRIDE_LOG_FILE = Path("trading_loop_logs/signal_overrides.json")

    # Load existing log
    if OVERRRIDE_LOG_FILE.exists():
        with open(OVERRRIDE_LOG_FILE) as f:
            log = json.load(f)
    else:
        log = {"overrides": [], "summary": {"total": 0, "by_severity": {}}}

    # Add new entry
    log["overrides"].append(override_info)
    log["summary"]["total"] += 1

    # Update severity counts
    severity = override_info["severity"]
    log["summary"]["by_severity"][severity] = log["summary"]["by_severity"].get(severity, 0) + 1

    # Save
    OVERRRIDE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OVERRRIDE_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def print_override_warning(override_info: dict):
    """Print override warning to console."""
    ticker = override_info["ticker"]
    upstream = override_info["upstream_signal"]
    conv = override_info["upstream_conviction"]
    final = override_info["final_signal"]
    severity = override_info["severity"]

    emoji = "🔴" if severity == "critical" else "🟠" if severity == "high" else "🟡"

    print(f"\n{emoji} OVERRIDE DETECTED: {ticker}")
    print(f"   Upstream: {upstream} (conviction {conv})")
    print(f"   Final:    {final}")
    print(f"   Severity: {severity.upper()}")
    if override_info["reason"] != "unknown":
        print(f"   Reason:   {override_info['reason'][:80]}")
    print()


def should_revert_override(override_info: dict) -> bool:
    """Determine if an override should be reverted (enforcement).

    An override is reverted when ALL conditions are met:
    1. Severity is 'critical' (upstream conviction >= 9) or 'high' (>= 8)
    2. Cash ratio > 80% (capital needs deployment)
    3. The Risk Judge changed a BUY to HOLD (not SELL overrides — those are riskier to force)
    4. Research signal agrees with upstream (if available)

    Args:
        override_info: Dict from detect_signal_override()

    Returns:
        True if override should be reverted to upstream signal
    """
    if not override_info:
        return False

    severity = override_info.get("severity", "")
    cash_ratio = override_info.get("cash_ratio", 0)
    upstream = override_info.get("upstream_signal", "")
    final = override_info.get("final_signal", "")
    research = override_info.get("research_signal")

    # Only revert critical/high severity overrides
    if severity not in ("critical", "high"):
        return False

    # Only when cash needs deployment
    if cash_ratio < 0.80:
        return False

    # Only revert BUY->HOLD overrides (safest to enforce)
    # SELL->HOLD overrides are left to the Risk Judge (exiting has lower urgency)
    if upstream != "BUY" or final != "HOLD":
        return False

    # If research signal exists and disagrees with upstream, don't revert
    if research and research not in ("BUY", None):
        return False

    return True


def get_override_stats(days: int = 7) -> dict:
    """Get override statistics for recent days.

    Args:
        days: Number of days to look back

    Returns:
        Stats dict with counts and patterns
    """
    if not OVERRIDE_LOG_FILE.exists():
        return {"total": 0, "recent": []}

    with open(OVERRIDE_LOG_FILE) as f:
        log = json.load(f)

    # Filter recent
    cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
    recent = [
        o for o in log.get("overrides", [])
        if datetime.fromisoformat(o["timestamp"]).timestamp() > cutoff
    ]

    # Calculate stats
    stats = {
        "total_recent": len(recent),
        "by_ticker": {},
        "by_severity": {"critical": 0, "high": 0, "medium": 0},
        "high_cash_overrides": 0,  # Overrides when cash > 80%
    }

    for o in recent:
        ticker = o["ticker"]
        stats["by_ticker"][ticker] = stats["by_ticker"].get(ticker, 0) + 1
        stats["by_severity"][o["severity"]] += 1

        if o["cash_ratio"] > 0.80:
            stats["high_cash_overrides"] += 1

    return stats
