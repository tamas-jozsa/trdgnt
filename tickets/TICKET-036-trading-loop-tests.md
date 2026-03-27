# TICKET-036 — Tests for trading_loop.py Core Functions

**Priority:** HIGH
**Effort:** 2h
**Status:** DONE

## Problem

The core production logic in `trading_loop.py` has zero test coverage:
- `get_analysis_date()` — date arithmetic used every cycle
- `parse_watchlist_changes()` — regex parsing of LLM-generated markdown
- `load_watchlist_overrides()` / `save_watchlist_overrides()` — file I/O + merge logic
- `seconds_until_next_run()` — scheduling arithmetic
- Portfolio limit guard in `analyse_and_trade()` (BUY → HOLD downgrade)

These are the highest-risk untested paths — a silent bug in `get_analysis_date()`
would cause the entire pipeline to analyse the wrong day.

## Acceptance Criteria
- [ ] `TestGetAnalysisDate` — covers Mon→Fri, Tue→Mon-1, Fri→Thu, Sat→Fri, Sun→Fri
- [ ] `TestParseWatchlistChanges` — covers SELL row → remove, NEW PICKS section → add,
      both present, neither present, malformed input
- [ ] `TestLoadSaveWatchlistOverrides` — covers no file, valid file, merge (add+remove),
      ticker in both add and remove is resolved to remove
- [ ] `TestSecondsUntilNextRun` — covers before 10am (same day target), after 10am
      (next day target), Friday after 10am (skip weekend → Monday)
- [ ] `TestPortfolioLimitGuard` — mock `get_portfolio_summary` to return 20 positions,
      verify BUY is downgraded to HOLD; 19 positions → BUY is kept
- [ ] All tests use `tmp_path` for file I/O, never touch real disk state
- [ ] All tests pass
