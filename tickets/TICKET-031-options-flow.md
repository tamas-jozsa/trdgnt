# TICKET-031 — Options Flow (Put/Call Ratio + Unusual Activity)

**Priority:** MEDIUM
**Effort:** 2h
**Status:** DONE

## Problem

Options flow is one of the strongest leading indicators for retail-driven moves.
A 5:1 call/put ratio on a meme stock is a short squeeze setup signal that no other
source captures. We have no options data at all.

## Free public sources

**Yahoo Finance options chain (via yfinance):**
```python
import yfinance as yf
t = yf.Ticker("NVDA")
opts = t.option_chain("2026-04-17")  # nearest expiry
calls = opts.calls  # DataFrame: strike, volume, openInterest, impliedVolatility
puts  = opts.puts
```

**What to compute:**
- Put/call volume ratio (today's volume, not OI)
- Put/call OI ratio
- Highest volume calls/puts (unusual activity flag if >3x avg)
- Implied volatility — rising IV = event expected

## New tool: `get_options_flow(ticker)`

Returns a formatted string for the analyst:
```
Options Flow for NVDA (nearest expiry: 2026-04-17):
- Put/Call Volume Ratio: 0.42 (BULLISH — more calls than puts)
- Put/Call OI Ratio: 0.61
- Unusual call activity: $185 strike — 12,450 contracts (4.2x avg volume) ⚡
- IV: 48.3% (elevated — market expects a move)
```

## Acceptance Criteria
- [ ] `get_options_flow(ticker)` returns formatted string with P/C ratio, unusual activity flag
- [ ] Falls back gracefully if no options data (not all tickers have options)
- [ ] Added to Social Analyst tool list (retail options ↔ retail sentiment)
- [ ] Unit tests: mock yfinance options response, assert P/C ratio computed correctly
- [ ] All tests pass
