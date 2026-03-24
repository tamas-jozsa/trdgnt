# TICKET-017 — README + Ticket Status Updates

**Priority:** LOW
**Effort:** 30 min
**Status:** DONE
**Files:** `README.md`, `tickets/*.md`

## Problem

1. All 10 original ticket files say `Status: TODO` even though 9 are fully implemented.
2. `README.md` has zero mention of the custom trading infrastructure:
   - `trading_loop.py`, `alpaca_bridge.py`, `watch_agent.sh`
   - `MARKET_RESEARCH_PROMPT.md`, `update_positions.py`
   - How to set up `.env` and run end-to-end

## Acceptance Criteria

### Ticket statuses
- [ ] TICKET-001 through TICKET-010 all updated to `Status: DONE`
- [ ] Each done ticket gets a one-line `## Implemented in` note with the commit SHA

### README
- [ ] New `## Paper Trading Setup` section added covering:
  - Prerequisites (conda env, `.env` file with all required keys)
  - How to run: `python trading_loop.py [--dry-run] [--once] [--stop-loss 0.15]`
  - How to watch: `trading` alias / `bash watch_agent.sh`
  - How to sync positions: `python update_positions.py`
  - How to run daily research: copy prompt from `MARKET_RESEARCH_PROMPT.md`
  - How to run tests: `pytest tests/`
