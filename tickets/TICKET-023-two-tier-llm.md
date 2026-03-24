# TICKET-023 — Two-Tier LLM: gpt-4o for Decision Nodes

**Priority:** HIGH
**Effort:** 30 min
**Status:** TODO

## Problem

`trading_loop.py` overrides both `deep_think_llm` and `quick_think_llm` to
`gpt-4o-mini`. This defeats the two-tier design:

- **Research Manager** uses `deep_thinking_llm` — it synthesises all analyst reports
  and produces the investment plan. Getting this wrong means a bad trade.
- **Risk Judge** uses `deep_thinking_llm` — it makes the final BUY/SELL/HOLD call.

These are the two most important nodes in the pipeline and they're running on the
cheapest model. The 4 analysts (market, social, news, fundamentals) are good candidates
for `gpt-4o-mini` since they just fetch data and summarise — quality matters less there.

## Cost Impact

With current token usage (~100k in / 13k out per ticker):
- Research Manager + Risk Judge: ~15% of total tokens
- Upgrading just those two to gpt-4o costs ~$0.003/ticker extra
- Total extra per 34-ticker cycle: ~$0.10
- Annual extra at 1 cycle/day: ~$36/year

That's a very reasonable price for significantly better final decisions.

## Acceptance Criteria

- [ ] `trading_loop.py` sets `deep_think_llm = "gpt-4o"` and
      `quick_think_llm = "gpt-4o-mini"` (restore the intended split)
- [ ] `alpaca_bridge.run_analysis()` does the same
- [ ] `RESEARCH_LLM_MODEL` env var documented in `.env.example` as overriding
      the research model specifically
- [ ] Log line at cycle start: `[LLM] deep=gpt-4o  quick=gpt-4o-mini`
- [ ] Unit test: assert `TradingAgentsGraph` is instantiated with different models
      for deep vs quick clients
- [ ] All tests still pass
