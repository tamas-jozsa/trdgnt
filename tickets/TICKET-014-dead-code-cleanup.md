# TICKET-014 — Dead Code Cleanup

**Priority:** MEDIUM
**Effort:** 30 min
**Status:** DONE
**Files:** `alpaca_bridge.py`, `trading_loop.py`

## Problem

1. `alpaca_bridge.run_analysis()` is never called by `trading_loop.py` (dead code).
   It also doesn't call `load_memories()`/`save_memories()` — inconsistent with prod.

2. `analyse_and_trade()` in `trading_loop.py` accepts `trading_client` and
   `data_client` parameters that are never used inside the function body.

## Acceptance Criteria

- [ ] `alpaca_bridge.run_analysis()` retained as a standalone CLI entry point but
      updated to call `ta.load_memories()` / `ta.save_memories()` for consistency;
      add a docstring noting it's for standalone use only
- [ ] `trading_client` and `data_client` params removed from `analyse_and_trade()`
      signature and all call sites updated
- [ ] `run_daily_cycle()` no longer passes `trading_client`/`data_client` to
      `analyse_and_trade()`
- [ ] All tests still pass after cleanup
