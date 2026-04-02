# TICKET-058 — Implement Tier-Based Position Sizing Guardrails

**Priority:** CRITICAL  
**Effort:** 2 hours  
**Status:** TODO  
**Files:**
- `tradingagents/agents/managers/risk_manager.py`
- `trading_loop.py`
- `tradingagents/default_config.py`

## Problem

Position sizing is inconsistent with tier definitions. Example from logs:
- RCKT (SPECULATIVE tier, should be 0.4× max) was sized at **1.75×** on Mar 27
- This contradicts tier-based risk management and exposes portfolio to excess risk

## Acceptance Criteria

- [ ] Define min/max position multipliers per tier
- [ ] Enforce tier limits in Risk Judge decision parsing
- [ ] Add validation in `parse_agent_decision()` to clamp sizes to tier limits
- [ ] Log when position size is clamped due to tier limits
- [ ] Update SPEC for tier sizing rules

## Implementation

### 1. Update `tradingagents/default_config.py`:

```python
TIER_POSITION_LIMITS = {
    "CORE": {"min": 0.5, "max": 2.0, "description": "High conviction, macro-aligned"},
    "TACTICAL": {"min": 0.25, "max": 1.5, "description": "Momentum/catalyst-driven"},
    "SPECULATIVE": {"min": 0.1, "max": 0.75, "description": "Squeeze/biotech/meme, max 2-3% portfolio"},
    "HEDGE": {"min": 0.25, "max": 1.0, "description": "Geopolitical/volatility buffer"}
}

# Override message templates
TIER_OVERRIDE_MESSAGE = "Position size {original:.2f}× clamped to {clamped:.2f}× (tier: {tier}, limit: {limit})"
```

### 2. Update `tradingagents/agents/managers/risk_manager.py`:

Add to Risk Judge system prompt:
```
POSITION SIZE CONSTRAINTS (must respect tier limits):
- CORE tickers: 0.5× to 2.0× base allocation
- TACTICAL tickers: 0.25× to 1.5× base allocation  
- SPECULATIVE tickers: 0.1× to 0.75× base allocation
- HEDGE tickers: 0.25× to 1.0× base allocation

Your output POSITION SIZE will be validated against these limits.
```

### 3. Update `alpaca_bridge.py` `parse_agent_decision()`:

```python
def parse_agent_decision(decision_text: str, ticker: str, tier: str) -> dict:
    """Parse decision with tier-based sizing enforcement."""
    from tradingagents.default_config import TIER_POSITION_LIMITS
    
    parsed = _parse_raw_decision(decision_text)  # Existing parsing
    
    # Enforce tier limits
    tier_limits = TIER_POSITION_LIMITS.get(tier, TIER_POSITION_LIMITS["CORE"])
    original_size = parsed.get("size_multiplier", 1.0)
    
    clamped_size = max(tier_limits["min"], min(tier_limits["max"], original_size))
    
    if clamped_size != original_size:
        logging.warning(
            f"TIER_OVERRIDE: {ticker} ({tier}) size {original_size:.2f}× -> {clamped_size:.2f}× "
            f"(limits: {tier_limits['min']}-{tier_limits['max']})"
        )
        parsed["size_multiplier"] = clamped_size
        parsed["size_clamped"] = True
        parsed["size_original"] = original_size
    
    return parsed
```

### 4. Update `trading_loop.py` to pass tier info:

```python
# In execute_decision call
tier = get_tier_for_ticker(ticker)  # New helper
decision = parse_agent_decision(agent_output, ticker, tier)
```

### 5. Add helper function:

```python
def get_tier_for_ticker(ticker: str) -> str:
    """Return tier for a given ticker."""
    WATCHLIST = {...}  # Existing watchlist
    for tier, tickers in WATCHLIST.items():
        if ticker in tickers:
            return tier
    return "CORE"  # Default
```

## Testing

- [ ] Unit test: SPECULATIVE ticker with 1.75× size → clamped to 0.75×
- [ ] Unit test: CORE ticker with 3.0× size → clamped to 2.0×
- [ ] Unit test: TACTICAL ticker with 0.1× size → clamped to 0.25×
- [ ] Integration test: Full decision pipeline respects tier limits
