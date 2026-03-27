# TICKET-051 — Price Inconsistency Across Analyst Reports

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE

## Problem

Three different prices for LITE appeared in the same analysis cycle:
- Market Report: $777.17 (last close from `ticker.history()` end_date)
- Fundamentals Report: $688.80 (`ticker_obj.info["currentPrice"]` — real-time)
- Actual fill price: $661.20 (Alpaca ask at execution time)

All three are technically correct for what they measure, but agents see
contradictory numbers. The Research Manager and Risk Judge receive all four
reports and reason across them — seeing "$777" in one section and "$688" in
another for the same ticker on the same day is confusing and can distort the
stop/target calculations.

## Root Cause

`get_fundamentals()` in `y_finance.py` calls `ticker_obj.info` which returns
the real-time price at the moment of the API call. When the trading loop runs
after market close (10am ET analyses the previous day), the "current price" in
info is the after-hours / next-morning price, not the analysis-date close.

`get_stock_data()` uses `ticker.history()` with an explicit date range — the
last row is the close on `trade_date`, which is what the Market Analyst sees
and what the agents are supposed to be reasoning about.

## Fix

In `get_fundamentals()`, add the `trade_date` close price as an explicit field
sourced from the same `ticker.history()` that the Market Analyst uses, and
label it clearly:

```python
# Get the trade_date close (same source as Market Analyst) for consistency
hist = ticker_obj.history(period="5d")
if not hist.empty and curr_date:
    # Find the row closest to curr_date (the analysis date)
    hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
    trade_dt = pd.to_datetime(curr_date)
    available = hist.index[hist.index <= trade_dt]
    if len(available):
        analysis_close = round(float(hist.loc[available[-1], "Close"]), 2)
        lines.append(f"Price (analysis date {curr_date} close): {analysis_close}")
```

Also suppress the real-time `currentPrice` from `info` (it will be confusing
relative to the historical close). The real-time price is already available via
the Alpaca quote at execution time — agents don't need it in the fundamentals report.

## Acceptance Criteria
- [ ] `get_fundamentals()` includes `Price (analysis date {date} close)` from `history()` when `curr_date` is provided
- [ ] `get_fundamentals()` does NOT include `info["currentPrice"]` or `info["regularMarketPrice"]`
- [ ] Market Report and Fundamentals Report show the same price for the same ticker on the same analysis date
- [ ] Unit test: `get_fundamentals("AAPL", "2026-03-26")` returns a price field consistent with `get_stock_data("AAPL", ...)` last close
- [ ] All tests pass
