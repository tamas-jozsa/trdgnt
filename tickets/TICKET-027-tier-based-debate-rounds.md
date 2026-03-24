# TICKET-027 — Tier-Based Debate Rounds

**Priority:** MEDIUM
**Effort:** 1h
**Status:** TODO

## Problem

All 34 tickers run 2 debate rounds (4 Bull/Bear turns) + 2 risk rounds (6 risk turns)
regardless of tier. This makes no sense:

- **RCAT** (meme stock, >20% short float): a 6-round risk debate is overkill.
  It either squeezes or it doesn't. More debate doesn't improve the decision.
- **MOS** (Hormuz fertilizer thesis): one catalyst event — over-debating adds noise.
- **NVDA** (CORE, $4T company): 2 rounds of debate is justified — lots of nuance.

Running 2 rounds on SPECULATIVE tickers wastes ~40% of their LLM budget on debate
that doesn't add signal.

## Solution

Map tier to debate rounds in `analyse_and_trade()`:

```python
TIER_DEBATE_ROUNDS = {
    "CORE":        2,   # full scrutiny
    "TACTICAL":    1,   # one round enough for momentum plays
    "SPECULATIVE": 1,   # catalyst plays — don't over-debate
    "HEDGE":       1,   # GLD moves on macro, not analysis
}

TIER_RISK_ROUNDS = {
    "CORE":        2,
    "TACTICAL":    1,
    "SPECULATIVE": 1,
    "HEDGE":       1,
}
```

Pass into `TradingAgentsGraph` config per-ticker.

## Cost Impact

TACTICAL (5) + SPECULATIVE (3) + HEDGE (1) = 9 tickers at half debate cost.
Estimated saving: ~$0.05/cycle. Small but compounds over time.

## Acceptance Criteria

- [ ] `TIER_DEBATE_ROUNDS` and `TIER_RISK_ROUNDS` dicts defined in `trading_loop.py`
- [ ] `analyse_and_trade()` sets `max_debate_rounds` and `max_risk_discuss_rounds`
  in config based on ticker tier
- [ ] Log line shows rounds: `[LLM] debate=2 risk=2` or `[LLM] debate=1 risk=1`
- [ ] Unit test: assert SPECULATIVE ticker gets 1 debate round, CORE gets 2
- [ ] All 115 tests still pass
