# TICKET-080 -- Dashboard Research API

**Priority:** HIGH
**Effort:** 2 hours
**Status:** DONE
**Depends on:** TICKET-075, TICKET-076
**Files:**
- `dashboard/backend/routers/research.py`
- `dashboard/backend/services/research_service.py`

## Description

Implement research endpoints:

1. `GET /api/research/findings?date=` -- Load research findings markdown,
   parse sentiment/VIX from header, extract per-ticker signals via
   `parse_research_signals()`, extract sector signals via `parse_sector_signals()`.
   Return list of available dates for date picker.

2. `GET /api/research/watchlist` -- Merge static WATCHLIST with dynamic
   overrides, return categorized by tier with source (static/dynamic).

3. `GET /api/research/quota` -- Read buy_quota_log.json, return history.

## Acceptance Criteria

- [ ] Findings endpoint parses sentiment/VIX from markdown header
- [ ] Signals table matches parse_research_signals() output
- [ ] Watchlist merges static + dynamic correctly
- [ ] Available dates list populated from results/ directory scan
