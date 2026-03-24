# TICKET-002 — Automated Stop-Loss Monitor

**Priority:** HIGH  
**Effort:** 3h  
**Status:** TODO  
**Files:** `trading_loop.py`, `alpaca_bridge.py`

## Problem

Once a BUY is placed there is zero downside protection. A position can fall 50% with no
automated response until the next day's agent analysis happens to say SELL. This is a
capital preservation failure.

## Acceptance Criteria

- [ ] `stop_loss_monitor()` function reads all open positions from Alpaca at startup
- [ ] Computes unrealised P&L % for each position
- [ ] If any position is down ≥ `STOP_LOSS_PCT` (default 15%): auto-submits market SELL,
      logs `STOP_LOSS_TRIGGERED` to the daily JSON log
- [ ] Sends macOS notification on trigger
- [ ] Configurable via `--stop-loss` CLI arg (e.g. `--stop-loss 0.15`)
- [ ] Dry-run mode prints what would be sold but does not execute
- [ ] `stop_loss_monitor()` is called at the top of every `run_daily_cycle()`
- [ ] Unit test: mock positions at -20% → assert SELL submitted

## Implementation

In `alpaca_bridge.py`, add:
```python
def check_stop_losses(threshold: float = 0.15, dry_run: bool = False) -> list[dict]:
    """Check all open positions and sell any below the stop-loss threshold."""
    ...
```

In `trading_loop.py`, call `check_stop_losses()` at the start of `run_daily_cycle()`.
Add `--stop-loss` arg to argparse (default 0.15).
