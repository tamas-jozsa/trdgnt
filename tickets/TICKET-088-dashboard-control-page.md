# TICKET-088 -- Dashboard Control Page

**Priority:** MEDIUM
**Effort:** 3 hours
**Status:** DONE
**Depends on:** TICKET-081, TICKET-082, TICKET-083
**Files:**
- `dashboard/frontend/src/pages/Control.tsx`
- `dashboard/frontend/src/components/LiveFeed.tsx`
- `dashboard/frontend/src/components/WatchlistEditor.tsx`

## Description

1. **System Status Panel** -- Agent running/stopped badge, PID, last cycle
   time, next cycle time, today's trade counts, research status.
   Auto-refreshes every 30 seconds.

2. **Action Buttons** -- Run Cycle Now, Dry Run, Force Research Refresh,
   Sync Positions. Each triggers a POST and shows result toast.
   "Run Single Ticker" has a text input for the ticker symbol.

3. **Live Feed** -- WebSocket-connected scrolling log. Color-coded lines:
   BUY=green, SELL=red, HOLD=gray, ERROR=orange, OVERRIDE=purple.
   Auto-scrolls to bottom. Pause/resume button.

4. **Watchlist Editor** -- Add ticker form (ticker input, tier dropdown,
   sector input, note input). Remove ticker button. Shows current dynamic
   overrides with remove buttons. Does NOT touch static watchlist.

5. **Configuration Display** -- Read-only display of current settings:
   base amount, stop-loss threshold, LLM models, provider.

## Acceptance Criteria

- [ ] Status panel shows real agent state
- [ ] Action buttons work and show feedback
- [ ] Live feed streams real-time log output
- [ ] Watchlist editor adds/removes tickers
- [ ] No ability to modify static watchlist or env vars through UI
