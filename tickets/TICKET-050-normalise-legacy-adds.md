# TICKET-050 — Normalise Legacy Add Entries Missing added_on Date

**Priority:** LOW
**Effort:** 20min
**Status:** DONE

## Problem

Add entries created before TICKET-045 deployed (SRPT, LUNR, BRZE, CORT) have
no `added_on` field in `watchlist_overrides.json`:

```json
"SRPT": {"sector": "Research Pick", "tier": "TACTICAL", "note": "..."}
```

These display as `added=?` in the dashboard and sort to the top of the
"oldest" list when the add cap fires, making them candidates for eviction
even though they may be newer than entries with proper dates.

## Fix

In `save_watchlist_overrides()`, when reading `existing_adds`, normalise any
entry missing `added_on` by stamping it with `"1970-01-01"` (epoch sentinel —
sorts before all real dates, explicitly marks it as "unknown age, treat as
oldest"). This happens once on the next save and persists from then on.

```python
existing_adds = existing.get("add", {})
for t, info in existing_adds.items():
    if "added_on" not in info:
        existing_adds[t] = {**info, "added_on": "1970-01-01"}
```

## Acceptance Criteria
- [ ] After the next `save_watchlist_overrides()` call, all add entries have an `added_on` field
- [ ] Legacy entries without a date get `"1970-01-01"` sentinel
- [ ] Entries with a real date are not modified
- [ ] Unit test: existing add without `added_on` is normalised on save
- [ ] All tests pass
