# TICKET-054 — Agents Must Use 30-Day Own Target, Not Analyst Consensus

**Priority:** HIGH
**Effort:** 30min
**Status:** DONE

## Problem

The Risk Judge, Trader, and Research Manager are all instructed to output a
`TARGET: [30-day price target]` but agents frequently pull the Wall St analyst
consensus mean target instead of deriving their own 30-day estimate.

Examples observed:
- META: `TARGET: $862.60` — this is exactly the analyst mean target from the
  fundamentals report, representing ~61% upside from $534. No 30-day swing trade
  has a realistic 61% target.
- GOOGL: `TARGET: $314.67` — the analyst mean was $376.75, so this one was
  agent-derived (the 50-day SMA), which is correct.

Using analyst consensus targets as 30-day swing targets inflates the apparent
risk/reward ratio, which biases position sizing toward oversizing and makes the
reasoning look more compelling than it is.

## Fix

Add an explicit constraint to all three decision-agent prompts:

```
TARGET rules:
- Your TARGET must be YOUR OWN 30-day price estimate based on the technical and
  fundamental data above — NOT the Wall St analyst consensus target.
- Anchoring: use the nearest meaningful technical level (resistance, prior high,
  Bollinger upper, 50-day SMA, 200-day SMA) that could realistically be reached
  in 30 days given current momentum.
- Sanity check: a realistic 30-day swing trade target is typically 5-25% from
  the current price. Targets above 30% from current price require explicit
  justification tied to a specific near-term catalyst (earnings, product launch).
- Do NOT use the analyst mean/high price target as your TARGET.
```

Apply to: `research_manager.py`, `trader.py`, `risk_manager.py`.

## Acceptance Criteria
- [ ] All three prompts include the TARGET constraint
- [ ] Unit test: assert the constraint text appears in the prompt source
- [ ] All existing tests pass
