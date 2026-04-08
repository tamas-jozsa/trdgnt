"""
Research data service.

Reads research findings, watchlist state, and buy quota log.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from ..config import (
    PROJECT_ROOT, RESULTS_DIR, WATCHLIST_OVERRIDES_FILE, BUY_QUOTA_LOG_FILE,
)

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps"))


def _load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def get_available_dates() -> list[str]:
    """Get list of dates with research findings, newest first."""
    if not RESULTS_DIR.exists():
        return []
    files = sorted(RESULTS_DIR.glob("RESEARCH_FINDINGS_*.md"), reverse=True)
    return [f.stem.replace("RESEARCH_FINDINGS_", "") for f in files]


def get_findings(date: str | None = None) -> dict:
    """Get research findings for a date (defaults to latest)."""
    available = get_available_dates()
    if not available:
        return {"date": "", "markdown": "", "signals": [], "available_dates": []}

    if not date or date not in available:
        date = available[0]

    findings_file = RESULTS_DIR / f"RESEARCH_FINDINGS_{date}.md"
    if not findings_file.exists():
        return {"date": date, "markdown": "", "signals": [], "available_dates": available}

    text = findings_file.read_text(encoding="utf-8")

    # Parse sentiment and VIX from header
    sentiment = ""
    vix = 0.0
    vix_trend = ""

    m = re.search(r"Sentiment:\s*(\w+)", text, re.IGNORECASE)
    if m:
        sentiment = m.group(1).upper()

    m = re.search(r"VIX:\s*([\d.]+)", text)
    if m:
        vix = float(m.group(1))

    m = re.search(r"Trend:\s*(\w+)", text, re.IGNORECASE)
    if m:
        vix_trend = m.group(1).upper()

    # Parse per-ticker signals using existing parser
    signals = []
    try:
        from tradingagents.research_context import parse_research_signals
        raw_signals = parse_research_signals(text)
        for ticker, sig in raw_signals.items():
            signals.append({
                "ticker": ticker,
                "decision": sig.get("decision", ""),
                "conviction": sig.get("conviction", ""),
                "reason": sig.get("reason", ""),
                "tier": sig.get("tier", ""),
            })
    except Exception:
        pass

    # Parse sector signals
    sector_signals = {}
    try:
        from tradingagents.research_context import parse_sector_signals
        sector_signals = parse_sector_signals(text)
    except Exception:
        pass

    # Parse new picks
    new_picks = []
    m = re.search(r"NEW PICK[S]?.*?\n((?:[\d]+\..*\n?)+)", text, re.IGNORECASE)
    if m:
        for line in m.group(1).strip().split("\n"):
            ticker_match = re.match(r"\d+\.\s*\*?\*?(\w+)", line)
            if ticker_match:
                new_picks.append(ticker_match.group(1).upper())

    return {
        "date": date,
        "markdown": text,
        "sentiment": sentiment,
        "vix": vix,
        "vix_trend": vix_trend,
        "signals": signals,
        "sector_signals": sector_signals,
        "new_picks": new_picks,
        "available_dates": available,
    }


def get_watchlist() -> dict:
    """Get merged watchlist (static + dynamic overrides)."""
    tickers = []

    # Static watchlist
    try:
        from trading_loop import WATCHLIST
        for ticker, entry in WATCHLIST.items():
            if isinstance(entry, dict):
                tickers.append({
                    "ticker": ticker,
                    "sector": entry.get("sector", ""),
                    "tier": entry.get("tier", "TACTICAL"),
                    "note": entry.get("note", ""),
                    "source": "static",
                    "added_on": None,
                })
    except Exception:
        pass

    static_count = len(tickers)

    # Dynamic overrides
    overrides = _load_json(WATCHLIST_OVERRIDES_FILE)
    if not isinstance(overrides, dict):
        overrides = {}

    adds = overrides.get("add", {})
    removes = overrides.get("remove", [])

    # Add dynamic tickers
    for ticker, entry in adds.items():
        if not any(t["ticker"] == ticker for t in tickers):
            tickers.append({
                "ticker": ticker,
                "sector": entry.get("sector", "Research Pick"),
                "tier": entry.get("tier", "TACTICAL"),
                "note": entry.get("note", "Added by research"),
                "source": "dynamic",
                "added_on": entry.get("added_on"),
            })

    # Mark removed tickers
    removed_tickers = set()
    if isinstance(removes, list):
        for r in removes:
            if isinstance(r, dict):
                removed_tickers.add(r.get("ticker", ""))
            elif isinstance(r, str):
                removed_tickers.add(r)

    tickers = [t for t in tickers if t["ticker"] not in removed_tickers]

    return {
        "static_count": static_count,
        "effective_count": len(tickers),
        "tickers": tickers,
        "overrides": overrides,
    }


def get_quota_history() -> dict:
    """Get buy quota enforcement history."""
    data = _load_json(BUY_QUOTA_LOG_FILE)
    if not isinstance(data, dict):
        return {"total_misses": 0, "recent": []}

    misses = data.get("misses", [])
    # Sort by timestamp descending
    misses.sort(key=lambda m: m.get("timestamp", ""), reverse=True)

    return {
        "total_misses": data.get("summary", {}).get("total_misses", len(misses)),
        "recent": misses[:20],
    }
