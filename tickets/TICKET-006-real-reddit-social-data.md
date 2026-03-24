# TICKET-006 — Wire Real Reddit/Social Data into Social Analyst

**Priority:** MEDIUM  
**Effort:** 3h  
**Status:** TODO  
**Files:** `tradingagents/dataflows/`, `tradingagents/agents/analysts/social_media_analyst.py`

## Problem

The "Social Media Analyst" is named as such and its prompt says *"analyzing social media
posts and public sentiment"*, but its only tool is `get_news` (yfinance). There is no
Reddit, X/Twitter, or StockTwits data. The agent is essentially manufacturing fake social
sentiment from generic news headlines.

## Acceptance Criteria

- [ ] New tool: `get_reddit_sentiment(ticker, days=7)` using Reddit's public JSON API
  - Searches `r/wallstreetbets`, `r/stocks`, `r/investing` for `$TICKER` cashtag
  - Returns: mention count, top post titles + scores, bullish/bearish ratio estimate
  - No auth required (uses `.json` suffix on Reddit URLs)
- [ ] New tool: `get_stocktwits_sentiment(ticker)` using StockTwits public API
  - `https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json`
  - Returns: bullish %, bearish %, message count, sample messages
- [ ] Both tools added to `social_media_analyst.py` tool list
- [ ] Social analyst prompt updated to explicitly call these tools first
- [ ] Graceful degradation: if Reddit/StockTwits unreachable, fall back to yfinance news only
- [ ] Unit test: mock Reddit JSON response → assert mention count parsed correctly

## Implementation

Add `tradingagents/dataflows/reddit_utils.py`:
```python
def get_reddit_sentiment(ticker: str, days: int = 7) -> str:
    subreddits = ["wallstreetbets", "stocks", "investing"]
    ...
    return formatted_summary
```

Add `tradingagents/dataflows/stocktwits_utils.py`:
```python
def get_stocktwits_sentiment(ticker: str) -> str:
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    ...
    return formatted_summary
```
