# TICKET-007 — Position Awareness in Agent Prompts + Increase Debate Rounds

**Priority:** MEDIUM  
**Effort:** 2h  
**Status:** TODO  
**Files:** `trading_loop.py`, `tradingagents/graph/propagation.py`, `default_config.py`

## Problem

1. Agents don't know what positions are currently held. A BUY signal on a stock already
   held at -20% is treated identically to a fresh entry. The agent could blindly recommend
   adding to a losing position with no awareness of the existing exposure.

2. `max_debate_rounds=1` means Bull and Bear each speak once — two monologues, not a debate.
   The Research Manager judges based on a single unopposed argument from each side.

## Acceptance Criteria

### Position Awareness
- [ ] Before each ticker analysis, current Alpaca positions are fetched
- [ ] If a position exists for this ticker, inject into the initial state:
  `"CURRENT POSITION: Long {qty} shares @ avg ${avg_cost:.2f}, unrealised P&L: {pnl_pct:+.1f}%"`
- [ ] This context is prepended to the `company_of_interest` field or added as `position_context`
- [ ] All analyst prompts and the Research Manager receive this context
- [ ] Unit test: assert position context is non-empty when position exists

### Debate Rounds
- [ ] `max_debate_rounds` default changed from `1` → `2`
- [ ] `max_risk_discuss_rounds` default changed from `1` → `2`
- [ ] Both remain configurable via `DEFAULT_CONFIG` and CLI `--debate-rounds` arg

## Implementation

In `trading_loop.py`, before `analyse_and_trade()`:
```python
position = get_position_for_ticker(ticker)  # from alpaca_bridge
position_context = format_position_context(position)  # e.g. "Long 10 @ $142.30, P&L: -8.2%"
```

Pass `position_context` into `run_analysis()` and through to `Propagator.create_initial_state()`.

In `default_config.py`:
```python
"max_debate_rounds": 2,
"max_risk_discuss_rounds": 2,
```
