# TICKET-005 — Inject Daily Research Findings into Agent Context

**Priority:** HIGH  
**Effort:** 2h  
**Status:** DONE  
**Files:** `trading_loop.py`, `tradingagents/graph/trading_graph.py`, `tradingagents/graph/propagation.py`

## Problem

The daily `MARKET_RESEARCH_PROMPT.md` session produces rich macro intelligence
(`results/RESEARCH_FINDINGS_*.md`) that the trading agents completely ignore. Agents
rediscover macro context from scratch via shallow yfinance news calls, often missing
the Iran war, copper deficit, meme stock setups, etc. that were already researched.

## Acceptance Criteria

- [ ] `load_latest_research_context(results_dir)` reads the most recent `RESEARCH_FINDINGS_*.md`
- [ ] Extracts: macro themes section, full ticker decision table, sectors to avoid
- [ ] Returns a condensed string (max 2000 tokens)
- [ ] `AgentState` gains a `macro_context: str` field (empty string if no file found)
- [ ] All 4 analyst system prompts prepend: `"CURRENT MACRO CONTEXT (from daily research):\n{macro_context}\n\n"`
- [ ] Research Manager and Risk Judge also receive `macro_context`
- [ ] If no findings file exists: agents run normally with no context (graceful degradation)
- [ ] Unit test: assert context is loaded and non-empty when file exists

## Implementation

```python
def load_latest_research_context(results_dir: str = "results") -> str:
    files = sorted(Path(results_dir).glob("RESEARCH_FINDINGS_*.md"), reverse=True)
    if not files:
        return ""
    text = files[0].read_text()
    # Extract top macro themes + ticker decision table
    ...
    return truncated_context  # max ~2000 tokens
```

Inject into `Propagator.create_initial_state()` as `macro_context` field.
Pass through to each analyst node in `setup.py`.
