"""
stocktwits_utils.py
===================
Fetches public StockTwits sentiment stream for a ticker.
Uses the public StockTwits API — no authentication required.

Falls back gracefully to an empty string if unreachable.
"""

from __future__ import annotations

import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 8
USER_AGENT = "TradingAgents/1.0 research-bot"


def get_stocktwits_sentiment(ticker: str) -> str:
    """
    Fetch the latest StockTwits message stream for a ticker and return
    a formatted sentiment summary.

    Args:
        ticker: Stock ticker symbol (e.g. "NVDA")

    Returns:
        Formatted string with StockTwits sentiment, or empty string if
        the API is unreachable.
    """
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        logger.debug("StockTwits API failed for %s: %s", ticker, e)
        return ""

    messages = data.get("messages", [])
    if not messages:
        return ""

    return _format_summary(ticker, messages)


def _format_summary(ticker: str, messages: list[dict]) -> str:
    """Format StockTwits messages into a readable summary."""
    bull_count    = 0
    bear_count    = 0
    neutral_count = 0
    sample_msgs   = []

    for msg in messages:
        sentiment = (msg.get("entities", {}).get("sentiment") or {}).get("basic", "")
        if sentiment == "Bullish":
            bull_count += 1
        elif sentiment == "Bearish":
            bear_count += 1
        else:
            neutral_count += 1

        if len(sample_msgs) < 5:
            body = msg.get("body", "").replace("\n", " ")[:120]
            user = msg.get("user", {}).get("username", "unknown")
            sample_msgs.append(f"  @{user}: {body} [{sentiment or 'neutral'}]")

    total = bull_count + bear_count + neutral_count
    bull_pct = round(bull_count / total * 100) if total else 0
    bear_pct = round(bear_count / total * 100) if total else 0

    sentiment_label = (
        "BULLISH" if bull_pct > 55 else
        "BEARISH" if bear_pct > 55 else
        "NEUTRAL"
    )

    lines = [
        f"## StockTwits Sentiment for {ticker}",
        f"- Total messages analysed: {total}",
        f"- Bullish: {bull_count} ({bull_pct}%)",
        f"- Bearish: {bear_count} ({bear_pct}%)",
        f"- Neutral: {neutral_count}",
        f"- Overall sentiment: {sentiment_label}",
        "",
        "### Sample messages:",
    ] + sample_msgs

    return "\n".join(lines)
