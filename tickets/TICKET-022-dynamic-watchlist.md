# TICKET-022 — Dynamic Watchlist from Research Findings

**Priority:** HIGH
**Effort:** 2h
**Status:** TODO

## Problem

The watchlist is a hardcoded Python dict in `trading_loop.py`. Every day the agent
analyses the same 34 tickers regardless of what the daily research found. The research
session produces explicit ADD/REMOVE decisions in `RESEARCH_FINDINGS_*.md` but nothing
reads them. The research loop never closes — you have to manually edit `trading_loop.py`
to change tickers.

## Solution

After `daily_research.py` saves findings, parse the `### WATCHLIST DECISIONS:` table
and the `### TOP 3 NEW PICKS:` section. Apply ADD decisions (with default tier) and
REMOVE decisions to a **runtime watchlist** that overrides the static `WATCHLIST` dict
for that cycle. Persist changes to `trading_loop_logs/watchlist_overrides.json` so
they survive restarts.

## Acceptance Criteria

- [ ] `parse_watchlist_changes(findings_path)` extracts ADD and REMOVE tickers
      from the `WATCHLIST DECISIONS` table in the findings markdown
- [ ] `load_watchlist_overrides()` reads `trading_loop_logs/watchlist_overrides.json`
      and merges adds/removes into the base `WATCHLIST`
- [ ] `save_watchlist_overrides(adds, removes)` persists changes to the JSON file
- [ ] `run_daily_cycle()` calls `load_watchlist_overrides()` to get the effective
      ticker list for that cycle
- [ ] ADD tickers from `TOP 3 NEW PICKS` section added as TACTICAL tier by default
- [ ] REMOVE tickers flagged in findings are excluded from the cycle
- [ ] Dashboard watchlist panel reflects the effective (overridden) list
- [ ] `--ignore-overrides` CLI flag skips override loading (use static list)
- [ ] Unit tests: parse ADD/REMOVE from sample findings markdown
- [ ] All tests still pass

## Implementation

```python
# daily_research.py — new function
def parse_watchlist_changes(findings_text: str) -> dict:
    """Extract ADD/REMOVE tickers from WATCHLIST DECISIONS table."""
    adds = {}    # {ticker: tier}
    removes = [] # [ticker]
    # Parse | Ticker | ... | BUY/SELL rows for REMOVE signals
    # Parse TOP 3 NEW PICKS section for ADD candidates
    return {"add": adds, "remove": removes}

# trading_loop.py — new function
def get_effective_watchlist() -> dict:
    """Merge static WATCHLIST with persisted overrides."""
    overrides_path = PROJECT_ROOT / "trading_loop_logs" / "watchlist_overrides.json"
    if not overrides_path.exists():
        return dict(WATCHLIST)
    overrides = json.loads(overrides_path.read_text())
    effective = dict(WATCHLIST)
    for ticker, info in overrides.get("add", {}).items():
        if ticker not in effective:
            effective[ticker] = info
    for ticker in overrides.get("remove", []):
        effective.pop(ticker, None)
    return effective
```
