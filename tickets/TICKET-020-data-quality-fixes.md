# TICKET-020 — Data Quality Fixes

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE

## Problems

### 020-A: `get_global_news` ignores `look_back_days` for actual filtering
`yfinance_news.py`: `look_back_days` is only used to display a label in the
header. Articles are never filtered by date — potentially months-old news returned.

**Fix:** Filter articles by `pub_date >= start_date` (same as `get_news_yfinance`).

### 020-B: Flat-structure yfinance articles bypass date filter
When yfinance returns flat (non-nested) article format, `pub_date` is set to None
and ALL articles pass the date filter unconditionally.

**Fix:** For flat-structure articles, try to extract `providerPublishTime` from the
root level (yfinance includes this in flat format). If not available, skip the
article rather than always including it.

### 020-C: `get_global_news` default limit is 5 — too thin
The LangChain tool definition defaults to `limit=5`. Five articles for
"current state of the world relevant to trading" is extremely thin.

**Fix:** Change default `limit` from 5 → 20 in the tool definition.

### 020-D: Dead code and imports across all agent files
Every agent file has unused imports (`time`, `json`, `AIMessage`) and a dead
`company_name = state["company_of_interest"]` assignment that's never used.

**Fix:** Remove all dead imports and dead variable assignments.

### 020-E: `PROMPT_FILE` defined but never used in `daily_research.py`
`load_research_prompt()` function exists but is never called. Docstring says
the script reads `MARKET_RESEARCH_PROMPT.md` but it doesn't.

**Fix:** Remove `PROMPT_FILE` constant and `load_research_prompt()` function,
update docstring to accurately describe what the script does.

## Acceptance Criteria
- [ ] `get_global_news` articles filtered by date using `look_back_days`
- [ ] Flat-structure articles use `providerPublishTime` or are excluded
- [ ] `get_global_news` tool default limit changed to 20
- [ ] All dead imports removed from all 12 agent files
- [ ] `load_research_prompt()` and `PROMPT_FILE` removed from daily_research.py
- [ ] All 88 tests still pass
