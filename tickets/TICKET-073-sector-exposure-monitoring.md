# TICKET-073 — Add Sector Exposure Monitoring

**Priority:** MEDIUM  
**Effort:** 2 hours  
**Status:** DONE  
**Files:**
- `alpaca_bridge.py`
- `watch_agent.sh`

## Problem

Sector mapping exists (TICKET-065) but exposure calculation is not implemented. System should warn when any sector exceeds 40% of portfolio.

## Solution

Calculate and monitor sector exposure in real-time.

## Acceptance Criteria

- [ ] Calculate sector exposure from current positions
- [ ] Warn when any sector exceeds 40%
- [ ] Show sector breakdown in dashboard
- [ ] Block new BUYs in over-exposed sector (optional)

## Implementation

```python
TICKER_SECTORS = {
    "NVDA": "TECHNOLOGY", "AVGO": "TECHNOLOGY", ...
    "RTX": "DEFENSE", "LMT": "DEFENSE", ...
    "LNG": "ENERGY", ...
}

def get_sector_exposure() -> dict:
    """Calculate current portfolio exposure by sector."""
    positions = get_portfolio_summary().get("positions", [])
    total_value = sum(p["market_value"] for p in positions)
    
    if total_value == 0:
        return {}
    
    exposure = {}
    for pos in positions:
        sector = TICKER_SECTORS.get(pos["ticker"], "OTHER")
        exposure[sector] = exposure.get(sector, 0) + pos["market_value"]
    
    # Convert to percentages
    return {sector: value/total_value for sector, value in exposure.items()}

def check_sector_limits(max_pct=0.40):
    """Warn if any sector exceeds limit."""
    exposure = get_sector_exposure()
    warnings = []
    
    for sector, pct in exposure.items():
        if pct > max_pct:
            warnings.append(f"⚠️  SECTOR LIMIT: {sector} at {pct:.1%} (max {max_pct:.0%})")
    
    return warnings
```

## Dashboard Integration

Add to watch_agent.sh:
```
SECTOR EXPOSURE
===============
TECHNOLOGY: 45% ⚠️ (limit 40%)
ENERGY: 25%
DEFENSE: 30%
```

## Testing

- [ ] Unit test: Single sector 50% = warning triggered
- [ ] Unit test: All sectors 20% = no warnings
- [ ] Unit test: Empty portfolio = no errors
