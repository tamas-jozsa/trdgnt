# TICKET-098 — Fix Dashboard Backend Service Issues

**Priority:** MEDIUM  
**Effort:** 2 hours  
**Status:** TODO  
**Files:** `dashboard/backend/services/portfolio_service.py`, `dashboard/backend/services/trade_service.py`, `dashboard/backend/services/research_service.py`, `dashboard/backend/main.py`

## Problem

The dashboard backend mixes "read services" with filesystem mutations and fragile imports. `get_portfolio()` writes equity snapshots as a side effect of a read request. `get_equity_history()` reconstructs history with rough `qty * 1000` estimates, which makes the analytics unreliable. Several services still import `trading_loop` from the old topology and rely on path hacks.

## Affected Locations

- `dashboard/backend/services/portfolio_service.py:103-107` — side effect write in read
- `dashboard/backend/services/portfolio_service.py:153-183` — rough equity estimates
- `dashboard/backend/services/portfolio_service.py:243-253` — old imports
- `dashboard/backend/services/trade_service.py:26-31` — old topology imports
- `dashboard/backend/services/research_service.py:118-131` — path hacks
- `dashboard/backend/main.py:4` — port 8080 in docs, 8888 at runtime

## Solution

1. Separate read and write operations in portfolio service
2. Use actual position prices instead of `qty * 1000` estimates
3. Update all imports to use new package structure
4. Fix port documentation in `main.py`
5. Remove path hacks, use proper imports

## Acceptance Criteria

- [ ] `get_portfolio()` does not mutate files (pure read)
- [ ] `get_equity_history()` uses real price data
- [ ] All imports from new `apps/` locations
- [ ] Port correctly documented as 8888
- [ ] No `sys.path` manipulation in services
- [ ] News monitor router handles `None` case
