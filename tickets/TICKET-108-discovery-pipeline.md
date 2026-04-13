# TICKET-108 — Discovery Pipeline

**Priority:** HIGH
**Effort:** 1 day
**Status:** TODO
**Related:** TICKET-105, TICKET-106, TICKET-107
**Spec:** docs/SPEC.md — "Process 1: Discovery Pipeline"

## Summary

Create `apps/discovery_pipeline.py` — the daily process that screens all US
equities for new investment candidates, filters them through an LLM, runs the
full 12-agent debate on top picks, and executes BUY orders with recorded theses.

This replaces the static WATCHLIST + daily re-debate pattern from v1.

## Requirements

1. **Main pipeline function:**
   ```python
   def run_discovery(
       dry_run: bool = False,
       max_candidates: int = 15,
       once: bool = False,
       no_wait: bool = False,
   ) -> DiscoveryResult:
   ```

2. **Pipeline stages:**

   a. **Daily research** — call `daily_research.run_daily_research()` for macro context

   b. **Screen** — call `screener.scan()` → 50-100 raw candidates

   c. **Exclude** — remove tickers that are:
      - Already in portfolio (from Redis)
      - In cooldown (recently sold / stop-loss triggered)
      - Debated in last N days (`discovery.lookback_days`, default 7)

   d. **LLM filter** — send candidates + macro context + portfolio gaps to
      `gpt-4o-mini` with structured output:
      - Rank by fit with current macro themes
      - Identify portfolio gaps (sector underweight, missing themes)
      - Select top 10-15 for full debate
      - Return with brief rationale per candidate

   e. **Full 12-agent debate** — for each selected candidate:
      - Create `TradingAgentsGraph` with appropriate config
      - Call `propagate()` with macro context
      - Process signal (BUY/HOLD/SELL)

   f. **Execute BUY decisions:**
      - Build thesis from debate output (TICKET-106)
      - Determine category (CORE/TACTICAL) from Research Manager assessment
      - Calculate position size: `base × category_multiplier × risk_judge_size`
      - Execute via `alpaca_bridge.execute_decision()`
      - Store thesis in Redis
      - Mark ticker as analyzed today

   g. **Save discovery log** to `data/discovery/{date}.json`

3. **Scheduling:**
   - Runs at 9:00 AM ET weekdays (same as v1)
   - `--once` flag for single run
   - `--no-wait` flag to skip time-of-day wait
   - Internal scheduler with weekend skip

4. **CLI flags:**
   ```
   --once              Run one cycle then exit
   --no-wait           Skip 9 AM ET wait
   --dry-run           Analyze only, no orders
   --max-candidates N  Override max debate candidates (default 15)
   --parallel N        Parallel workers for debate phase (default 1)
   ```

5. **Crash recovery:**
   - Checkpoint after each debated ticker
   - On restart, skip already-debated tickers for today

## Files

- **Create:** `apps/discovery_pipeline.py`

## Dependencies

- TICKET-105 (RedisState)
- TICKET-106 (ThesisStore)
- TICKET-107 (Screener)
- Existing: TradingAgentsGraph, alpaca_bridge, daily_research

## Tests

- Full pipeline with mocked screener + mocked LLM + mocked Alpaca
- Portfolio exclusion logic
- LLM filter prompt construction
- Thesis creation from debate output
- Checkpoint save/resume
- Dry-run mode (no orders, no thesis creation)
