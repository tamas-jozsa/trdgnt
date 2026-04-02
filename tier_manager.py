#!/usr/bin/env python3
"""Dynamic tier management based on performance (TICKET-066).

Automatically promotes/demotes tickers between tiers based on 30-day performance.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# File to persist tier assignments
TIER_FILE = Path("trading_loop_logs/dynamic_tiers.json")
PERFORMANCE_FILE = Path("trading_loop_logs/ticker_performance.json")


def load_trade_history(days: int = 30) -> List[dict]:
    """Load trade history from recent log files."""
    history = []
    logs_dir = Path("trading_loop_logs")

    cutoff = datetime.now() - timedelta(days=days)

    for log_file in logs_dir.glob("*.json"):
        if not log_file.name.startswith("2"):  # Skip non-date files
            continue

        try:
            file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
            if file_date < cutoff:
                continue
        except ValueError:
            continue

        try:
            with open(log_file) as f:
                data = json.load(f)
                for trade in data.get("trades", []):
                    trade["date"] = file_date.isoformat()
                    history.append(trade)
        except Exception:
            continue

    return history


def calculate_ticker_performance(ticker: str, history: List[dict]) -> Optional[dict]:
    """Calculate performance metrics for a ticker from trade history."""
    ticker_trades = [t for t in history if t.get("ticker") == ticker]

    if not ticker_trades:
        return None

    # Calculate realized P&L from completed trades
    sells = [t for t in ticker_trades
             if t.get("decision") == "SELL"
             and t.get("order", {}).get("action") == "SELL"]

    realized_pnl = 0
    profitable_trades = 0
    total_sells = len(sells)

    for sell in sells:
        # Find the corresponding BUY
        buy_price = None
        sell_price = None

        # Get sell price from order
        sell_order = sell.get("order", {})
        # We don't have actual fill price in logs, use position data or estimate

        # For now, count profitable based on unrealized P&L at sell time
        # This is a simplification - in production would track actual fills
        pnl_pct = sell_order.get("pnl_pct", 0)
        realized_pnl += pnl_pct
        if pnl_pct > 0:
            profitable_trades += 1

    # Calculate win rate
    win_rate = profitable_trades / total_sells if total_sells > 0 else 0

    # Count total round trips (BUY + SELL pairs)
    buys = [t for t in ticker_trades if t.get("decision") == "BUY"]
    round_trips = min(len(buys), total_sells)

    return {
        "ticker": ticker,
        "round_trips": round_trips,
        "realized_pnl": realized_pnl,
        "win_rate": win_rate,
        "total_trades": len(ticker_trades),
    }


def load_current_tiers() -> Dict[str, List[str]]:
    """Load current tier assignments."""
    if TIER_FILE.exists():
        try:
            with open(TIER_FILE) as f:
                return json.load(f)
        except Exception:
            pass

    # Default tiers from trading_loop
    return {
        "CORE": ["NVDA", "AVGO", "AMD", "ARM", "TSM", "MU", "LITE", "MSFT", "GOOGL",
                 "META", "PLTR", "GLW", "MDB", "NOW", "PANW", "CRWD", "RTX", "LMT",
                 "NOC", "VG", "LNG", "XOM", "FCX", "MP", "UBER"],
        "TACTICAL": ["CMC", "NUE", "APA", "SOC", "SCCO"],
        "SPECULATIVE": ["RCAT", "MOS", "RCKT"],
        "HEDGE": ["GLD"],
    }


def save_tiers(tiers: Dict[str, List[str]]):
    """Save tier assignments."""
    TIER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TIER_FILE, "w") as f:
        json.dump(tiers, f, indent=2)


def get_tier_for_ticker(ticker: str, tiers: Dict[str, List[str]]) -> str:
    """Get current tier for a ticker."""
    for tier, tickers in tiers.items():
        if ticker in tickers:
            return tier
    return "TACTICAL"  # Default


def review_tier_assignments() -> List[dict]:
    """Review all tickers and recommend tier changes based on performance."""
    history = load_trade_history(days=30)
    tiers = load_current_tiers()
    recommendations = []

    # Get all tickers from all tiers
    all_tickers = set()
    for tier_tickers in tiers.values():
        all_tickers.update(tier_tickers)

    for ticker in all_tickers:
        perf = calculate_ticker_performance(ticker, history)
        if not perf or perf["round_trips"] < 2:  # Need at least 2 round trips
            continue

        current_tier = get_tier_for_ticker(ticker, tiers)

        # Promotion criteria: >60% win rate and positive P&L
        if perf["win_rate"] > 0.6 and perf["realized_pnl"] > 0:
            if current_tier == "TACTICAL":
                recommendations.append({
                    "ticker": ticker,
                    "current_tier": current_tier,
                    "recommended_tier": "CORE",
                    "reason": f"Win rate {perf['win_rate']:.0%}, P&L +{perf['realized_pnl']:.1f}%",
                    "action": "PROMOTE",
                    "performance": perf,
                })
            elif current_tier == "SPECULATIVE":
                recommendations.append({
                    "ticker": ticker,
                    "current_tier": current_tier,
                    "recommended_tier": "TACTICAL",
                    "reason": f"Win rate {perf['win_rate']:.0%}, improving performance",
                    "action": "PROMOTE",
                    "performance": perf,
                })

        # Demotion criteria: <30% win rate and negative P&L
        elif perf["win_rate"] < 0.3 and perf["realized_pnl"] < 0:
            if current_tier == "CORE":
                recommendations.append({
                    "ticker": ticker,
                    "current_tier": current_tier,
                    "recommended_tier": "TACTICAL",
                    "reason": f"Poor performance: Win rate {perf['win_rate']:.0%}, P&L {perf['realized_pnl']:.1f}%",
                    "action": "DEMOTE",
                    "performance": perf,
                })
            elif current_tier == "TACTICAL":
                recommendations.append({
                    "ticker": ticker,
                    "current_tier": current_tier,
                    "recommended_tier": "SPECULATIVE",
                    "reason": f"Poor performance: Win rate {perf['win_rate']:.0%}, P&L {perf['realized_pnl']:.1f}%",
                    "action": "DEMOTE",
                    "performance": perf,
                })

        # Removal criteria: significant losses
        elif perf["realized_pnl"] < -10:
            recommendations.append({
                "ticker": ticker,
                "current_tier": current_tier,
                "recommended_tier": None,
                "reason": f"Significant losses: {perf['realized_pnl']:.1f}%",
                "action": "REMOVE",
                "performance": perf,
            })

    return recommendations


def apply_tier_changes(recommendations: List[dict], dry_run: bool = True) -> Dict[str, List[str]]:
    """Apply tier changes."""
    tiers = load_current_tiers()

    for rec in recommendations:
        ticker = rec["ticker"]
        action = rec["action"]

        # Remove from current tier
        for tier, tickers in tiers.items():
            if ticker in tickers:
                tickers.remove(ticker)

        # Add to new tier
        if rec["recommended_tier"]:
            tiers[rec["recommended_tier"]].append(ticker)

        print(f"[TIER_CHANGE] {ticker}: {action} {rec['current_tier']} -> {rec['recommended_tier']}: {rec['reason']}")

    if not dry_run:
        save_tiers(tiers)

    return tiers


def run_monthly_review(dry_run: bool = False):
    """Run monthly tier review."""
    print("=" * 60)
    print("TICKET-066: Monthly Tier Performance Review")
    print("=" * 60)

    recommendations = review_tier_assignments()

    if not recommendations:
        print("No tier changes recommended.")
        return

    print(f"\nFound {len(recommendations)} recommendations:\n")

    for rec in recommendations:
        emoji = "⬆️" if rec["action"] == "PROMOTE" else "⬇️" if rec["action"] == "DEMOTE" else "❌"
        print(f"  {emoji} {rec['ticker']}: {rec['current_tier']} -> {rec['recommended_tier'] or 'REMOVE'}")
        print(f"     Reason: {rec['reason']}")
        print()

    if not dry_run:
        apply_tier_changes(recommendations, dry_run=False)
        print("Changes applied and saved.")
    else:
        print("Run with dry_run=False to apply changes.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tier performance manager")
    parser.add_argument("--apply", action="store_true", help="Apply recommended changes")
    args = parser.parse_args()

    run_monthly_review(dry_run=not args.apply)
