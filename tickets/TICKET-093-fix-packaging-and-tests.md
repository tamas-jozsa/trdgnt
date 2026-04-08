# TICKET-093 — Fix Packaging and Tests for New Layout

**Priority:** HIGH  
**Effort:** 2-3 hours  
**Status:** TODO  
**Files:** `pyproject.toml`, `tests/`

## Problem

`pyproject.toml` only discovers packages under `src`, but `cli/` is still at repo root while `project.scripts` points at `cli.main:app`. That means wheel packaging is inconsistent. The test suite still imports `trading_loop`, `alpaca_bridge`, and `daily_research` from the old root layout, so the current source/test topology is out of sync.

## Affected Locations

- `pyproject.toml:74-85` — package discovery under `src`
- `pyproject.toml:163-165` — `project.scripts` points to `cli.main:app`
- `tests/test_trading_loop_core.py:38` — old import path
- `tests/test_agent_decision_parser.py:9` — old import path
- Many other tests under `tests/`

## Solution

1. Move `cli/` into `src/tradingagents/cli/` or add to package discovery
2. Update all test imports to use new package structure:
   - `from trading_loop import ...` → `from apps.trading_loop import ...` OR
   - Move app code to `src/tradingagents/apps/` for proper packaging
3. Add `apps/` to package discovery OR convert to proper package
4. Ensure wheel includes CLI entrypoint

## Acceptance Criteria

- [ ] `pip install -e .` installs CLI command successfully
- [ ] All tests import from correct locations
- [ ] Test suite passes (`pytest`)
- [ ] Wheel build includes all necessary packages
- [ ] CLI works after pip install: `trdagnt --help`
