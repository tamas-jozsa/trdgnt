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

WATCHLIST = {
    # ── CORE HOLDS ──────────────────────────────────────────────────────────
    # AI & Semiconductors — AI capex supercycle intact
    "NVDA":  "AI & Semiconductors",   # GPU monopoly; SK Hynix ASML order confirms AI demand
    "AVGO":  "AI & Semiconductors",   # $970M DoD private cloud deal closed Mar 24; custom ASICs
    "AMD":   "AI & Semiconductors",   # GPU #2, datacenter CPUs; horizon 4 weeks
    "ARM":   "AI & Semiconductors",   # CPU architecture licensing, edge AI
    "TSM":   "AI & Semiconductors",   # fabricates all leading-edge chips; SK Hynix order benefits
    "MU":    "AI & Semiconductors",   # Micron; AI memory; short-term headwind — monitor
    "LITE":  "AI Photonics",          # BNP PT $1000; Nvidia/Google transceiver wins

    # AI Software & Cloud
    "MSFT":  "AI Software & Cloud",   # RSI 30 oversold + 200 WMA; Azure+OpenAI; 24x PE
    "GOOGL": "AI Software & Cloud",   # Gemini, TPUs, cloud
    "META":  "AI Software & Cloud",   # recovering from selloff; WSB confirmed bounce; AI infra
    "PLTR":  "AI Software & Cloud",   # Maven AI federal; DoD spending surge during Iran war

    # AI Infrastructure
    "GLW":   "AI Infrastructure",     # Corning; BofA Buy Mar 24; optical fiber for DC interconnects
    "MDB":   "AI Infrastructure",     # Mizuho upgrade; database layer for AI apps

    # Productivity SaaS — hiring freeze winners
    "NOW":   "Productivity SaaS",     # ServiceNow+Vonage AI workflow integration Mar 24; best SaaS play

    # Cybersecurity — Iran cyberattack risk + new AI security launches
    "PANW":  "Cybersecurity",         # new agentic AI browser + Iran war winner
    "CRWD":  "Cybersecurity",         # new AI adversary security product launched Mar 24

    # Defense — Iran war, drone warfare, DoD spending surge
    "RTX":   "Defense",               # Patriot systems; 60+ drone interceptions/day; structural
    "LMT":   "Defense",               # F-35, hypersonics, space; Iran war
    "NOC":   "Defense",               # B-21 bomber, space systems; Iran war

    # LNG / Energy — structural + Iran war accelerant
    "VG":    "LNG / Energy",          # TOP GAINER +9.72% Mar 24; Vitol 5yr deal; Morgan Stanley Buy
    "LNG":   "LNG / Energy",          # structural LNG demand; Iran war accelerant
    "XOM":   "Energy Hedge",          # largest US oil major; Iran war beneficiary

    # Commodities — AI + defense physical backbone
    "FCX":   "Copper / Materials",    # JPMorgan 330kt deficit 2026; AI+defense demand confirmed
    "MP":    "Rare Earths",           # only US rare earth producer; defense magnets + Iran war

    # Mobility / AV
    "UBER":  "Mobility / AV",         # AV facilitator; WeRide +6.8% Mar 24 signals AV recovery

    # Macro hedge
    "GLD":   "Gold / Macro Hedge",    # $4,389/oz; geopolitical premium; safe haven

    # ── TACTICAL PLAYS ──────────────────────────────────────────────────────
    # Steel / AI infrastructure second-order play
    "CMC":   "Steel / AI Infrastructure",  # 11x fwd PE; DC steel buildout; 25% tariff tailwind; WSB DD Mar 24
    "NUE":   "Steel / AI Infrastructure",  # Nucor; 95% US DC steel; larger/more liquid than CMC

    # Oil E&P — Iran war beneficiaries
    "APA":   "Oil E&P",               # +5.5% Mar 24; 9.8x PE; Iran war; 52-week breakout candidate
    "SOC":   "Oil & Gas Drilling",    # Sable Offshore; top energy performer past month (Seeking Alpha)

    # Copper complement
    "SCCO":  "Copper / Materials",    # Southern Copper; pure-play copper deficit; complement to FCX

    # ── SPECULATIVE / HIGH-RISK (max 2% position each) ──────────────────────
    "RCAT":  "Defense / Drone Warfare",   # Red Cat; >20% short float; drone war DoD contracts; Iran war
    "MOS":   "Fertilizer / Macro",        # Mosaic; Hormuz fertilizer supply shock; 1679 Reddit upvotes; Sept calls
    "RCKT":  "Biotech Binary",            # Rocket Pharma; FDA re-review; 16% SI; 100% clinical survivability
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
