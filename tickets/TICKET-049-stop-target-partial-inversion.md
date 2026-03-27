# TICKET-049 — Stop/Target Swap Misses Partial Inversion

**Priority:** HIGH
**Effort:** 30min
**Status:** DONE

## Problem

`execute_decision()` in `alpaca_bridge.py` checks for inverted stop/target using:

```python
buy_inverted = decision == "BUY" and stop_price > price and target_price < price
```

This requires **both** sides to be wrong simultaneously. The LITE BUY case had:
- stop=$680, target=$800, price=$661
- stop > price ($680 > $661) → stop is above the buy price ✗
- target > price ($800 > $661) → target is fine ✓

Because `target_price < price` is False, the whole condition is False — no swap.
The stop remained at $680, which is **above the fill price**, making it an
immediate stop-out trigger rather than a downside protection.

The same partial-inversion bug exists for HOLD.

## Root Cause

The condition was written assuming a fully inverted pair (both wrong at once),
which happens when the Risk Judge copies stop/target from a SELL thesis when
overruling to BUY. But it misses the more common case where only the stop is
misplaced (inherited from a directionally different proposal) while the target
happened to land on the correct side.

## Fix

Check each leg independently. For BUY: if stop ≥ price, it's above the entry
and will trigger immediately — clamp it to a 1.5×ATR default below price.
For SELL: if stop ≤ price, clamp it above. Don't swap with target blindly —
the target may be correct; only fix the stop.

Since ATR isn't available in `execute_decision()`, use a simple percentage
fallback: pin the stop at `price × (1 - 0.05)` for BUY and `price × (1 + 0.05)`
for SELL when the stop is on the wrong side.

```python
# BUY: stop must be below entry price
if decision == "BUY" and stop_price and stop_price >= price:
    corrected = round(price * 0.95, 2)
    print(f"[ALPACA] Warning: BUY stop ${stop_price:.2f} ≥ price ${price:.2f} "
          f"— correcting to 5% below entry: ${corrected:.2f}")
    stop_price = corrected

# SELL: stop must be above entry price
if decision == "SELL" and stop_price and stop_price <= price:
    corrected = round(price * 1.05, 2)
    print(f"[ALPACA] Warning: SELL stop ${stop_price:.2f} ≤ price ${price:.2f} "
          f"— correcting to 5% above entry: ${corrected:.2f}")
    stop_price = corrected
```

Apply the same fix in the HOLD branch using `get_latest_price()`.

## Acceptance Criteria
- [ ] BUY with stop above price → stop corrected to price × 0.95
- [ ] BUY with stop below price → stop unchanged
- [ ] SELL with stop below price → stop corrected to price × 1.05
- [ ] SELL with stop above price → stop unchanged
- [ ] HOLD with stop above price → stop corrected to price × 0.95
- [ ] Warning logged whenever a correction is applied
- [ ] Tests updated + new tests for partial inversion cases
- [ ] All tests pass
