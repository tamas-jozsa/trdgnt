# TICKET-112 — Refactor News Monitor with Graduated Response

**Priority:** HIGH
**Effort:** 1 day
**Status:** TODO
**Related:** TICKET-105, TICKET-106, TICKET-111
**Spec:** docs/SPEC.md — "Process 3: News Reaction Pipeline"

## Summary

Refactor `apps/news_monitor.py` to use the new graduated response pipeline
(TICKET-111) instead of spawning `trading_loop.py` subprocesses. The news
monitor becomes a self-contained process with thesis-aware triage and
conviction-gated trade execution.

## Requirements

1. **Replace subprocess spawning:**
   - v1: `_spawn_single_analysis()` runs `trading_loop.py --tickers TICKER --once`
   - v2: Call `news_debate.py` functions directly (in-process)
   - Remove all subprocess management code

2. **Integrate Redis state:**
   - Load portfolio (positions + theses) from Redis on each poll cycle
   - Push news events to Redis for dashboard visibility
   - Coordinate with discovery/review (mark tickers as analyzed)

3. **Graduated response integration:**
   ```python
   async def _process_triage_results(self, results: list[TriageResult]):
       for result in results:
           if result.severity == NewsSeverity.LOW:
               self._log_event(result)
           elif result.severity == NewsSeverity.MEDIUM:
               assessment = await self._run_quick_assessment(result)
               self._log_event(result, assessment)
           elif result.severity == NewsSeverity.HIGH:
               debate_result = await self._run_full_debate(result)
               if debate_result.conviction >= 8:
                   await self._execute_trade(debate_result)
           elif result.severity == NewsSeverity.CRITICAL:
               immediate = await self._run_immediate_assessment(result)
               if immediate.conviction >= 8:
                   await self._execute_trade(immediate)
   ```

4. **Thesis-aware triage:**
   - Pass portfolio theses to triage function
   - Triage evaluates news against thesis, not just ticker mention
   - A news item mentioning NVDA that doesn't affect our thesis → LOW
   - A news item about AI capex cuts → HIGH (directly threatens our NVDA thesis)

5. **Poll interval adjustment:**
   - Market hours (9:30-16:00 ET): every 5 minutes
   - Extended hours (6:00-20:00 ET): every 15 minutes
   - Closed/weekends: paused

6. **Trade execution:**
   - Use `alpaca_bridge.execute_decision()` for actual orders
   - On SELL: remove thesis from Redis, set cooldown
   - On BUY (rare — e.g., flash crash opportunity): create thesis, store in Redis
   - Conviction >= 8 required for any trade

7. **Event logging:**
   - All news events logged to `data/news_events/{date}.json`
   - HIGH/CRITICAL events with trade decisions logged with full reasoning
   - Push to Redis for real-time dashboard display

8. **Preserve existing functionality:**
   - Keep Reuters, Finnhub, Reddit fetchers (they work well)
   - Keep SHA-256 dedup logic
   - Keep market state detection
   - Keep daily stats tracking

## Files

- **Modify:** `apps/news_monitor.py` (major refactor)
- **Modify:** `apps/news_monitor_triage.py` (update for severity classification)

## Dependencies

- TICKET-105 (RedisState)
- TICKET-106 (ThesisStore)
- TICKET-111 (news_debate pipeline)
- Existing: alpaca_bridge, news fetchers

## Tests

- Graduated response routing (correct function called per severity)
- Thesis-aware triage (portfolio context in prompt)
- Conviction gating (trade only at >= 8)
- Redis integration (events pushed, coordination marks set)
- Poll interval adjustment by market state
