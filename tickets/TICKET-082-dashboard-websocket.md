# TICKET-082 -- Dashboard WebSocket Live Log Streamer

**Priority:** HIGH
**Effort:** 2 hours
**Status:** DONE
**Depends on:** TICKET-075
**Files:**
- `dashboard/backend/services/log_streamer.py`
- `dashboard/backend/main.py` (add WS route)

## Description

Implement WebSocket endpoint at `/ws/live` that:

1. Tails `trading_loop_logs/stdout.log` using async file watching
2. Parses known line patterns into typed JSON messages:
   - `[TRADINGAGENTS] Analysing X` -> `{"type": "ticker_progress", ...}`
   - `[ALPACA] BUY` -> `{"type": "trade", ...}`
   - `[STOP-LOSS]` -> `{"type": "stop_loss", ...}`
   - `[OVERRIDE-ENFORCE]` -> `{"type": "override", ...}`
   - `[QUOTA-FORCE]` -> `{"type": "quota", ...}`
   - `[WAIT]` -> `{"type": "log", ...}` (filtered to latest only)
   - Other lines -> `{"type": "log", "text": "..."}`
3. Broadcasts to all connected clients
4. Handles disconnects gracefully

## Acceptance Criteria

- [ ] WebSocket connects and receives messages
- [ ] Known patterns parsed into typed messages
- [ ] Multiple clients can connect simultaneously
- [ ] No crash if stdout.log doesn't exist or is empty
