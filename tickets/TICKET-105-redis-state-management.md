# TICKET-105 — Redis State Management Module

**Priority:** CRITICAL
**Effort:** 0.5 days
**Status:** TODO
**Related:** TICKET-106, TICKET-108, TICKET-110, TICKET-112
**Spec:** docs/SPEC.md — "Data Models / Portfolio State (Redis)"

## Summary

Create `src/tradingagents/redis_state.py` — the shared state layer that all
three v2 processes (discovery, portfolio review, news reaction) use to
coordinate via Redis.

## Requirements

1. **RedisState class** with connection management:
   - Connect via `REDIS_URL` env var (default `redis://localhost:6379/0`)
   - Key prefix `trdagnt:` to avoid collisions
   - Graceful fallback if Redis is unavailable (log warning, degrade to no-op)
   - Connection pooling for concurrent access

2. **Portfolio state operations:**
   - `get_positions() -> dict[str, ThesisRecord]` — all current positions
   - `get_position(ticker) -> ThesisRecord | None` — single position
   - `set_position(ticker, thesis)` — create/update position
   - `remove_position(ticker)` — remove on sell
   - `get_cash() -> float` — current cash balance
   - `set_cash(amount)` — update cash
   - `get_portfolio_value() -> float` — total portfolio value
   - `get_sector_exposure() -> dict[str, float]` — sector → % of portfolio

3. **Coordination operations:**
   - `mark_analyzed_today(ticker)` — prevent duplicate analysis
   - `was_analyzed_today(ticker) -> bool`
   - `set_cooldown(ticker, days)` — block re-buy after stop-loss
   - `is_in_cooldown(ticker) -> bool`
   - `clear_daily_coordination()` — reset at start of new day

4. **Event queue operations:**
   - `push_news_event(event)` — news monitor → queue
   - `pop_news_events() -> list` — consumer drains queue
   - `push_review_flag(ticker, reason)` — flag for accelerated review
   - `pop_review_flags() -> list`

5. **JSON file backup:**
   - Every write to Redis also writes a JSON backup to `data/` directory
   - On startup, if Redis is empty, load from JSON backups (migration path)

## Files

- **Create:** `src/tradingagents/redis_state.py`

## Dependencies

- `redis` (already in pyproject.toml)

## Tests

- Unit tests with fakeredis or mocked Redis
- Test graceful degradation when Redis unavailable
- Test JSON backup/restore round-trip
