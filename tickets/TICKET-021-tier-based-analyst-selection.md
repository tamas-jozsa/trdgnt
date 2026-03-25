# TICKET-021 — Tier-Based Analyst Selection

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE

## Problem

All 34 tickers run the same 4-analyst pipeline regardless of what type of play
they are. This wastes LLM calls and can produce noise:

- **SPECULATIVE** (RCAT, MOS, RCKT): meme stocks, short squeezes, biotech binary
  events. Fundamentals analysis is irrelevant — these move on momentum, social
  sentiment, and catalysts. Skip fundamentals analyst.
- **HEDGE** (GLD): gold ETF. Reddit/StockTwits sentiment is irrelevant.
  Skip social analyst.
- **CORE/TACTICAL**: run all 4 analysts (full due diligence justified).

Savings: ~25% fewer LLM calls for SPECULATIVE, ~25% for HEDGE.

## Implementation

In `analyse_and_trade()` in `trading_loop.py`, determine `selected_analysts`
based on ticker tier before creating `TradingAgentsGraph`:

```python
TIER_ANALYSTS = {
    "CORE":        ["market", "social", "news", "fundamentals"],
    "TACTICAL":    ["market", "social", "news", "fundamentals"],
    "SPECULATIVE": ["market", "social", "news"],   # skip fundamentals
    "HEDGE":       ["market", "news", "fundamentals"],  # skip social
}
```

Pass `selected_analysts` to `TradingAgentsGraph(selected_analysts=...)`.

## Acceptance Criteria
- [ ] `TIER_ANALYSTS` mapping defined in `trading_loop.py`
- [ ] `analyse_and_trade()` selects analysts based on `get_tier(ticker)`
- [ ] SPECULATIVE tickers log "[ANALYSTS] Skipping fundamentals (SPECULATIVE tier)"
- [ ] HEDGE tickers log "[ANALYSTS] Skipping social (HEDGE tier)"
- [ ] Graph compiles correctly for all 4 tier configurations
- [ ] Unit test: assert SPECULATIVE ticker uses 3 analysts, HEDGE uses 3
- [ ] All 88 tests still pass
