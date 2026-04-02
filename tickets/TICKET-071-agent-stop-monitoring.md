# TICKET-071 — Implement Agent Stop Monitoring

**Priority:** HIGH  
**Effort:** 3 hours  
**Status:** TODO  
**Files:**
- `alpaca_bridge.py`
- `trading_loop.py`

## Problem

Agent-defined stops are saved to `position_entries.json` but not actively monitored. The system only has a global -15% stop-loss. Per-trade agent stops (e.g., BRZE stop at $21.08) should trigger sells independently.

## Current State

From logs:
```
[AGENT-STOP] BRZE: price $20.33 ≤ agent stop $21.08 — closing 42.6439 shares
  [ORDER] Agent-stop order submitted: 1ab050a4-2090-448d-aef7-101bc9b1ffbd
```

This worked for BRZE, but we need to verify it's checking ALL positions every cycle.

## Solution

Ensure agent stops are checked at the start of every cycle, before any new trades.

## Acceptance Criteria

- [ ] Check all open positions against agent-defined stops
- [ ] Run BEFORE global stop-loss check (agent stops are tighter)
- [ ] Log trigger: "AGENT STOP: {ticker} at ${price} (stop: ${stop})"
- [ ] Execute sell order when triggered
- [ ] Update position_entries.json to remove sold position
- [ ] macOS notification on trigger

## Implementation

### 1. Enhance check_agent_stops()

```python
def check_agent_stops(
    position_entries: dict = None,
    dry_run: bool = False
) -> list[dict]:
    """Check all positions against agent-defined stop levels.
    
    Args:
        position_entries: Dict from position_entries.json
        dry_run: If True, log only don't execute
        
    Returns:
        List of triggered stops
    """
    if position_entries is None:
        position_entries = _load_position_entries()
    
    positions = get_portfolio_summary().get("positions", [])
    triggered = []
    
    for pos in positions:
        ticker = pos["ticker"]
        entry = position_entries.get(ticker, {})
        agent_stop = entry.get("stop")
        
        if not agent_stop:
            continue
        
        current_price = pos["current_price"]
        
        if current_price <= agent_stop:
            triggered.append({
                "ticker": ticker,
                "current_price": current_price,
                "stop": agent_stop,
                "qty": pos["qty"]
            })
            
            if not dry_run:
                execute_sell(ticker, pos["qty"])
                # Remove from position_entries
                del position_entries[ticker]
                _save_position_entries(position_entries)
    
    return triggered
```

### 2. Run order in trading_loop.py

```python
# 1. Agent stops (tighter, per-trade)
agent_stops = check_agent_stops()

# 2. Global stop-loss (portfolio-wide -15%)
global_stops = check_stop_losses()

# 3. Exit rules (profit taking, time stops)
exit_rules = check_exit_rules()

# 4. Then run new trades
run_daily_cycle()
```

## Testing

- [ ] Unit test: Price at stop = trigger
- [ ] Unit test: Price above stop = no trigger
- [ ] Unit test: No entry data = skip
- [ ] Integration test: Position removed from entries after sell
