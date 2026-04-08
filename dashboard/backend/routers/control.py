"""Control API endpoints."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter

from ..config import (
    PROJECT_ROOT, TRADING_LOGS_DIR, POSITIONS_FILE, RESULTS_DIR,
    WATCHLIST_OVERRIDES_FILE, STDOUT_LOG_FILE,
)
from ..models.schemas import SystemStatus, RunRequest, RunResponse, WatchlistAction

sys.path.insert(0, str(PROJECT_ROOT / "apps"))

router = APIRouter()

# Path to the Python interpreter (use tradingagents conda env)
PYTHON = sys.executable
# If we're not in the tradingagents env, use the explicit path
if "tradingagents" not in PYTHON:
    PYTHON = "/Users/tjozsa/miniconda3/envs/tradingagents/bin/python"


def _load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


@router.get("/status", response_model=SystemStatus)
async def get_status():
    """Get system status."""
    # Check if agent is running via launchctl
    agent_running = False
    agent_pid = None
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "tradingagents" in line.lower():
                parts = line.split()
                if parts[0] != "-":
                    agent_pid = int(parts[0])
                    agent_running = True
                break
    except Exception:
        pass

    # Today's trades
    today_str = date.today().isoformat()
    today_trades = {"buy": 0, "sell": 0, "hold": 0, "na": 0, "error": 0}
    trade_log = TRADING_LOGS_DIR / f"{today_str}.json"
    if trade_log.exists():
        data = _load_json(trade_log)
        for t in data.get("trades", []):
            d = t.get("decision", "HOLD").upper()
            if d == "BUY":
                today_trades["buy"] += 1
            elif d == "SELL":
                today_trades["sell"] += 1
            elif d == "HOLD":
                today_trades["hold"] += 1
            elif d == "WAIT":
                today_trades["na"] += 1
            else:
                today_trades["error"] += 1

    # Research status
    today_research = (RESULTS_DIR / f"RESEARCH_FINDINGS_{today_str}.md").exists()

    # Portfolio
    positions_data = _load_json(POSITIONS_FILE)
    account = positions_data.get("account", {})
    equity = account.get("equity", 0)
    cash = account.get("cash", 0)
    num_positions = len(positions_data.get("positions", []))

    # Ticker count
    try:
        from trading_loop import WATCHLIST
        ticker_count = len(WATCHLIST)
    except Exception:
        ticker_count = 34

    return SystemStatus(
        agent_running=agent_running,
        agent_pid=agent_pid,
        tickers=ticker_count,
        cash_ratio=round(cash / max(equity, 1), 3),
        open_positions=num_positions,
        today_trades=today_trades,
        today_research_done=today_research,
    )


@router.post("/run", response_model=RunResponse)
async def run_cycle(req: RunRequest):
    """Trigger a trading cycle."""
    # Use -u for unbuffered output so logs appear immediately
    cmd = [PYTHON, "-u", str(PROJECT_ROOT / "apps" / "trading_loop.py"), "--once", "--no-wait"]

    if req.dry_run or req.mode == "dry_run":
        cmd.append("--dry-run")

    if req.tickers:
        cmd.extend(["--tickers"] + req.tickers)

    # Add parallel workers (capped at 4 for safety)
    parallel = min(max(req.parallel, 1), 4)
    if parallel > 1:
        cmd.extend(["--parallel", str(parallel)])

    # Use separate log file for manual runs to avoid interleaving with daemon output
    import time
    timestamp = int(time.time())
    stdout_log = TRADING_LOGS_DIR / f"manual_run_{timestamp}.log"
    stderr_log = TRADING_LOGS_DIR / f"manual_run_{timestamp}.err.log"

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=open(stdout_log, "w"),
        stderr=open(stderr_log, "w"),
    )

    return RunResponse(
        status="started",
        pid=proc.pid,
        mode=req.mode,
        tickers=len(req.tickers) if req.tickers else 34,
        log_file=str(stdout_log),
    )


@router.post("/research")
async def force_research():
    """Force a daily research refresh."""
    cmd = [PYTHON, str(PROJECT_ROOT / "apps" / "daily_research.py"), "--force"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=open(TRADING_LOGS_DIR / "stdout.log", "a"),
        stderr=open(TRADING_LOGS_DIR / "stderr.log", "a"),
    )
    return {"status": "started", "pid": proc.pid}


@router.post("/sync-positions")
async def sync_positions():
    """Sync positions from Alpaca."""
    try:
        from update_positions import fetch_positions, save_positions
        data = fetch_positions()
        save_positions(data)
        return {
            "status": "done",
            "positions": len(data.get("positions", [])),
            "equity": data.get("account", {}).get("equity", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/watchlist")
async def modify_watchlist(req: WatchlistAction):
    """Add or remove a ticker from the dynamic watchlist."""
    overrides = _load_json(WATCHLIST_OVERRIDES_FILE)
    if not isinstance(overrides, dict):
        overrides = {"add": {}, "remove": []}
    if "add" not in overrides:
        overrides["add"] = {}
    if "remove" not in overrides:
        overrides["remove"] = []

    ticker = req.ticker.upper()

    if req.action == "add":
        overrides["add"][ticker] = {
            "sector": req.sector or "Dashboard Add",
            "tier": req.tier.upper(),
            "note": req.note or "Added via dashboard",
            "added_on": date.today().isoformat(),
        }
        # Remove from removes if present
        overrides["remove"] = [
            r for r in overrides["remove"]
            if (r.get("ticker") if isinstance(r, dict) else r) != ticker
        ]

    elif req.action == "remove":
        # Remove from adds if present
        overrides["add"].pop(ticker, None)
        # Add to removes
        overrides["remove"].append({
            "ticker": ticker,
            "removed_on": date.today().isoformat(),
        })

    WATCHLIST_OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHLIST_OVERRIDES_FILE, "w") as f:
        json.dump(overrides, f, indent=2)

    return {"status": "ok", "action": req.action, "ticker": ticker}


@router.get("/logs/scheduled")
async def get_scheduled_logs(lines: int = 2000):
    """Get last N lines from scheduled (daemon) stdout.log."""
    if not STDOUT_LOG_FILE.exists():
        return {"lines": [], "count": 0}
    
    with open(STDOUT_LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    # Return last N non-empty lines
    non_empty = [line.rstrip() for line in all_lines if line.strip()]
    last_lines = non_empty[-lines:] if len(non_empty) > lines else non_empty
    
    return {"lines": last_lines, "count": len(last_lines)}


@router.get("/logs/manual")
async def get_manual_logs(lines: int = 2000):
    """Get last N lines from most recent manual_run_*.log."""
    manual_logs = sorted(
        TRADING_LOGS_DIR.glob("manual_run_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not manual_logs:
        return {"lines": [], "count": 0, "file": None}
    
    latest = manual_logs[0]
    with open(latest, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    # Return last N non-empty lines
    non_empty = [line.rstrip() for line in all_lines if line.strip()]
    last_lines = non_empty[-lines:] if len(non_empty) > lines else non_empty
    
    return {"lines": last_lines, "count": len(last_lines), "file": latest.name}
