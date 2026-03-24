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

RESULTS_DIR  = Path("results")
PROMPT_FILE  = Path("MARKET_RESEARCH_PROMPT.md")
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
    """Quick price snapshot for all watchlist tickers."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from trading_loop import DEFAULT_TICKERS, get_tier, get_sector
    except Exception:
        return ""

    tickers_str = ",".join(DEFAULT_TICKERS)
    data = _fetch_url(
        f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={tickers_str}"
        "&fields=regularMarketPrice,regularMarketChangePercent,regularMarketVolume"
        ",fiftyTwoWeekHigh,fiftyTwoWeekLow,averageDailyVolume10Day"
    )
    if not data:
        return ""
    try:
        quotes = json.loads(data)["quoteResponse"]["result"]
        lines = ["### Current Watchlist Prices"]
        lines.append(f"{'Ticker':<6}  {'Price':>8}  {'Chg%':>7}  {'52wHi':>8}  {'52wLo':>8}  {'Vol/AvgVol':>12}  Tier")
        lines.append("-" * 75)
        for q in sorted(quotes, key=lambda x: x.get("regularMarketChangePercent", 0), reverse=True):
            sym   = q.get("symbol", "")
            price = q.get("regularMarketPrice", 0)
            chg   = q.get("regularMarketChangePercent", 0)
            hi52  = q.get("fiftyTwoWeekHigh", 0)
            lo52  = q.get("fiftyTwoWeekLow", 0)
            vol   = q.get("regularMarketVolume", 0)
            avg   = q.get("averageDailyVolume10Day", 1) or 1
            vol_ratio = vol / avg
            tier  = get_tier(sym)
            lines.append(
                f"{sym:<6}  ${price:>7.2f}  {chg:>+6.2f}%  ${hi52:>7.2f}  ${lo52:>7.2f}"
                f"  {vol_ratio:>5.1f}x avg   {tier}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.debug("watchlist prices failed: %s", e)
        return ""


def fetch_live_market_data() -> str:
    """Collect all live data in parallel-ish fashion."""
    logger.info("Scraping live market data...")
    sections = []

    vix     = fetch_vix()
    gainers = fetch_yahoo_gainers()
    prices  = fetch_watchlist_prices()

    wsb    = fetch_reddit_hot("wallstreetbets")
    stocks = fetch_reddit_hot("stocks")
    investing = fetch_reddit_hot("investing")
    penny  = fetch_reddit_hot("pennystocks")

    for section in [vix, gainers, prices, wsb, stocks, investing, penny]:
        if section:
            sections.append(section)

    sourced = len([s for s in sections if s])
    logger.info("Live data collected: %d sections", sourced)

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Prompt extraction
# ---------------------------------------------------------------------------

def load_research_prompt() -> str:
    """
    Read MARKET_RESEARCH_PROMPT.md and extract everything between
    ---BEGIN PROMPT--- and ---END PROMPT--- (or end of file).
    """
    text = PROMPT_FILE.read_text(encoding="utf-8")
    match = re.search(r"---BEGIN PROMPT---\s*(.*?)(?:---END PROMPT---|$)", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: return everything after the first ---
    parts = text.split("---", 2)
    return parts[-1].strip() if len(parts) > 2 else text


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_llm(prompt: str, live_data: str) -> str:
    """
    Call the OpenAI API (or compatible endpoint) with the research prompt
    + live scraped data injected.
    """
    import openai

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set. Add it to your .env file.")

    client = openai.OpenAI(api_key=api_key)

    today = date.today().isoformat()

    system_msg = (
        "You are a quantitative research analyst and aggressive momentum trader. "
        "Today is " + today + ". "
        "You have access to live market data scraped minutes ago (provided below). "
        "Use it alongside all research instructions in the user message to produce "
        "the most current, data-driven research findings possible. "
        "Be specific: name actual tickers, prices, percentages. "
        "Do NOT hallucinate prices or analyst calls — if you are uncertain, say so."
    )

    full_prompt = prompt
    if live_data:
        full_prompt = (
            "## LIVE MARKET DATA (scraped " + datetime.now(timezone.utc).strftime("%H:%M UTC") + ")\n\n"
            + live_data
            + "\n\n---\n\n"
            + prompt
        )

    model = os.getenv("RESEARCH_LLM_MODEL", "gpt-4o")
    logger.info("Calling %s for research... (this takes 60-120 seconds)", model)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": full_prompt},
        ],
        max_tokens=8000,
        temperature=0.3,
    )

    return response.choices[0].message.content


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

    # Step 1: sync live positions into the prompt
    logger.info("Step 1/4 — Syncing live positions...")
    try:
        from update_positions import fetch_positions, save_positions, build_positions_markdown, inject_into_prompt
        pos_data = fetch_positions()
        save_positions(pos_data)
        md = build_positions_markdown(pos_data)
        inject_into_prompt(md)
        logger.info("Positions synced (%d open)", len(pos_data["positions"]))
    except Exception as e:
        logger.warning("Position sync failed (continuing anyway): %s", e)

    # Step 2: load the research prompt
    logger.info("Step 2/4 — Loading research prompt...")
    prompt = load_research_prompt()
    logger.info("Prompt loaded (%d chars)", len(prompt))

    # Step 3: scrape live data
    logger.info("Step 3/4 — Scraping live market data...")
    live_data = fetch_live_market_data()

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY-RUN: Would send this to the LLM:")
        print("=" * 60)
        print(live_data[:500] + "...\n[prompt truncated]")
        return None

    # Step 4: call LLM and save
    logger.info("Step 4/4 — Calling LLM for research analysis...")
    t0 = time.time()
    findings = call_llm(prompt, live_data)
    elapsed  = time.time() - t0
    logger.info("LLM responded in %.0fs", elapsed)

    path = save_findings(findings)

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
