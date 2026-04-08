# TICKET-094 — Fix Graph Logger Crashes on Bypass States

**Priority:** HIGH  
**Effort:** 1 hour  
**Status:** TODO  
**Files:** `src/tradingagents/graph/trading_graph.py`, `src/tradingagents/graph/setup.py`

## Problem

The graph logger crashes on partial/bypass states. `propagate()` safely uses `.get("final_trade_decision")` at `trading_graph.py:328`, but `_log_state()` immediately reverts to direct indexing of `final_state["final_trade_decision"]` and other nested fields. This causes `KeyError: 'final_trade_decision'` during a bypassed ticker.

## Affected Locations

- `src/tradingagents/graph/trading_graph.py:333-360` — unsafe dict access in `_log_state()`
- `src/tradingagents/graph/trading_graph.py:377` — unsafe access
- `src/tradingagents/graph/setup.py:79-84` — related logging setup

## Solution

1. Use `.get()` with defaults throughout `_log_state()`
2. Handle missing keys gracefully when logging bypassed/minimal states
3. Add null-checks for nested dict access
4. Consider adding a "bypass" log entry type

## Acceptance Criteria

- [ ] No `KeyError` when ticker is bypassed
- [ ] No `KeyError` when `final_trade_decision` is missing
- [ ] Safe access for all nested fields in `_log_state()`
- [ ] Graph completes successfully for bypassed tickers
- [ ] Logs still capture useful debug info for bypass cases
