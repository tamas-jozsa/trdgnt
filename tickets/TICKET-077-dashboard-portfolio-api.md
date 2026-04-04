# TICKET-077 -- Dashboard Portfolio API

**Priority:** HIGH
**Effort:** 3 hours
**Status:** DONE
**Depends on:** TICKET-075, TICKET-076
**Files:**
- `dashboard/backend/routers/portfolio.py`
- `dashboard/backend/services/portfolio_service.py`

## Description

Implement portfolio endpoints:

1. `GET /api/portfolio` -- Current positions, account summary, sector exposure,
   enforcement status for today. Reads `positions.json` + enriches with
   `position_entries.json` for stops/targets. Computes sector exposure from
   `TICKER_SECTORS`. Counts today's enforcement events from override/quota logs.

2. `GET /api/portfolio/equity-history?days=30` -- Daily equity snapshots.
   Reconstruct from trade logs: start at $100K, apply daily realized + unrealized P&L.
   Cache to `trading_loop_logs/equity_history.json` for performance.

## Acceptance Criteria

- [ ] `/api/portfolio` returns full schema matching SPEC.md
- [ ] `/api/portfolio/equity-history` returns at least one data point per trading day
- [ ] Handles missing files gracefully (returns empty/defaults, not 500)
- [ ] Sector exposure percentages sum to ~1.0
