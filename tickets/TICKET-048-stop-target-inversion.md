# TICKET-048 — Risk Judge Outputs Inverted Stop/Target on Bearish HOLD

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE

## Problem

On the MU HOLD (2026-03-26), the Risk Judge output was:
```
STOP-LOSS: $394.42   TARGET: $352.55
Current price: ~$382
```

The stop ($394) is **above** the current price and the target ($352) is
**below** it. For a HOLD-while-bearish position this is directionally inverted:

- A real stop on a neutral-to-bearish HOLD should be *below* current price
  (bail if it drops more than X%)
- A real target on a HOLD should be a *recovery level above* current price
  (the point at which the thesis is vindicated)

The agent inherited these numbers from the Trader's SELL proposal (stop above
price = buy-stop for a short, target below = short exit). The Risk Judge
overruled to HOLD but kept the SELL-oriented stop/target unchanged.

This is a prompt quality issue — the Risk Judge is not instructed to recalculate
stop and target to be consistent with its own HOLD decision.

## Fix

### 1. Constraint in the Risk Judge system prompt

Add an explicit rule to the Risk Judge agent's system prompt:

```
IMPORTANT — stop/target must be directionally consistent with your decision:
- BUY:  STOP-LOSS below current price (downside protection)
         TARGET above current price (upside objective)
- SELL: STOP-LOSS above current price (exit trigger if wrong)
         TARGET below current price (profit take level)
- HOLD: STOP-LOSS below current price (point at which you'd exit long)
         TARGET above current price (point at which you'd re-evaluate upside)
        If you have no position, STOP-LOSS is the level that would trigger a SELL
        if bought. TARGET is the level that would trigger a BUY review.
```

### 2. Post-parse validation in `parse_agent_decision()`

After extracting stop and target, validate directional consistency against the
signal. If the values are inverted, swap them and log a warning:

```python
if signal == "BUY" and stop_price and current_price and stop_price > current_price:
    logger.warning("Inverted stop/target detected for BUY — swapping")
    stop_price, target_price = target_price, stop_price
```

The current price is not available inside `parse_agent_decision()`, so this
validation belongs in `execute_decision()` after `get_latest_price()` is called.

### 3. Find the Risk Judge prompt file

Read `tradingagents/agents/risk_mgmt/` and the risk judge agent to locate
the exact prompt string to patch.

## Acceptance Criteria
- [ ] Risk Judge system prompt includes directional stop/target constraint
- [ ] `execute_decision()` validates stop/target direction against signal and
      logs `[ALPACA] Warning: inverted stop/target detected — swapping` when triggered
- [ ] Swapped values are stored correctly in the result dict and trade log
- [ ] Unit test: BUY with stop > price → values are swapped; BUY with stop < price → unchanged
- [ ] Unit test: SELL with stop < price → values are swapped
- [ ] Unit test: HOLD with stop > price → values are swapped
- [ ] All existing tests pass
