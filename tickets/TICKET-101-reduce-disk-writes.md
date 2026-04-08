# TICKET-101 — Reduce Excessive Disk Writes

**Priority:** MEDIUM  
**Effort:** 2 hours  
**Status:** TODO  
**Files:** `src/tradingagents/graph/trading_graph.py`, `dashboard/backend/services/portfolio_service.py`

## Problem

Several components write to disk excessively, causing performance issues and unnecessary I/O.

1. `trading_graph.py:363-371` writes full debug JSON into `eval_results/` for every analyzed ticker, every run, unconditionally. That is expensive and likely not needed in production.
2. `portfolio_service.get_portfolio()` writes equity history on each read; that creates unnecessary disk churn.

## Solution

1. Gate `eval_results` debug dumps behind a debug flag
2. Cache equity history writes (write periodically, not every read)
3. Add memory cache layer for dashboard reads

## Acceptance Criteria

- [ ] `eval_results/` writes only happen in debug mode
- [ ] Equity history written periodically (e.g., every minute) not every read
- [ ] Config flag to enable debug dumps
- [ ] Disk I/O significantly reduced in production
