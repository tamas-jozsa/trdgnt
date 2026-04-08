"""
Portfolio data service.

Reads positions.json, position_entries.json, and computes sector exposure.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, date
from pathlib import Path

from ..config import (
    PROJECT_ROOT, POSITIONS_FILE, POSITION_ENTRIES_FILE,
    SIGNAL_OVERRIDES_FILE, BUY_QUOTA_LOG_FILE, TRADING_LOGS_DIR,
    EQUITY_HISTORY_FILE,
)

# Add project root and apps to path for imports
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps"))


def _load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _get_ticker_meta(ticker: str) -> dict:
    """Get sector/tier from trading_loop.WATCHLIST."""
    try:
        from trading_loop import WATCHLIST
        entry = WATCHLIST.get(ticker, {})
        if isinstance(entry, dict):
            return {"sector": entry.get("sector", ""), "tier": entry.get("tier", "TACTICAL")}
    except Exception:
        pass
    return {"sector": "", "tier": "TACTICAL"}


def _get_sector(ticker: str) -> str:
    """Get sector for sector exposure calculation."""
    try:
        from tradingagents.research_context import TICKER_SECTORS
        return TICKER_SECTORS.get(ticker.upper(), "OTHER")
    except Exception:
        return "OTHER"


def get_portfolio() -> dict:
    """Get current portfolio state."""
    positions_data = _load_json(POSITIONS_FILE)
    entries_data = _load_json(POSITION_ENTRIES_FILE)
    if not isinstance(entries_data, dict):
        entries_data = {}

    account = positions_data.get("account", {})
    equity = account.get("equity", 0)
    cash = account.get("cash", 0)

    positions = []
    sector_totals: dict[str, float] = {}
    total_invested = 0

    for p in positions_data.get("positions", []):
        ticker = p.get("ticker", "")
        meta = _get_ticker_meta(ticker)
        entry = entries_data.get(ticker, {})
        mkt_val = p.get("market_value", 0) or p.get("mkt_value", 0)

        positions.append({
            "ticker": ticker,
            "sector": meta["sector"],
            "tier": meta["tier"],
            "qty": p.get("qty", 0),
            "avg_entry_price": p.get("avg_entry_price", 0),
            "current_price": round(mkt_val / max(p.get("qty", 1), 0.0001), 2) if mkt_val else 0,
            "market_value": mkt_val,
            "unrealized_pl": p.get("unrealized_pl", 0),
            "unrealized_pl_pct": p.get("unrealized_pl_pct", 0),
            "agent_stop": entry.get("stop"),
            "agent_target": entry.get("target"),
            "entry_date": entry.get("entry_date", ""),
        })

        sector = _get_sector(ticker)
        sector_totals[sector] = sector_totals.get(sector, 0) + mkt_val
        total_invested += mkt_val

    # Compute sector exposure as percentages
    sector_exposure = {}
    if total_invested > 0:
        for sector, value in sorted(sector_totals.items(), key=lambda x: -x[1]):
            sector_exposure[sector] = round(value / total_invested, 3)

    # Enforcement status for today
    enforcement = _get_today_enforcement()

    cash_ratio = cash / max(equity, 1)
    total_invested = sum(p["market_value"] for p in positions)

    # Calculate day P&L from equity history
    day_pnl, day_pnl_pct = _get_day_pnl(equity)
    
    # Save equity snapshot only if not written in last 5 minutes
    _save_equity_snapshot_throttled(equity, cash, total_invested)

    return {
        "updated_at": positions_data.get("updated_at", ""),
        "account": {
            "equity": equity,
            "cash": cash,
            "buying_power": account.get("buying_power", 0),
            "cash_ratio": round(cash_ratio, 3),
            "total_invested": round(total_invested, 2),
            "day_pnl": day_pnl,
            "day_pnl_pct": day_pnl_pct,
            "total_pnl": round(equity - 100000, 2),
            "total_pnl_pct": round((equity - 100000) / 100000 * 100, 2),
        },
        "positions": positions,
        "sector_exposure": sector_exposure,
        "enforcement": enforcement,
    }


def _get_day_pnl(current_equity: float) -> tuple[float, float]:
    """Calculate day's P&L by comparing to previous day's closing equity."""
    try:
        # Try to get previous day's equity from history file
        if EQUITY_HISTORY_FILE.exists():
            history = _load_json(EQUITY_HISTORY_FILE)
            if isinstance(history, list) and len(history) >= 2:
                # Find the most recent entry from a previous day
                today = date.today().isoformat()
                prev_equity = None
                for entry in reversed(history[:-1]):  # Exclude today's entry
                    if entry.get("date") != today:
                        prev_equity = entry.get("equity")
                        break
                
                if prev_equity:
                    day_pnl = current_equity - prev_equity
                    day_pnl_pct = (day_pnl / prev_equity * 100) if prev_equity > 0 else 0
                    return round(day_pnl, 2), round(day_pnl_pct, 2)
    except Exception:
        pass

    return 0.0, 0.0


def _save_equity_snapshot_throttled(equity: float, cash: float, invested: float):
    """Save equity snapshot only if not written in last 5 minutes."""
    try:
        history = []
        if EQUITY_HISTORY_FILE.exists():
            history = _load_json(EQUITY_HISTORY_FILE)
            if not isinstance(history, list):
                history = []
        
        today = date.today().isoformat()
        now = datetime.now()
        
        # Check if we already have a recent entry (within 5 minutes)
        if history and history[-1].get("date") == today:
            last_ts = history[-1].get("timestamp", "")
            try:
                last_time = datetime.fromisoformat(last_ts)
                if (now - last_time).total_seconds() < 300:  # 5 minutes
                    return  # Skip write, too soon
            except Exception:
                pass  # If timestamp parsing fails, proceed with write
        
        snapshot = {
            "date": today,
            "timestamp": now.isoformat(),
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "invested": round(invested, 2)
        }
        
        # Check if we already have an entry for today
        if history and history[-1].get("date") == today:
            # Update today's entry
            history[-1] = snapshot
        else:
            # Add new entry
            history.append(snapshot)
        
        # Keep only last 90 days
        history = history[-90:]
        
        EQUITY_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except Exception:
        pass  # Don't fail if we can't save history


def _save_equity_snapshot(equity: float, cash: float, invested: float):
    """Save equity snapshot to history file for day-over-day P&L tracking."""
    try:
        history = []
        if EQUITY_HISTORY_FILE.exists():
            history = _load_json(EQUITY_HISTORY_FILE)
            if not isinstance(history, list):
                history = []
        
        today = date.today().isoformat()
        snapshot = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "invested": round(invested, 2)
        }
        
        # Check if we already have an entry for today
        if history and history[-1].get("date") == today:
            # Update today's entry
            history[-1] = snapshot
        else:
            # Add new entry
            history.append(snapshot)
        
        # Keep only last 90 days
        history = history[-90:]
        
        EQUITY_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except Exception:
        pass  # Don't fail if we can't save history


def _get_today_enforcement() -> dict:
    """Count today's enforcement events."""
    today = date.today().isoformat()
    result = {"bypasses_today": 0, "overrides_reverted_today": 0,
              "quota_force_buys_today": 0, "stop_losses_today": 0}

    # Signal overrides
    overrides = _load_json(SIGNAL_OVERRIDES_FILE)
    for o in overrides.get("overrides", []):
        ts = o.get("timestamp", "")
        if ts.startswith(today):
            if o.get("reverted"):
                result["overrides_reverted_today"] += 1

    # Buy quota
    quota = _load_json(BUY_QUOTA_LOG_FILE)
    for m in quota.get("misses", []):
        ts = m.get("timestamp", "")
        if ts.startswith(today):
            result["quota_force_buys_today"] += len(m.get("force_buy_tickers", []))

    # Today's trade log for stop-losses
    trade_log_file = TRADING_LOGS_DIR / f"{today}.json"
    if trade_log_file.exists():
        trades = _load_json(trade_log_file)
        for t in trades.get("trades", []):
            decision = t.get("decision", "")
            if decision in ("STOP_LOSS_TRIGGERED", "AGENT_STOP_TRIGGERED"):
                result["stop_losses_today"] += 1

    return result


def get_equity_history(days: int = 30) -> list[dict]:
    """Get daily equity snapshots.

    Reconstructs from trade logs. Returns list of {date, equity, cash, invested}.
    """
    # Check for cached equity history
    if EQUITY_HISTORY_FILE.exists():
        cached = _load_json(EQUITY_HISTORY_FILE)
        if isinstance(cached, list) and cached:
            return cached[-days:]

    # Reconstruct from positions.json snapshots and trade logs
    snapshots = []

    # Scan all daily trade log files for dates
    log_files = sorted(TRADING_LOGS_DIR.glob("????-??-??.json"))
    for log_file in log_files:
        try:
            log_date = log_file.stem  # YYYY-MM-DD
            data = json.loads(log_file.read_text(encoding="utf-8"))
            trades = data.get("trades", [])

            # Count BUYs and estimate invested
            buys_value = sum(
                t.get("order", {}).get("qty", 0) * 1000  # rough estimate
                for t in trades
                if t.get("decision") == "BUY"
            )

            snapshots.append({
                "date": log_date,
                "equity": 100000,  # We don't have historical equity snapshots
                "cash": 100000 - buys_value,
                "invested": buys_value,
            })
        except Exception:
            continue

    # If we have current positions.json, use it for the latest point
    if POSITIONS_FILE.exists():
        pos_data = _load_json(POSITIONS_FILE)
        account = pos_data.get("account", {})
        equity = account.get("equity", 100000)
        cash = account.get("cash", 100000)
        invested = equity - cash
        today_str = date.today().isoformat()

        if snapshots and snapshots[-1]["date"] == today_str:
            snapshots[-1] = {"date": today_str, "equity": equity, "cash": cash, "invested": invested}
        else:
            snapshots.append({"date": today_str, "equity": equity, "cash": cash, "invested": invested})

    return snapshots[-days:]
