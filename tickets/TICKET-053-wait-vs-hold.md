# TICKET-053 — WAIT vs HOLD Distinction (No-Position HOLD)

**Priority:** HIGH
**Effort:** 1h
**Status:** DONE

## Problem

When the system has no open position in a ticker and the Risk Judge outputs HOLD,
the log shows `decision: HOLD, action: HOLD` — identical to HOLDing an existing
position. These are fundamentally different outcomes:

- **HOLD (position exists):** Agent has reviewed the position and decided to keep it.
- **HOLD (no position):** Agent has reviewed the ticker and decided NOT to buy yet.

The second case is more accurately a **WAIT** — "monitor, don't enter." Currently
these blend together in the log, making it impossible to tell from the data whether
the system is actively managing positions or just passively skipping tickers.

69 of 99 total trade entries are HOLD. From the log we cannot tell how many of
those were active position holds vs inactive no-entry decisions.

## Fix

After `execute_decision()` returns on a HOLD, check whether the ticker has an
open position. If not, rewrite the action in the order result and result dict
to `"WAIT"` to distinguish the two cases.

```python
# In analyse_and_trade(), after the HOLD order is obtained:
if order.get("action") == "HOLD":
    has_position = bool(_build_position_context(ticker))
    if not has_position:
        order = {**order, "action": "WAIT"}
        result["order"] = order
        result["decision_type"] = "WAIT"
```

The LLM decision remains `"HOLD"` (it's what the agent decided) — only the
executed action label changes to `"WAIT"` to reflect the real-world outcome.

Print and notify accordingly:
```
[ORDER] {'action': 'WAIT', 'ticker': 'GOOGL', ...}  → "Not entering GOOGL — waiting"
```

Also surface WAIT vs HOLD separately in the end-of-cycle summary.

## Acceptance Criteria
- [ ] Order dict has `action: "WAIT"` when decision is HOLD and no open position
- [ ] Order dict has `action: "HOLD"` when decision is HOLD and position exists
- [ ] `result["decision_type"]` is `"WAIT"` or `"HOLD"` accordingly
- [ ] Print line says "Not entering {ticker} — waiting" for WAIT
- [ ] Print line says "Holding {ticker} — no order placed" for HOLD
- [ ] Trade log records `action: "WAIT"` correctly
- [ ] End-of-cycle summary shows WAIT count separately from HOLD count
- [ ] All tests pass
