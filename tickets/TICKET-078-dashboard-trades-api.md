# TICKET-078 -- Dashboard Trades API

**Priority:** HIGH
**Effort:** 3 hours
**Status:** DONE
**Depends on:** TICKET-075, TICKET-076
**Files:**
- `dashboard/backend/routers/trades.py`
- `dashboard/backend/services/trade_service.py`

## Description

Implement trade endpoints:

1. `GET /api/trades` -- Paginated trade log with filtering by date range,
   ticker, action. Reads all `trading_loop_logs/YYYY-MM-DD.json` files.

2. `GET /api/trades/performance?days=30` -- Computed metrics: win rate,
   avg win/loss, Sharpe ratio approximation, max drawdown, best/worst trade,
   per-ticker breakdown, per-tier breakdown. Win/loss determined by comparing
   BUY entry price to current price (for open) or SELL price (for closed).

## Acceptance Criteria

- [ ] `/api/trades` returns paginated results with filtering
- [ ] `/api/trades/performance` computes all metrics from SPEC
- [ ] Handles edge cases: no trades, single trade, all HOLDs
- [ ] Performance metrics handle both realized and unrealized P&L
