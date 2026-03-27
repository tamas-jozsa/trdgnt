# TICKET-045 — Watchlist Override Decay and Cap

**Priority:** HIGH
**Effort:** 1.5h
**Status:** DONE

## Problem

`save_watchlist_overrides()` unconditionally accumulates every SELL/REMOVE from
each daily research session. After 2 days of bearish sentiment the override file
had 16 removes (more than half the static watchlist), gutting the portfolio thesis
based on short-term noise.

Root causes:
1. **No remove cap** — any number of tickers can be removed with no ceiling.
2. **No decay** — a REMOVE added on a bearish day stays forever; there is no
   mechanism to undo it when the thesis recovers.
3. **No minimum CORE protection** — CORE tickers (high-conviction, long-thesis)
   are removed the same way as SPECULATIVE or TACTICAL, despite representing the
   portfolio's strategic positions.
4. **Only 3 new picks from TOP 3 NEW PICKS** are added per session but they
   also accumulate indefinitely.

## Fix

### 1. Hard cap on removes from static WATCHLIST

Cap the number of static-WATCHLIST tickers that can be in the remove list at
any one time. When adding new removes, if the cap is exceeded, keep only the
most-recently-added removes (LIFO). Cap: **8 tickers** (≤ 30% of the 28-ticker
static list).

### 2. Remove expiry — adds a `removed_on` date

Each remove entry in `watchlist_overrides.json` gets a `"removed_on": "YYYY-MM-DD"`
timestamp. During `save_watchlist_overrides()`, removes older than
**N_REMOVE_EXPIRY_DAYS = 5** calendar days are dropped automatically.

Structure change:
```json
{
  "remove": [
    {"ticker": "MU",  "removed_on": "2026-03-27"},
    {"ticker": "LNG", "removed_on": "2026-03-26"}
  ]
}
```
`load_watchlist_overrides()` reads the list and filters out expired entries before
applying. Backwards-compatible: bare string entries (old format) are treated as
never-expiring until next save.

### 3. CORE-tier protection — require 3 consecutive SELL days before removing

For tickers in CORE tier, only add to removes if the ticker appeared as SELL
in the *previous* override save for that ticker as well (i.e. it was already
marked for removal and is being confirmed). A single-day SELL on a CORE ticker
does not trigger a remove. TACTICAL/SPECULATIVE/HEDGE: no protection, remove on
first SELL.

This is implemented by checking `existing.get("remove", [])` for CORE tickers
before adding them to `merged_removes`.

### 4. Add cap — limit accumulated adds to 10

When adds exceed 10 tickers, drop the oldest adds (by `added_on` date).

## Acceptance Criteria
- [ ] `watchlist_overrides.json` remove entries have `removed_on` date field
- [ ] Removes older than 5 days are automatically dropped on next `save_watchlist_overrides()`
- [ ] Total removes from static WATCHLIST capped at 8 at any time
- [ ] CORE tickers require prior-day confirmation before being added to removes
- [ ] Total adds capped at 10
- [ ] `load_watchlist_overrides()` handles both old (string) and new (dict) remove formats
- [ ] All existing watchlist override tests pass
- [ ] New tests cover: expiry, cap, CORE protection, format migration
