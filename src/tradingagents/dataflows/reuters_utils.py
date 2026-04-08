"""
reuters_utils.py
================
Fetches Reuters news headlines via their public XML sitemap.

No authentication required — the sitemap is publicly available and
updates hourly. Your reuters.com subscription adds nothing here since
the sitemap itself is free.

Key advantage over yfinance news:
- Reuters is the gold standard for breaking market/geopolitical news
- Sitemap includes stock_tickers tags — we can match articles directly
  to the ticker being analysed
- Updates every hour, not cached like yfinance
- Titles are high-signal (Reuters doesn't write clickbait)

Endpoints used:
  https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml
  (public, no auth, ~100 articles, updated hourly)
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

SITEMAP_URL  = "https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml"
USER_AGENT   = "Mozilla/5.0 TradingAgents/1.0"
REQUEST_TIMEOUT = 12

# Reuters section paths that matter for trading
TRADING_SECTIONS = {
    "/business/", "/markets/", "/technology/", "/finance/",
    "/business/energy/", "/business/aerospace-defense/",
    "/world/", "/business/media-telecom/",
}

# Namespaces in Reuters sitemap
NS = {
    "sm":    "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news":  "http://www.google.com/schemas/sitemap-news/0.9",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
}


def _fetch_sitemap(hours_back: int = 24) -> list[dict]:
    """
    Fetch and parse the Reuters news sitemap.

    Returns a list of article dicts with:
        url, title, published_at, section, stock_tickers, keywords
    Filtered to articles published within `hours_back` hours.
    """
    try:
        req = Request(SITEMAP_URL, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            xml_bytes = resp.read()
    except Exception as e:
        logger.debug("Reuters sitemap fetch failed: %s", e)
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        logger.debug("Reuters sitemap parse failed: %s", e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles = []

    for url_el in root.findall("sm:url", NS):
        try:
            loc  = url_el.findtext("sm:loc", default="", namespaces=NS)
            news = url_el.find("news:news", NS)
            if news is None:
                continue

            pub_date_str = news.findtext("news:publication_date", default="", namespaces=NS)
            title        = news.findtext("news:title",            default="", namespaces=NS)
            tickers_raw  = news.findtext("news:stock_tickers",    default="", namespaces=NS)
            keywords_raw = news.findtext("news:keywords",         default="", namespaces=NS)

            # Parse publication date
            try:
                pub_dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            except Exception:
                continue

            if pub_dt < cutoff:
                continue

            # Extract section from URL path
            path = loc.replace("https://www.reuters.com", "")
            section = "/" + path.split("/")[1] + "/" if path else "/"

            # Parse stock tickers (comma-separated, e.g. "NVDA.O,AVGO.O,PLTR.O")
            tickers = []
            if tickers_raw:
                for raw in tickers_raw.split(","):
                    # Strip exchange suffix: NVDA.O → NVDA, LMT.N → LMT
                    sym = raw.strip().split(".")[0].upper()
                    if sym and len(sym) <= 6:
                        tickers.append(sym)

            articles.append({
                "url":          loc,
                "title":        title,
                "published_at": pub_dt,
                "section":      section,
                "tickers":      tickers,
                "keywords":     keywords_raw[:200],
            })
        except Exception:
            continue

    # Sort newest first
    articles.sort(key=lambda a: a["published_at"], reverse=True)
    return articles


def get_reuters_news_for_ticker(ticker: str, hours_back: int = 24) -> str:
    """
    Get Reuters headlines relevant to a specific ticker.

    Matches articles where:
    1. The ticker appears in news:stock_tickers (exact match from Reuters)
    2. The ticker appears in the title (fuzzy fallback)

    Args:
        ticker:     Stock ticker symbol (e.g. "NVDA")
        hours_back: How many hours back to search (default 24)

    Returns:
        Formatted string of relevant headlines, or empty string if none found.
    """
    articles = _fetch_sitemap(hours_back=hours_back)
    if not articles:
        return ""

    ticker_upper = ticker.upper()
    relevant = []

    for a in articles:
        # Priority 1: Reuters explicitly tagged this ticker
        if ticker_upper in a["tickers"]:
            relevant.append((0, a))
        # Priority 2: ticker mentioned in title
        elif re.search(r'\b' + re.escape(ticker_upper) + r'\b', a["title"], re.IGNORECASE):
            relevant.append((1, a))

    if not relevant:
        return ""

    relevant.sort(key=lambda x: (x[0], -x[1]["published_at"].timestamp()))

    lines = [f"## Reuters News for {ticker} (last {hours_back}h)"]
    for _, a in relevant[:10]:
        age_h = (datetime.now(timezone.utc) - a["published_at"]).seconds // 3600
        age_str = f"{age_h}h ago" if age_h < 24 else a["published_at"].strftime("%Y-%m-%d")
        tagged = " [Reuters-tagged]" if ticker_upper in a["tickers"] else ""
        lines.append(f"- [{age_str}]{tagged} {a['title']}")
        lines.append(f"  {a['url']}")

    lines.append(f"\nTotal Reuters articles mentioning {ticker}: {len(relevant)}")
    return "\n".join(lines)


def get_reuters_global_news(hours_back: int = 12, limit: int = 25) -> str:
    """
    Get top Reuters business/markets/technology headlines (no ticker filter).

    Used by the News Analyst for global macro context.

    Args:
        hours_back: How many hours back to search (default 12)
        limit:      Maximum number of articles to return (default 25)

    Returns:
        Formatted string of top headlines.
    """
    articles = _fetch_sitemap(hours_back=hours_back)
    if not articles:
        return ""

    # Filter to trading-relevant sections only
    filtered = [
        a for a in articles
        if any(a["section"].startswith(s) for s in TRADING_SECTIONS)
    ]

    # Fall back to all articles if filter is too aggressive
    if len(filtered) < 5:
        filtered = articles

    lines = [f"## Reuters Top Headlines (last {hours_back}h — business/markets/tech)"]
    for a in filtered[:limit]:
        age_h = (datetime.now(timezone.utc) - a["published_at"]).seconds // 3600
        age_str = f"{age_h}h ago" if age_h < 24 else a["published_at"].strftime("%Y-%m-%d")
        ticker_str = f" [{', '.join(a['tickers'][:3])}]" if a["tickers"] else ""
        lines.append(f"- [{age_str}]{ticker_str} {a['title']}")

    lines.append(f"\nSource: Reuters news sitemap (updates hourly, no auth required)")
    return "\n".join(lines)
