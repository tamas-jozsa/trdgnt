# TICKET-009 — Better News Data (Finnhub + Fix Orphaned Insider Tool)

**Priority:** MEDIUM  
**Effort:** 2h  
**Status:** TODO  
**Files:** `tradingagents/dataflows/`, `tradingagents/agents/analysts/fundamentals_analyst.py`

## Problem

1. `get_news_yfinance` returns max 20 articles with unreliable date filtering. yfinance
   often returns articles outside the requested date range; the filter silently drops them,
   leaving the news analyst with few or zero articles.

2. `get_insider_transactions` is imported in `fundamentals_analyst.py` but never added to
   the agent's `tools` list. It's a dead import — the agent can never call it.

## Acceptance Criteria

### Finnhub News
- [ ] New `get_news_finnhub(ticker, from_date, to_date)` using Finnhub's company news API
  - `GET https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from}&to={to}&token={key}`
  - Returns formatted string of article headlines, sources, summaries, sentiment
- [ ] Falls back to yfinance if `FINNHUB_API_KEY` not set in `.env`
- [ ] `get_global_news` also has a Finnhub variant using market news endpoint
- [ ] `.env.example` updated with `FINNHUB_API_KEY=your_key_here`

### Fix Insider Transactions
- [ ] `get_insider_transactions` added to fundamentals analyst's `tools` list
- [ ] Fundamentals analyst prompt updated to mention insider transactions as a data source
- [ ] Unit test: assert fundamentals analyst tool list includes insider transactions

## Implementation

Add `tradingagents/dataflows/finnhub_utils.py`:
```python
import os, requests

def get_news_finnhub(ticker: str, from_date: str, to_date: str) -> str:
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        return ""  # caller falls back to yfinance
    url = f"https://finnhub.io/api/v1/company-news"
    ...
```

In `interface.py`, add `"finnhub"` as a vendor option for `news_data`.
Update `fundamentals_analyst.py` to include `get_insider_transactions` in tools list.
