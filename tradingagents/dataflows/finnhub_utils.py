"""
finnhub_utils.py
================
Fetches news and sentiment data from Finnhub's API.
Requires FINNHUB_API_KEY in the environment (set via .env).

Falls back gracefully to empty string if key not set or API unreachable.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

BASE_URL = "https://finnhub.io/api/v1"
REQUEST_TIMEOUT = 10


def _api_key() -> str | None:
    return os.getenv("FINNHUB_API_KEY")


def get_news_finnhub(ticker: str, from_date: str, to_date: str) -> str:
    """
    Fetch company news from Finnhub for a given ticker and date range.

    Args:
        ticker:    Stock ticker symbol (e.g. "NVDA")
        from_date: Start date in YYYY-MM-DD format
        to_date:   End date in YYYY-MM-DD format

    Returns:
        Formatted string of news articles, or empty string if unavailable.
    """
    key = _api_key()
    if not key:
        logger.debug("FINNHUB_API_KEY not set — skipping Finnhub news")
        return ""

    url = (
        f"{BASE_URL}/company-news"
        f"?symbol={ticker}&from={from_date}&to={to_date}&token={key}"
    )
    try:
        req = Request(url, headers={"User-Agent": "TradingAgents/1.0"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            articles = json.loads(resp.read().decode())
    except Exception as e:
        logger.debug("Finnhub company-news failed for %s: %s", ticker, e)
        return ""

    if not articles:
        return ""

    return _format_news(ticker, articles, from_date, to_date)


def get_global_news_finnhub(category: str = "general", limit: int = 20) -> str:
    """
    Fetch general market/financial news from Finnhub.

    Args:
        category: News category — "general", "forex", "crypto", "merger"
        limit:    Maximum number of articles to return

    Returns:
        Formatted string of market news, or empty string if unavailable.
    """
    key = _api_key()
    if not key:
        return ""

    url = f"{BASE_URL}/news?category={category}&token={key}"
    try:
        req = Request(url, headers={"User-Agent": "TradingAgents/1.0"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            articles = json.loads(resp.read().decode())
    except Exception as e:
        logger.debug("Finnhub general news failed: %s", e)
        return ""

    if not articles:
        return ""

    return _format_news("market", articles[:limit], category, "")


def _format_news(
    ticker: str,
    articles: list[dict],
    from_date: str,
    to_date: str,
) -> str:
    """Format Finnhub news articles into a readable string."""
    label = ticker if ticker != "market" else "General Market"
    header = f"## Finnhub News: {label}"
    if to_date:
        header += f" ({from_date} → {to_date})"
    lines = [header, f"Total articles: {len(articles)}", ""]

    for art in articles[:15]:  # cap at 15 articles
        headline = art.get("headline", "").strip()
        source   = art.get("source", "")
        url      = art.get("url", "")
        summary  = (art.get("summary") or "")[:200].strip()
        ts       = art.get("datetime", 0)
        date_str = (
            datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            if ts else "unknown date"
        )

        lines.append(f"### {headline}")
        lines.append(f"**Source:** {source} | **Date:** {date_str}")
        if summary:
            lines.append(f"*{summary}*")
        if url:
            lines.append(f"[Read more]({url})")
        lines.append("")

    return "\n".join(lines)
