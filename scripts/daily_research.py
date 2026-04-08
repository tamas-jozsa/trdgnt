"""
daily_research.py
=================
Automated daily market research runner.

Replaces the manual "paste prompt into Claude" step.

What it does:
  1. Runs update_positions.py to sync live Alpaca positions into the prompt
  2. Reads MARKET_RESEARCH_PROMPT.md and extracts the full research prompt
  3. Scrapes live data from Reddit, Yahoo Finance gainers, VIX, StockTwits
  4. Calls the OpenAI API (or any configured LLM) with the full prompt + live data
  5. Saves the response as results/RESEARCH_FINDINGS_YYYY-MM-DD.md
  6. Updates trading_loop.py WATCHLIST if the LLM recommends ticker changes

Usage:
  python daily_research.py                  # run full research session
  python daily_research.py --dry-run        # print prompt only, no API call
  python daily_research.py --force          # overwrite today's findings if exists

The trading loop calls this automatically at the start of each daily cycle.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[RESEARCH] %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR  = PROJECT_ROOT / "results"
PROMPT_FILE  = PROJECT_ROOT / "MARKET_RESEARCH_PROMPT.md"
USER_AGENT   = "TradingAgents/1.0 research-bot"
REQUEST_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Live data scrapers (same no-auth sources as MARKET_RESEARCH_PROMPT.md)
# ---------------------------------------------------------------------------

def _fetch_url(url: str) -> str:
    """Fetch a URL and return the body as text. Returns '' on error."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("fetch failed for %s: %s", url, e)
        return ""


def fetch_yahoo_gainers() -> str:
    """Top gainers from Yahoo Finance markets."""
    data = _fetch_url(
        "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        "?scrIds=day_gainers&count=20&formatted=false"
    )
    if not data:
        return ""
    try:
        j = json.loads(data)
        quotes = j["finance"]["result"][0]["quotes"]
        lines = ["### Yahoo Finance Top Gainers (today)"]
        for q in quotes[:15]:
            sym    = q.get("symbol", "")
            chg    = q.get("regularMarketChangePercent", 0)
            price  = q.get("regularMarketPrice", 0)
            name   = q.get("shortName", "")
            vol    = q.get("regularMarketVolume", 0)
            lines.append(f"- {sym:<6} {chg:+.2f}%  ${price:.2f}  {name}  (vol {vol:,})")
        return "\n".join(lines)
    except Exception:
        return ""


def fetch_vix() -> str:
    """Current VIX level."""
    data = _fetch_url(
        "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        "?interval=1d&range=5d"
    )
    if not data:
        return ""
    try:
        j = json.loads(data)
        meta  = j["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", "?")
        prev  = meta.get("chartPreviousClose", "?")
        chg   = ((price - prev) / prev * 100) if isinstance(price, float) and isinstance(prev, float) else 0
        return f"### VIX\nCurrent: {price:.2f}  Previous close: {prev:.2f}  Change: {chg:+.2f}%"
    except Exception:
        return ""


def fetch_reddit_hot(subreddit: str, limit: int = 15) -> str:
    """Hot posts from a subreddit."""
    data = _fetch_url(f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}")
    if not data:
        return ""
    try:
        posts = json.loads(data)["data"]["children"]
        lines = [f"### r/{subreddit} — Hot Posts"]
        for p in posts[:10]:
            d = p["data"]
            lines.append(
                f"- [{d.get('score',0):,} pts] {d.get('title','')[:110]}"
                + (f" [{d.get('link_flair_text','')}]" if d.get('link_flair_text') else "")
            )
        return "\n".join(lines)
    except Exception:
        return ""


def fetch_watchlist_prices() -> str:
    """Quick price snapshot for all watchlist tickers via yfinance."""
    try:
        from trading_loop import WATCHLIST, get_tier
        import yfinance as yf
        import pandas as pd
    except Exception:
        return ""

    tickers = list(WATCHLIST.keys())
    try:
        # Download 5 days so we can compute 1-day change and avg volume
        raw = yf.download(
            tickers, period="5d", progress=False, auto_adjust=True,
            group_by="ticker", threads=True,
        )
        if raw.empty:
            return ""

        rows = []
        for sym in tickers:
            try:
                if len(tickers) == 1:
                    closes = raw["Close"]
                    vols   = raw["Volume"]
                else:
                    # group_by='ticker' → MultiIndex (ticker, field)
                    closes = raw[sym]["Close"]
                    vols   = raw[sym]["Volume"]

                closes = closes.dropna()
                vols   = vols.dropna()
                if len(closes) < 2:
                    continue

                price     = float(closes.iloc[-1])
                prev      = float(closes.iloc[-2])
                chg_pct   = (price - prev) / prev * 100
                vol_today = float(vols.iloc[-1])
                avg_vol   = float(vols.mean())
                vol_ratio = vol_today / avg_vol if avg_vol > 0 else 1.0
                hi52      = float(closes.max())
                lo52      = float(closes.min())
                tier      = get_tier(sym)
                rows.append((chg_pct, sym, price, chg_pct, hi52, lo52, vol_ratio, tier))
            except Exception:
                continue

        if not rows:
            return ""

        rows.sort(reverse=True)  # sort by % change descending
        lines = ["### Current Watchlist Prices (sorted by today's % change)"]
        lines.append(f"{'Ticker':<6}  {'Price':>8}  {'Chg%':>7}  {'5d Hi':>8}  {'5d Lo':>8}  {'Vol/Avg':>8}  Tier")
        lines.append("-" * 72)
        for _, sym, price, chg, hi, lo, vol_r, tier in rows:
            flag = " *" if vol_r >= 2.0 else ""
            lines.append(
                f"{sym:<6}  ${price:>7.2f}  {chg:>+6.2f}%  ${hi:>7.2f}  ${lo:>7.2f}"
                f"  {vol_r:>5.1f}x  {tier[0]}{flag}"
            )
        lines.append("(* = volume ≥ 2x average — unusual activity)")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("watchlist prices failed: %s", e)
        return ""


def fetch_reuters_headlines() -> str:
    """Fetch top Reuters business/markets headlines via public sitemap."""
    try:
        from tradingagents.dataflows.reuters_utils import get_reuters_global_news
        result = get_reuters_global_news(hours_back=12, limit=30)
        return result
    except Exception as e:
        logger.debug("Reuters fetch failed: %s", e)
        return ""


def fetch_live_market_data() -> str:
    """Collect all live data."""
    logger.info("Scraping live market data...")
    sections = []

    vix      = fetch_vix()
    gainers  = fetch_yahoo_gainers()
    prices   = fetch_watchlist_prices()
    reuters  = fetch_reuters_headlines()   # Reuters headlines — highest quality news source

    wsb      = fetch_reddit_hot("wallstreetbets")
    stocks   = fetch_reddit_hot("stocks")
    investing = fetch_reddit_hot("investing")
    penny    = fetch_reddit_hot("pennystocks")

    for section in [vix, reuters, gainers, prices, wsb, stocks, investing, penny]:
        if section:
            sections.append(section)

    sourced = len([s for s in sections if s])
    logger.info("Live data collected: %d sections (Reuters: %s)", sourced, "OK" if reuters else "unavailable")

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Compact system prompt (replaces the 28k MARKET_RESEARCH_PROMPT.md for LLM use)
# ---------------------------------------------------------------------------

def _build_system_prompt(positions_md: str, watchlist_str: str) -> str:
    """
    Build a tight, focused system prompt for the LLM.
    """
    today = date.today().isoformat()
    tickers = [t.split("[")[0] for t in watchlist_str.split()] if watchlist_str else []
    ticker_count = len(tickers)
    ticker_list  = ", ".join(tickers)
    return f"""You are a quantitative momentum trader running a daily research session. Today is {today}.

You will receive live market data (VIX, top gainers, watchlist prices, Reddit hot posts).
Analyse it and produce a structured daily briefing in EXACTLY this format — no extra sections:

## RESEARCH FINDINGS — {today}
### Sentiment: [BULLISH/NEUTRAL/BEARISH] | VIX: [value] | Trend: [rising/falling/stable]

### TOP 3 MACRO THEMES:
1. Theme — implication — tickers that benefit
2. ...
3. ...

### WATCHLIST DECISIONS:
CRITICAL: The table below MUST contain exactly {ticker_count} rows — one per ticker.
Tickers ({ticker_count}): {ticker_list}
Do NOT skip, merge, or omit any ticker. If data is thin, write "Insufficient data" as the reason.
(Verdict must be one of: BUY / HOLD / REDUCE / SELL)
| Ticker | Tier | Decision | Conviction | Reason (1 line max) |
|--------|------|----------|------------|---------------------|
[fill one row per ticker — {ticker_count} rows total]

### TOP 3 NEW PICKS (not in current watchlist):
1. TICKER — setup — catalyst — risk

### SECTORS TO AVOID TODAY:
- sector — reason

### SOURCES USED: [list what live data you relied on]

RULES:
- Use ONLY the live data provided. Do not invent prices or analyst calls.
- Be concise. Each table row is one line. No paragraphs inside the table.
- If a ticker had unusual volume (>2x avg) flag it with * in the Reason column.
- Do not recommend removing more than 5 tickers (SELL verdict) in a single session.
- Speculative tickers — max 2% position, flag risk clearly.

CURRENT OPEN POSITIONS:
{positions_md or "No open positions. Portfolio is 100% cash."}

WATCHLIST ({watchlist_str}):"""


def _build_watchlist_str() -> str:
    """One-line summary of current watchlist for the prompt."""
    try:
        from trading_loop import WATCHLIST, get_tier
        parts = []
        for ticker, info in WATCHLIST.items():
            parts.append(f"{ticker}[{get_tier(ticker)[0]}]")  # e.g. NVDA[C], RCAT[S]
        return " ".join(parts)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_llm(live_data: str, positions_md: str = "") -> str:
    """
    Call the OpenAI API with a compact focused prompt + live data.
    Uses gpt-4o-mini by default (~$0.003/day vs $0.10/day for gpt-4o).
    Override with RESEARCH_LLM_MODEL env var.
    """
    import openai

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set. Add it to your .env file.")

    client = openai.OpenAI(api_key=api_key)

    system_msg  = _build_system_prompt(positions_md, _build_watchlist_str())
    scraped_at  = datetime.now(timezone.utc).strftime("%H:%M UTC")
    user_msg    = f"## LIVE MARKET DATA (scraped {scraped_at})\n\n{live_data}"

    model = os.getenv("RESEARCH_LLM_MODEL", "gpt-4o-mini")
    logger.info("Calling %s (cheap mode)...", model)

    # Estimate token count for logging
    total_chars = len(system_msg) + len(user_msg)
    logger.info("Prompt size: ~%d tokens in, 2000 tokens out", total_chars // 4)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=3000,
        temperature=0.2,   # lower = more consistent structured output
    )

    usage = response.usage
    cost = _estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)
    logger.info(
        "Tokens used: %d in + %d out = %d total  |  est cost: $%.5f",
        usage.prompt_tokens, usage.completion_tokens,
        usage.total_tokens, cost,
    )

    return response.choices[0].message.content


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Rough cost estimate in USD.

    Prices updated 2026-03-27. Source: https://openai.com/api/pricing/
    Format: (input_price_per_1k, output_price_per_1k)
    """
    pricing: dict[str, tuple[float, float]] = {
        # GPT-4o series
        "gpt-4o-mini":             (0.00015, 0.00060),
        "gpt-4o":                  (0.00250, 0.01000),
        "gpt-4o-realtime-preview": (0.00500, 0.02000),
        # GPT-4.1 series
        "gpt-4.1-nano":            (0.00010, 0.00040),
        "gpt-4.1-mini":            (0.00040, 0.00160),
        "gpt-4.1":                 (0.00200, 0.00800),
        # Reasoning models
        "o4-mini":                 (0.00110, 0.00440),
        "o3-mini":                 (0.00110, 0.00440),
        "o3":                      (0.01000, 0.04000),
        "o1-mini":                 (0.00110, 0.00440),
        "o1":                      (0.01500, 0.06000),
        # GPT-5 series (placeholder — update when released)
        "gpt-5-mini":              (0.00050, 0.00200),
        "gpt-5":                   (0.00500, 0.02000),
    }
    # Match by key substring so "gpt-4o-mini-2024-07-18" matches "gpt-4o-mini"
    for key, (in_price, out_price) in pricing.items():
        if key in model:
            return (input_tokens * in_price + output_tokens * out_price) / 1000
    logger.warning("_estimate_cost: unknown model %r — returning 0.0", model)
    return 0.0


# ---------------------------------------------------------------------------
# Coverage validation
# ---------------------------------------------------------------------------

def _validate_findings_coverage(findings_text: str, watchlist_tickers: list[str]) -> list[str]:
    """
    Check that every watchlist ticker appears in the WATCHLIST DECISIONS table.
    Returns a list of missing ticker symbols (empty list = full coverage).
    """
    # Extract the WATCHLIST DECISIONS section
    section_match = re.search(
        r"###\s*WATCHLIST DECISIONS.*?\n(.*?)(?=\n###|\Z)",
        findings_text, re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return list(watchlist_tickers)  # entire section missing

    section = section_match.group(1)
    # Find all tickers that appear as the first cell of a table row: | TICKER |
    found = set(re.findall(r"\|\s*([A-Z]{1,6})\s*\|", section))
    missing = [t for t in watchlist_tickers if t not in found]
    return missing


# ---------------------------------------------------------------------------
# Save findings
# ---------------------------------------------------------------------------

def save_findings(content: str) -> Path:
    """Save research findings to results/RESEARCH_FINDINGS_YYYY-MM-DD.md"""
    RESULTS_DIR.mkdir(exist_ok=True)
    today = date.today().isoformat()
    path  = RESULTS_DIR / f"RESEARCH_FINDINGS_{today}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("Saved findings → %s (%d chars)", path, len(content))
    return path


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_daily_research(dry_run: bool = False, force: bool = False) -> Path | None:
    """
    Full research pipeline. Returns the path to the findings file, or None
    if research was skipped (already done today and --force not set).

    Args:
        dry_run: If True, print the prompt but do not call the LLM or save.
        force:   If True, overwrite today's findings even if they exist.
    """
    today = date.today().isoformat()
    findings_path = RESULTS_DIR / f"RESEARCH_FINDINGS_{today}.md"

    if findings_path.exists() and not force:
        logger.info("Research already done today (%s). Use --force to redo.", findings_path)
        return findings_path

    # Step 1: sync live positions
    logger.info("Step 1/3 — Syncing live positions...")
    positions_md = ""
    try:
        from update_positions import fetch_positions, save_positions, build_positions_markdown, inject_into_prompt
        pos_data = fetch_positions()
        save_positions(pos_data)
        positions_md = build_positions_markdown(pos_data)
        inject_into_prompt(positions_md)
        logger.info("Positions synced (%d open)", len(pos_data["positions"]))
    except Exception as e:
        logger.warning("Position sync failed (continuing anyway): %s", e)

    # Step 2: scrape live data
    logger.info("Step 2/3 — Scraping live market data...")
    live_data = fetch_live_market_data()

    if dry_run:
        system = _build_system_prompt(positions_md, _build_watchlist_str())
        total  = len(system) + len(live_data)
        model  = os.getenv("RESEARCH_LLM_MODEL", "gpt-4o-mini")
        in_tok = total // 4
        out_tok = 2000
        cost = _estimate_cost(model, in_tok, out_tok)
        print(f"\n{'='*60}")
        print(f"DRY-RUN — model: {model}")
        print(f"System prompt: {len(system):,} chars (~{len(system)//4:,} tokens)")
        print(f"Live data:     {len(live_data):,} chars (~{len(live_data)//4:,} tokens)")
        print(f"Est input tokens:  ~{in_tok:,}")
        print(f"Est output tokens: ~{out_tok:,}")
        print(f"Est cost: ${cost:.5f}  (${cost*365:.2f}/year at 1x/day)")
        print(f"{'='*60}")
        print("\nSYSTEM PROMPT PREVIEW:")
        print(system[:600] + "...")
        print("\nLIVE DATA PREVIEW:")
        print(live_data[:400] + "...")
        return None

    # Step 3: call LLM and save
    logger.info("Step 3/3 — Calling LLM for research analysis...")
    t0 = time.time()
    findings = call_llm(live_data, positions_md=positions_md)
    elapsed  = time.time() - t0
    logger.info("LLM responded in %.0fs", elapsed)

    path = save_findings(findings)

    # Coverage validation — warn if any watchlist ticker is missing from the table
    try:
        from trading_loop import load_watchlist_overrides
        effective_tickers = list(load_watchlist_overrides().keys())
        missing = _validate_findings_coverage(findings, effective_tickers)
        if missing:
            logger.warning(
                "Research findings missing %d ticker(s) from WATCHLIST DECISIONS table: %s",
                len(missing), ", ".join(missing),
            )
    except Exception as cov_err:
        logger.debug("Coverage validation skipped: %s", cov_err)

    # macOS notification
    try:
        import subprocess
        subprocess.run(
            ["osascript", "-e",
             f'display notification "Research complete — {path.name}" '
             f'with title "TradingAgents — Daily Research"'],
            check=False, capture_output=True,
        )
    except Exception:
        pass

    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run automated daily market research.")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt, skip LLM call")
    parser.add_argument("--force",   action="store_true", help="Overwrite today's findings")
    args = parser.parse_args()

    result = run_daily_research(dry_run=args.dry_run, force=args.force)
    if result:
        print(f"\nFindings saved: {result}")
