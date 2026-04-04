# TICKET-081 -- Dashboard Control API

**Priority:** HIGH
**Effort:** 2 hours
**Status:** DONE
**Depends on:** TICKET-075, TICKET-076
**Files:**
- `dashboard/backend/routers/control.py`

## Description

Implement control endpoints:

1. `GET /api/control/status` -- Check launchctl for agent PID, compute
   next cycle time, count today's trades from daily log, check if today's
   research exists.

2. `POST /api/control/run` -- Spawn trading_loop.py subprocess with
   appropriate flags. Return PID.

3. `POST /api/control/research` -- Spawn daily_research.py --force subprocess.

4. `POST /api/control/sync-positions` -- Import and call update_positions.

5. `POST /api/control/watchlist` -- Add/remove tickers from
   watchlist_overrides.json using the existing format.

## Security

- All POST actions are equivalent to CLI commands the user already runs.
- No secrets exposed. No destructive operations.
- Subprocess spawning uses full paths, no shell injection risk.

## Acceptance Criteria

- [ ] Status endpoint returns agent PID and cycle timing
- [ ] Run endpoint spawns subprocess and returns PID
- [ ] Watchlist endpoint writes valid overrides JSON
- [ ] All endpoints handle errors gracefully (agent not running, file missing)
