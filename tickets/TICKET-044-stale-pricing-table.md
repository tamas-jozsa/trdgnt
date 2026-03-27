# TICKET-044 — Update Stale OpenAI Pricing Table

**Priority:** LOW
**Effort:** 20min
**Status:** DONE

## Problem

`daily_research.py::_estimate_cost()` contains a hardcoded pricing table:

```python
PRICES = {
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o":      (0.00250, 0.01000),
    "gpt-4":       (0.03000, 0.06000),  # already stale
}
```

OpenAI changes prices regularly. The `gpt-4` entry is already stale (the model
was deprecated in 2025). More importantly, newer models (`gpt-4.1`, `o4-mini`,
`o3`) are not listed.

Since `_estimate_cost()` is used only for informational logging (not for any
decision logic), the impact is cosmetic. But a grossly wrong cost estimate can
be misleading.

## Approach

1. Update the pricing table with current OpenAI prices as of the ticket date
2. Add `gpt-4.1`, `gpt-4.1-mini`, `o4-mini`, `o3` entries
3. Remove the deprecated `gpt-4` entry
4. Add a comment with the last-updated date and a URL to the OpenAI pricing page
5. Add a fallback for unknown model names: log a warning and return `None` / `0.0`
   rather than silently returning 0 (current behaviour)

## Acceptance Criteria
- [ ] Pricing table updated with current prices (document source URL in comment)
- [ ] `gpt-4.1`, `gpt-4.1-mini`, `o4-mini`, `o3` entries added
- [ ] `gpt-4` entry removed
- [ ] Unknown model → warning logged, returns `0.0` with a note in output
- [ ] Unit test: known model returns expected cost; unknown model returns `0.0`
- [ ] All tests pass
