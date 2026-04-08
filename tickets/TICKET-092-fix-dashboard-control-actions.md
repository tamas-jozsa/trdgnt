# TICKET-092 — Fix Dashboard Control Actions Targeting Deleted Entrypoints

**Priority:** HIGH  
**Effort:** 1-2 hours  
**Status:** TODO  
**Files:** `dashboard/backend/routers/control.py`

## Problem

The dashboard still imports `trading_loop` from the old flat layout and launches `PROJECT_ROOT / "trading_loop.py"` and `PROJECT_ROOT / "daily_research.py"`, even though the repo moved those to `apps/`. Also, `/sync-positions` calls `fetch_positions()` but never persists the fetched data before reading `POSITIONS_FILE`, so it can report stale portfolio state even when the fetch succeeds.

## Affected Locations

- `dashboard/backend/routers/control.py:89` — launches `"trading_loop.py"` (old path)
- `dashboard/backend/routers/control.py:109` — launches `"daily_research.py"` (old path)
- `dashboard/backend/routers/control.py:147` — imports from old topology
- `dashboard/backend/routers/control.py:161-163` — stale positions sync

## Solution

1. Update all path references to point to `apps/` directory
2. Use packaged entrypoints (`python -m apps.trading_loop`) instead of direct script paths
3. Fix `/sync-positions` to persist fetched data before returning
4. Remove imports from old flat layout

## Acceptance Criteria

- [ ] Dashboard control endpoints target `apps/` entrypoints
- [ ] `/sync-positions` persists data before reading `POSITIONS_FILE`
- [ ] No imports from old flat layout (root-level scripts)
- [ ] Control actions work when triggered from dashboard UI
- [ ] No `FileNotFoundError` when launching processes
