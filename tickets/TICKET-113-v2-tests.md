# TICKET-113 — Tests for v2 Modules

**Priority:** MEDIUM
**Effort:** 1 day
**Status:** TODO
**Related:** TICKET-105 through TICKET-112

## Summary

Create comprehensive test coverage for all new v2 modules. Tests should be
self-contained (no live API calls, no live Redis) using mocks and fixtures.

## Test Files to Create

1. **`tests/test_redis_state.py`**
   - RedisState connection and key prefixing
   - Portfolio CRUD (get/set/remove positions)
   - Coordination (analyzed_today, cooldown)
   - Event queue (push/pop news events, review flags)
   - JSON backup/restore
   - Graceful degradation when Redis unavailable

2. **`tests/test_thesis.py`**
   - ThesisRecord model validation
   - ThesisStore CRUD via Redis
   - Review scheduling (next_review_date calculation)
   - Category-based intervals (CORE=14d, TACTICAL=7d)
   - Thesis generation from debate output
   - History tracking (reviews, news events)

3. **`tests/test_screener.py`**
   - FinvizScreener with mocked HTTP responses
   - Filter application (market cap, price, volume)
   - Multiple scan strategies (volume, momentum, fundamental)
   - Deduplication across strategies
   - CompositeScreener merging
   - Rate limiting / error handling

4. **`tests/test_discovery_pipeline.py`**
   - Full pipeline with mocked components
   - Portfolio exclusion logic
   - LLM filter prompt construction and parsing
   - BUY execution flow (thesis creation, Alpaca order)
   - HOLD/SELL skip flow
   - Checkpoint save/resume
   - Dry-run mode
   - Discovery log output format

5. **`tests/test_review_agents.py`**
   - Thesis Assessor with mocked LLM
   - Parse all three verdicts (intact, weakening, broken)
   - Quick assessment (news context)
   - System prompt thesis injection
   - Confidence scoring

6. **`tests/test_portfolio_review.py`**
   - Scheduling distribution across window
   - Verdict → action mapping
   - Exit rule checks (trailing stop, catastrophic, hold period)
   - `--all` and `--ticker` overrides
   - Dry-run mode

7. **`tests/test_news_debate.py`**
   - Triage severity classification
   - Portfolio-aware triage (held vs not-held tickers)
   - Graduated response routing
   - MEDIUM quick assessment
   - HIGH full debate
   - CRITICAL immediate decision
   - Conviction gating

8. **`tests/test_news_monitor_v2.py`**
   - Graduated response integration
   - Trade execution on conviction >= 8
   - No trade on conviction < 8
   - Redis event logging
   - Poll interval by market state

## Requirements

- All tests use mocks (no live APIs, no live Redis)
- Use `fakeredis` or mock Redis for state tests
- Use `unittest.mock.patch` for LLM calls
- Use `pytest` fixtures for common setup
- Target: 80%+ coverage on new modules
- All tests pass in CI without API keys

## Files

- **Create:** 8 test files as listed above

## Dependencies

- All TICKET-105 through TICKET-112 modules
- `fakeredis` (new dev dependency)
- `pytest`, `pytest-cov` (existing)
