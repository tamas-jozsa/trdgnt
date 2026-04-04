# TICKET-057 — Fix Risk Judge Override (HOLD Bias)

**Priority:** CRITICAL  
**Effort:** 2 hours  
**Status:** DONE  
**Files:** 
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/default_config.py`

## Problem

The Risk Judge is systematically overriding strong BUY/SELL signals from the Research Manager with HOLD decisions. Analysis of recent trades shows:

| Ticker | Research Manager | Trader | Risk Judge | Result |
|--------|-----------------|--------|------------|--------|
| RTX | BUY (8) | BUY | HOLD (7) | ❌ No trade |
| LMT | SELL (8) | SELL | HOLD (6) | ❌ No trade |
| NVDA | SELL (8) | SELL | HOLD (7) | ❌ No trade |

Root causes identified:
1. Risk Judge is overly cautious around earnings (30-50 day window)
2. No mechanism to respect high-conviction upstream signals
3. Portfolio context (94.8% cash) not considered in risk assessment

## Acceptance Criteria

- [ ] Reduce earnings avoidance window from 30-50 days to 7 days (true binary events only)
- [ ] Implement conviction threshold override: If Research Manager conviction ≥ 8 AND Trader agrees, Risk Judge must have 2/3 risk debaters disagree to override
- [ ] Add portfolio cash ratio context to Risk Judge prompt when cash > 80%
- [ ] Add explicit override logging when Risk Judge changes upstream signal
- [ ] Update Risk Judge system prompt with new rules

## Implementation

### 1. Update `tradingagents/default_config.py`:

```python
# Risk Judge Configuration
EARNINGS_AVOID_DAYS = 7  # Was effectively 30-50
HIGH_CONVICTION_THRESHOLD = 8
RISK_OVERRIDE_REQUIRED_DEBATERS = 2  # Of 3 must disagree to override high conviction
CAPITAL_DEPLOYMENT_CASH_THRESHOLD = 0.80  # 80% cash triggers deployment bias
```

### 2. Update Risk Judge prompt in `tradingagents/agents/managers/risk_manager.py`:

Add to system prompt:
```
OVERRIDE RULES:
1. Earnings avoidance: Only avoid positions within 7 days of earnings report
2. High conviction respect: If Research Manager conviction ≥ 8 and Trader agrees, 
   you need 2 of 3 risk debaters to disagree to override
3. Capital deployment: When portfolio cash > 80%, bias toward deploying on 
   high-conviction setups rather than holding

OVERRIDE LOGGING: When you change an upstream signal (BUY/SELL → HOLD), 
explicitly state: "OVERRIDE REASON: [reason]"
```

### 3. Update `tradingagents/graph/trading_graph.py`:

Pass additional context to Risk Judge:
```python
# In run_agent() for risk_manager
context = {
    "portfolio_cash_ratio": cash / equity,
    "research_manager_conviction": state.get("research_manager_conviction"),
    "trader_agrees": state.get("trader_signal") == state.get("research_manager_signal"),
    "earnings_days_away": get_earnings_days_away(ticker)
}
```

### 4. Add override logging:

```python
def log_override(state, original_signal, final_signal, reason):
    if original_signal != final_signal:
        logging.info(f"RISK_OVERRIDE: {state['ticker']} {original_signal} -> {final_signal}: {reason}")
```

## Testing

- [ ] Unit test: High conviction BUY → Risk Judge should BUY (not HOLD)
- [ ] Unit test: Earnings 10 days away → Should not avoid
- [ ] Unit test: Earnings 3 days away → Should avoid
- [ ] Unit test: Cash 85%, high conviction → Should deploy capital
