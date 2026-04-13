# TICKET-110 — Portfolio Review Process

**Priority:** HIGH
**Effort:** 1 day
**Status:** TODO
**Related:** TICKET-105, TICKET-106, TICKET-109
**Spec:** docs/SPEC.md — "Process 2: Portfolio Review"

## Summary

Create `apps/portfolio_review.py` — the staggered weekly process that checks
if existing holdings' investment theses still hold. Runs 2-4 reviews per day
so the entire portfolio is covered over a 2-4 week window.

## Requirements

1. **Main review function:**
   ```python
   def run_portfolio_review(
       dry_run: bool = False,
       ticker: str | None = None,  # review specific ticker
       all_holdings: bool = False,  # review everything today
   ) -> list[ReviewOutcome]:
   ```

2. **Scheduling logic:**
   - Distribute all holdings across `review.window_days` (default 10 trading days)
   - CORE positions: reviewed every `review.core_interval_days` (default 14)
   - TACTICAL positions: reviewed every `review.tactical_interval_days` (default 7)
   - Positions with last verdict "weakening": reviewed in `review.weakening_recheck_days` (default 3)
   - Sort by `next_review_date` — oldest first
   - Each day, pick the next N holdings due for review

3. **Per-ticker review flow:**
   a. Load thesis from Redis
   b. Fetch current position from Alpaca (price, P&L)
   c. Run review pipeline (TICKET-109):
      - Market Analyst → current technicals
      - Fundamentals Analyst → latest data
      - Thesis Assessor → verdict
   d. Act on verdict:
      - **INTACT:** Update `next_review_date`, log to review history
      - **WEAKENING:** Shorten review interval to 3 days, optionally tighten stop,
        flag for full debate at next discovery cycle
      - **BROKEN:** If conviction >= 8, execute SELL via Alpaca + remove thesis.
        If conviction < 8, queue for full 12-agent debate (push to review_queue in Redis)

4. **Exit rule checks** (run alongside thesis review):
   - Trailing stop: 20%+ gain, then 15% pullback from high → SELL
   - Catastrophic loss: -15% from entry → SELL + 7-day cooldown
   - Hold period exceeded: CORE > 12mo, TACTICAL > 3mo → trigger full review
   - Profit target: price >= thesis target → trigger review (update target or sell half)

5. **CLI flags:**
   ```
   --all               Review all holdings today (override schedule)
   --ticker NVDA       Review specific ticker only
   --dry-run           Analyze only, no trades
   --once              Run once then exit (default: loop daily)
   --no-wait           Skip 8 AM ET wait
   ```

6. **Output:**
   - Review report per ticker: `data/reviews/{TICKER}/{date}.json`
   - Summary log: `data/reviews/{date}-summary.json`
   - Markdown report: `trading_loop_logs/reports/{TICKER}/{date}-review.md`

## Files

- **Create:** `apps/portfolio_review.py`

## Dependencies

- TICKET-105 (RedisState)
- TICKET-106 (ThesisStore)
- TICKET-109 (review_agents)
- Existing: alpaca_bridge, Market Analyst, Fundamentals Analyst

## Tests

- Scheduling logic (correct distribution, priority ordering)
- All three verdict paths (intact, weakening, broken)
- Exit rule checks (trailing stop, catastrophic loss, hold period)
- Dry-run mode
- `--all` and `--ticker` overrides
