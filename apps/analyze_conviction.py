#!/usr/bin/env python3
"""Analyze conviction mismatches from recent reports (TICKET-064).

Parses trading reports to find when Risk Judge overrode strong upstream signals.
"""

# Path setup
import _path_setup  # noqa: F401


import re
import json
from pathlib import Path
from datetime import datetime


def parse_report_for_convictions(report_path: str) -> dict:
    """Extract conviction scores from a report file."""
    try:
        with open(report_path) as f:
            content = f.read()
    except Exception:
        return None

    ticker = Path(report_path).parent.name

    # Extract Research Manager conviction and recommendation
    rm_match = re.search(r'RECOMMENDATION:\s*(BUY|SELL|HOLD).*?CONVICTION:\s*(\d+)', content, re.DOTALL | re.IGNORECASE)
    rm_recommendation = rm_match.group(1).upper() if rm_match else None
    rm_conviction = int(rm_match.group(2)) if rm_match else None

    # Also look for alternative format: CONVICTION: 8 on its own line
    if not rm_conviction:
        rm_match = re.search(r'CONVICTION:\s*(\d+)', content, re.IGNORECASE)
        rm_conviction = int(rm_match.group(1)) if rm_match else None

    # Extract Risk Judge final decision
    rj_dec_match = re.search(r'Risk Judge Final Decision.*?FINAL DECISION:\s*\*?(BUY|SELL|HOLD)\*?', content, re.DOTALL | re.IGNORECASE)
    rj_decision = rj_dec_match.group(1).upper() if rj_dec_match else None

    # Alternative: look for FINAL DECISION: **BUY** at end
    if not rj_decision:
        rj_dec_match = re.search(r'FINAL DECISION:\s*\*\*(BUY|SELL|HOLD)\*\*', content, re.IGNORECASE)
        rj_decision = rj_dec_match.group(1).upper() if rj_dec_match else None

    # Extract Risk Judge conviction
    rj_match = re.search(r'Risk Judge.*?CONVICTION:\s*(\d+)', content, re.DOTALL | re.IGNORECASE)
    rj_conviction = int(rj_match.group(1)) if rj_match else None

    if not rj_decision:
        return None

    return {
        "ticker": ticker,
        "research_manager": {
            "recommendation": rm_recommendation or "HOLD",
            "conviction": rm_conviction or 5
        },
        "risk_judge": {
            "decision": rj_decision,
            "conviction": rj_conviction or 5
        },
        "mismatch": rm_recommendation != rj_decision if rm_recommendation else False,
        "high_conviction_override": (
            rm_conviction and rm_conviction >= 8 and
            rm_recommendation != rj_decision and
            rj_decision == "HOLD"
        )
    }


def get_recent_mismatches(days: int = 1) -> list:
    """Get conviction mismatches from recent reports."""
    reports_dir = Path("trading_loop_logs/reports")
    mismatches = []

    if not reports_dir.exists():
        return mismatches

    date_str = datetime.now().strftime("%Y-%m-%d")

    for ticker_dir in reports_dir.iterdir():
        if not ticker_dir.is_dir():
            continue

        report_file = ticker_dir / f"{date_str}.md"
        if report_file.exists():
            data = parse_report_for_convictions(str(report_file))
            if data and data.get("mismatch"):
                mismatches.append(data)

    # Sort: high conviction overrides first, then by ticker
    mismatches.sort(key=lambda x: (not x.get("high_conviction_override", False), x.get("ticker", "")))

    return mismatches


def format_mismatch_table(mismatches: list) -> str:
    """Format mismatches for dashboard display."""
    if not mismatches:
        return "  No conviction mismatches today ✓"

    lines = ["  Ticker    Research    →    Risk Judge    Type"]
    lines.append("  " + "─" * 52)

    for m in mismatches:
        rm = m["research_manager"]
        rj = m["risk_judge"]

        type_indicator = "🚨 HIGH" if m.get("high_conviction_override") else "⚠️"

        line = f"  {m['ticker']:<8} {rm['recommendation']:>4}({rm['conviction']}) → {rj['decision']:>4}({rj['conviction']})  {type_indicator}"
        lines.append(line)

    return "\n".join(lines)


def main():
    """Main entry point."""
    mismatches = get_recent_mismatches()
    print(format_mismatch_table(mismatches))


if __name__ == "__main__":
    main()
