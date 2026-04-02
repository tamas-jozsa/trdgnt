# TICKET-062 — Add Time-Based Exit Rules

**Priority:** MEDIUM  
**Effort:** 2 hours  
**Status:** TODO  
**Files:**
- `trading_loop.py`
- `alpaca_bridge.py`
- `tradingagents/default_config.py`

## Problem

Current exit rules are limited to:
- Stop-loss (-15%)
- Manual sell decisions

Missing:
- Profit-taking at intermediate targets
- Time-based re-evaluation (positions held too long without movement)
- Trailing stops to protect profits

This leads to missed profits and capital tied up in stagnant positions.

## Acceptance Criteria

- [ ] Implement 50% target profit-taking (sell half position)
- [ ] Add time-based re-evaluation (force review after 30 days)
- [ ] Add trailing stop activation (at +10% profit)
- [ ] Create exit rule engine that's checked daily
- [ ] Log all exits with reason codes

## Implementation

### 1. Update `tradingagents/default_config.py`:

```python
# Exit rule configuration
EXIT_RULES = {
    "profit_taking_50": {
        "enabled": True,
        "trigger": "position_pnl_pct >= target_profit_pct * 0.5",
        "action": "sell_half_position",
        "description": "Take profits on half position at 50% of target"
    },
    "time_stop": {
        "enabled": True,
        "days_held": 30,
        "action": "force_re_evaluation",
        "description": "Force full re-analysis after 30 days"
    },
    "trailing_stop": {
        "enabled": True,
        "activation_profit_pct": 10,
        "trailing_pct": 15,  # 15% trailing from highs
        "description": "Protect profits with trailing stop once +10%"
    }
}
```

### 2. Update `alpaca_bridge.py` to track position entry dates:

```python
def get_positions_with_metadata() -> list:
    """Get positions with entry date and target info."""
    positions = get_positions()  # Existing
    
    # Load entry metadata
    metadata_file = Path("trading_loop_logs/position_metadata.json")
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    for pos in positions:
        ticker = pos["ticker"]
        pos["entry_date"] = metadata.get(ticker, {}).get("entry_date", datetime.now().isoformat())
        pos["target_price"] = metadata.get(ticker, {}).get("target_price")
        pos["stop_price"] = metadata.get(ticker, {}).get("stop_price")
        pos["agent_target"] = metadata.get(ticker, {}).get("agent_target")
    
    return positions

def save_position_metadata(ticker: str, entry_price: float, target: float, stop: float):
    """Save position entry metadata."""
    metadata_file = Path("trading_loop_logs/position_metadata.json")
    
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    metadata[ticker] = {
        "entry_date": datetime.now().isoformat(),
        "entry_price": entry_price,
        "target_price": target,
        "stop_price": stop,
        "agent_target": target
    }
    
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
```

### 3. Create exit rule engine in `trading_loop.py`:

```python
def check_exit_rules(position: dict) -> dict:
    """Check all exit rules for a position."""
    from tradingagents.default_config import EXIT_RULES
    
    exits = []
    rules = EXIT_RULES
    
    # Calculate days held
    entry_date = datetime.fromisoformat(position.get("entry_date", datetime.now().isoformat()))
    days_held = (datetime.now() - entry_date).days
    
    # Calculate profit metrics
    entry_price = float(position.get("avg_entry_price", 0))
    current_price = float(position.get("current_price", entry_price))
    pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
    
    target = position.get("agent_target")
    target_profit_pct = ((target - entry_price) / entry_price * 100) if target and entry_price else 20
    
    # Rule 1: 50% Profit Taking
    if rules["profit_taking_50"]["enabled"]:
        if pnl_pct >= target_profit_pct * 0.5:
            exits.append({
                "rule": "profit_taking_50",
                "action": "SELL_HALF",
                "reason": f"PnL {pnl_pct:.1f}% reached 50% of target ({target_profit_pct * 0.5:.1f}%)",
                "priority": 1
            })
    
    # Rule 2: Time Stop
    if rules["time_stop"]["enabled"]:
        if days_held >= rules["time_stop"]["days_held"]:
            exits.append({
                "rule": "time_stop",
                "action": "FORCE_REEVAL",
                "reason": f"Position held {days_held} days, exceeds {rules['time_stop']['days_held']} day limit",
                "priority": 2
            })
    
    # Rule 3: Trailing Stop (simplified - would need high tracking)
    if rules["trailing_stop"]["enabled"]:
        if pnl_pct >= rules["trailing_stop"]["activation_profit_pct"]:
            # Check if dropped 15% from high (would need historical tracking)
            exits.append({
                "rule": "trailing_stop",
                "action": "MONITOR",
                "reason": f"Trailing stop active - profit {pnl_pct:.1f}% exceeds activation threshold",
                "priority": 3
            })
    
    # Return highest priority exit
    if exits:
        exits.sort(key=lambda x: x["priority"])
        return exits[0]
    
    return None

def execute_exit_rule(ticker: str, rule: dict, position: dict, dry_run: bool = False):
    """Execute an exit rule."""
    if rule["action"] == "SELL_HALF":
        qty = float(position["qty"]) / 2
        logging.info(f"EXIT_RULE: Selling half of {ticker} ({qty:.2f} shares) - {rule['reason']}")
        if not dry_run:
            place_order(ticker, qty, "sell")
    
    elif rule["action"] == "FORCE_REEVAL":
        logging.info(f"EXIT_RULE: Force re-evaluation for {ticker} - {rule['reason']}")
        # Trigger full analysis cycle for this ticker
        return {"action": "FORCE_REEVAL", "ticker": ticker}
    
    return None
```

### 4. Add daily exit check to `trading_loop.py`:

```python
def run_daily_exit_check(positions: list, dry_run: bool = False):
    """Check all positions for exit rules."""
    for pos in positions:
        rule = check_exit_rules(pos)
        if rule:
            execute_exit_rule(pos["ticker"], rule, pos, dry_run)
```

## Testing

- [ ] Unit test: Position at 50% of target → SELL_HALF triggered
- [ ] Unit test: Position held 35 days → FORCE_REEVAL triggered
- [ ] Unit test: Position at +12% → trailing stop monitoring activated
- [ ] Integration test: Exit rules checked daily before regular analysis
