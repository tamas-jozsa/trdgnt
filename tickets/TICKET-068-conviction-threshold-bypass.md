# TICKET-068 — Add Conviction Threshold Bypass

**Priority:** CRITICAL  
**Effort:** 4 hours  
**Status:** TODO  
**Files:**
- `trading_loop.py`
- `tradingagents/graph/conditional_logic.py`
- `tradingagents/graph/trading_graph.py`

## Problem

When Research Manager has conviction ≥ 8 AND daily research signal agrees (both BUY or both SELL), the Risk Judge can still override with HOLD. This is happening too frequently and causing missed opportunities when cash is high.

With 94.6% cash and 10 HIGH conviction BUY signals, we should be executing 7-10 trades, not 3.

## Solution

Implement a bypass mechanism that skips Risk Judge when:
1. Research Manager conviction ≥ 8
2. Research signal agrees (both BUY or both SELL)
3. For BUY: Portfolio cash > 80%
4. For SELL: Position exists

## Acceptance Criteria

- [ ] Add `should_bypass_risk_judge()` function
- [ ] When bypass triggered, log: "BYPASS: High conviction signal for {ticker}, skipping Risk Judge"
- [ ] Execute trade directly from Trader output (skip Risk debate + Judge)
- [ ] Still log the trade with full context
- [ ] Track bypass statistics per cycle

## Implementation

### 1. Bypass detection logic

```python
def should_bypass_risk_judge(
    ticker: str,
    investment_plan: str,
    research_signal: dict,
    portfolio_context: dict,
    has_position: bool
) -> bool:
    """Determine if high-conviction signal should bypass Risk Judge.
    
    Bypass conditions:
    - Research Manager conviction >= 8
    - Research signal agrees with RM (both BUY or both SELL)
    - For BUY: Cash > 80%
    - For SELL: Has position
    """
    rm_conviction = extract_conviction(investment_plan)
    rm_signal = extract_signal(investment_plan)
    research_decision = research_signal.get("decision", "HOLD")
    cash_ratio = portfolio_context.get("cash_ratio", 0)
    
    # Must have high conviction
    if rm_conviction < 8:
        return False
    
    # Signals must agree
    if rm_signal != research_decision:
        return False
    
    # BUY: need high cash
    if rm_signal == "BUY" and cash_ratio > 0.80:
        return True
    
    # SELL: need position
    if rm_signal == "SELL" and has_position:
        return True
    
    return False
```

### 2. Modify trading graph flow

In `conditional_logic.py`, add bypass check before Risk debate:

```python
if should_bypass_risk_judge(...):
    # Skip Risk debate and Judge, go directly to execution
    return "execute_trade"
else:
    # Normal flow
    return "Risk Debate"
```

### 3. Direct execution path

When bypass triggered:
1. Use Trader output for trade parameters (stop, target, size)
2. Execute immediately
3. Log with "BYPASS" flag

## Bypass Statistics

Track per cycle:
- Total bypasses
- Bypass success rate (did we avoid a bad trade?)
- Override prevention count

## Testing

- [ ] Unit test: RM conv 8 + Research BUY + Cash 85% = bypass True
- [ ] Unit test: RM conv 8 + Research BUY + Cash 50% = bypass False
- [ ] Unit test: RM conv 7 + Research BUY + Cash 85% = bypass False
- [ ] Unit test: RM conv 8 + Research SELL + Has position = bypass True
- [ ] Integration test: Bypass trade executes correctly
