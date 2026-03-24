# TICKET-004 — Persist Agent Memory Across Restarts

**Priority:** HIGH  
**Effort:** 2h  
**Status:** TODO  
**Files:** `tradingagents/agents/utils/memory.py`, `trading_loop.py`, `tradingagents/graph/trading_graph.py`

## Problem

`FinancialSituationMemory` is in-process only. All 5 agent memories (bull, bear, trader,
invest_judge, risk_manager) are lost every time `trading_loop.py` restarts. `reflect_and_remember()`
is never called in the production loop at all — the entire learning system is wired up but
completely inactive in production.

## Acceptance Criteria

- [ ] `FinancialSituationMemory` gains `save(path)` and `load(path)` methods
- [ ] Situations are serialized to JSON: `[{"situation": "...", "recommendation": "..."}]`
- [ ] `trading_loop.py` calls `reflect_and_remember()` after each ticker's result is known
- [ ] Memory files are saved to `trading_loop_logs/memory/{ticker}_{agent}.json`
- [ ] On startup, memory files are loaded if they exist
- [ ] Memory grows over time; capped at 500 entries per agent per ticker (evict oldest)
- [ ] Unit test: save → delete in-memory → load → assert situations restored

## Implementation

In `memory.py`:
```python
def save(self, path: str):
    with open(path, "w") as f:
        json.dump(self.situations, f, indent=2)

def load(self, path: str):
    with open(path) as f:
        data = json.load(f)
    self.add_situations([(d["situation"], d["recommendation"]) for d in data])
```

In `trading_loop.py`, after `analyse_and_trade()` returns, call:
```python
ta.reflect_and_remember(ticker, decision, trade_date)
ta.save_memories(f"trading_loop_logs/memory/{ticker}")
```
