# TICKET-069 — Remove Duplicate sector_context Code

**Priority:** HIGH  
**Effort:** 15 minutes  
**Status:** DONE  
**Files:**
- `tradingagents/agents/managers/risk_manager.py`

## Problem

Lines 35-45 in risk_manager.py contain duplicate code:

```python
# TICKET-065: Get sector context
sector_context = ""
if company_name:
    from tradingagents.research_context import build_sector_context
    sector_context = build_sector_context(company_name)

# TICKET-065: Get sector context
sector_context = ""
if company_name:
    from tradingagents.research_context import build_sector_context
    sector_context = build_sector_context(company_name)
```

This is a copy-paste error from implementing TICKET-065.

## Fix

Remove the duplicate block (lines 41-45).

## Acceptance Criteria

- [ ] Remove duplicate code
- [ ] Verify Risk Judge still receives sector context
- [ ] No functional changes
