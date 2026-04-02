# TICKET-063 — Increase Max Positions for Capital Deployment

**Priority:** HIGH  
**Effort:** 30 minutes  
**Status:** TODO  
**Files:**
- `trading_loop.py`
- `tradingagents/default_config.py`
- `SPEC.md` (update docs)

## Problem

Current `MAX_POSITIONS = 20` is too restrictive given:
- 28-ticker watchlist
- 94.8% cash deployment
- $100K equity with ~$2K average position size

At current sizing, 20 positions = ~$40K deployed (40%), leaving 60% cash idle.

## Acceptance Criteria

- [ ] Increase `MAX_POSITIONS` from 20 to 28 (full watchlist coverage)
- [ ] Add dynamic max based on cash ratio (higher max when cash > 80%)
- [ ] Update SPEC.md documentation
- [ ] Log when position limit affects decision

## Implementation

### 1. Update `tradingagents/default_config.py`:

```python
# Portfolio limits
MAX_POSITIONS = 28  # Was 20 - allow full watchlist coverage
MAX_POSITIONS_CONSERVATIVE = 20  # Used when portfolio is fully deployed

# Dynamic position limit based on cash ratio
def get_dynamic_max_positions(cash_ratio: float) -> int:
    """Return max positions based on cash deployment level."""
    if cash_ratio > 0.80:
        return 28  # Deploy aggressively when cash is high
    elif cash_ratio > 0.50:
        return 25  # Moderate deployment
    else:
        return 20  # Conservative when fully invested
```

### 2. Update `trading_loop.py`:

```python
def check_portfolio_limit(current_positions: int, cash_ratio: float = None) -> tuple[bool, int, str]:
    """Check if portfolio limit would block a new position.
    
    Returns: (would_block, max_positions, reason)
    """
    from tradingagents.default_config import get_dynamic_max_positions
    
    max_pos = get_dynamic_max_positions(cash_ratio or 0.5)
    would_block = current_positions >= max_pos
    
    reason = f"{current_positions}/{max_pos} positions"
    if would_block:
        reason = f"LIMIT REACHED: {current_positions}/{max_pos} positions"
    
    return would_block, max_pos, reason

def execute_decision(decision: dict, ticker: str, ...):
    """Execute with dynamic position limit."""
    from alpaca_bridge import get_portfolio_summary
    
    if decision["action"] == "BUY":
        summary = get_portfolio_summary()
        would_block, max_pos, reason = check_portfolio_limit(
            summary["position_count"], 
            summary["cash_ratio"]
        )
        
        if would_block:
            logging.warning(f"PORTFOLIO_LIMIT: Cannot buy {ticker} - {reason}")
            return {
                "action": "SKIPPED",
                "reason": f"portfolio_limit: {reason}"
            }
```

### 3. Update the guard in `trading_loop.py`:

```python
# Current code:
# if live_positions >= 20:  # Hardcoded

# New code:
summary = get_portfolio_summary()
max_positions = get_dynamic_max_positions(summary["cash_ratio"])

if live_positions >= max_positions:
    logging.info(f"BUY_BLOCKED: {ticker} - Portfolio limit {live_positions}/{max_positions}")
    decision["action"] = "HOLD"
    decision["block_reason"] = f"portfolio_limit_{max_positions}"
```

### 4. Update `SPEC.md`:

```markdown
## Portfolio Limits

| Guard | Value | Behavior |
|-------|-------|----------|
| Max open positions | 20-28 (dynamic) | BUY downgraded to HOLD if at limit. Dynamic: 28 when cash>80%, 25 when cash>50%, 20 when cash<50% |
| Min cash for BUY | $1 | BUY skipped (`insufficient_cash`) |
| No-position SELL | — | SELL skipped (`no_position`) |
```

### 5. Update `README.md`:

```markdown
## Portfolio safeguards

| Guard | Value | Behavior |
|-------|-------|-----------|
| Max open positions | 20-28 (dynamic) | BUY downgraded to HOLD based on cash deployment: 28 when cash>80%, 20 when fully invested |
...
```

## Testing

- [ ] Unit test: Cash 85% → max positions = 28
- [ ] Unit test: Cash 60% → max positions = 25
- [ ] Unit test: Cash 30% → max positions = 20
- [ ] Integration test: 21st position allowed when cash > 80%
