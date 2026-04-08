# TICKET-095 — Remove Duplicate Scripts Tree and Fix watch_agent.sh

**Priority:** MEDIUM  
**Effort:** 1 hour  
**Status:** TODO  
**Files:** `scripts/`, `watch_agent.sh`

## Problem

The duplicate `scripts/` Python tree is now effectively dead code and `watch_agent.sh` uses it instead of the active app tree. There are duplicate Python entrypoints under `scripts/*.py`. The shell dashboard resolves `SCRIPT_DIR` to `scripts/` and then imports `trading_loop` from there, not from `apps/`. That means the terminal dashboard is coupled to a stale duplicate tree, not the active one.

## Affected Locations

- `scripts/trading_loop.py` — duplicate of `apps/trading_loop.py`
- `scripts/alpaca_bridge.py` — duplicate
- `scripts/daily_research.py` — duplicate
- `scripts/update_positions.py` — duplicate
- `scripts/watch_agent.sh:5-7` — resolves to scripts/
- `scripts/watch_agent.sh:54-58` — imports from scripts/
- `scripts/watch_agent.sh:99` — stale import

## Solution

1. Delete all `scripts/*.py` files (keep only shell scripts)
2. Update `watch_agent.sh` to import from `apps/`
3. Update `SCRIPT_DIR` logic if needed
4. Move any unique functionality from `scripts/` to `apps/`

## Acceptance Criteria

- [ ] All `scripts/*.py` files deleted
- [ ] `watch_agent.sh` imports from `apps/`
- [ ] No duplicate Python code between `scripts/` and `apps/`
- [ ] Dashboard still works with new paths
- [ ] No broken shell script references
