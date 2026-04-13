# TICKET-106 — Thesis Data Model and Storage

**Priority:** CRITICAL
**Effort:** 0.5 days
**Status:** TODO
**Related:** TICKET-105, TICKET-108, TICKET-110
**Spec:** docs/SPEC.md — "Data Models / Thesis Record"

## Summary

Create `src/tradingagents/thesis.py` — the central data model for
thesis-driven investing. Every position has a thesis that records why we
bought it, what catalysts to watch, and what would invalidate the investment.

## Requirements

1. **Pydantic data models:**

   ```python
   class ThesisCore(BaseModel):
       rationale: str
       key_catalysts: list[str]
       invalidation_conditions: list[str]
       sector: str
       macro_theme: str

   class ThesisTargets(BaseModel):
       price_target: float
       stop_loss: float
       trailing_stop_activation: float = 0.20
       trailing_stop_trail: float = 0.15

   class ThesisReview(BaseModel):
       next_review_date: str
       review_interval_days: int
       review_count: int = 0
       last_verdict: str | None = None  # intact | weakening | broken

   class ThesisRecord(BaseModel):
       ticker: str
       entry_date: str
       entry_price: float
       shares: float
       position_size_usd: float
       category: Literal["CORE", "TACTICAL"]
       expected_hold_months: int
       thesis: ThesisCore
       targets: ThesisTargets
       review: ThesisReview
       history: ThesisHistory  # review_history, news_events, thesis_updates
   ```

2. **ThesisStore class** (wraps RedisState):
   - `create_thesis(ticker, ...) -> ThesisRecord` — create new thesis on BUY
   - `get_thesis(ticker) -> ThesisRecord | None`
   - `get_all_theses() -> dict[str, ThesisRecord]`
   - `update_thesis(ticker, **updates)` — partial update (e.g., tighten stop)
   - `add_review(ticker, verdict, notes)` — append to review history
   - `add_news_event(ticker, event)` — append to news history
   - `remove_thesis(ticker)` — on SELL
   - `get_due_for_review(date) -> list[ThesisRecord]` — theses due for review
   - `get_by_category(category) -> list[ThesisRecord]`

3. **Thesis generation helper:**
   - `build_thesis_from_debate(ticker, research_manager_output, risk_judge_output, category) -> ThesisRecord`
   - Extracts rationale, catalysts, invalidation conditions from Research Manager text
   - Extracts target, stop-loss from Risk Judge text
   - Sets review schedule based on category

4. **Migration helper:**
   - `migrate_v1_positions(alpaca_positions, latest_reports) -> list[ThesisRecord]`
   - Converts existing v1 positions into thesis records
   - Generates initial thesis from most recent agent report per ticker

## Files

- **Create:** `src/tradingagents/thesis.py`

## Dependencies

- TICKET-105 (RedisState)
- pydantic (already in pyproject.toml)

## Tests

- Model validation (required fields, types, defaults)
- ThesisStore CRUD operations
- Review scheduling logic
- Thesis generation from debate output
- Migration from v1 positions
