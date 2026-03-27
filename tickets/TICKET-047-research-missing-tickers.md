# TICKET-047 — Research Findings Table Silently Drops Tickers

**Priority:** LOW
**Effort:** 1h
**Status:** DONE

## Problem

The 2026-03-27 research findings table (33 rows) is missing `SOC` from the
WATCHLIST DECISIONS section. The static watchlist has 28 tickers + 4 dynamic
adds = 32 tickers; the table covered 33 rows but SOC was not among them.

This is likely caused by the research LLM (`gpt-4o-mini`) silently skipping
tickers when the watchlist string injected into the system prompt is long or
the model runs out of its output budget (`max_tokens=2000`).

The current `_build_watchlist_str()` produces a compact one-liner like:
```
NVDA[C] AVGO[C] AMD[C] ... (32 tokens) ...
```
With 32 tickers this is fine for the prompt, but the LLM is not explicitly
required to produce one row *per ticker* — it's told to "fill one row per ticker,
do not skip any" but there's no validation that enforces this.

Secondary issue: the research prompt allows `max_tokens=2000` output but a full
28-row table with reasons typically uses 900–1,100 tokens, leaving only 900–1,100
for the rest of the report. When the LLM is verbose in the macro themes or pick
descriptions, it silently truncates the table.

## Fix

### 1. Post-call validation and warning

After `call_llm()` returns, parse the findings text for the WATCHLIST DECISIONS
table and check that all tickers in the effective watchlist appear. Log a warning
listing any missing tickers:

```
[RESEARCH] Warning: 1 ticker(s) missing from findings table: SOC
```

This does not re-call the LLM — it just makes the gap visible rather than silent.

### 2. Increase max_tokens to 3000

The current 2,000-token limit is too tight when the watchlist grows with dynamic
adds. Raise to `max_tokens=3000`. Cost impact: negligible (output tokens are
0.00060/1k for gpt-4o-mini, so +1000 tokens = +$0.0006/day).

### 3. Tighten the prompt constraint

Add an explicit instruction to the system prompt:
```
CRITICAL: The WATCHLIST DECISIONS table MUST include exactly one row for EVERY
ticker listed. Tickers ({count}): {ticker_list}. Do not skip any.
```
This gives the model a concrete reference count it can check itself.

## Acceptance Criteria
- [ ] `run_daily_research()` logs a warning when any watchlist ticker is absent
      from the WATCHLIST DECISIONS table in the returned findings
- [ ] `max_tokens` raised from 2000 to 3000 in `call_llm()`
- [ ] System prompt includes explicit ticker count and list with instruction not to skip
- [ ] Unit test: `_validate_findings_coverage(findings_text, watchlist)` returns
      list of missing tickers (empty list = all present)
- [ ] All existing tests pass
