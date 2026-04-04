# TICKET-067 — Fix Risk Judge Override Enforcement

**Priority:** CRITICAL  
**Effort:** 3 hours  
**Status:** DONE  
**Files:**
- `trading_loop.py`
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/graph/signal_processing.py`

## Problem

The Risk Judge prompt includes override rules (TICKET-057) but the LLM doesn't consistently follow them. Research identifies 10 HIGH conviction BUY signals, but only 3 were executed. The Risk Judge is overriding strong signals with HOLD despite explicit instructions not to.

Example from 2026-04-02 logs:
- TSM: Research BUY (High) → Research Manager conviction 7 → Risk Judge HOLD
- LITE: Research BUY (High) → Research Manager conviction 5 → Risk Judge HOLD
- GOOGL/META/CRWD/XOM/FCX: Research BUY (High) → Risk Judge likely HOLD

## Root Cause

1. Override rules are suggestions in the prompt, not enforced in code
2. No logging when overrides occur - can't track pattern
3. No feedback loop to train the LLM to follow rules

## Acceptance Criteria

- [ ] Add explicit override detection function that compares Research Manager signal vs Risk Judge output
- [ ] Log all overrides with: ticker, upstream signal, upstream conviction, final decision, reason
- [ ] Add "OVERRIDE" warning to console output when override detected
- [ ] Create override log file for dashboard analysis
- [ ] When override detected, require explicit reasoning in Risk Judge output

## Implementation

### 1. Create override detection module

```python
def detect_signal_override(
    ticker: str,
    research_manager_plan: str,
    risk_judge_decision: str,
    portfolio_context: dict
) -> dict:
    """Detect when Risk Judge overrides strong upstream signals.
    
    Returns:
        {
            "overridden": bool,
            "upstream_signal": "BUY|SELL|HOLD",
            "upstream_conviction": int,
            "final_signal": "BUY|SELL|HOLD",
            "severity": "high|medium|low",
            "reason": str
        }
    """
```

### 2. Integration in trading_loop.py

After `analyse_and_trade()` returns, check for override and log:

```python
override_info = detect_signal_override(
    ticker, 
    final_state.get("investment_plan", ""),
    final_state.get("final_trade_decision", ""),
    portfolio_context
)

if override_info["overridden"]:
    print(f"⚠️  OVERRIDE: {ticker} {override_info['upstream_signal']}({override_info['upstream_conviction']}) → {override_info['final_signal']}")
    log_override_to_file(override_info)
```

### 3. Override log format

```json
{
  "timestamp": "2026-04-02T10:15:30Z",
  "ticker": "TSM",
  "upstream_signal": "BUY",
  "upstream_conviction": 7,
  "final_signal": "HOLD",
  "final_conviction": 6,
  "cash_ratio": 0.95,
  "severity": "high",
  "reason": "earnings_within_7_days"
}
```

## Testing

- [ ] Unit test: Conviction 8 BUY → HOLD = override detected
- [ ] Unit test: Conviction 5 BUY → HOLD = no override (medium conviction)
- [ ] Unit test: Conviction 8 BUY → BUY = no override
- [ ] Integration test: Override log file created with correct format
