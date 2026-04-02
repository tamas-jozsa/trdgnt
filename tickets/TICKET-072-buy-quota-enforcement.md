# TICKET-072 — Add BUY Quota Enforcement

**Priority:** MEDIUM  
**Effort:** 3 hours  
**Status:** TODO  
**Files:**
- `trading_loop.py`
- `tradingagents/research_context.py`

## Problem

When research identifies ≥5 HIGH conviction BUYs and cash > 80%, the system should execute minimum number of trades. Currently it's too selective.

## Solution

Implement a BUY quota system that forces trades when conditions are favorable.

## Acceptance Criteria

- [ ] Count HIGH conviction BUY signals from research
- [ ] If count ≥5 AND cash > 80%, set MIN_BUY_QUOTA = 5
- [ ] Track BUYs executed during cycle
- [ ] If quota not met by end of cycle, log warning with analysis
- [ ] Consider auto-buying highest conviction on next cycle

## Implementation

```python
MIN_BUY_QUOTA = 5
HIGH_CONVICTION_THRESHOLD = "HIGH"

def check_buy_quota(tickers, results, research_signals, cash_ratio):
    """Check if minimum BUY quota was met."""
    if cash_ratio < 0.80:
        return  # No quota when cash is lower
    
    high_conviction_buys = [
        t for t in tickers
        if research_signals.get(t, {}).get("conviction") == HIGH_CONVICTION_THRESHOLD
        and research_signals.get(t, {}).get("decision") == "BUY"
    ]
    
    if len(high_conviction_buys) < MIN_BUY_QUOTA:
        return  # Not enough signals to require quota
    
    buys_executed = sum(1 for r in results if r.get("decision") == "BUY")
    
    if buys_executed < MIN_BUY_QUOTA:
        missed = [t for t in high_conviction_buys 
                  if not any(r.get("ticker") == t and r.get("decision") == "BUY" 
                            for r in results)]
        print(f"⚠️  BUY QUOTA NOT MET: {buys_executed}/{MIN_BUY_QUOTA}")
        print(f"    Missed opportunities: {missed}")
        
        # Log for analysis
        log_quota_miss(buys_executed, MIN_BUY_QUOTA, missed)
```

## Quota Report

Generate at end of cycle:
```
BUY QUOTA REPORT
================
Research HIGH conviction BUYs: 10
Minimum quota required: 5
Actual BUYs executed: 3
Quota met: NO

Missed opportunities:
- TSM (conviction 7, Risk Judge HOLD)
- LITE (conviction 5, Risk Judge HOLD)
- GOOGL (conviction HIGH)
- META (conviction HIGH)
- CRWD (conviction HIGH)
- XOM (conviction HIGH)
- FCX (conviction HIGH)
```

## Testing

- [ ] Unit test: 10 HIGH signals + 3 BUYs = quota not met warning
- [ ] Unit test: 10 HIGH signals + 6 BUYs = quota met
- [ ] Unit test: 3 HIGH signals = no quota check
