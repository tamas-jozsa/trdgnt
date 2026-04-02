# TICKET-059 — Add Stop-Loss Cooldown to Prevent Whipsaw

**Priority:** HIGH  
**Effort:** 1.5 hours  
**Status:** TODO  
**Files:**
- `alpaca_bridge.py`
- `trading_loop.py`
- `tradingagents/default_config.py`

## Problem

Stop-loss whipsaw observed: RCKT was stopped out on Mar 30, then **re-bought the same day** at similar levels. This causes:
- Unnecessary transaction costs
- Realized losses without meaningful position change
- Risk of repeated stops in volatile conditions

## Acceptance Criteria

- [ ] Implement cooldown period: Don't re-buy tickers stopped out within N days
- [ ] Store stop-loss events in checkpoint or separate file
- [ ] Check cooldown before executing BUY orders
- [ ] Configurable cooldown duration (default: 3 days)
- [ ] Log cooldown skips clearly

## Implementation

### 1. Update `tradingagents/default_config.py`:

```python
# Stop-loss cooldown configuration
STOP_LOSS_COOLDOWN_DAYS = 3  # Days to wait before re-buying after stop
STOP_LOSS_HISTORY_FILE = "trading_loop_logs/stop_loss_history.json"
```

### 2. Create stop-loss tracking in `alpaca_bridge.py`:

```python
import json
from datetime import datetime, timedelta
from pathlib import Path

def load_stop_loss_history() -> dict:
    """Load history of stop-loss triggered sells."""
    history_file = Path(DEFAULT_CONFIG["STOP_LOSS_HISTORY_FILE"])
    if history_file.exists():
        with open(history_file) as f:
            return json.load(f)
    return {}

def save_stop_loss_history(history: dict):
    """Save stop-loss history to file."""
    history_file = Path(DEFAULT_CONFIG["STOP_LOSS_HISTORY_FILE"])
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2, default=str)

def record_stop_loss(ticker: str, price: float, qty: float):
    """Record a stop-loss triggered sell."""
    history = load_stop_loss_history()
    history[ticker] = {
        "date": datetime.now().isoformat(),
        "price": price,
        "qty": qty,
        "reason": "stop_loss_triggered"
    }
    save_stop_loss_history(history)
    logging.info(f"STOP_RECORDED: {ticker} stop-loss at ${price:.2f}")

def is_in_cooldown(ticker: str, cooldown_days: int = None) -> tuple[bool, str]:
    """Check if ticker is in stop-loss cooldown period."""
    if cooldown_days is None:
        cooldown_days = DEFAULT_CONFIG["STOP_LOSS_COOLDOWN_DAYS"]
    
    history = load_stop_loss_history()
    if ticker not in history:
        return False, ""
    
    stop_date = datetime.fromisoformat(history[ticker]["date"])
    cooldown_end = stop_date + timedelta(days=cooldown_days)
    
    if datetime.now() < cooldown_end:
        days_remaining = (cooldown_end - datetime.now()).days
        return True, f"Cooldown: {days_remaining} days remaining (stopped at ${history[ticker]['price']:.2f})"
    
    return False, ""
```

### 3. Update stop-loss execution in `alpaca_bridge.py`:

```python
def execute_stop_loss_sell(ticker: str, position: dict, dry_run: bool = False):
    """Execute stop-loss sell and record for cooldown."""
    # ... existing sell logic ...
    
    if not dry_run and order_successful:
        record_stop_loss(
            ticker=ticker,
            price=position["current_price"],
            qty=position["qty"]
        )
```

### 4. Update BUY logic in `trading_loop.py`:

```python
def execute_decision(decision: dict, ticker: str, ...):
    """Execute trade with cooldown check."""
    from alpaca_bridge import is_in_cooldown
    
    if decision["action"] == "BUY":
        in_cooldown, reason = is_in_cooldown(ticker)
        if in_cooldown:
            logging.warning(f"BUY_BLOCKED: {ticker} in stop-loss cooldown - {reason}")
            return {
                "action": "SKIPPED",
                "reason": f"stop_loss_cooldown: {reason}"
            }
    
    # ... proceed with normal execution ...
```

### 5. Update stop-loss monitoring in `trading_loop.py`:

```python
def check_stop_losses(positions: list, stop_loss_pct: float = 0.15):
    """Check and execute stop-losses with cooldown recording."""
    for pos in positions:
        if pos["unrealized_pl_pct"] <= -stop_loss_pct:
            logging.info(f"STOP_TRIGGERED: {pos['ticker']} at {pos['unrealized_pl_pct']:.2%}")
            execute_stop_loss_sell(pos["ticker"], pos)
```

## Testing

- [ ] Unit test: Ticker stopped yesterday → cooldown active
- [ ] Unit test: Ticker stopped 4 days ago → cooldown expired
- [ ] Integration test: Stop-loss triggered → BUY skipped → BUY allowed after cooldown
- [ ] Test cooldown persistence across restarts
