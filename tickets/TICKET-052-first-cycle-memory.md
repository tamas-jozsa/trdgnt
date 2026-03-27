# TICKET-052 — Seed Memory on First Cycle Without P&L

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE

## Problem

Memory is only written via `reflect_and_remember()`, which requires prior P&L data
(`_build_returns_losses_summary()` must return a non-empty string). On the first
time a ticker is analysed, there is no prior position and no prior trade log entry,
so reflection is skipped with `"No prior P&L data — skipping reflection"` and
all 5 memory files are saved as `[]`.

The result is that memory is always one full cycle behind. After the first cycle
the analysis has been done — the bull case, bear case, and risk judgement are
available in `final_state` — but none of it is retained. The second cycle starts
with zero memory just like the first.

## Fix

After each completed analysis (regardless of whether there's P&L data), write
a "seed" memory entry derived from the current cycle's analysis results. This
uses the existing `reflect_and_remember()` path — the only change is that we
construct a synthetic `returns_losses` string from the current decision when
no real P&L is available.

In `trading_loop.py::analyse_and_trade()`, after the decision is made:

```python
returns_losses = _build_returns_losses_summary(ticker)
if not returns_losses:
    # No prior P&L — seed memory with today's decision as context
    returns_losses = (
        f"First analysis of {ticker} on {trade_date}. "
        f"Decision: {decision}. "
        f"No prior position. "
        f"Seed memory for future cycles."
    )
    print(f"  [REFLECT] Seeding first-cycle memory for {ticker} with decision context")
ta.reflect_and_remember(returns_losses)
```

This ensures agents at least have one memory entry after the first cycle that
records the decision context — so the second cycle's agents can retrieve it
and avoid repeating identical reasoning.

## Acceptance Criteria
- [ ] After a first-cycle analysis, all 5 memory files have ≥1 entry
- [ ] The seed entry `situation` contains the analyst reports from the current cycle
- [ ] The seed entry `recommendation` contains a reflection on the decision made
- [ ] Subsequent cycles that have real P&L still use the real P&L path
- [ ] `[REFLECT] Seeding first-cycle memory` is logged when the seed path fires
- [ ] Unit test: after `analyse_and_trade` with no prior position, memory files are non-empty
- [ ] All tests pass
