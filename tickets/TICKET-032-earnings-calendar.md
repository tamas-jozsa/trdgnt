# TICKET-032 — Earnings Calendar Integration

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE

## Problem

The news analyst prompt says "flag any earnings report due within the next 7 days
as a BINARY RISK EVENT" but it has no actual tool to look up earnings dates.
It can only infer from news articles. This means it often misses or gets wrong
the earnings date.

## Free public source

**Yahoo Finance earnings calendar (via yfinance):**
```python
import yfinance as yf
t = yf.Ticker("NVDA")
cal = t.calendar  # dict with 'Earnings Date', 'EPS Estimate', 'Revenue Estimate'
```

Also: `yf.get_earnings_history("NVDA")` for past earnings surprises.

## New tool: `get_earnings_calendar(ticker)`

Returns:
```
Earnings Calendar for NOW:
- Next earnings: 2026-03-31 (in 6 days) ⚠️ BINARY RISK EVENT
- EPS estimate: $3.84
- Revenue estimate: $3.92B
- Last quarter surprise: +8.2% (beat by $0.31)
```

## Acceptance Criteria
- [ ] `get_earnings_calendar(ticker)` returns next earnings date + estimate + last surprise
- [ ] Flags "BINARY RISK EVENT" if earnings within 7 days
- [ ] Returns "No upcoming earnings found" gracefully if not available
- [ ] Added to News Analyst tool list
- [ ] Unit tests covering: upcoming earnings, no earnings, past surprise calc
- [ ] All tests pass
