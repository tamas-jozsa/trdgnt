# TICKET-087 -- Dashboard Research Page

**Priority:** MEDIUM
**Effort:** 3 hours
**Status:** DONE
**Depends on:** TICKET-080, TICKET-083
**Files:**
- `dashboard/frontend/src/pages/Research.tsx`

## Description

1. **Findings Viewer** -- Rendered markdown of the research findings file.
   Date selector dropdown populated from available dates. Shows sentiment
   badge and VIX with trend arrow.

2. **Signals Table** -- Per-ticker BUY/SELL/HOLD signals from research.
   Columns: Ticker, Decision, Conviction, Reason. Color-coded.
   Click ticker -> navigate to Agents page.

3. **Watchlist Changes** -- List of ADD/REMOVE events with dates and tiers.

4. **Buy Quota Audit** -- Table of quota enforcement events showing:
   date, high-conviction signals, BUYs executed, quota met, missed tickers,
   force-buy tickers.

5. **Sector Signals** -- Table: Sector, Signal (FAVOR/AVOID/NEUTRAL),
   affected tickers.

## Acceptance Criteria

- [ ] Research findings render as formatted markdown
- [ ] Date selector switches between available findings
- [ ] Signals table populated from parsed research
- [ ] Watchlist changes display with add/remove indicators
- [ ] Quota audit table shows enforcement history
