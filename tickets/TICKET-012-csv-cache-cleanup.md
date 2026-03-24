# TICKET-012 — CSV Data Cache Cleanup

**Priority:** HIGH
**Effort:** 30 min
**Status:** DONE
**Files:** `tradingagents/dataflows/y_finance.py`

## Problem

`get_YFin_data_online()` caches OHLCV data as CSV files named
`{symbol}-YFin-data-{start}-{end}.csv`. The date range changes daily so a new
file is created every run. With 34 tickers running daily this generates ~34 files/day
that never get cleaned up. After a month: 1000+ stale CSVs filling disk.

## Acceptance Criteria

- [ ] At load time, `get_YFin_data_online()` scans its cache dir and deletes
      any CSV files whose mtime is older than 2 days
- [ ] Cleanup runs once per process (guard flag or check at module level)
- [ ] Deletion failures are silently ignored (log.debug only)
- [ ] Unit test: create 3 fake CSVs (2 old, 1 fresh) → assert only old ones deleted
