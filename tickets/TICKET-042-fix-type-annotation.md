# TICKET-042 — Fix TradingAgentsGraph config Type Annotation

**Priority:** LOW
**Effort:** 10min
**Status:** DONE

## Problem

`TradingAgentsGraph.__init__` in `tradingagents/graph/trading_graph.py:58` has:

```python
config: Dict[str, Any] = None,
```

This is a type error — `None` is not a `Dict[str, Any]`. The correct annotation
is `Optional[Dict[str, Any]] = None`. Without this fix, mypy/pyright (if ever
enabled) will report an error here, and the annotation is actively misleading
to anyone reading the code.

## Acceptance Criteria
- [ ] `config` parameter annotated as `Optional[Dict[str, Any]] = None`
- [ ] `Optional` imported from `typing` (already imported — just needs adding)
- [ ] All existing tests pass
