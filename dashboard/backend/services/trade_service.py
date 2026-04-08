"""
Trade data service.

Reads daily trade logs and computes performance metrics.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

from ..config import TRADING_LOGS_DIR, POSITIONS_FILE, PROJECT_ROOT

import sys
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps"))


def _load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _get_tier(ticker: str) -> str:
    try:
        from trading_loop import get_tier
        return get_tier(ticker)
    except Exception:
        return "TACTICAL"


def get_all_trades(
    date_from: str | None = None,
    date_to: str | None = None,
    ticker: str | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Get paginated trade log with filtering."""
    all_trades = []

    log_files = sorted(TRADING_LOGS_DIR.glob("????-??-??.json"), reverse=True)
    for log_file in log_files:
        log_date = log_file.stem
        if date_from and log_date < date_from:
            continue
        if date_to and log_date > date_to:
            continue

        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        for t in data.get("trades", []):
            t_ticker = t.get("ticker") or ""
            t_decision = t.get("decision") or ""
            order = t.get("order") or {}

            if ticker and t_ticker.upper() != ticker.upper():
                continue
            if action and t_decision.upper() != action.upper():
                continue

            all_trades.append({
                "date": log_date,
                "time": t.get("time", ""),
                "ticker": t_ticker,
                "tier": _get_tier(t_ticker),
                "decision": t_decision,
                "conviction": order.get("conviction", 0),
                "size_multiplier": order.get("size_mult", 1.0),
                "amount_usd": 0,
                "qty": order.get("qty", 0),
                "price": 0,
                "agent_stop": order.get("agent_stop"),
                "agent_target": order.get("agent_target"),
                "order_id": order.get("order_id", ""),
                "status": order.get("status", order.get("action", "")),
                "source": order.get("source", "normal"),
                "error": t.get("error"),
            })

    total = len(all_trades)
    paginated = all_trades[offset:offset + limit]
    return {"total": total, "trades": paginated}


def get_performance(days: int = 30) -> dict:
    """Compute performance metrics over the last N days."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    buys = []
    sells = []
    holds = []
    all_decisions = []

    log_files = sorted(TRADING_LOGS_DIR.glob("????-??-??.json"))
    for log_file in log_files:
        log_date = log_file.stem
        if log_date < cutoff:
            continue

        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        for t in data.get("trades", []):
            decision = t.get("decision", "HOLD")
            order = t.get("order", {})
            ticker = t.get("ticker", "")

            entry = {
                "date": log_date,
                "ticker": ticker,
                "decision": decision,
                "conviction": order.get("conviction", 0),
                "qty": order.get("qty", 0),
                "tier": _get_tier(ticker),
            }
            all_decisions.append(entry)

            if decision == "BUY" and order.get("action") == "BUY":
                buys.append(entry)
            elif decision == "SELL" and order.get("action") == "SELL":
                sells.append(entry)
            elif decision in ("HOLD", "WAIT"):
                holds.append(entry)

    # Load current positions for unrealized P&L
    positions_data = _load_json(POSITIONS_FILE)
    pos_pnl = {}
    for p in positions_data.get("positions", []):
        pos_pnl[p["ticker"]] = {
            "pnl": p.get("unrealized_pl", 0),
            "pnl_pct": p.get("unrealized_pl_pct", 0),
        }

    # Per-ticker performance
    ticker_stats: dict[str, dict] = {}
    for entry in all_decisions:
        tk = entry["ticker"]
        if tk not in ticker_stats:
            ticker_stats[tk] = {"trades": 0, "buys": 0, "pnl": 0, "wins": 0}
        ticker_stats[tk]["trades"] += 1
        if entry["decision"] == "BUY":
            ticker_stats[tk]["buys"] += 1

    # Add unrealized P&L to ticker stats
    for tk, pp in pos_pnl.items():
        if tk not in ticker_stats:
            ticker_stats[tk] = {"trades": 0, "buys": 0, "pnl": 0, "wins": 0}
        ticker_stats[tk]["pnl"] = pp["pnl"]
        if pp["pnl"] > 0:
            ticker_stats[tk]["wins"] += 1

    # Aggregate
    wins = [s for s in ticker_stats.values() if s["pnl"] > 0]
    losses = [s for s in ticker_stats.values() if s["pnl"] < 0]

    total_pnl = sum(s["pnl"] for s in ticker_stats.values())
    win_pcts = [s["pnl"] for s in wins] if wins else [0]
    loss_pcts = [s["pnl"] for s in losses] if losses else [0]

    total_with_pnl = len(wins) + len(losses)
    win_rate = len(wins) / max(total_with_pnl, 1)

    by_ticker = sorted(
        [{"ticker": k, "trades": v["trades"], "pnl": round(v["pnl"], 2),
          "win_rate": round(v["wins"] / max(v["trades"], 1), 2)}
         for k, v in ticker_stats.items()],
        key=lambda x: -x["pnl"]
    )

    # Per-tier
    tier_stats: dict[str, dict] = {}
    for tk, stats in ticker_stats.items():
        tier = _get_tier(tk)
        if tier not in tier_stats:
            tier_stats[tier] = {"trades": 0, "pnl": 0, "wins": 0}
        tier_stats[tier]["trades"] += stats["trades"]
        tier_stats[tier]["pnl"] += stats["pnl"]
        if stats["pnl"] > 0:
            tier_stats[tier]["wins"] += 1

    by_tier = [
        {"tier": k, "trades": v["trades"], "pnl": round(v["pnl"], 2),
         "win_rate": round(v["wins"] / max(v["trades"], 1), 2)}
        for k, v in tier_stats.items()
    ]

    best = max(by_ticker, key=lambda x: x["pnl"]) if by_ticker else None
    worst = min(by_ticker, key=lambda x: x["pnl"]) if by_ticker else None

    return {
        "period_days": days,
        "total_trades": len(all_decisions),
        "buys": len(buys),
        "sells": len(sells),
        "holds": len(holds),
        "win_rate": round(win_rate, 2),
        "avg_win_pct": round(sum(win_pcts) / max(len(win_pcts), 1), 2),
        "avg_loss_pct": round(sum(loss_pcts) / max(len(loss_pcts), 1), 2),
        "best_trade": best,
        "worst_trade": worst,
        "sharpe_ratio": 0,  # Need daily returns series for proper Sharpe
        "max_drawdown_pct": 0,
        "total_pnl": round(total_pnl, 2),
        "by_ticker": by_ticker,
        "by_tier": by_tier,
    }
