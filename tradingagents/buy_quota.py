"""
TICKET-072: BUY Quota Enforcement

Tracks if minimum BUY quotas are met when research signals are strong.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

QUOTA_LOG_FILE = Path("trading_loop_logs/buy_quota_log.json")
MIN_BUY_QUOTA = 5
HIGH_CONVICTION_THRESHOLD = "HIGH"


def count_high_conviction_buys(research_signals: Dict) -> List[str]:
    """Count tickers with HIGH conviction BUY signals.

    Args:
        research_signals: Dict from parse_research_signals()

    Returns:
        List of ticker symbols with HIGH conviction BUY
    """
    high_conviction_buys = []
    for ticker, signal in research_signals.items():
        if (signal.get("conviction") == HIGH_CONVICTION_THRESHOLD
                and signal.get("decision") == "BUY"):
            high_conviction_buys.append(ticker)
    return high_conviction_buys


def check_buy_quota(
    tickers: List[str],
    results: List[dict],
    research_signals: Dict,
    cash_ratio: float
) -> Dict:
    """Check if minimum BUY quota was met.

    Args:
        tickers: All tickers analyzed
        results: List of result dicts from analyse_and_trade()
        research_signals: Dict from parse_research_signals()
        cash_ratio: Current portfolio cash ratio

    Returns:
        Quota report dict
    """
    # Only enforce quota when cash is high
    if cash_ratio < 0.80:
        return {"enforced": False, "reason": "cash_below_80%"}

    # Count high conviction BUY signals
    high_conviction_buys = count_high_conviction_buys(research_signals)

    # Not enough signals to require quota
    if len(high_conviction_buys) < MIN_BUY_QUOTA:
        return {
            "enforced": False,
            "reason": "insufficient_signals",
            "high_conviction_count": len(high_conviction_buys),
            "min_required": MIN_BUY_QUOTA
        }

    # Count actual BUYs executed
    buys_executed = sum(
        1 for r in results
        if r.get("decision") == "BUY" and r.get("order", {}).get("action") == "BUY"
    )

    # Find missed opportunities
    executed_tickers = {r.get("ticker") for r in results if r.get("decision") == "BUY"}
    missed = [t for t in high_conviction_buys if t not in executed_tickers]

    quota_met = buys_executed >= MIN_BUY_QUOTA

    report = {
        "timestamp": datetime.now().isoformat(),
        "enforced": True,
        "cash_ratio": cash_ratio,
        "high_conviction_signals": len(high_conviction_buys),
        "high_conviction_tickers": high_conviction_buys,
        "min_quota": MIN_BUY_QUOTA,
        "buys_executed": buys_executed,
        "quota_met": quota_met,
        "missed_opportunities": missed,
    }

    # Log if quota not met
    if not quota_met:
        log_quota_miss(report)
        print_quota_warning(report)

    return report


def log_quota_miss(report: Dict):
    """Log quota miss to file."""
    if QUOTA_LOG_FILE.exists():
        with open(QUOTA_LOG_FILE) as f:
            log = json.load(f)
    else:
        log = {"misses": [], "summary": {"total_misses": 0}}

    log["misses"].append(report)
    log["summary"]["total_misses"] += 1

    QUOTA_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUOTA_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def print_quota_warning(report: Dict):
    """Print quota warning to console."""
    print("\n" + "=" * 60)
    print("⚠️  BUY QUOTA NOT MET")
    print("=" * 60)
    print(f"Research HIGH conviction BUYs: {report['high_conviction_signals']}")
    print(f"Minimum quota required: {report['min_quota']}")
    print(f"Actual BUYs executed: {report['buys_executed']}")
    print(f"Quota met: {'YES ✓' if report['quota_met'] else 'NO ✗'}")
    print(f"\nMissed opportunities ({len(report['missed_opportunities'])}):")
    for ticker in report['missed_opportunities'][:10]:  # Show first 10
        print(f"  - {ticker}")
    if len(report['missed_opportunities']) > 10:
        print(f"  ... and {len(report['missed_opportunities']) - 10} more")
    print("=" * 60 + "\n")


def get_quota_stats(days: int = 7) -> Dict:
    """Get quota statistics for recent days.

    Args:
        days: Number of days to look back

    Returns:
        Stats dict
    """
    if not QUOTA_LOG_FILE.exists():
        return {"total_misses": 0, "recent": []}

    with open(QUOTA_LOG_FILE) as f:
        log = json.load(f)

    # Filter recent
    cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
    recent = [
        m for m in log.get("misses", [])
        if datetime.fromisoformat(m["timestamp"]).timestamp() > cutoff
    ]

    return {
        "total_misses": log.get("summary", {}).get("total_misses", 0),
        "recent_misses": len(recent),
        "recent": recent,
    }
