# TICKET-100 — Cleanup Deprecations and Small Issues

**Priority:** LOW  
**Effort:** 1 hour  
**Status:** TODO  
**Files:** `apps/update_positions.py`, `dashboard/backend/routers/news_monitor.py`

## Problem

There are smaller correctness and hygiene issues that should be cleaned up. `datetime.utcnow()` is deprecated. `update_positions.py` still uses manual requests + disabled SSL verification + no explicit request timeout. The news-monitor router assumes `get_news_monitor()` is never `None` even though startup now handles that case.

## Affected Locations

- `apps/update_positions.py:75` — `datetime.utcnow()` deprecated
- `apps/update_positions.py:60-61` — no request timeout
- `dashboard/backend/routers/news_monitor.py:116-132` — assumes not None

## Solution

1. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`
2. Add explicit request timeouts (e.g., 30 seconds)
3. Add null check for `get_news_monitor()`
4. Scope SSL bypass to only Alpaca calls

## Acceptance Criteria

- [ ] No deprecated `datetime.utcnow()` usage
- [ ] All `requests` calls have explicit timeout
- [ ] `get_news_monitor()` null check added
- [ ] SSL bypass scoped to Alpaca only
- [ ] No deprecation warnings
