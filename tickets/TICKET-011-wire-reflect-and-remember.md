# TICKET-011 — Wire reflect_and_remember into Trading Loop

**Priority:** HIGH
**Effort:** 2h
**Status:** DONE
**Files:** `trading_loop.py`, `tradingagents/graph/trading_graph.py`

## Problem

`reflect_and_remember()` in `TradingAgentsGraph` exists and is fully implemented but
is never called in production. The learning system is permanently dormant:
- Memories are loaded at startup ✅
- Agents make decisions ✅
- Memories are saved after each cycle ✅
- **`reflect_and_remember()` is never called** ❌

The method requires `returns_losses` — the actual P&L of the previous trade for this
ticker. This is computable from Alpaca's position data (entry price vs current price).

## Acceptance Criteria

- [ ] `get_previous_trade_pnl(ticker)` helper reads the previous day's trade log
      and computes realised or unrealised P&L for the ticker
- [ ] After `ta.propagate()` completes, if a previous position existed:
      call `ta.reflect_and_remember(returns_losses)` with the P&L
- [ ] Memory is saved AFTER reflection (currently saved before any learning happens)
- [ ] If no prior position exists (fresh BUY): skip reflect, save memory anyway
- [ ] `reflect_and_remember()` is protected in its own try/except so a reflection
      failure never blocks the trade execution
- [ ] Unit test: mock a prior position + decision → assert reflect was called
