"""
trading_loop.py
===============
Runs TradingAgents analysis on a curated macro-aware watchlist after market
close each day, executing paper trades on Alpaca.

Strategy:
  - Runs at 4:15 PM ET after market close using YESTERDAY's completed data
  - 20 tickers chosen for the current macro environment:
      AI boom, hiring freezes, US/Iran tensions, rising oil, news-driven volatility
  - $1000 equal weight per ticker
  - Holds positions across days (not flipped daily)

Ticker rationale:
  AI & Semiconductors  — direct beneficiaries of AI capex boom
  Defense              — US/Iran tensions, increased defense budgets
  Energy               — rising oil prices, geopolitical risk premium
  Cybersecurity        — AI-era attack surface expanding
  Gold/Macro hedge     — safe haven in volatile geopolitical environment
  Productivity SaaS    — benefits from hiring freezes (do more with less)

Usage:
  python trading_loop.py                        # run forever
  python trading_loop.py --amount 500           # $500 per trade
  python trading_loop.py --dry-run              # analyse only, no orders
  python trading_loop.py --once                 # run one cycle then exit
  python trading_loop.py --tickers AAPL MSFT    # override ticker list
  python trading_loop.py --no-wait              # skip wait, run immediately
"""

# ---------------------------------------------------------------------------

import argparse
import json
import logging
import os
import requests
import time
import urllib3
import warnings
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
# Project root — all paths are anchored here so the loop works regardless
# of the working directory the process is started from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
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
_OVERRIDES_FILE = PROJECT_ROOT / "trading_loop_logs" / "watchlist_overrides.json"


def load_watchlist_overrides() -> dict:
    """
    Merge static WATCHLIST with persisted overrides from research findings.

    Returns a dict in the same format as WATCHLIST with any ADD/REMOVE
    changes applied. The static WATCHLIST is never mutated.
    """
    effective = dict(WATCHLIST)
    if not _OVERRIDES_FILE.exists():
        return effective
    try:
        overrides = json.loads(_OVERRIDES_FILE.read_text())
        added   = overrides.get("add", {})
        removed = overrides.get("remove", [])
        for ticker, info in added.items():
            if ticker not in effective:
                effective[ticker] = info
                print(f"  [WATCHLIST] +{ticker} (from research override: {info.get('note','')})")
        for ticker in removed:
            if ticker in effective:
                effective.pop(ticker)
                print(f"  [WATCHLIST] -{ticker} (removed by research override)")
    except Exception as e:
        print(f"  [WATCHLIST] Warning: could not load overrides: {e}")
    return effective


def save_watchlist_overrides(adds: dict, removes: list) -> None:
    """Persist watchlist ADD/REMOVE decisions to disk."""
    _OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Merge with existing overrides rather than overwriting
    existing = {}
    if _OVERRIDES_FILE.exists():
        try:
            existing = json.loads(_OVERRIDES_FILE.read_text())
        except Exception:
            pass
    merged_adds   = {**existing.get("add", {}), **adds}
    merged_removes = list(set(existing.get("remove", []) + removes))
    # Clean up: don't keep a ticker in both add and remove
    for t in list(merged_adds.keys()):
        if t in merged_removes:
            merged_removes.remove(t)
    _OVERRIDES_FILE.write_text(json.dumps(
        {"add": merged_adds, "remove": merged_removes}, indent=2
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
    r = requests.get(
        "https://paper-api.alpaca.markets/v2/clock",
        headers={
            "APCA-API-KEY-ID":     ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        },
        timeout=10,
        verify=False,   # paper-api.alpaca.markets CA cert has key usage extension issue
    )
    r.raise_for_status()
    return r.json()


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


def seconds_until_after_close() -> int:
    """
    Return seconds until 4:15 PM ET today (15 min after market close).
    If it's already past 4:15 PM today, return seconds until 4:15 PM
    on the next trading day (via next_close from Alpaca clock).
    """
    clock = get_market_clock()
    now = datetime.now(ET)

    # Build today's 4:15 PM ET target
    target = now.replace(hour=16, minute=15, second=0, microsecond=0)

    if now < target and not clock["is_open"] and now.hour < 9:
        # It's early morning before open — run today after close
        pass
    elif now >= target:
        # Already past 4:15 PM today — aim for next trading day's close
        next_close_str = clock["next_close"]
        next_close = datetime.fromisoformat(next_close_str)
        target = next_close.astimezone(ET).replace(
            hour=16, minute=15, second=0, microsecond=0
        )
        # If next_close is today (shouldn't happen but guard anyway)
        if target <= now:
            target += timedelta(days=1)

    return max(0, int((target - now).total_seconds()))


_AFTER_CLOSE_HOUR = 16   # 4 PM ET
_AFTER_CLOSE_MIN  = 15   # 4:15 PM ET — market close + 15 min


def get_analysis_date() -> str:
    """
    Return the most recent completed trading session date.

    After 4:15 PM ET on a weekday, today's session is complete — use today.
    Before 4:15 PM ET, today's session is still open — use previous session.
    Weekends always use the most recent Friday.

    Examples (all run from ET timezone):
      Tue 17:00  → "2026-03-24"  (today, session closed)
      Tue 09:00  → "2026-03-23"  (yesterday, today still open)
      Mon 17:00  → "2026-03-23"  (today Monday, session closed)
      Mon 09:00  → "2026-03-20"  (Friday, Monday not yet closed)
      Sat any    → "2026-03-21"  (Friday)
      Sun any    → "2026-03-21"  (Friday)
    """
    ET      = ZoneInfo("America/New_York")
    now_et  = datetime.now(ET)
    today   = now_et.date()
    weekday = today.weekday()  # 0=Mon … 4=Fri, 5=Sat, 6=Sun

    after_close = (
        now_et.hour > _AFTER_CLOSE_HOUR or
        (now_et.hour == _AFTER_CLOSE_HOUR and now_et.minute >= _AFTER_CLOSE_MIN)
    )

    # Weekend → most recent Friday
    if weekday == 5:   # Saturday
        return str(today - timedelta(days=1))
    if weekday == 6:   # Sunday
        return str(today - timedelta(days=2))

    # Weekday before close → previous trading day
    if not after_close:
        if weekday == 0:   # Monday before close → Friday
            return str(today - timedelta(days=3))
        return str(today - timedelta(days=1))

    # Weekday after close → today's completed session
    return str(today)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = PROJECT_ROOT / "trading_loop_logs"
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
        logs = sorted((PROJECT_ROOT / "trading_loop_logs").glob("????-??-??.json"), reverse=True)
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


def analyse_and_trade(
    ticker: str,
    trade_date: str,
    amount: float,
    dry_run: bool,
) -> dict:
    """
    Run TradingAgents on one ticker and execute on Alpaca.
    Returns a result dict. Never raises — errors are caught and returned.
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

        # Build TradingAgentsGraph once per ticker so we can persist memories
        memory_dir = str(PROJECT_ROOT / "trading_loop_logs" / "memory" / ticker)
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

        print(f"\n[TRADINGAGENTS] Analysing {ticker} for {trade_date} ...")
        if position_context:
            print(f"[TRADINGAGENTS] Position context: {position_context}")
        if macro_context:
            print(f"[TRADINGAGENTS] Macro context loaded ({len(macro_context)} chars)")

        from langchain_community.callbacks import get_openai_callback
        with get_openai_callback() as cb:
            _, decision = ta.propagate(
                ticker, trade_date,
                position_context=position_context,
                macro_context=macro_context,
            )

        decision = decision.strip().upper() if decision else "HOLD"
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

        if dry_run:
            print(f"  [DRY-RUN] Would execute: {decision} {ticker} up to ${amount:.2f}")
            result["order"] = {"action": "DRY_RUN", "decision": decision}
            notify("TradingAgents [DRY-RUN]", f"{decision} {ticker}", subtitle=f"Up to ${amount:.0f}")
        else:
            order = execute_decision(ticker, decision, amount)
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
                notify("TradingAgents — HOLD", f"Holding {ticker}", subtitle="No order placed")

        # ── Reflect on outcome then persist memory ───────────────────────
        try:
            returns_losses = _build_returns_losses_summary(ticker)
            if returns_losses:
                print(f"  [REFLECT] {returns_losses[:120]}...")
                ta.reflect_and_remember(returns_losses)
            else:
                print(f"  [REFLECT] No prior P&L data for {ticker} — skipping reflection")
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


# ---------------------------------------------------------------------------
# Portfolio summary (reuse from alpaca_bridge)
# ---------------------------------------------------------------------------

def print_portfolio(trading_client):
    from alpaca_bridge import get_portfolio_summary, print_portfolio as _print
    portfolio = get_portfolio_summary()
    _print(portfolio)


# ---------------------------------------------------------------------------
# One full daily cycle
# ---------------------------------------------------------------------------

def run_daily_cycle(tickers, amount, dry_run, stop_loss, trading_client, data_client):
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

    # ── Stop-loss monitor ────────────────────────────────────────────────────
    from alpaca_bridge import check_stop_losses
    print_separator()
    print(f"  STOP-LOSS CHECK (threshold: -{stop_loss*100:.0f}%)")
    print_separator()
    sl_results = check_stop_losses(threshold=stop_loss, dry_run=dry_run)
    for sl in sl_results:
        log_decision(trade_date, sl["ticker"], sl["action"], sl)
    # ────────────────────────────────────────────────────────────────────────

    results = []
    cycle_tokens_in  = 0
    cycle_tokens_out = 0
    cycle_cost       = 0.0

    for i, ticker in enumerate(tickers, 1):
        sector    = get_sector(ticker)
        trade_amt = tier_amount(amount, ticker)
        print_separator()
        print(f"  [{i}/{len(tickers)}] {ticker}  {f'({sector})' if sector else ''}  [${trade_amt:.0f}]")
        print_separator()

        result = analyse_and_trade(ticker, trade_date, trade_amt, dry_run)
        results.append(result)
        # Use "ERROR" as decision when the ticker failed so log has no null fields
        logged_decision = result["decision"] if result["decision"] else "ERROR"
        logged_order    = result["order"] if result["order"] else {"action": "ERROR", "reason": str(result.get("error", "unknown"))}
        log_decision(trade_date, ticker, logged_decision, logged_order)
        cycle_tokens_in  += result.get("llm_tokens_in", 0)
        cycle_tokens_out += result.get("llm_tokens_out", 0)
        cycle_cost       += result.get("llm_cost", 0.0)

        # Brief pause between tickers to avoid rate limiting
        if i < len(tickers):
            time.sleep(3)

    # Summary
    print_separator("=")
    print(f"  CYCLE SUMMARY — analysed:{trade_date}")
    print_separator("=")
    buys   = [r["ticker"] for r in results if r["decision"] == "BUY"]
    sells  = [r["ticker"] for r in results if r["decision"] == "SELL"]
    holds  = [r["ticker"] for r in results if r["decision"] == "HOLD"]
    errors = [r["ticker"] for r in results if r["error"]]

    def with_sector(tickers):
        return ", ".join(f"{t}({get_sector(t)[:3] or '?'})" for t in tickers) or "none"

    print(f"  BUY  ({len(buys)}):   {with_sector(buys)}")
    print(f"  SELL ({len(sells)}):  {with_sector(sells)}")
    print(f"  HOLD ({len(holds)}):  {with_sector(holds)}")
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

    summary_msg = f"BUY {len(buys)}  SELL {len(sells)}  HOLD {len(holds)}"
    if errors:
        summary_msg += f"  Errors {len(errors)}"
        notify("TradingAgents — Cycle Done", summary_msg, subtitle=f"{trade_date} — check logs")
    else:
        notify("TradingAgents — Cycle Done", summary_msg, subtitle=trade_date)

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
    print(f"\n  TradingAgents After-Close Loop")
    print(f"  Tickers ({len(tickers)}):\n    {ticker_list}")
    print(f"  Amount : ${args.amount:.0f}/trade")
    from zoneinfo import ZoneInfo
    from datetime import datetime
    et_time  = datetime.now(ET).replace(hour=16, minute=15, second=0, microsecond=0)
    utc_time = et_time.astimezone(ZoneInfo("UTC"))
    print(f"  Timing : runs daily at 4:15 PM ET / {utc_time.strftime('%H:%M UTC')}, analyses previous day's data")
    if args.dry_run:
        print("  [DRY-RUN MODE — no real orders will be placed]")
    print()
    notify("TradingAgents", f"Agent started — {len(tickers)} tickers, ${args.amount:.0f}/trade",
           subtitle="DRY-RUN" if args.dry_run else "Runs after market close daily")

    def wait_until_after_close(label=""):
        """Sleep until 4:15 PM ET, printing a live countdown every 60 seconds."""
        while True:
            secs = seconds_until_after_close()
            if secs <= 0:
                break
            wake     = datetime.now(ET) + timedelta(seconds=secs)
            wake_utc = wake.astimezone(ZoneInfo("UTC"))
            h, rem   = divmod(secs, 3600)
            m        = rem // 60
            print(f"[WAIT]{' ' + label if label else ''} "
                  f"Next cycle at {wake.strftime('%Y-%m-%d %H:%M ET')} "
                  f"/ {wake_utc.strftime('%H:%M UTC')} "
                  f"— {h}h {m:02d}m remaining")
            time.sleep(min(60, secs))

    cycle = 0
    while True:
        cycle += 1

        if not args.no_wait:
            secs = seconds_until_after_close()
            if secs > 0:
                wake = datetime.now(ET) + timedelta(seconds=secs)
                notify("TradingAgents", "Waiting for market close",
                       subtitle=f"Next run: {wake.strftime('%Y-%m-%d %H:%M ET')}")
                wait_until_after_close()

        run_daily_cycle(tickers, args.amount, args.dry_run, args.stop_loss, trading_client, data_client)

        if args.once:
            print("  [--once] Done.")
            break

        # Wait until next after-close window
        secs = seconds_until_after_close()
        wake = datetime.now(ET) + timedelta(seconds=secs)
        notify("TradingAgents — Cycle Done", f"Next run: {wake.strftime('%a %H:%M ET')}",
               subtitle=f"Cycle {cycle} complete")
        wait_until_after_close(label=f"Cycle {cycle} complete.")


if __name__ == "__main__":
    main()
