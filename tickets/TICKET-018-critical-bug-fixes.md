# TICKET-018 — Critical Bug Fixes

**Priority:** CRITICAL
**Effort:** 30 min
**Status:** DONE

## Bugs

### 018-A: `DEFAULT_TICKERS` doesn't exist — watchlist prices never reach the LLM
`daily_research.py:132` imports `DEFAULT_TICKERS` from `trading_loop` but only
`WATCHLIST` (a dict) exists there. `fetch_watchlist_prices()` silently returns `""`
every run — the LLM never sees live price/volume data for the watchlist.

**Fix:** Replace `from trading_loop import DEFAULT_TICKERS` with
`from trading_loop import WATCHLIST` and use `list(WATCHLIST.keys())`.

### 018-B: `default_config.py` has non-existent model names
`"deep_think_llm": "gpt-5.2"` and `"quick_think_llm": "gpt-5-mini"` don't exist.
Any code using DEFAULT_CONFIG without overriding fails immediately.

**Fix:** Change defaults to `"gpt-4o"` (deep) and `"gpt-4o-mini"` (quick).

### 018-C: Global SSL verification disabled for entire process
`trading_loop.py:31-53` monkey-patches `requests.Session.__init__` to disable SSL
verification for ALL HTTP connections including OpenAI API calls. Security risk.

**Fix:** Scope the SSL bypass only to the `update_positions.py` / Alpaca calls
that need it (Alpaca's paper API has SSL issues). Remove global monkey-patch.

## Acceptance Criteria
- [ ] `fetch_watchlist_prices()` returns a populated table with 34 ticker rows
- [ ] `DEFAULT_CONFIG` uses real model names that the OpenAI API accepts
- [ ] SSL monkey-patch removed from `trading_loop.py`; Alpaca calls still work
- [ ] All 88 tests still pass
