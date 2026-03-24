# TICKET-008 — Parallelise the 4 Analyst Nodes

**Priority:** MEDIUM  
**Effort:** 3h  
**Status:** DONE  
**Files:** `tradingagents/graph/setup.py`, `tradingagents/graph/conditional_logic.py`

## Problem

The 4 analyst nodes (Market, Social, News, Fundamentals) run sequentially in a chain.
They are completely independent of each other — none reads the other's output. On a
34-ticker watchlist running sequentially wastes significant wall-clock time and increases
LLM API round-trip latency by ~3x unnecessarily.

## Acceptance Criteria

- [ ] All 4 selected analysts fan out from `START` in parallel LangGraph branches
- [ ] A `sync_analysts` node waits for all branches to complete before passing to Bull researcher
- [ ] Total wall-clock time for data collection phase reduces by ~60-70%
- [ ] Existing sequential behaviour is preserved when only 1-2 analysts are selected
- [ ] No race conditions in `AgentState` writes (each analyst writes to its own field)
- [ ] Integration test: run with 4 analysts and assert all 4 reports are populated

## Implementation

In `setup.py`, instead of chaining analysts:
```python
# Before (sequential):
graph.add_edge("market_analyst", "social_analyst")
graph.add_edge("social_analyst", "news_analyst")
...

# After (parallel fan-out):
for analyst in selected_analysts:
    graph.add_edge(START, analyst)
    graph.add_edge(analyst, "sync_analysts")

graph.add_node("sync_analysts", sync_analysts_node)
graph.add_edge("sync_analysts", "bull_researcher")
```

The `sync_analysts_node` is a passthrough that LangGraph will only execute once all
incoming edges (all analyst branches) have completed.

## Notes

- LangGraph supports parallel branches natively via fan-out/fan-in patterns
- Each analyst already writes to its own `AgentState` field so no write conflicts exist
- Tool call loops per analyst still work correctly in parallel branches
