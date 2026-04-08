# TICKET-090 — Fix Split-Brain Runtime State After Repo Reorg

**Priority:** CRITICAL  
**Effort:** 2-3 hours  
**Status:** TODO  
**Files:** `apps/trading_loop.py`, `apps/daily_research.py`, `apps/update_positions.py`, `dashboard/backend/config.py`

## Problem

The repo reorg introduced split-brain runtime state across `apps/`, repo root, and `dashboard/`. The active apps now resolve "project root" as `apps/`, so they write to `apps/trading_loop_logs`, `apps/results`, and `apps/positions.json`, while the dashboard reads root `trading_loop_logs`, root `results`, and root `positions.json`.

Both `apps/positions.json` and root `positions.json` exist, and both `apps/trading_loop_logs` and root `trading_loop_logs` exist. This is the most serious issue in the codebase right now.

## Affected Locations

- `apps/trading_loop.py:48-53` — `_path_setup` sets PROJECT_ROOT to `apps/`
- `apps/trading_loop.py:515` — writes to `apps/trading_loop_logs/`
- `apps/trading_loop.py:1411` — results written to `apps/results/`
- `apps/daily_research.py:49-51` — same path setup issue
- `apps/update_positions.py:98-103` — writes `apps/positions.json`
- `dashboard/backend/config.py:13-20` — reads from root `trading_loop_logs/`, `results/`, `positions.json`

## Solution

1. Create a shared `paths.py` module in `src/tradingagents/` that defines canonical paths
2. All apps and dashboard must use this shared module
3. Decide on canonical data root: either:
   - Root level (`trading_loop_logs/`, `results/`, `positions.json`)
   - Or `data/` directory (`data/logs/`, `data/results/`, `data/positions.json`)
4. Update `_path_setup` in all apps to resolve to repo root, not `apps/`
5. Migrate any existing data from `apps/` to canonical locations

## Acceptance Criteria

- [ ] Single canonical path module used by all components
- [ ] Apps write to same locations dashboard reads from
- [ ] No duplicate `positions.json` files
- [ ] No duplicate `trading_loop_logs` directories
- [ ] Dashboard shows current live data from running trading loop
- [ ] Migration guide for any existing data
