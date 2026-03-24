# TICKET-013 — Sync MARKET_RESEARCH_PROMPT Watchlist Table

**Priority:** MEDIUM
**Effort:** 30 min
**Status:** DONE
**Files:** `MARKET_RESEARCH_PROMPT.md`

## Problem

The CURRENT WATCHLIST table in `MARKET_RESEARCH_PROMPT.md` is out of sync with
`trading_loop.py`. Any AI research session using this prompt analyses the wrong universe.

**Stale (should be removed):** BIP, CRM
**Missing (should be added):** GLW, CMC, NUE, APA, SOC, SCCO, RCAT, MOS, RCKT

## Acceptance Criteria

- [ ] BIP and CRM removed from the watchlist table
- [ ] All 9 new tickers added with correct sector and reason
- [ ] Tickers grouped by tier (CORE / TACTICAL / SPECULATIVE) in the table
- [ ] Table matches `trading_loop.py WATCHLIST` exactly (34 tickers total)
- [ ] Date in the prompt header updated to reflect current research date
