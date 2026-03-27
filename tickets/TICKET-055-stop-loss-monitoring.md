# TICKET-055 — Per-Position Stop-Loss Monitoring Against Agent Stop

**Priority:** MEDIUM
**Effort:** 1.5h
**Status:** DONE

## Problem

The system has a global stop-loss check (`check_stop_losses()`) that triggers at
-15% from average entry cost. But agents also set per-trade stops (e.g. LITE
`agent_stop: $627.95`, ARM `agent_stop: $125.00`) which are tighter and more
contextual — ARM was bought at ~$132 with a stop at $125 (5.3% below entry),
much tighter than the 15% global threshold.

Currently `agent_stop` is only saved to the trade log as a reference. It is
never enforced. If LITE drops to $628 (6% below the $661 entry) the system
will continue holding until it reaches -15% (-$99), despite the agent having
set a $628 stop based on technical analysis.

The open positions with logged stops:
- ARM: bought ~$132, agent_stop=$125 → trigger at $125 (-5.3%)
- LITE: bought ~$661, agent_stop=$627.95 → trigger at $627.95 (-5.0%)

## Fix

Add a second stop-loss pass in `check_stop_losses()` (or a new
`check_agent_stops()`) that:

1. Reads all positions from Alpaca
2. For each position, looks up the most recent trade log entry for that ticker
   that has an `agent_stop` field
3. If current market price ≤ agent_stop, triggers a SELL

```python
def check_agent_stops(dry_run: bool = False) -> list[dict]:
    """Check open positions against per-trade agent-set stop levels."""
    from trading_loop import LOG_DIR
    # Load the last 5 days of trade logs to find agent_stop values
    ...
```

This runs BEFORE the global stop-loss check so tighter agent stops fire first.

The trade log lookup needs to handle the case where a position has been held for
multiple days — take the most recent BUY log entry for the ticker.

## Acceptance Criteria
- [ ] `check_agent_stops()` implemented in `alpaca_bridge.py`
- [ ] Called at start of each cycle, before global `check_stop_losses()`
- [ ] Reads agent_stop from the most recent BUY log entry per ticker
- [ ] Sells full position if current price ≤ agent_stop
- [ ] Dry-run safe
- [ ] Logs `AGENT_STOP_TRIGGERED` in trade log with stop level that fired
- [ ] macOS notification sent
- [ ] Unit tests: position above stop → no sell; position at/below stop → sell triggered
- [ ] All tests pass
