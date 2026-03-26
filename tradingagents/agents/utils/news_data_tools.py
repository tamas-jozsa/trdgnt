from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.reddit_utils import get_reddit_sentiment as _get_reddit_sentiment
from tradingagents.dataflows.stocktwits_utils import get_stocktwits_sentiment as _get_stocktwits_sentiment
from tradingagents.dataflows.reuters_utils import (
    get_reuters_news_for_ticker as _get_reuters_ticker_news,
    get_reuters_global_news as _get_reuters_global_news,
)
from tradingagents.dataflows.market_data_tools import (
    get_options_flow as _get_options_flow,
    get_earnings_calendar as _get_earnings_calendar,
    get_analyst_targets as _get_analyst_targets,
    get_short_interest as _get_short_interest,
)

@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    return route_to_vendor("get_news", ticker, start_date, end_date)

@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
) -> str:
    """
    Retrieve global news data.
    Uses the configured news_data vendor.
    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back (default 7)
        limit (int): Maximum number of articles to return (default 5)
    Returns:
        str: A formatted string containing global news data
    """
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)

@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
    Returns:
        str: A report of insider transaction data
    """
    return route_to_vendor("get_insider_transactions", ticker)


@tool
def get_reddit_sentiment(
    ticker: Annotated[str, "Ticker symbol (e.g. NVDA)"],
    days: Annotated[int, "Number of days to look back (default 7)"] = 7,
) -> str:
    """
    Retrieve Reddit sentiment for a ticker by searching r/wallstreetbets,
    r/stocks, r/investing, and r/options. Returns mention counts, top post
    titles and scores, and a bullish/bearish signal.

    Use this tool to understand retail investor sentiment and identify
    meme stock setups or short squeeze narratives.

    Args:
        ticker (str): Ticker symbol
        days (int): Look-back window in days (default 7)
    Returns:
        str: Formatted Reddit sentiment summary, or empty string if unavailable
    """
    return _get_reddit_sentiment(ticker, days)


@tool
def get_stocktwits_sentiment(
    ticker: Annotated[str, "Ticker symbol (e.g. NVDA)"],
) -> str:
    """
    Retrieve StockTwits message stream sentiment for a ticker.
    Returns bullish %, bearish %, total message count and sample messages.

    Use this as a real-time retail sentiment gauge alongside Reddit data.

    Args:
        ticker (str): Ticker symbol
    Returns:
        str: Formatted StockTwits sentiment summary, or empty string if unavailable
    """
    return _get_stocktwits_sentiment(ticker)


@tool
def get_reuters_news(
    ticker: Annotated[str, "Ticker symbol (e.g. NVDA)"],
    hours_back: Annotated[int, "How many hours back to search (default 24)"] = 24,
) -> str:
    """
    Retrieve Reuters news headlines for a specific ticker from the Reuters
    news sitemap (updates hourly, no authentication required).

    Reuters is the gold standard for breaking market, geopolitical, and
    corporate news. Articles are tagged with stock tickers by Reuters editors
    so matches are high-precision.

    Call this FIRST in news analysis — Reuters headlines are more authoritative
    than Yahoo Finance news and update faster.

    Args:
        ticker (str): Ticker symbol
        hours_back (int): Hours to look back (default 24)
    Returns:
        str: Formatted Reuters headlines with timestamps, or empty string if none found
    """
    return _get_reuters_ticker_news(ticker, hours_back=hours_back)


@tool
def get_reuters_global_news(
    hours_back: Annotated[int, "How many hours back to search (default 12)"] = 12,
    limit: Annotated[int, "Maximum number of headlines to return (default 25)"] = 25,
) -> str:
    """
    Retrieve top Reuters business, markets, and technology headlines for
    macro context (no ticker filter).

    Use this for understanding the broader market environment — central bank
    news, geopolitical events, commodity moves, sector-level stories.

    Args:
        hours_back (int): Hours to look back (default 12)
        limit (int): Max headlines (default 25)
    Returns:
        str: Formatted global Reuters headlines with ticker tags where available
    """
    return _get_reuters_global_news(hours_back=hours_back, limit=limit)


@tool
def get_options_flow(
    ticker: Annotated[str, "Ticker symbol (e.g. NVDA)"],
) -> str:
    """
    Fetch options chain data for the nearest expiry: put/call volume ratio,
    OI ratio, unusual activity flags, and ATM implied volatility.

    A put/call ratio < 0.7 is BULLISH (more calls). A ratio > 1.3 is BEARISH.
    Unusual activity (>3x avg volume on a single strike) often precedes big moves.
    High IV means the market expects volatility — a binary event may be near.

    Call this in the Social Analyst when assessing retail conviction and
    potential squeeze setups.

    Args:
        ticker (str): Ticker symbol
    Returns:
        str: Formatted options flow summary or empty string if unavailable
    """
    return _get_options_flow(ticker)


@tool
def get_earnings_calendar(
    ticker: Annotated[str, "Ticker symbol (e.g. NOW)"],
) -> str:
    """
    Fetch the next earnings date, EPS and revenue estimates, and last quarter
    earnings surprise for a ticker.

    CRITICAL: If earnings are within the next 7 days, this is a BINARY RISK
    EVENT. The stock can move ±10-20% in either direction on earnings day.
    Always flag this prominently in your analysis.

    Call this in the News Analyst as the first step — before searching for
    news articles.

    Args:
        ticker (str): Ticker symbol
    Returns:
        str: Formatted earnings calendar or empty string if unavailable
    """
    return _get_earnings_calendar(ticker)


@tool
def get_analyst_targets(
    ticker: Annotated[str, "Ticker symbol (e.g. NVDA)"],
) -> str:
    """
    Fetch Wall Street analyst consensus price targets (low/mean/high),
    recommendation (Buy/Hold/Sell), and upside % to mean target.

    This provides an external valuation anchor. If the current price is
    already above the analyst mean target, the stock may be expensive vs
    professional consensus. If there is >30% upside to mean target, Wall
    Street sees significant value.

    Call this in the Fundamentals Analyst after reviewing financials.

    Args:
        ticker (str): Ticker symbol
    Returns:
        str: Formatted analyst consensus or empty string if unavailable
    """
    return _get_analyst_targets(ticker)


@tool
def get_short_interest(
    ticker: Annotated[str, "Ticker symbol (e.g. GME)"],
) -> str:
    """
    Fetch short interest data: short float %, days to cover, shares short,
    and month-over-month change in short positions.

    SHORT SQUEEZE CHECK: if short float ≥ 15% AND Reddit/StockTwits mention
    volume is rising AND options call/put ratio < 0.7 (more calls), flag as
    SQUEEZE CANDIDATE. High days-to-cover (≥5) amplifies squeeze potential.

    Call this in the Social Analyst to complete the squeeze risk assessment.

    Args:
        ticker (str): Ticker symbol
    Returns:
        str: Formatted short interest summary or empty string if unavailable
    """
    return _get_short_interest(ticker)
