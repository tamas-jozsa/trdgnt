# TICKET-070 — Position Size Boost When Cash High

**Priority:** HIGH  
**Effort:** 2 hours  
**Status:** TODO  
**Files:**
- `tradingagents/default_config.py`
- `tradingagents/agents/managers/risk_manager.py`
- `alpaca_bridge.py`

## Problem

When portfolio cash > 80%, the system tells the LLM to "bias toward executing" but doesn't enforce larger position sizes. With $100K and 94.6% cash, we should be taking larger positions to deploy capital faster.

## Solution

Add automatic position size multiplier when cash is high.

## Acceptance Criteria

- [ ] Add `get_position_size_boost(cash_ratio)` function
- [ ] Apply boost to Risk Judge output (multiply position size)
- [ ] Log boosted size: "Position size: 1.5x → 1.875x (25% cash boost)"
- [ ] Cap at tier maximum (don't exceed tier limits)
- [ ] Only apply to BUY signals when cash > 80%

## Implementation

### 1. Add boost function

```python
def get_position_size_boost(cash_ratio: float) -> float:
    """Return position size multiplier based on cash deployment.
    
    Returns:
        Multiplier to apply to position size (1.0 = no boost)
    """
    if cash_ratio > 0.85:
        return 1.50  # 50% larger positions
    elif cash_ratio > 0.80:
        return 1.25  # 25% larger positions
    elif cash_ratio > 0.70:
        return 1.10  # 10% larger positions
    return 1.0
```

### 2. Apply in alpaca_bridge.py

In `parse_agent_decision()`:

```python
base_size = parsed.get("size_multiplier", 1.0)
cash_ratio = portfolio_context.get("cash_ratio", 0.5)
boost = get_position_size_boost(cash_ratio)
boosted_size = base_size * boost

# Apply tier limits
clamped_size = max(tier_min, min(tier_max, boosted_size))

if clamped_size != base_size:
    print(f"[ALPACA] Position size boost: {base_size:.2f}x → {clamped_size:.2f}x (cash: {cash_ratio:.0%})")
```

## Boost Levels

| Cash Ratio | Boost | Example: Base 1.5x |
|------------|-------|-------------------|
| > 85% | 1.50× | 1.5× → 2.25× (clamped to 2.0× max) |
| > 80% | 1.25× | 1.5× → 1.875× |
| > 70% | 1.10× | 1.5× → 1.65× |
| ≤ 70% | 1.00× | 1.5× → 1.5× |

## Testing

- [ ] Unit test: Cash 90% + base 1.5x = 2.0x (capped)
- [ ] Unit test: Cash 82% + base 1.0x = 1.25x
- [ ] Unit test: Cash 50% + base 1.5x = 1.5x (no boost)
- [ ] Integration test: Boost logged correctly
