"""
trading_loop.py
===============
Runs TradingAgents analysis on a curated macro-aware watchlist once per day,
executing paper trades on Alpaca.
"""

# ---------------------------------------------------------------------------
# Path setup - MUST be first
# ---------------------------------------------------------------------------
import _path_setup  # noqa: F401
from _path_setup import PROJECT_ROOT, TRADING_LOGS_DIR, MEMORY_DIR, RESULTS_DIR

# ---------------------------------------------------------------------------

import argparse
import concurrent.futures
import json
import logging
import os
import resource
import requests
import time
import urllib3
import warnings

# Raise the file descriptor limit to avoid [Errno 24] Too many open files
# when running 34 tickers sequentially (each opens several CSVs + DB files)
try:
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = min(4096, hard)
    if soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
except Exception:
    pass  # non-fatal if we can't raise the limit
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Suppress noisy httpx / LangChain HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Project root imported from _path_setup — all paths are anchored here
# ---------------------------------------------------------------------------
load_dotenv()


# ---------------------------------------------------------------------------
# macOS notifications
# ---------------------------------------------------------------------------

import subprocess

def notify(title: str, message: str, subtitle: str = ""):
    """Send a macOS Notification Center alert via osascript."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        if subtitle:
            script += f' subtitle "{subtitle}"'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass  # Never let a notification failure break the trading loop

# ---------------------------------------------------------------------------
# Curated watchlist — deep research update March 24, 2026
#
# Macro themes (updated):
#   - AI capex supercycle: SK Hynix $8B ASML order + AVGO $970M DoD deal confirm
#   - US/Iran war ("Operation Epic Fury"): 11M bbl/day offline, Hormuz crisis
#     > rebuilding timeline 3-5 years — structural energy bull regardless of ceasefire
#   - Trump tweet volatility: $3.8T swung in 9 min; VIX 26.48 (+74.92% YTD)
#   - Copper supply structural deficit: JPMorgan 330kt deficit 2026
#     > Grasberg + Kamoa-Kakula + El Teniente all disrupted simultaneously
#   - Steel / AI infrastructure: 20k+ tons per data center; 25% tariff tailwind
#   - Private credit stress: Apollo/BlackRock/Blue Owl gating redemptions
#   - Fertilizer Hormuz play: 60% of global supply routes through Hormuz
#   - Drone warfare theme: 60+ interceptions/day, DoD spending surge
#
# Research sources: Yahoo Finance, CNBC, Seeking Alpha (Mar 24 live),
#   Reddit r/wallstreetbets, r/stocks, r/investing, r/pennystocks (Mar 24),
#   Finviz screener (short float >20% + momentum), Citi/BofA/JPMorgan calls
#
# Key calls: Citi (Brent $120/bbl), JPMorgan (copper deficit), BofA (GLW Buy),
#   Mizuho (MDB), Morgan Stanley (VG Buy), WSB DD (CMC steel thesis)
#
# Changes vs previous:
#   ADDED:  GLW, CMC, NUE, APA, SOC, SCCO, RCAT, MOS, RCKT
#   REMOVED: BIP (high-rate headwind + private credit risk), CRM (NOW is better play)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tier multipliers — scale the base --amount per trade by conviction level
#   CORE        → 2.0x  (high conviction, macro-aligned, liquid)
#   TACTICAL    → 1.0x  (momentum / catalyst-driven, 1-4 week horizon)
#   SPECULATIVE → 0.4x  (meme / squeeze / biotech, max 2-3% of portfolio)
#   HEDGE       → 0.5x  (macro protection, gold, inverse ETFs)
# ---------------------------------------------------------------------------
TIER_MULTIPLIER: dict[str, float] = {
    "CORE":        2.0,
    "TACTICAL":    1.0,
    "SPECULATIVE": 0.4,
    "HEDGE":       0.5,
}

# ---------------------------------------------------------------------------
# Tier-based debate rounds — CORE gets full 2-round scrutiny;
# TACTICAL/SPECULATIVE/HEDGE get 1 round (catalyst plays, less nuance needed)
# Saves ~40% LLM debate cost on non-CORE tickers.
# ---------------------------------------------------------------------------
TIER_DEBATE_ROUNDS: dict[str, int] = {
    "CORE":        2,
    "TACTICAL":    1,
    "SPECULATIVE": 1,
    "HEDGE":       1,
}
TIER_RISK_ROUNDS: dict[str, int] = {
    "CORE":        2,
    "TACTICAL":    1,
    "SPECULATIVE": 1,
    "HEDGE":       1,
}

# Each entry: { "sector": str, "tier": str, "note": str }
WATCHLIST: dict[str, dict] = {
    # ── CORE HOLDS ──────────────────────────────────────────────────────────
    "NVDA":  {"sector": "AI & Semiconductors",      "tier": "CORE",        "note": "GPU monopoly; SK Hynix ASML order confirms AI demand"},
    "AVGO":  {"sector": "AI & Semiconductors",      "tier": "CORE",        "note": "$970M DoD private cloud deal closed Mar 24; custom ASICs"},
    "AMD":   {"sector": "AI & Semiconductors",      "tier": "CORE",        "note": "GPU #2, datacenter CPUs"},
    "ARM":   {"sector": "AI & Semiconductors",      "tier": "CORE",        "note": "CPU architecture licensing, edge AI"},
    "TSM":   {"sector": "AI & Semiconductors",      "tier": "CORE",        "note": "fabricates all leading-edge chips; SK Hynix order benefits"},
    "MU":    {"sector": "AI & Semiconductors",      "tier": "CORE",        "note": "Micron; AI memory; short-term headwind — monitor"},
    "LITE":  {"sector": "AI Photonics",             "tier": "CORE",        "note": "BNP PT $1000; Nvidia/Google transceiver wins"},
    "MSFT":  {"sector": "AI Software & Cloud",      "tier": "CORE",        "note": "RSI 30 oversold + 200 WMA; Azure+OpenAI; 24x PE"},
    "GOOGL": {"sector": "AI Software & Cloud",      "tier": "CORE",        "note": "Gemini, TPUs, cloud"},
    "META":  {"sector": "AI Software & Cloud",      "tier": "CORE",        "note": "recovering from selloff; WSB confirmed bounce; AI infra"},
    "PLTR":  {"sector": "AI Software & Cloud",      "tier": "CORE",        "note": "Maven AI federal; DoD spending surge during Iran war"},
    "GLW":   {"sector": "AI Infrastructure",        "tier": "CORE",        "note": "Corning; BofA Buy Mar 24; optical fiber for DC interconnects"},
    "MDB":   {"sector": "AI Infrastructure",        "tier": "CORE",        "note": "Mizuho upgrade; database layer for AI apps"},
    "NOW":   {"sector": "Productivity SaaS",        "tier": "CORE",        "note": "ServiceNow+Vonage AI workflow integration Mar 24"},
    "PANW":  {"sector": "Cybersecurity",            "tier": "CORE",        "note": "new agentic AI browser + Iran war winner"},
    "CRWD":  {"sector": "Cybersecurity",            "tier": "CORE",        "note": "new AI adversary security product launched Mar 24"},
    "RTX":   {"sector": "Defense",                  "tier": "CORE",        "note": "Patriot systems; 60+ drone interceptions/day; structural"},
    "LMT":   {"sector": "Defense",                  "tier": "CORE",        "note": "F-35, hypersonics, space; Iran war"},
    "NOC":   {"sector": "Defense",                  "tier": "CORE",        "note": "B-21 bomber, space systems; Iran war"},
    "VG":    {"sector": "LNG / Energy",             "tier": "CORE",        "note": "TOP GAINER +9.72% Mar 24; Vitol 5yr deal; Morgan Stanley Buy"},
    "LNG":   {"sector": "LNG / Energy",             "tier": "CORE",        "note": "structural LNG demand; Iran war accelerant"},
    "XOM":   {"sector": "Energy Hedge",             "tier": "CORE",        "note": "largest US oil major; Iran war beneficiary"},
    "FCX":   {"sector": "Copper / Materials",       "tier": "CORE",        "note": "JPMorgan 330kt deficit 2026; AI+defense demand confirmed"},
    "MP":    {"sector": "Rare Earths",              "tier": "CORE",        "note": "only US rare earth producer; defense magnets + Iran war"},
    "UBER":  {"sector": "Mobility / AV",            "tier": "CORE",        "note": "AV facilitator; WeRide +6.8% Mar 24 signals AV recovery"},
    "GLD":   {"sector": "Gold / Macro Hedge",       "tier": "HEDGE",       "note": "$4,389/oz; geopolitical premium; safe haven"},

    # ── TACTICAL PLAYS ──────────────────────────────────────────────────────
    "CMC":   {"sector": "Steel / AI Infrastructure","tier": "TACTICAL",    "note": "11x fwd PE; DC steel buildout; 25% tariff tailwind; WSB DD Mar 24"},
    "NUE":   {"sector": "Steel / AI Infrastructure","tier": "TACTICAL",    "note": "Nucor; 95% US DC steel; larger/more liquid than CMC"},
    "APA":   {"sector": "Oil E&P",                  "tier": "TACTICAL",    "note": "+5.5% Mar 24; 9.8x PE; Iran war; 52-week breakout candidate"},
    "SOC":   {"sector": "Oil & Gas Drilling",       "tier": "TACTICAL",    "note": "Sable Offshore; top energy performer past month"},
    "SCCO":  {"sector": "Copper / Materials",       "tier": "TACTICAL",    "note": "Southern Copper; pure-play copper deficit; complement to FCX"},

    # ── SPECULATIVE / HIGH-RISK ──────────────────────────────────────────────
    "RCAT":  {"sector": "Defense / Drone Warfare",  "tier": "SPECULATIVE", "note": "Red Cat; >20% short float; drone war DoD contracts; Iran war"},
    "MOS":   {"sector": "Fertilizer / Macro",       "tier": "SPECULATIVE", "note": "Mosaic; Hormuz fertilizer supply shock; 1679 Reddit upvotes"},
    "RCKT":  {"sector": "Biotech Binary",           "tier": "SPECULATIVE", "note": "Rocket Pharma; FDA re-review; 16% SI; 100% clinical survivability"},
}


def get_sector(ticker: str) -> str:
    """Return the sector string for a ticker (for display / logging)."""
    entry = WATCHLIST.get(ticker)
    if isinstance(entry, dict):
        return entry.get("sector", "")
    return str(entry) if entry else ""


def get_tier(ticker: str) -> str:
    """Return the conviction tier for a ticker."""
    entry = WATCHLIST.get(ticker)
    if isinstance(entry, dict):
        return entry.get("tier", "TACTICAL")
    return "TACTICAL"


def tier_amount(base_amount: float, ticker: str) -> float:
    """Scale a base trade amount by the ticker's conviction tier."""
    multiplier = TIER_MULTIPLIER.get(get_tier(ticker), 1.0)
    return round(base_amount * multiplier, 2)


DEFAULT_TICKERS = list(WATCHLIST.keys())

# ---------------------------------------------------------------------------
# Dynamic watchlist — overrides from daily research findings
# ---------------------------------------------------------------------------
_OVERRIDES_FILE = TRADING_LOGS_DIR / "watchlist_overrides.json"

# Decay / cap constants
_REMOVE_EXPIRY_DAYS = 5   # removes older than this many calendar days are dropped
_MAX_REMOVES        = 8   # at most this many static-WATCHLIST tickers removed at once
_MAX_ADDS           = 10  # at most this many dynamic adds accumulated


def _remove_entry_date(entry) -> str:
    """Extract the 'removed_on' date from a remove entry (str or dict)."""
    if isinstance(entry, dict):
        return entry.get("removed_on", "")
    return ""  # legacy plain-string format — no date, treated as non-expiring


def _remove_entry_ticker(entry) -> str:
    """Extract ticker symbol from a remove entry (str or dict)."""
    if isinstance(entry, dict):
        return entry.get("ticker", "")
    return str(entry)


def _is_expired(entry) -> bool:
    """Return True if a remove entry is older than _REMOVE_EXPIRY_DAYS."""
    d = _remove_entry_date(entry)
    if not d:
        return False  # legacy entries without a date are kept
    try:
        from datetime import date as _date
        removed_on = _date.fromisoformat(d)
        return (_date.today() - removed_on).days > _REMOVE_EXPIRY_DAYS
    except Exception:
        return False


def load_watchlist_overrides() -> dict:
    """
    Merge static WATCHLIST with persisted overrides from research findings.

    Returns a dict in the same format as WATCHLIST with any ADD/REMOVE
    changes applied. The static WATCHLIST is never mutated.

    Remove entries expire after _REMOVE_EXPIRY_DAYS days and are ignored
    during load (they will be cleaned up on the next save_watchlist_overrides call).
    """
    # TICKET-074: Clean legacy data before loading
    try:
        from watchlist_cleaner import load_and_clean_watchlist_overrides
        overrides = load_and_clean_watchlist_overrides()
    except Exception as e:
        print(f"  [WATCHLIST] Cleanup warning: {e}")
        overrides = {"add": {}, "remove": []}

    effective = dict(WATCHLIST)

    # Apply adds
    added = overrides.get("add", {})
    for ticker, info in added.items():
        if ticker not in effective:
            effective[ticker] = info
            print(f"  [WATCHLIST] +{ticker} (from research override: {info.get('note','')})")

    # Apply removes
    removed = overrides.get("remove", [])
    for entry in removed:
        ticker = _remove_entry_ticker(entry)
        if _is_expired(entry):
            continue  # silently skip expired entries during load
        if ticker in effective:
            effective.pop(ticker)
            date_str = _remove_entry_date(entry)
            expiry_note = f", expires in {_REMOVE_EXPIRY_DAYS - (date.today() - date.fromisoformat(date_str)).days}d" if date_str else ""
            print(f"  [WATCHLIST] -{ticker} (removed by research override{expiry_note})")

    return effective


def save_watchlist_overrides(adds: dict, removes: list) -> None:
    """
    Persist watchlist ADD/REMOVE decisions to disk with decay and caps.

    Rules applied on every save:
    - Expired removes (> _REMOVE_EXPIRY_DAYS old) are dropped.
    - CORE-tier tickers require a prior-day remove entry to be confirmed;
      a brand-new SELL on a CORE ticker on a single day is ignored.
    - Total removes from static WATCHLIST capped at _MAX_REMOVES.
    - Total dynamic adds capped at _MAX_ADDS (oldest by added_on dropped first).
    - A ticker in both add and remove lists: add wins (remove is cleared).
    """
    today_str = str(date.today())
    _OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if _OVERRIDES_FILE.exists():
        try:
            existing = json.loads(_OVERRIDES_FILE.read_text())
        except Exception:
            pass

    # --- Existing removes: normalise to dicts, drop expired ---
    existing_remove_entries = existing.get("remove", [])
    existing_remove_dicts: list[dict] = []
    for e in existing_remove_entries:
        d = {"ticker": _remove_entry_ticker(e), "removed_on": _remove_entry_date(e) or today_str}
        existing_remove_dicts.append(d)
    # Drop expired
    existing_remove_dicts = [e for e in existing_remove_dicts if not _is_expired(e)]
    existing_tickers_in_remove = {e["ticker"] for e in existing_remove_dicts}

    # --- New removes: apply CORE-tier protection ---
    new_remove_dicts: list[dict] = []
    for ticker in removes:
        if ticker in existing_tickers_in_remove:
            # Already scheduled for removal — confirm it (update date to today)
            new_remove_dicts.append({"ticker": ticker, "removed_on": today_str})
        elif get_tier(ticker) == "CORE":
            # CORE tickers need a prior-day remove entry — single-day SELL is ignored
            print(f"  [WATCHLIST] Ignoring single-day SELL for CORE ticker {ticker} "
                  f"(requires prior-day confirmation)")
            continue
        else:
            new_remove_dicts.append({"ticker": ticker, "removed_on": today_str})

    # Merge: confirmed entries take priority (replace older date with today_str)
    confirmed_tickers = {e["ticker"] for e in new_remove_dicts}
    kept_existing = [e for e in existing_remove_dicts if e["ticker"] not in confirmed_tickers]
    merged_remove_dicts = kept_existing + new_remove_dicts

    # Cap at _MAX_REMOVES — keep most recently added (sort by removed_on desc, take first N)
    merged_remove_dicts.sort(key=lambda e: e.get("removed_on", ""), reverse=True)
    if len(merged_remove_dicts) > _MAX_REMOVES:
        dropped = [e["ticker"] for e in merged_remove_dicts[_MAX_REMOVES:]]
        print(f"  [WATCHLIST] Remove cap ({_MAX_REMOVES}) reached — dropping oldest: {dropped}")
        merged_remove_dicts = merged_remove_dicts[:_MAX_REMOVES]

    # --- Adds: merge, cap at _MAX_ADDS ---
    existing_adds = existing.get("add", {})
    # Normalise legacy entries that predate the added_on field
    for t, info in existing_adds.items():
        if "added_on" not in info:
            existing_adds[t] = {**info, "added_on": "1970-01-01"}
    # Stamp new adds with added_on date
    stamped_adds = {}
    for ticker, info in adds.items():
        stamped_adds[ticker] = {**info, "added_on": info.get("added_on", today_str)}
    merged_adds = {**existing_adds, **stamped_adds}

    if len(merged_adds) > _MAX_ADDS:
        # Sort by added_on ascending, drop oldest
        sorted_adds = sorted(merged_adds.items(),
                             key=lambda kv: kv[1].get("added_on", ""), reverse=True)
        dropped_adds = [k for k, _ in sorted_adds[_MAX_ADDS:]]
        print(f"  [WATCHLIST] Add cap ({_MAX_ADDS}) reached — dropping oldest: {dropped_adds}")
        merged_adds = dict(sorted_adds[:_MAX_ADDS])

    # --- Consistency: add wins over remove ---
    remove_tickers = {e["ticker"] for e in merged_remove_dicts}
    for t in list(merged_adds.keys()):
        if t in remove_tickers:
            merged_remove_dicts = [e for e in merged_remove_dicts if e["ticker"] != t]

    _OVERRIDES_FILE.write_text(json.dumps(
        {"add": merged_adds, "remove": merged_remove_dicts}, indent=2
    ))


def parse_watchlist_changes(findings_text: str) -> dict:
    """
    Parse ADD/REMOVE ticker decisions from a RESEARCH_FINDINGS_*.md file.

    Looks for:
    1. WATCHLIST DECISIONS table — rows with SELL verdict → candidate for REMOVE
    2. TOP 3 NEW PICKS section — tickers → ADD as TACTICAL

    Returns {"add": {ticker: info_dict}, "remove": [ticker, ...]}
    """
    import re
    adds:    dict[str, dict] = {}
    removes: list[str]       = []

    # Parse WATCHLIST DECISIONS table for REMOVE signals
    # Matches lines like: | NVDA   | AI     | SELL     | HIGH       | reason |
    table_pattern = re.compile(
        r"\|\s*([A-Z]{1,6})\s*\|[^|]+\|\s*(SELL|REMOVE)\s*\|",
        re.IGNORECASE
    )
    for m in table_pattern.finditer(findings_text):
        ticker = m.group(1).strip().upper()
        if ticker in WATCHLIST:
            removes.append(ticker)

    # Parse TOP 3 NEW PICKS section
    # Matches lines like: 1. TICKER — setup — catalyst — risk
    picks_section = re.search(
        r"###\s*TOP\s*\d*\s*NEW\s*PICKS.*?\n(.*?)(?=\n###|\Z)",
        findings_text, re.DOTALL | re.IGNORECASE
    )
    if picks_section:
        pick_pattern = re.compile(r"^\d+\.\s+([A-Z]{1,6})\s*[—\-]", re.MULTILINE)
        for m in pick_pattern.finditer(picks_section.group(1)):
            ticker = m.group(1).strip().upper()
            if ticker not in WATCHLIST and len(ticker) >= 2:
                adds[ticker] = {
                    "sector": "Research Pick",
                    "tier":   "TACTICAL",
                    "note":   "Added by daily research",
                }

    return {"add": adds, "remove": removes}

ET = ZoneInfo("America/New_York")


def get_market_clock() -> dict:
    """Query Alpaca's /v2/clock endpoint — the authoritative source for market status."""
    ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
    ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise EnvironmentError(
            "Missing ALPACA_API_KEY or ALPACA_API_SECRET. "
            "Add them to your .env file. See .env.example."
        )
    headers = {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }
    alpaca_base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    last_exc = None
    for attempt in range(3):
        try:
            r = requests.get(
                f"{alpaca_base_url}/v2/clock",
                headers=headers,
                timeout=30,
                verify=False,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_exc = e
            if attempt < 2:
                time.sleep(5)
    raise last_exc


def is_market_open() -> bool:
    """Return True if the US stock market is currently open (via Alpaca clock)."""
    return get_market_clock()["is_open"]


def seconds_until_next_market_open() -> int:
    """Return seconds until next market open (via Alpaca clock)."""
    clock = get_market_clock()
    next_open_str = clock["next_open"]
    next_open = datetime.fromisoformat(next_open_str)
    now = datetime.now(next_open.tzinfo)
    return max(0, int((next_open - now).total_seconds()))


def seconds_until_next_run() -> int:
    """
    Return seconds until the next daily run time (10:00 AM ET).

    If it's before 10 AM today → run today at 10 AM.
    If it's already past 10 AM today → run tomorrow at 10 AM.
    Weekends: skip to Monday 10 AM.
    """
    now = datetime.now(ET)
    target = now.replace(hour=_RUN_HOUR, minute=_RUN_MIN, second=0, microsecond=0)

    if now >= target:
        # Already past today's run time — schedule for tomorrow
        target += timedelta(days=1)

    # Skip weekends: if target lands on Sat → Mon, Sun → Mon
    while target.weekday() >= 5:  # 5=Sat, 6=Sun
        target += timedelta(days=1)

    return max(0, int((target - now).total_seconds()))


_RUN_HOUR = 9    # 9 AM ET — daily run time (30 min before market open)
_RUN_MIN  =  0


def get_analysis_date() -> str:
    """
    Return the most recent completed trading session date.

    The loop runs at 9 AM ET — 30 min before market open, so we always analyse
    the previous completed session (yesterday or last Friday).

      Mon 9:00  → Friday's session
      Tue-Fri   → yesterday's session
      Sat/Sun   → Friday's session (shouldn't run on weekends but guard anyway)
    """
    now_et  = datetime.now(ET)
    today   = now_et.date()
    weekday = today.weekday()  # 0=Mon, 5=Sat, 6=Sun

    if weekday == 0:   # Monday → Friday
        return str(today - timedelta(days=3))
    if weekday == 5:   # Saturday → Friday
        return str(today - timedelta(days=1))
    if weekday == 6:   # Sunday → Friday
        return str(today - timedelta(days=2))
    return str(today - timedelta(days=1))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = TRADING_LOGS_DIR
LOG_DIR.mkdir(exist_ok=True)


def log_decision(trade_date: str, ticker: str, decision: str, order_result: dict):
    log_file = LOG_DIR / f"{trade_date}.json"
    if log_file.exists():
        with open(log_file) as f:
            data = json.load(f)
    else:
        data = {"date": trade_date, "trades": []}

    data["trades"].append({
        "ticker":   ticker,
        "decision": decision,
        "order":    order_result,
        "time":     datetime.now(ET).isoformat(),
    })

    with open(log_file, "w") as f:
        json.dump(data, f, indent=2)


def print_separator(char="─", width=60):
    print(char * width)


# ---------------------------------------------------------------------------
# Single ticker analysis + trade
# ---------------------------------------------------------------------------

def _build_position_context(ticker: str) -> str:
    """Return a formatted position context string for the given ticker, or empty string."""
    try:
        from alpaca_bridge import _get_trading_client
        tc = _get_trading_client()
        pos = tc.get_open_position(ticker)
        qty      = float(pos.qty)
        avg_cost = float(pos.avg_entry_price)
        pnl_pct  = float(pos.unrealized_plpc) * 100
        pnl_usd  = float(pos.unrealized_pl)
        sign     = "+" if pnl_usd >= 0 else ""
        return (
            f"CURRENT POSITION: Long {qty:.4f} shares of {ticker} "
            f"@ avg ${avg_cost:.2f}, "
            f"unrealised P&L: {sign}${pnl_usd:.2f} ({sign}{pnl_pct:.1f}%)"
        )
    except Exception:
        return ""   # no position or API unavailable


def _build_returns_losses_summary(ticker: str) -> str:
    """
    Build a returns/losses summary string for reflect_and_remember().

    Tries to compute P&L from:
      1. Live Alpaca position (unrealised P&L if position still open)
      2. Yesterday's trade log (prior decision + rough price change)

    Returns a descriptive string or empty string if no data available.
    """
    try:
        from alpaca_bridge import _get_trading_client
        tc = _get_trading_client()
        pos = tc.get_open_position(ticker)
        pnl_pct = float(pos.unrealized_plpc) * 100
        pnl_usd = float(pos.unrealized_pl)
        sign    = "+" if pnl_usd >= 0 else ""
        direction = "gained" if pnl_usd >= 0 else "lost"
        return (
            f"The position in {ticker} has {direction} "
            f"{sign}${pnl_usd:.2f} ({sign}{pnl_pct:.1f}%) since entry. "
            f"Current unrealised P&L: {sign}{pnl_pct:.1f}%."
        )
    except Exception:
        pass

    # Fall back to yesterday's trade log if no open position
    try:
        logs = sorted(TRADING_LOGS_DIR.glob("????-??-??.json"), reverse=True)
        for log_path in logs[:3]:   # check last 3 days
            with open(log_path) as f:
                data = json.load(f)
            for trade in data.get("trades", []):
                if trade.get("ticker") == ticker and trade.get("decision") in ("BUY", "SELL"):
                    return (
                        f"Previously decided {trade['decision']} on {ticker} "
                        f"on {data.get('date', 'unknown date')}. "
                        f"No current open position — position may have been closed or not yet opened."
                    )
    except Exception:
        pass

    return ""


def _build_portfolio_context(target_deployment_pct: float | None = None) -> dict:
    """Build portfolio context for Risk Judge (TICKET-057 & 061).

    Returns dict with cash_ratio, position_count, etc. for dynamic decision making.

    Args:
        target_deployment_pct: Optional target deployment percentage.
            If None, loads from deployment config.
    """
    try:
        from alpaca_bridge import get_portfolio_summary
        from tradingagents.deployment_config import get_target_deployment_pct
        summary = get_portfolio_summary()

        cash_ratio = summary.get("cash", 0) / max(summary.get("equity", 1), 1)
        position_count = len(summary.get("positions", []))

        # Load target deployment if not provided
        if target_deployment_pct is None:
            target_deployment_pct = get_target_deployment_pct()

        context = {
            "cash_ratio": cash_ratio,
            "position_count": position_count,
            "equity": summary.get("equity", 0),
            "cash": summary.get("cash", 0),
            "target_deployment_pct": target_deployment_pct,
        }

        return context
    except Exception as e:
        # If we can't get portfolio data, return empty context
        return {}


def analyse_and_trade(
    ticker: str,
    trade_date: str,
    amount: float,
    dry_run: bool,
    max_open_positions: int = 20,
    current_open_positions: int = 0,
) -> dict:
    """
    Run TradingAgents on one ticker and execute on Alpaca.
    Returns a result dict. Never raises — errors are caught and returned.

    Args:
        max_open_positions:    Portfolio-level cap — BUY is skipped if this is breached.
        current_open_positions: Number of positions currently held (checked pre-execution).
    """
    from alpaca_bridge import execute_decision

    result = {"ticker": ticker, "decision": None, "order": None, "error": None}

    try:
        from tradingagents.research_context import load_latest_research_context
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        macro_context    = load_latest_research_context()
        position_context = _build_position_context(ticker)
        if position_context:
            print(f"  [POSITION] {position_context}")
        else:
            # Explicitly tell agents there is no position — a SELL decision will
            # be skipped (nothing to sell). Only BUY or HOLD are actionable.
            position_context = (
                f"NO CURRENT POSITION in {ticker}. "
                f"A SELL decision will be skipped (there is nothing to sell). "
                f"Only BUY or HOLD are actionable right now."
            )

        # Build TradingAgentsGraph once per ticker so we can persist memories
        memory_dir = str(MEMORY_DIR / ticker)
        config = DEFAULT_CONFIG.copy()
        # Two-tier LLM: gpt-4o for Research Manager + Risk Judge (decision nodes)
        # gpt-4o-mini for the 4 analysts + debaters (data summarisation, cheaper)
        config["deep_think_llm"]  = os.getenv("DEEP_LLM_MODEL",  "gpt-4o")
        config["quick_think_llm"] = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
        config["data_vendors"] = {
            "core_stock_apis":      "yfinance",
            "technical_indicators": "yfinance",
            "fundamental_data":     "yfinance",
            "news_data":            "yfinance",
        }
        # Tier-based debate rounds: CORE gets full scrutiny, others get 1 round
        tier = get_tier(ticker)
        config["max_debate_rounds"]      = TIER_DEBATE_ROUNDS.get(tier, 1)
        config["max_risk_discuss_rounds"] = TIER_RISK_ROUNDS.get(tier, 1)
        print(
            f"  [LLM] deep={config['deep_think_llm']}  quick={config['quick_think_llm']}"
            f"  debate={config['max_debate_rounds']}r  risk={config['max_risk_discuss_rounds']}r"
        )
        ta = TradingAgentsGraph(config=config)
        ta.load_memories(memory_dir)

        # TICKET-057 & 061: Build portfolio context for Risk Judge
        portfolio_context = _build_portfolio_context()

        print(f"\n[TRADINGAGENTS] Analysing {ticker} for {trade_date} ...")
        if position_context:
            print(f"[TRADINGAGENTS] Position context: {position_context}")
        if macro_context:
            print(f"[TRADINGAGENTS] Macro context loaded ({len(macro_context)} chars)")
        if portfolio_context:
            print(f"[TRADINGAGENTS] Portfolio context: cash {portfolio_context.get('cash_ratio', 0):.0%}")

        from langchain_community.callbacks import get_openai_callback
        with get_openai_callback() as cb:
            final_state, decision = ta.propagate(
                ticker, trade_date,
                position_context=position_context,
                macro_context=macro_context,
                portfolio_context=portfolio_context,
            )

        decision = decision.strip().upper() if decision else "HOLD"
        # Grab the full Risk Judge text for structured parsing (stop/target/size)
        agent_decision_text = (final_state or {}).get("final_trade_decision", "") or ""

        cost_usd = cb.total_cost
        print(
            f"[TRADINGAGENTS] Decision → {decision}  |  "
            f"tokens: {cb.prompt_tokens:,} in + {cb.completion_tokens:,} out  |  "
            f"cost: ${cost_usd:.4f}"
        )

        result["llm_cost"] = cost_usd
        result["llm_tokens_in"]  = cb.prompt_tokens
        result["llm_tokens_out"] = cb.completion_tokens
        result["decision"] = decision

        # ── Portfolio position-limit guard ────────────────────────────────────
        # If the portfolio is already at the max-positions cap, downgrade BUY
        # to HOLD rather than opening yet another position.
        if decision == "BUY" and not dry_run:
            from alpaca_bridge import get_portfolio_summary
            try:
                live_portfolio = get_portfolio_summary()
                live_positions = len(live_portfolio.get("positions", []))
            except Exception:
                live_positions = current_open_positions
            if live_positions >= max_open_positions:
                # TICKET-063: Log cash ratio context for dynamic limits
                cash_pct = live_portfolio.get("cash", 0) / max(live_portfolio.get("equity", 1), 1) * 100
                print(
                    f"  [RISK] Portfolio at max positions ({live_positions}/{max_open_positions}, "
                    f"cash: {cash_pct:.0f}%) — downgrading BUY to HOLD for {ticker}"
                )
                decision = "HOLD"
                result["decision"] = "HOLD"
        # ─────────────────────────────────────────────────────────────────────

        # TICKET-067: Detect, log, and ENFORCE Risk Judge overrides
        try:
            from tradingagents.signal_override import (
                detect_signal_override, log_override, print_override_warning,
                should_revert_override
            )
            from tradingagents.research_context import get_ticker_research_signal

            research_signal = get_ticker_research_signal(ticker)
            portfolio_context = _build_portfolio_context()

            override_info = detect_signal_override(
                ticker=ticker,
                investment_plan=final_state.get("investment_plan", ""),
                risk_judge_decision=agent_decision_text,
                portfolio_context=portfolio_context,
                research_signal=research_signal
            )

            if override_info:
                print_override_warning(override_info)
                log_override(override_info)

                # ENFORCEMENT: Revert critical BUY->HOLD overrides when cash is high
                if should_revert_override(override_info):
                    upstream_signal = override_info["upstream_signal"]
                    print(f"  [OVERRIDE-ENFORCE] Reverting {ticker} from HOLD to {upstream_signal} "
                          f"(severity={override_info['severity']}, cash={override_info['cash_ratio']:.0%})")
                    decision = upstream_signal
                    result["decision"] = upstream_signal
                    override_info["reverted"] = True
                    log_override(override_info)
        except Exception as e:
            # Non-critical, don't fail the trade
            print(f"  [OVERRIDE-CHECK] Warning: override detection failed: {e}")
        # ─────────────────────────────────────────────────────────────────────

        # TICKET-058: Get tier for position sizing limits
        tier = get_tier(ticker)

        if dry_run:
            print(f"  [DRY-RUN] Would execute: {decision} {ticker} up to ${amount:.2f} (tier: {tier})")
            result["order"] = {"action": "DRY_RUN", "decision": decision, "tier": tier}
            notify("TradingAgents [DRY-RUN]", f"{decision} {ticker}", subtitle=f"Up to ${amount:.0f}")
        else:
            order = execute_decision(ticker, decision, amount, agent_decision_text=agent_decision_text, tier=tier)
            result["order"] = order
            print(f"  [ORDER] {order}")
            action = order.get("action", decision)
            if action == "SKIPPED":
                reason = order.get("reason", "unknown")
                notify("TradingAgents — SKIPPED", f"{ticker} {decision} skipped", subtitle=reason)
            elif action == "BUY":
                qty = order.get("qty", "?")
                notify("TradingAgents — BUY", f"Bought {qty:.4f} shares of {ticker}", subtitle=f"${amount:.0f} paper trade")
            elif action == "SELL":
                qty = order.get("qty", "?")
                notify("TradingAgents — SELL", f"Sold {qty:.4f} shares of {ticker}", subtitle="Paper trade")
            elif action == "HOLD":
                notify("TradingAgents — HOLD", f"Holding {ticker}", subtitle="Keeping open position")
            elif action == "WAIT":
                notify("TradingAgents — WAIT", f"Not entering {ticker}", subtitle="No position opened")

        # ── Reflect on outcome then persist memory ───────────────────────
        try:
            returns_losses = _build_returns_losses_summary(ticker)
            if returns_losses:
                print(f"  [REFLECT] {returns_losses[:120]}...")
            else:
                # No prior P&L — seed memory with current decision context so
                # the next cycle starts with at least one entry to learn from.
                returns_losses = (
                    f"First analysis of {ticker} on {trade_date}. "
                    f"Decision: {decision}. "
                    f"No prior position held. "
                    f"Reflect on whether this decision appears correct given "
                    f"the technical and fundamental data seen today."
                )
                print(f"  [REFLECT] Seeding first-cycle memory for {ticker}")
            ta.reflect_and_remember(returns_losses)
        except Exception as ref_err:
            print(f"  [REFLECT] Warning: reflection failed: {ref_err}")

        try:
            ta.save_memories(memory_dir)
            print(f"  [MEMORY] Saved agent memories → {memory_dir}/")
        except Exception as mem_err:
            print(f"  [MEMORY] Warning: could not save memories: {mem_err}")

    except Exception as e:
        result["error"] = str(e)
        print(f"  [ERROR] {ticker}: {e}")
        notify("TradingAgents — Error", f"{ticker}: {str(e)[:80]}", subtitle="Check stderr.log")

    return result


class _WorkerStdOut:
    """Custom stdout wrapper that adds timestamps and worker ID to each line."""
    def __init__(self, worker_id: int, buffer):
        self.worker_id = worker_id
        self.buffer = buffer
        self._line_start = True

    def write(self, text: str):
        from datetime import datetime
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                self.buffer.write("\n")
                self._line_start = True
            if line or (i == len(lines) - 1 and text.endswith("\n")):
                if self._line_start and line:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.buffer.write(f"[W{self.worker_id:02d} {timestamp}] ")
                    self._line_start = False
                self.buffer.write(line)

    def flush(self):
        pass


def _analyse_ticker_worker(
    ticker: str,
    trade_date: str,
    amount: float,
    worker_id: int = 0,
) -> dict:
    """
    Worker function for parallel ticker analysis.
    Runs ONLY the analysis phase (no trade execution, no shared file writes).
    Returns all data needed for the parent process to execute the trade.
    """
    result = {
        "ticker": ticker,
        "decision": None,
        "agent_decision_text": "",
        "tier": None,
        "llm_cost": 0.0,
        "llm_tokens_in": 0,
        "llm_tokens_out": 0,
        "error": None,
        "output_lines": [],  # Capture print output
    }

    # Capture print output to return to parent with timestamps and worker ID
    import io
    import sys
    output_buffer = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = _WorkerStdOut(worker_id, output_buffer)

    try:
        from tradingagents.research_context import load_latest_research_context
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        macro_context = load_latest_research_context()
        position_context = _build_position_context(ticker)
        if not position_context:
            position_context = (
                f"NO CURRENT POSITION in {ticker}. "
                f"A SELL decision will be skipped (there is nothing to sell). "
                f"Only BUY or HOLD are actionable right now."
            )

        memory_dir = str(MEMORY_DIR / ticker)
        config = DEFAULT_CONFIG.copy()
        config["deep_think_llm"] = os.getenv("DEEP_LLM_MODEL", "gpt-4o")
        config["quick_think_llm"] = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
        config["data_vendors"] = {
            "core_stock_apis": "yfinance",
            "technical_indicators": "yfinance",
            "fundamental_data": "yfinance",
            "news_data": "yfinance",
        }
        tier = get_tier(ticker)
        config["max_debate_rounds"] = TIER_DEBATE_ROUNDS.get(tier, 1)
        config["max_risk_discuss_rounds"] = TIER_RISK_ROUNDS.get(tier, 1)

        print(f"  [LLM] deep={config['deep_think_llm']}  quick={config['quick_think_llm']}"
              f"  debate={config['max_debate_rounds']}r  risk={config['max_risk_discuss_rounds']}r")

        ta = TradingAgentsGraph(config=config)
        ta.load_memories(memory_dir)

        portfolio_context = _build_portfolio_context()

        print(f"\n[TRADINGAGENTS] Analysing {ticker} for {trade_date} ...")
        print(f"[TRADINGAGENTS] Position context: {position_context}")
        if macro_context:
            print(f"[TRADINGAGENTS] Macro context loaded ({len(macro_context)} chars)")
        if portfolio_context:
            print(f"[TRADINGAGENTS] Portfolio context: cash {portfolio_context.get('cash_ratio', 0):.0%}")

        from langchain_community.callbacks import get_openai_callback
        with get_openai_callback() as cb:
            final_state, decision = ta.propagate(
                ticker, trade_date,
                position_context=position_context,
                macro_context=macro_context,
                portfolio_context=portfolio_context,
            )

        decision = decision.strip().upper() if decision else "HOLD"
        agent_decision_text = (final_state or {}).get("final_trade_decision", "") or ""

        print(f"[TRADINGAGENTS] Decision → {decision}  |  "
              f"tokens: {cb.prompt_tokens:,} in + {cb.completion_tokens:,} out  |  "
              f"cost: ${cb.total_cost:.4f}")

        # Detect overrides (for logging, but don't log from worker)
        try:
            from tradingagents.signal_override import detect_signal_override, should_revert_override
            from tradingagents.research_context import get_ticker_research_signal

            research_signal = get_ticker_research_signal(ticker)
            override_info = detect_signal_override(
                ticker=ticker,
                investment_plan=final_state.get("investment_plan", ""),
                risk_judge_decision=agent_decision_text,
                portfolio_context=portfolio_context,
                research_signal=research_signal
            )

            if override_info:
                print(f"  [OVERRIDE] {ticker}: Risk Judge overrode Trader ({override_info['severity']})")
                if should_revert_override(override_info):
                    print(f"  [OVERRIDE-ENFORCE] Reverting {ticker} from HOLD to {override_info['upstream_signal']}")
                    decision = override_info["upstream_signal"]
                    override_info["reverted"] = True
        except Exception as e:
            print(f"  [OVERRIDE-CHECK] Warning: {e}")

        # Reflect and save memories
        try:
            returns_losses = _build_returns_losses_summary(ticker)
            if not returns_losses:
                returns_losses = (
                    f"First analysis of {ticker} on {trade_date}. "
                    f"Decision: {decision}. "
                    f"No prior position held."
                )
            ta.reflect_and_remember(returns_losses)
        except Exception as e:
            print(f"  [REFLECT] Warning: {e}")

        try:
            ta.save_memories(memory_dir)
            print(f"  [MEMORY] Saved agent memories → {memory_dir}/")
        except Exception as e:
            print(f"  [MEMORY] Warning: {e}")

        result["decision"] = decision
        result["agent_decision_text"] = agent_decision_text
        result["tier"] = tier
        result["llm_cost"] = cb.total_cost
        result["llm_tokens_in"] = cb.prompt_tokens
        result["llm_tokens_out"] = cb.completion_tokens

    except Exception as e:
        result["error"] = str(e)
        print(f"  [ERROR] {ticker}: {e}")

    finally:
        sys.stdout = original_stdout
        result["output_lines"] = output_buffer.getvalue().split("\n")

    return result


# ---------------------------------------------------------------------------
# Portfolio summary (reuse from alpaca_bridge)
# ---------------------------------------------------------------------------

def print_portfolio(trading_client):
    from alpaca_bridge import get_portfolio_summary, print_portfolio as _print
    portfolio = get_portfolio_summary()
    _print(portfolio)


def _warn_multi_run_sessions(watchlist_size: int, lookback_days: int = 7) -> None:
    """Warn if any recent trade log has more entries than 2× the watchlist size.

    This indicates a multi-run crash-resume session that may have produced
    ghost positions (positions opened under chaotic or duplicated analysis).
    """
    threshold = watchlist_size * 2
    try:
        for log_path in sorted(LOG_DIR.glob("????-??-??.json"), reverse=True)[:lookback_days]:
            if "checkpoint" in log_path.name:
                continue
            data = json.loads(log_path.read_text())
            trades = data.get("trades", [])
            if len(trades) > threshold and not data.get("multi_run_session"):
                print(
                    f"  [WARNING] {log_path.name} has {len(trades)} trade entries "
                    f"(>{threshold} = 2× watchlist). This may indicate a multi-run "
                    f"crash session. Positions opened that day may not reflect clean "
                    f"analysis. Review: {log_path}"
                )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Analysis Checkpoint System (TICKET-XXX)
# ---------------------------------------------------------------------------
# Saves expensive LLM analysis results so crashes don't lose work.
# Checkpoints are keyed by (trade_date, ticker) and stored separately from
# the execution checkpoint.

ANALYSIS_CHECKPOINT_DIR = TRADING_LOGS_DIR / "analysis_checkpoints"
ANALYSIS_CHECKPOINT_DIR.mkdir(exist_ok=True)


def _get_analysis_checkpoint_path(trade_date: str, ticker: str) -> Path:
    """Get path to analysis checkpoint file for a specific ticker/date."""
    # Use trade_date as subdirectory to allow easy cleanup of old data
    checkpoint_dir = ANALYSIS_CHECKPOINT_DIR / trade_date
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"{ticker}.json"


def _save_analysis_checkpoint(trade_date: str, ticker: str, analysis_result: dict) -> None:
    """Save analysis result to checkpoint file.

    This allows recovery of expensive LLM work if the process crashes
    between analysis and trade execution phases.
    """
    checkpoint_path = _get_analysis_checkpoint_path(trade_date, ticker)

    # Extract serializable fields (exclude output_lines which are for display)
    checkpoint_data = {
        "ticker": analysis_result["ticker"],
        "decision": analysis_result["decision"],
        "agent_decision_text": analysis_result.get("agent_decision_text", ""),
        "tier": analysis_result.get("tier"),
        "llm_cost": analysis_result.get("llm_cost", 0.0),
        "llm_tokens_in": analysis_result.get("llm_tokens_in", 0),
        "llm_tokens_out": analysis_result.get("llm_tokens_out", 0),
        "error": analysis_result.get("error"),
        "checkpointed_at": datetime.now(ET).isoformat(),
    }

    try:
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)
    except Exception as e:
        # Non-fatal: checkpoint is optimization, not required
        print(f"  [CHECKPOINT-WARN] Could not save analysis checkpoint for {ticker}: {e}")


def _load_analysis_checkpoint(trade_date: str, ticker: str) -> dict | None:
    """Load analysis result from checkpoint if it exists.

    Returns the checkpointed analysis result, or None if not found or invalid.
    """
    checkpoint_path = _get_analysis_checkpoint_path(trade_date, ticker)

    if not checkpoint_path.exists():
        return None

    try:
        with open(checkpoint_path) as f:
            data = json.load(f)

        # Validate required fields
        if data.get("ticker") != ticker:
            return None
        if "decision" not in data:
            return None

        # Reconstruct result dict with required fields
        return {
            "ticker": data["ticker"],
            "decision": data["decision"],
            "agent_decision_text": data.get("agent_decision_text", ""),
            "tier": data.get("tier"),
            "llm_cost": data.get("llm_cost", 0.0),
            "llm_tokens_in": data.get("llm_tokens_in", 0),
            "llm_tokens_out": data.get("llm_tokens_out", 0),
            "error": data.get("error"),
            "output_lines": [f"[CHECKPOINT] Restored analysis from {data.get('checkpointed_at', 'unknown')}"],
        }
    except Exception:
        # Invalid checkpoint, ignore it
        return None


def _clear_analysis_checkpoints(trade_date: str) -> None:
    """Clear all analysis checkpoints for a specific trade date.
    Called when using --force to ensure fresh analysis."""
    checkpoint_dir = ANALYSIS_CHECKPOINT_DIR / trade_date
    if checkpoint_dir.exists():
        try:
            import shutil
            shutil.rmtree(checkpoint_dir)
            print(f"  [CHECKPOINT] Cleared analysis checkpoints for {trade_date}")
        except Exception as e:
            print(f"  [CHECKPOINT-WARN] Could not clear analysis checkpoints: {e}")


# ---------------------------------------------------------------------------
# One full daily cycle
# ---------------------------------------------------------------------------

def run_daily_cycle(tickers, amount, dry_run, stop_loss, trading_client, data_client, parallel: int = 1, force: bool = False, target_deployment: float | None = None):
    # Apply dynamic watchlist overrides (adds/removes from research)
    effective_watchlist = load_watchlist_overrides()
    # tickers arg may be a custom override list — only apply dynamic changes to default list
    if set(tickers) == set(DEFAULT_TICKERS):
        tickers = list(effective_watchlist.keys())

    trade_date = get_analysis_date()
    run_date   = str(date.today())
    print_separator("=")
    print(f"  AFTER-CLOSE CYCLE — run:{run_date}  analysing:{trade_date}  ({len(tickers)} tickers)")
    print_separator("=")
    notify("TradingAgents", f"After-close cycle starting — {len(tickers)} tickers",
           subtitle=f"Analysing {trade_date}")

    # Detect multi-run contamination in recent logs — warn if any date has
    # suspiciously many entries (> 2× watchlist size suggests multiple crash-resume runs)
    _warn_multi_run_sessions(len(tickers))

    print("\n[PORTFOLIO] Start of cycle:")
    print_portfolio(trading_client)

    # ── Automated daily research ─────────────────────────────────────────────
    print_separator()
    print("  DAILY RESEARCH")
    print_separator()
    try:
        from daily_research import run_daily_research
        research_path = run_daily_research()
        if research_path:
            print(f"  [RESEARCH] Findings: {research_path}")
            # Parse watchlist changes from fresh findings and persist them
            try:
                findings_text = Path(research_path).read_text()
                changes = parse_watchlist_changes(findings_text)
                if changes["add"] or changes["remove"]:
                    save_watchlist_overrides(changes["add"], changes["remove"])
                    print(
                        f"  [RESEARCH] Watchlist changes: "
                        f"+{len(changes['add'])} adds, -{len(changes['remove'])} removes"
                    )
            except Exception as parse_err:
                print(f"  [RESEARCH] Warning: could not parse watchlist changes: {parse_err}")
        else:
            print("  [RESEARCH] Already done today — using existing findings")
    except Exception as research_err:
        print(f"  [RESEARCH] Warning: research failed ({research_err}) — agents will run without today's macro context")
    # ────────────────────────────────────────────────────────────────────────

    # ── Agent stop-loss monitor (tighter, per-trade stops) ──────────────────
    from alpaca_bridge import check_agent_stops, check_stop_losses, get_portfolio_summary
    print_separator()
    print("  AGENT STOP CHECK (per-trade stops from Risk Judge)")
    print_separator()
    agent_sl_results = check_agent_stops(log_dir=str(LOG_DIR), dry_run=dry_run)
    for sl in agent_sl_results:
        log_decision(trade_date, sl["ticker"], sl["action"], sl)

    # ── Global stop-loss monitor (portfolio-wide -15% floor) ─────────────────
    print_separator()
    print(f"  STOP-LOSS CHECK (threshold: -{stop_loss*100:.0f}%)")
    print_separator()
    sl_results = check_stop_losses(threshold=stop_loss, dry_run=dry_run)
    for sl in sl_results:
        log_decision(trade_date, sl["ticker"], sl["action"], sl)
    # ────────────────────────────────────────────────────────────────────────

    # ── TICKET-062: Time-based exit rules ───────────────────────────────────
    from alpaca_bridge import check_exit_rules
    print_separator()
    print("  EXIT RULES CHECK (profit-taking, time stops)")
    print_separator()
    exit_results = check_exit_rules(dry_run=dry_run)
    for ex in exit_results:
        log_decision(trade_date, ex["ticker"], ex["action"], ex)
    # ────────────────────────────────────────────────────────────────────────

    # ── TICKET-073: Sector exposure monitoring ──────────────────────────────
    try:
        from tradingagents.sector_monitor import check_sector_limits, format_sector_report
        print_separator()
        print("  SECTOR EXPOSURE CHECK")
        print_separator()
        print(format_sector_report())
        sector_warnings = check_sector_limits(max_pct=0.40)
        for w in sector_warnings:
            if "exceeds" in w.lower():
                print(f"  {w}")
    except Exception as e:
        print(f"  [SECTOR] Warning: sector check failed: {e}")
    # ────────────────────────────────────────────────────────────────────────

    # ── Portfolio limits snapshot ─────────────────────────────────────────────
    # Pre-load portfolio state once; refreshed live in execute_decision for each BUY.
    # Used to enforce max-position guard without querying Alpaca 34 times.
    # TICKET-063: Dynamic position limits based on cash deployment
    # TICKET-078: Target deployment percentage support
    from tradingagents.default_config import get_dynamic_max_positions
    from tradingagents.deployment_config import get_target_deployment_pct
    
    # Load target deployment (from CLI arg or config file)
    target_deployment_pct = target_deployment
    if target_deployment_pct is None:
        target_deployment_pct = get_target_deployment_pct()
    
    try:
        _portfolio_snapshot = get_portfolio_summary()
        _open_positions_count = len(_portfolio_snapshot.get("positions", []))
        _cash_ratio = _portfolio_snapshot.get("cash", 0) / max(_portfolio_snapshot.get("equity", 1), 1)
        MAX_OPEN_POSITIONS = get_dynamic_max_positions(_cash_ratio, target_deployment_pct)
        print(f"  [DEPLOYMENT] Target: {target_deployment_pct:.0%}, Current cash: {_cash_ratio:.1%}, Max positions: {MAX_OPEN_POSITIONS}")
    except Exception:
        _portfolio_snapshot = {}
        _open_positions_count = 0
        _cash_ratio = 1.0
        MAX_OPEN_POSITIONS = 28  # Default to max when we can't determine
    # ─────────────────────────────────────────────────────────────────────────

    results = []
    cycle_tokens_in  = 0
    cycle_tokens_out = 0
    cycle_cost       = 0.0

    # Checkpoint — track completed tickers so a restart doesn't re-run them.
    # The checkpoint file lives alongside the daily trade log and is keyed to
    # the analysis date so a new calendar day automatically starts fresh.
    checkpoint_path = LOG_DIR / f"{trade_date}.checkpoint.json"
    completed_tickers: set[str] = set()

    if force:
        print(f"  [CHECKPOINT] --force flag set — ignoring checkpoint, will re-analyze all tickers")
        if checkpoint_path.exists():
            try:
                checkpoint_path.unlink()
                print(f"  [CHECKPOINT] Deleted existing checkpoint: {checkpoint_path}")
            except Exception as e:
                print(f"  [CHECKPOINT] Warning: Could not delete checkpoint: {e}")
    elif checkpoint_path.exists():
        try:
            completed_tickers = set(json.loads(checkpoint_path.read_text()).get("completed", []))
            if completed_tickers:
                print(f"  [CHECKPOINT] {len(completed_tickers)} tickers already done today — skipping: {', '.join(sorted(completed_tickers))}")
        except Exception:
            pass

    # Filter out already completed tickers
    pending_tickers = [t for t in tickers if t not in completed_tickers]
    if len(pending_tickers) < len(tickers) and not force:
        skipped = [t for t in tickers if t in completed_tickers]
        print(f"  [CHECKPOINT] Skipping {len(skipped)} already completed: {', '.join(sorted(skipped))}")

    # TICKET-XXX: Check for analysis checkpoints (recover from crash between analysis and execution)
    analysis_results = []
    tickers_to_analyze = []
    
    if force:
        # Clear all analysis checkpoints when forcing re-run
        _clear_analysis_checkpoints(trade_date)
        tickers_to_analyze = pending_tickers
    else:
        for ticker in pending_tickers:
            checkpointed = _load_analysis_checkpoint(trade_date, ticker)
            if checkpointed:
                analysis_results.append(checkpointed)
                print(f"  [CHECKPOINT] Restored analysis for {ticker} → {checkpointed['decision']}")
            else:
                tickers_to_analyze.append(ticker)
        
        if analysis_results:
            print(f"  [CHECKPOINT] Restored {len(analysis_results)} analysis results from checkpoint")
        if tickers_to_analyze:
            print(f"  [CHECKPOINT] Need to analyze {len(tickers_to_analyze)} tickers")

    # PHASE 1: Analyze tickers (parallel or sequential)
    if parallel > 1 and len(tickers_to_analyze) > 1:
        print(f"\n  [PARALLEL] Analyzing {len(pending_tickers)} tickers with {parallel} workers...\n")

        with concurrent.futures.ProcessPoolExecutor(max_workers=parallel) as executor:
            # Submit all analysis tasks with worker IDs
            future_to_ticker = {}
            for idx, ticker in enumerate(pending_tickers):
                worker_id = (idx % parallel) + 1  # Assign worker ID 1-N
                future = executor.submit(_analyse_ticker_worker, ticker, trade_date, tier_amount(amount, ticker), worker_id)
                future_to_ticker[future] = ticker

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    worker_result = future.result(timeout=600)  # 10 min timeout per ticker
                    analysis_results.append(worker_result)

                    # TICKET-XXX: Save analysis checkpoint immediately
                    _save_analysis_checkpoint(trade_date, ticker, worker_result)

                    # Print captured output from worker
                    for line in worker_result.get("output_lines", []):
                        if line.strip():
                            print(line)

                except concurrent.futures.TimeoutError:
                    print(f"  [TIMEOUT] {ticker}: Analysis timed out after 10 minutes")
                    error_result = {
                        "ticker": ticker,
                        "decision": "ERROR",
                        "error": "Analysis timeout",
                        "output_lines": [],
                    }
                    analysis_results.append(error_result)
                    _save_analysis_checkpoint(trade_date, ticker, error_result)
                except Exception as e:
                    print(f"  [ERROR] {ticker}: Worker failed — {e}")
                    error_result = {
                        "ticker": ticker,
                        "decision": "ERROR",
                        "error": str(e),
                        "output_lines": [],
                    }
                    analysis_results.append(error_result)
                    _save_analysis_checkpoint(trade_date, ticker, error_result)
    else:
        # Sequential mode (original behavior)
        for ticker in tickers_to_analyze:
            sector = get_sector(ticker)
            trade_amt = tier_amount(amount, ticker)
            print_separator()
            print(f"  [{len(analysis_results)+1}/{len(pending_tickers)}] {ticker}  {f'({sector})' if sector else ''}  [${trade_amt:.0f}]")
            print_separator()

            result = analyse_and_trade(
                ticker, trade_date, trade_amt, dry_run,
                max_open_positions=MAX_OPEN_POSITIONS,
                current_open_positions=_open_positions_count,
            )
            analysis_result = {
                "ticker": ticker,
                "decision": result.get("decision"),
                "agent_decision_text": result.get("order", {}).get("agent_decision_text", ""),
                "tier": get_tier(ticker),
                "llm_cost": result.get("llm_cost", 0),
                "llm_tokens_in": result.get("llm_tokens_in", 0),
                "llm_tokens_out": result.get("llm_tokens_out", 0),
                "error": result.get("error"),
                "_full_result": result,
            }
            analysis_results.append(analysis_result)
            
            # TICKET-XXX: Save analysis checkpoint after each sequential analysis
            _save_analysis_checkpoint(trade_date, ticker, analysis_result)

    # PHASE 2: Execute trades (always sequential to avoid race conditions)
    print(f"\n  [EXECUTION] Executing {len(analysis_results)} trades sequentially...\n")

    for i, analysis in enumerate(analysis_results, 1):
        ticker = analysis["ticker"]
        decision = analysis.get("decision", "HOLD")
        trade_amt = tier_amount(amount, ticker)

        print_separator()
        print(f"  [{i}/{len(analysis_results)}] Executing: {ticker} → {decision}")
        print_separator()

        # Skip if analysis failed
        if analysis.get("error"):
            print(f"  [SKIP] {ticker}: Analysis failed — {analysis['error']}")
            result = {"ticker": ticker, "decision": "ERROR", "order": None, "error": analysis["error"]}
        else:
            # Portfolio position-limit guard (re-check live before each trade)
            if decision == "BUY" and not dry_run:
                try:
                    live_portfolio = get_portfolio_summary()
                    live_positions = len(live_portfolio.get("positions", []))
                    if live_positions >= MAX_OPEN_POSITIONS:
                        cash_pct = live_portfolio.get("cash", 0) / max(live_portfolio.get("equity", 1), 1) * 100
                        print(f"  [RISK] Portfolio at max ({live_positions}/{MAX_OPEN_POSITIONS}) — downgrading BUY to HOLD")
                        decision = "HOLD"
                except Exception:
                    pass

            # Execute the trade
            if dry_run:
                print(f"  [DRY-RUN] Would execute: {decision} {ticker} up to ${trade_amt:.2f}")
                result = {
                    "ticker": ticker,
                    "decision": decision,
                    "order": {"action": "DRY_RUN", "decision": decision, "tier": analysis.get("tier")},
                    "error": None,
                    "llm_cost": analysis.get("llm_cost", 0),
                    "llm_tokens_in": analysis.get("llm_tokens_in", 0),
                    "llm_tokens_out": analysis.get("llm_tokens_out", 0),
                }
            else:
                from alpaca_bridge import execute_decision
                try:
                    order = execute_decision(
                        ticker, decision, trade_amt,
                        agent_decision_text=analysis.get("agent_decision_text", ""),
                        tier=analysis.get("tier")
                    )
                    print(f"  [ORDER] {order}")
                    result = {
                        "ticker": ticker,
                        "decision": decision,
                        "order": order,
                        "error": None,
                        "llm_cost": analysis.get("llm_cost", 0),
                        "llm_tokens_in": analysis.get("llm_tokens_in", 0),
                        "llm_tokens_out": analysis.get("llm_tokens_out", 0),
                    }
                except Exception as e:
                    print(f"  [ERROR] Trade execution failed: {e}")
                    result = {
                        "ticker": ticker,
                        "decision": decision,
                        "order": None,
                        "error": str(e),
                        "llm_cost": analysis.get("llm_cost", 0),
                        "llm_tokens_in": analysis.get("llm_tokens_in", 0),
                        "llm_tokens_out": analysis.get("llm_tokens_out", 0),
                    }

        results.append(result)

        # Log the decision
        logged_decision = result["decision"] if result["decision"] else "ERROR"
        logged_order = result["order"] if result["order"] else {"action": "ERROR", "reason": str(result.get("error", "unknown"))}
        log_decision(trade_date, ticker, logged_decision, logged_order)

        cycle_tokens_in += result.get("llm_tokens_in", 0)
        cycle_tokens_out += result.get("llm_tokens_out", 0)
        cycle_cost += result.get("llm_cost", 0.0)

        # Update checkpoint after each trade
        completed_tickers.add(ticker)
        try:
            checkpoint_path.write_text(json.dumps({"completed": sorted(completed_tickers), "trade_date": trade_date}))
        except Exception:
            pass

        # Brief pause between executions
        if i < len(analysis_results):
            time.sleep(1)

    # Summary
    print_separator("=")
    print(f"  CYCLE SUMMARY — analysed:{trade_date}")
    print_separator("=")
    buys   = [r["ticker"] for r in results if r["decision"] == "BUY"]
    sells  = [r["ticker"] for r in results if r["decision"] == "SELL"]
    # HOLD = kept an existing position; WAIT = no position, not entering
    holds  = [r["ticker"] for r in results
              if r["decision"] == "HOLD" and (r.get("order") or {}).get("action") == "HOLD"]
    waits  = [r["ticker"] for r in results
              if r["decision"] == "HOLD" and (r.get("order") or {}).get("action") == "WAIT"]
    errors = [r["ticker"] for r in results if r["error"]]

    def with_sector(tickers):
        return ", ".join(f"{t}({get_sector(t)[:3] or '?'})" for t in tickers) or "none"

    print(f"  BUY  ({len(buys)}):   {with_sector(buys)}")
    print(f"  SELL ({len(sells)}):  {with_sector(sells)}")
    print(f"  HOLD ({len(holds)}):  {with_sector(holds)}")
    print(f"  WAIT ({len(waits)}):  {with_sector(waits)}  ← no position, not entering")
    if errors:
        print(f"  ERRORS ({len(errors)}): {', '.join(errors)}")

    print()
    print_separator()
    print("  AI COST THIS CYCLE")
    print_separator()
    print(f"  Tokens  : {cycle_tokens_in:,} in  +  {cycle_tokens_out:,} out  =  {cycle_tokens_in+cycle_tokens_out:,} total")
    print(f"  Cost    : ${cycle_cost:.4f}  (${cycle_cost*365:.2f} projected/year at 1 cycle/day)")
    print(f"  Per ticker: ${cycle_cost/len(tickers):.4f} avg")
    print()

    summary_msg = f"BUY {len(buys)}  SELL {len(sells)}  HOLD {len(holds)}  WAIT {len(waits)}"
    if errors:
        summary_msg += f"  Errors {len(errors)}"
        notify("TradingAgents — Cycle Done", summary_msg, subtitle=f"{trade_date} — check logs")
    else:
        notify("TradingAgents — Cycle Done", summary_msg, subtitle=trade_date)

    # TICKET-072: Check BUY quota and ENFORCE if missed
    try:
        from tradingagents.buy_quota import check_buy_quota, get_force_buy_tickers
        from tradingagents.research_context import parse_research_signals

        research_file = RESULTS_DIR / f"RESEARCH_FINDINGS_{trade_date}.md"
        if research_file.exists():
            research_text = research_file.read_text()
            research_signals = parse_research_signals(research_text)

            quota_report = check_buy_quota(
                tickers=tickers,
                results=results,
                research_signals=research_signals,
                cash_ratio=_cash_ratio if '_cash_ratio' in locals() else 0.5,
                target_deployment_pct=target_deployment_pct
            )

            # ENFORCEMENT: Force-buy highest conviction missed opportunities
            force_tickers = get_force_buy_tickers(quota_report)
            if force_tickers and not dry_run:
                print_separator()
                print(f"  QUOTA ENFORCEMENT — force-buying {len(force_tickers)} missed opportunities")
                print_separator()
                from alpaca_bridge import execute_decision as _exec_decision
                for ft in force_tickers:
                    ft_amount = tier_amount(amount, ft)
                    tier = get_tier(ft)
                    print(f"  [QUOTA-FORCE] BUY {ft} (${ft_amount:.0f}, tier={tier})")
                    try:
                        order = _exec_decision(ft, "BUY", ft_amount, tier=tier)
                        log_decision(trade_date, ft, "BUY", {**order, "source": "quota_enforcement"})
                        results.append({"ticker": ft, "decision": "BUY", "order": order, "error": None})
                        print(f"  [QUOTA-FORCE] {ft}: {order}")
                    except Exception as fe:
                        print(f"  [QUOTA-FORCE] {ft}: Failed — {fe}")
    except Exception as e:
        print(f"  [QUOTA-CHECK] Warning: quota check failed: {e}")

    print("[PORTFOLIO] End of cycle:")
    print_portfolio(trading_client)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Daily TradingAgents loop on Alpaca paper account.")
    parser.add_argument("--amount",    type=float, default=1000.0,  help="USD per trade (default: 1000)")
    parser.add_argument("--dry-run",   action="store_true",          help="Analyse only, no orders")
    parser.add_argument("--once",      action="store_true",          help="Run one cycle then exit")
    parser.add_argument("--no-wait",   action="store_true",          help="Skip market-hours check and run immediately")
    parser.add_argument("--tickers",   nargs="+",                    help="Override ticker list")
    parser.add_argument("--stop-loss", type=float, default=0.15,    help="Stop-loss threshold fraction (default: 0.15 = -15%%)")
    parser.add_argument("--from",      dest="from_ticker", metavar="TICKER",
                        help="Resume cycle from a specific ticker (skips all tickers before it)")
    parser.add_argument("--parallel",  type=int,   default=1,       help="Number of parallel workers for analysis (default: 1, max: 4)")
    parser.add_argument("--force",     action="store_true",          help="Ignore checkpoint and re-analyze all tickers")
    parser.add_argument("--target-deployment", type=float, default=None,
                        help="Target deployment percentage 0.10-0.95 (default: load from config)")
    args = parser.parse_args()

    tickers = args.tickers if args.tickers else DEFAULT_TICKERS

    # --from: skip all tickers before the specified one
    if args.from_ticker:
        from_upper = args.from_ticker.upper()
        if from_upper not in tickers:
            print(f"[ERROR] --from ticker '{from_upper}' not found in watchlist.")
            print(f"  Valid tickers: {', '.join(tickers)}")
            raise SystemExit(1)
        start_idx = tickers.index(from_upper)
        skipped   = tickers[:start_idx]
        tickers   = tickers[start_idx:]
        print(f"  [RESUME] Starting from {from_upper} — skipping {len(skipped)} tickers: {', '.join(skipped)}")

    # Initialise Alpaca clients once (reuse across cycles)
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient

    ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
    ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise EnvironmentError(
            "Missing ALPACA_API_KEY or ALPACA_API_SECRET. "
            "Add them to your .env file. See .env.example."
        )

    trading_client = TradingClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_API_SECRET, paper=True)
    data_client    = StockHistoricalDataClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_API_SECRET)

    ticker_list = "\n    ".join(
        f"{t:<6} — {get_sector(t) or 'custom'}  [{get_tier(t)}  ${tier_amount(args.amount, t):.0f}]"
        for t in tickers
    )
    from zoneinfo import ZoneInfo as _ZI
    run_et  = datetime.now(ET).replace(hour=_RUN_HOUR, minute=_RUN_MIN, second=0, microsecond=0)
    run_utc = run_et.astimezone(_ZI("UTC"))

    print(f"\n  TradingAgents Daily Loop")
    print(f"  Tickers ({len(tickers)}):\n    {ticker_list}")
    print(f"  Amount : ${args.amount:.0f}/trade")
    print(f"  Timing : runs once daily at {_RUN_HOUR:02d}:{_RUN_MIN:02d} ET / {run_utc.strftime('%H:%M UTC')}, analyses previous day's data")
    if args.dry_run:
        print("  [DRY-RUN MODE — no real orders will be placed]")
    print()
    notify("TradingAgents", f"Agent started — {len(tickers)} tickers, ${args.amount:.0f}/trade",
           subtitle="DRY-RUN" if args.dry_run else f"Runs daily at {_RUN_HOUR:02d}:{_RUN_MIN:02d} ET")

    def wait_until_next_run(label=""):
        """Sleep until the next daily run time, printing countdown and syncing positions periodically."""
        last_position_sync = 0
        while True:
            secs = seconds_until_next_run()
            if secs <= 0:
                break
            wake     = datetime.now(ET) + timedelta(seconds=secs)
            wake_utc = wake.astimezone(_ZI("UTC"))
            h, rem   = divmod(secs, 3600)
            m        = rem // 60
            print(f"[WAIT]{' ' + label if label else ''} "
                  f"Next cycle at {wake.strftime('%Y-%m-%d %H:%M ET')} "
                  f"/ {wake_utc.strftime('%H:%M UTC')} "
                  f"— {h}h {m:02d}m remaining")
            
            # Sync positions every 5 minutes (300 seconds) to keep dashboard fresh
            now = time.time()
            if now - last_position_sync >= 300:
                try:
                    from update_positions import fetch_positions, save_positions
                    data = fetch_positions()
                    save_positions(data)
                    print("  [SYNC] Positions updated from Alpaca")
                    last_position_sync = now
                except Exception as e:
                    print(f"  [SYNC] Warning: position sync failed: {e}")
            
            time.sleep(min(60, secs))

    cycle = 0
    while True:
        cycle += 1

        if not args.no_wait:
            secs = seconds_until_next_run()
            if secs > 0:
                wake = datetime.now(ET) + timedelta(seconds=secs)
                notify("TradingAgents", f"Waiting — next run at {wake.strftime('%a %H:%M ET')}",
                       subtitle="One run per day")
                wait_until_next_run()

        # Cap parallel workers for safety
        parallel_workers = min(max(args.parallel, 1), 4)
        if parallel_workers > 1:
            print(f"  [PARALLEL MODE] Using {parallel_workers} workers for analysis phase")

        run_daily_cycle(tickers, args.amount, args.dry_run, args.stop_loss, trading_client, data_client, parallel=parallel_workers, force=args.force, target_deployment=args.target_deployment)

        # TICKET-066: Monthly tier review (run on first trading day of month)
        if datetime.now(ET).day <= 5 and not args.dry_run:
            try:
                from tier_manager import run_monthly_review
                run_monthly_review(dry_run=True)  # Log recommendations, don't auto-apply
            except Exception as e:
                print(f"[TIER_REVIEW] Warning: tier review failed: {e}")

        if args.once:
            print("  [--once] Done.")
            break

        # Wait until tomorrow's run time
        secs = seconds_until_next_run()
        wake = datetime.now(ET) + timedelta(seconds=secs)
        notify("TradingAgents — Cycle Done", f"Next run: {wake.strftime('%a %H:%M ET')}",
               subtitle=f"Cycle {cycle} complete")
        wait_until_next_run(label=f"Cycle {cycle} complete.")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Analysis Checkpoint System (TICKET-XXX)

