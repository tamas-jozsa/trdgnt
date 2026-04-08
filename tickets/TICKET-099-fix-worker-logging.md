# TICKET-099 — Fix Worker Logging and Fake IDs

**Priority:** LOW  
**Effort:** 1 hour  
**Status:** TODO  
**Files:** `apps/trading_loop.py`

## Problem

The new worker timestamps/IDs are not actually "live worker logs", and the worker label is not a real process identity. Worker output is buffered in `StringIO` and only printed after the future completes, so the timestamps are post-hoc, not live. Also, `worker_id = (idx % parallel) + 1` is just a submission label, not the actual `ProcessPoolExecutor` worker identity, so `W01/W02/W03` can mislead debugging.

## Affected Locations

- `apps/trading_loop.py:900-905` — buffered StringIO logging
- `apps/trading_loop.py:1223-1238` — fake worker IDs

## Solution

1. Use multiprocessing Queue for real-time logging OR
2. Add timestamps at log generation time, not post-hoc
3. Replace fake worker IDs with actual process IDs OR
4. Rename to "batch labels" to avoid confusion

## Acceptance Criteria

- [ ] Worker logs are timestamped at generation time
- [ ] No buffering delay in log output OR documented limitation
- [ ] Worker IDs are actual process IDs OR renamed to avoid confusion
- [ ] Debugging experience is improved
