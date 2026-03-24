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

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Patch requests/urllib3 SSL (corporate proxy workaround)
import requests
from requests.adapters import HTTPAdapter
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NoVerifyAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

_orig_session_init = requests.Session.__init__
def _patched_session_init(self, *args, **kwargs):
    _orig_session_init(self, *args, **kwargs)
    self.verify = False
    self.mount("https://", NoVerifyAdapter())
requests.Session.__init__ = _patched_session_init

# ---------------------------------------------------------------------------

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
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
# Curated watchlist — updated March 24, 2026
#
# Macro themes:
#   - AI capex supercycle (semiconductors, photonics, memory, networking)
#   - Hiring freezes → productivity & agentic AI software wins
#   - US/Iran tensions → defense, cybersecurity, satellite intel
#   - LNG structural demand (Europe/Asia energy diversification, multi-year)
#   - Iran de-escalation risk → reduced pure oil exposure, kept LNG
#   - Copper & rare earths = physical backbone of AI + defense buildout
#   - News/social-driven volatility → liquid large-caps where possible
#
# Research sources: Seeking Alpha, Yahoo Finance, CERAWeek (March 23, 2026)
# Key analyst calls: Morgan Stanley (BIP, LNG, VG), BNP Paribas (LITE),
#   Wedbush (MU, PLTR), Mizuho (MDB), Citi (UBER), Jefferies (OKE)
# ---------------------------------------------------------------------------

WATCHLIST = {
    # AI & Semiconductors — core AI infrastructure
    "NVDA":  "AI & Semiconductors",   # GPU monopoly for AI training
    "AVGO":  "AI & Semiconductors",   # custom AI chips, networking ASICs
    "AMD":   "AI & Semiconductors",   # GPU #2, datacenter CPUs
    "ARM":   "AI & Semiconductors",   # CPU architecture licensing, edge AI
    "TSM":   "AI & Semiconductors",   # fabricates all leading-edge chips (ADR)
    "MU":    "AI & Semiconductors",   # Wedbush: AI memory prices up 100%+
    "LITE":  "AI Photonics",          # BNP PT $1000; Nvidia/Google transceiver wins

    # AI Software & Cloud — platforms capturing AI spend
    "MSFT":  "AI Software & Cloud",   # Azure + OpenAI partnership
    "GOOGL": "AI Software & Cloud",   # Gemini, TPUs, cloud
    "META":  "AI Software & Cloud",   # massive AI infra spend, ad targeting
    "PLTR":  "AI Software & Cloud",   # Wedbush: Maven AI federal program of record

    # AI Infrastructure — non-obvious data center plays
    "BIP":   "AI Infrastructure",     # Morgan Stanley upgrade: leading DC developer
    "MDB":   "AI Infrastructure",     # Mizuho upgrade: database layer for AI apps

    # Productivity SaaS — hiring freeze winners
    "CRM":   "Productivity SaaS",     # Salesforce AI agents
    "NOW":   "Productivity SaaS",     # ServiceNow workflow automation

    # Cybersecurity — Iran war + AI agentic attack surface
    "PANW":  "Cybersecurity",         # Iran war winner + agentic AI browser launch
    "CRWD":  "Cybersecurity",         # Iran war winner, endpoint security leader

    # Defense — US/Iran tensions, elevated NATO budgets
    "RTX":   "Defense",               # missiles, radar, Patriot systems
    "LMT":   "Defense",               # F-35, hypersonics, space
    "NOC":   "Defense",               # B-21 bomber, space systems

    # LNG — structural energy diversification (survives Iran de-escalation)
    "LNG":   "LNG / Energy",          # Morgan Stanley Buy; CERAWeek structural story
    "VG":    "LNG / Energy",          # Morgan Stanley Buy + Vitol 5yr deal today

    # Energy — kept as smaller geopolitical hedge (reduced from 3 to 1)
    "XOM":   "Energy Hedge",          # largest US oil major, liquid hedge

    # Commodities — physical backbone of AI + defense buildout
    "FCX":   "Copper / Materials",    # AI data centers + defense = copper demand surge
    "MP":    "Rare Earths",           # only US rare earth producer; defense magnets

    # Mobility / AV — Citi: Uber as largest AV facilitator by 2029
    "UBER":  "Mobility / AV",         # AV distribution layer, fresh Citi bullish call

    # Macro hedge — geopolitical volatility buffer
    "GLD":   "Gold / Macro Hedge",    # safe haven; down on Iran talks = entry point
}

DEFAULT_TICKERS = list(WATCHLIST.keys())

ET = ZoneInfo("America/New_York")


def get_market_clock() -> dict:
    """Query Alpaca's /v2/clock endpoint — the authoritative source for market status."""
    ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY",    "PKCE6UTF35ARLE5IAXHREVTAZT")
    ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "7NE6NJ5uHrR6WhveKn8jdC5YRZjp2QvYnmq1EW2BudSS")
    r = requests.get(
        "https://paper-api.alpaca.markets/v2/clock",
        headers={
            "APCA-API-KEY-ID":     ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        },
        timeout=10,
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


def get_analysis_date() -> str:
    """
    Return the date string to pass to TradingAgents.
    We run after close, so we analyse yesterday's completed data.
    If today is Monday, use Friday (skip weekend).
    """
    today = date.today()
    if today.weekday() == 0:       # Monday → use Friday
        return str(today - timedelta(days=3))
    elif today.weekday() == 6:     # Sunday → use Friday
        return str(today - timedelta(days=2))
    elif today.weekday() == 5:     # Saturday → use Friday
        return str(today - timedelta(days=1))
    else:
        return str(today - timedelta(days=1))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path("trading_loop_logs")
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

def analyse_and_trade(
    ticker: str,
    trade_date: str,
    amount: float,
    dry_run: bool,
    trading_client,
    data_client,
) -> dict:
    """
    Run TradingAgents on one ticker and execute on Alpaca.
    Returns a result dict. Never raises — errors are caught and returned.
    """
    from alpaca_bridge import run_analysis, execute_decision

    result = {"ticker": ticker, "decision": None, "order": None, "error": None}

    try:
        decision = run_analysis(ticker, trade_date)
        result["decision"] = decision

        if dry_run:
            print(f"  [DRY-RUN] Would execute: {decision} {ticker} up to ${amount:.2f}")
            result["order"] = {"action": "DRY_RUN", "decision": decision}
            notify("TradingAgents [DRY-RUN]", f"{decision} {ticker}", subtitle=f"Up to ${amount:.0f}")
        else:
            order = execute_decision(ticker, decision, amount)
            result["order"] = order
            print(f"  [ORDER] {order}")
            if decision == "BUY":
                qty = order.get("qty", "?")
                notify("TradingAgents — BUY", f"Bought {qty} shares of {ticker}", subtitle=f"Up to ${amount:.0f} paper trade")
            elif decision == "SELL":
                qty = order.get("qty", "?")
                notify("TradingAgents — SELL", f"Sold {qty} shares of {ticker}", subtitle="Paper trade")
            elif decision == "HOLD":
                notify("TradingAgents — HOLD", f"Holding {ticker}", subtitle="No order placed")

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

def run_daily_cycle(tickers, amount, dry_run, trading_client, data_client):
    trade_date = get_analysis_date()
    run_date   = str(date.today())
    print_separator("=")
    print(f"  AFTER-CLOSE CYCLE — run:{run_date}  analysing:{trade_date}  ({len(tickers)} tickers)")
    print_separator("=")
    notify("TradingAgents", f"After-close cycle starting — {len(tickers)} tickers",
           subtitle=f"Analysing {trade_date}")

    print("\n[PORTFOLIO] Start of cycle:")
    print_portfolio(trading_client)

    results = []
    for i, ticker in enumerate(tickers, 1):
        sector = WATCHLIST.get(ticker, "")
        print_separator()
        print(f"  [{i}/{len(tickers)}] {ticker}  {f'({sector})' if sector else ''}")
        print_separator()

        result = analyse_and_trade(
            ticker, trade_date, amount, dry_run, trading_client, data_client
        )
        results.append(result)
        log_decision(trade_date, ticker, result["decision"], result["order"])

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
        return ", ".join(f"{t}({WATCHLIST.get(t,'?')[:3]})" for t in tickers) or "none"

    print(f"  BUY  ({len(buys)}):   {with_sector(buys)}")
    print(f"  SELL ({len(sells)}):  {with_sector(sells)}")
    print(f"  HOLD ({len(holds)}):  {with_sector(holds)}")
    if errors:
        print(f"  ERRORS ({len(errors)}): {', '.join(errors)}")
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
    parser.add_argument("--amount",  type=float, default=1000.0, help="USD per trade (default: 1000)")
    parser.add_argument("--dry-run", action="store_true",        help="Analyse only, no orders")
    parser.add_argument("--once",    action="store_true",        help="Run one cycle then exit")
    parser.add_argument("--no-wait", action="store_true",        help="Skip market-hours check and run immediately")
    parser.add_argument("--tickers", nargs="+",                  help="Override ticker list")
    args = parser.parse_args()

    tickers = args.tickers if args.tickers else DEFAULT_TICKERS

    # Initialise Alpaca clients once (reuse across cycles)
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient

    ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY",    "PKCE6UTF35ARLE5IAXHREVTAZT")
    ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "7NE6NJ5uHrR6WhveKn8jdC5YRZjp2QvYnmq1EW2BudSS")

    trading_client = TradingClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_API_SECRET, paper=True)
    data_client    = StockHistoricalDataClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_API_SECRET)

    ticker_list = "\n    ".join(
        f"{t:<6} — {WATCHLIST.get(t, 'custom')}" for t in tickers
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

        run_daily_cycle(tickers, args.amount, args.dry_run, trading_client, data_client)

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
