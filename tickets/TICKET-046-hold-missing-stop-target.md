# TICKET-046 — HOLD Trade Log Missing agent_stop / agent_target

**Priority:** MEDIUM
**Effort:** 30min
**Status:** DONE

## Problem

`execute_decision()` in `alpaca_bridge.py` returns early with a minimal dict on
HOLD decisions (line 392):

```python
if decision == "HOLD":
    return {"action": "HOLD", "ticker": ticker}
```

The agent's `STOP-LOSS` and `TARGET` parsed from the Risk Judge output are
discarded. The `conviction` and `size_multiplier` are also not included.

The trade log for MU (which was a HOLD) shows:
```json
{"action": "HOLD", "ticker": "MU"}
```

While ARM (which was a BUY) shows:
```json
{"action": "BUY", "ticker": "ARM", "agent_stop": 125.0, "agent_target": 150.0,
 "conviction": 6, "size_mult": 1.0, ...}
```

These fields are the monitoring parameters the system sets — losing them on
HOLD means we have no record of what the agent thought a safe exit would be
if sentiment turned. They should always be logged regardless of action.

## Fix

Extend the HOLD return dict to include the already-parsed structured fields:

```python
if decision == "HOLD":
    result = {"action": "HOLD", "ticker": ticker, "conviction": conviction,
              "size_mult": size_multiplier}
    if stop_price:
        result["agent_stop"] = stop_price
    if target_price:
        result["agent_target"] = target_price
    return result
```

Note: `parsed`, `size_multiplier`, `stop_price`, `target_price`, and `conviction`
are already extracted before the HOLD early-return — this is a one-line fix at
the HOLD branch.

## Acceptance Criteria
- [ ] HOLD order dict includes `conviction` and `size_mult`
- [ ] HOLD order dict includes `agent_stop` when the Risk Judge provided one
- [ ] HOLD order dict includes `agent_target` when the Risk Judge provided one
- [ ] BUY and SELL dicts unchanged
- [ ] Unit test: `execute_decision(HOLD)` with parsed stop/target returns all fields
- [ ] All existing tests pass
