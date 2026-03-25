# TICKET-028 — Max Tool-Call Guard on Analysts

**Priority:** MEDIUM
**Effort:** 30 min
**Status:** DONE

## Problem

The 4 analyst nodes have no limit on tool-call loop iterations. The conditional
logic routes back to the analyst node every time `messages[-1].tool_calls` is truthy.
If the LLM keeps emitting tool calls (e.g. calling get_fundamentals 10 times), the
analyst loops silently until LangGraph's 100-step recursion limit kills the whole
graph with an unhandled exception.

Observed: Fundamentals analyst sometimes calls all 5 tools sequentially (get_fundamentals,
get_balance_sheet, get_cashflow, get_income_statement, get_insider_transactions) in
separate turns — that's 5 tool-call iterations + 1 report = 6 LLM calls for one analyst.
There is no guarantee it stops at 5.

## Solution

Track tool-call iteration count per analyst in state and cap it. After N tool calls,
force the analyst to write its report regardless of whether it wants to keep calling tools.

```python
# In each analyst node, before invoking the chain:
tool_call_count = state.get(f"{analyst_type}_tool_call_count", 0)
MAX_TOOL_CALLS = 6

if tool_call_count >= MAX_TOOL_CALLS:
    # Force the report — LLM has had enough tool calls
    # Invoke without tools bound so it must respond in text
    chain_no_tools = prompt | llm
    result = chain_no_tools.invoke(state["messages"])
else:
    chain = prompt | llm.bind_tools(tools)
    result = chain.invoke(state["messages"])
    if result.tool_calls:
        return {"messages": [result], f"{analyst_type}_tool_call_count": tool_call_count + 1, report_field: ""}
```

Alternatively, add `{analyst_type}_tool_call_count` to `AgentState` and increment it,
then check in `should_continue_{analyst_type}` conditional logic.

## Acceptance Criteria

- [ ] `AgentState` gains 4 new integer fields:
  `market_tool_calls`, `social_tool_calls`, `news_tool_calls`, `fundamentals_tool_calls`
- [ ] `should_continue_{type}` checks count against `MAX_ANALYST_TOOL_CALLS = 6`
- [ ] When count >= max: route to `Msg Clear` regardless of tool_calls in messages
- [ ] Each tool-call turn increments the counter in state
- [ ] Counter resets to 0 in `create_initial_state()` (fresh graph per ticker)
- [ ] `MAX_ANALYST_TOOL_CALLS` is a named constant, not a magic number
- [ ] Unit test: mock analyst that emits 10 tool calls — assert it terminates at 6
- [ ] All 115 tests still pass
