# TICKET-056 — Flag and Review 2026-03-24 Ghost Positions

**Priority:** MEDIUM
**Effort:** 30min
**Status:** DONE

## Problem

The 2026-03-24 trade log has 85 entries for 28 tickers — the cycle ran 3 times
due to crashes before the checkpoint system was reliable. This created "ghost"
positions: NOW, VG, and LNG were all opened under chaotic conditions where the
same ticker may have been analysed multiple times in the same day.

Current portfolio positions opened on 2026-03-24:
- LNG: +4.4% P&L (+$88) — probably fine, but opened under chaotic conditions
- NOW: -6.8% P&L (-$134) — approaching the stop range, opened in a re-run
- VG: +1.6% P&L (+$33) — fine

The NOW position at -6.8% is the main concern. The agent originally decided BUY
on the first run, then HOLD on subsequent re-runs. If the original BUY decision
was made with stale/inconsistent state it may not reflect a clean analysis.

## Fix

This ticket is an **audit + decision**, not a code change:

1. Read the GOOGL and META reports from 2026-03-24 to verify decision quality
2. Read the NOW report from 2026-03-24 to evaluate the original BUY thesis
3. Based on analysis decide: keep NOW, close NOW, or let the system handle it
4. Add a log annotation noting positions that were opened in a multi-run session
   (a one-time retroactive fix to the log JSON)
5. Optionally: add a startup warning if the trade log has duplicate entries for
   the same ticker on the same date (detection of future multi-run contamination)

## Acceptance Criteria
- [ ] NOW/LNG/VG BUY theses reviewed
- [ ] Decision made: keep or close each ghost position
- [ ] Trade log annotated with `"multi_run_session": true` flag on 2026-03-24 trades
- [ ] Startup check added: if checkpoint has > 3x the watchlist size in entries
      for a single date, print a warning
- [ ] All tests pass
