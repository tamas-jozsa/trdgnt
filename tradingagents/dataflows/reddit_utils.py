"""
reddit_utils.py
===============
Fetches Reddit sentiment data for a ticker using Reddit's public JSON API.
No authentication required — uses the .json suffix on subreddit search URLs.

Falls back gracefully to an empty string if Reddit is unreachable.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

SUBREDDITS = ["wallstreetbets", "stocks", "investing", "options"]
USER_AGENT = "TradingAgents/1.0 research-bot"
REQUEST_TIMEOUT = 8   # seconds per subreddit
MAX_POSTS = 10        # posts to fetch per subreddit


def get_reddit_sentiment(ticker: str, days: int = 7) -> str:
    """
    Search Reddit for recent posts mentioning a ticker and return a
    formatted sentiment summary.

    Args:
        ticker: Stock ticker symbol (e.g. "NVDA")
        days:   How many days back to look (default 7)

    Returns:
        Formatted string summarising Reddit sentiment, or empty string
        if Reddit is unreachable.
    """
    cashtag = f"${ticker}"
    all_posts: list[dict] = []

    for sub in SUBREDDITS:
        try:
            posts = _search_subreddit(sub, ticker, cashtag)
            for p in posts:
                p["subreddit"] = sub
            all_posts.extend(posts)
        except Exception as e:
            logger.debug("Reddit %s search failed for %s: %s", sub, ticker, e)

    if not all_posts:
        return ""

    return _format_summary(ticker, all_posts, days)


def _search_subreddit(subreddit: str, ticker: str, cashtag: str) -> list[dict]:
    """Fetch hot posts from a subreddit mentioning ticker."""
    # Search for cashtag first, fall back to ticker name
    url = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={cashtag}&restrict_sr=1&sort=hot&limit={MAX_POSTS}&t=week"
    )
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode())

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        posts.append({
            "title":   p.get("title", ""),
            "score":   p.get("score", 0),
            "comments": p.get("num_comments", 0),
            "url":     f"https://reddit.com{p.get('permalink', '')}",
            "flair":   p.get("link_flair_text", ""),
            "created": p.get("created_utc", 0),
        })
    return posts


def _format_summary(ticker: str, posts: list[dict], days: int) -> str:
    """Format Reddit posts into a readable summary string."""
    # Sort by score descending
    posts.sort(key=lambda p: p["score"], reverse=True)

    total_mentions = len(posts)
    total_score    = sum(p["score"] for p in posts)
    top_posts      = posts[:5]

    lines = [
        f"## Reddit Sentiment for {ticker} (past {days} days)",
        f"- Total mentions across {SUBREDDITS}: {total_mentions}",
        f"- Combined upvote score: {total_score:,}",
        "",
        "### Top Posts:",
    ]
    for p in top_posts:
        ts = datetime.fromtimestamp(p["created"], tz=timezone.utc).strftime("%Y-%m-%d")
        lines.append(
            f"- [{p['score']:,} pts] r/{p['subreddit']} | {ts} | "
            f"{p['title'][:120]}"
        )
        if p["flair"]:
            lines[-1] += f" [{p['flair']}]"

    # Rough bullish/bearish signal from flair keywords
    bull_keywords = {"buy", "bull", "long", "dd", "gain", "yolo", "calls"}
    bear_keywords = {"sell", "bear", "short", "loss", "puts", "crash", "dump"}
    bull_count = sum(
        1 for p in posts
        if any(k in (p["flair"] or "").lower() or k in p["title"].lower()
               for k in bull_keywords)
    )
    bear_count = sum(
        1 for p in posts
        if any(k in (p["flair"] or "").lower() or k in p["title"].lower()
               for k in bear_keywords)
    )
    lines += [
        "",
        f"### Sentiment signal (keyword-based):",
        f"- Bullish signals: {bull_count} posts",
        f"- Bearish signals: {bear_count} posts",
        f"- Overall: {'BULLISH' if bull_count > bear_count else 'BEARISH' if bear_count > bull_count else 'NEUTRAL'}",
    ]

    return "\n".join(lines)
