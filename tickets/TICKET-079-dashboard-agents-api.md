# TICKET-079 -- Dashboard Agents API

**Priority:** HIGH
**Effort:** 3 hours
**Status:** DONE
**Depends on:** TICKET-075, TICKET-076
**Files:**
- `dashboard/backend/routers/agents.py`
- `dashboard/backend/services/agent_service.py`

## Description

Implement agent reasoning endpoints:

1. `GET /api/agents/report/{ticker}/{date}` -- Parse the per-ticker markdown
   report into sections (Research Manager, Trader, Risk Judge, Bull, Bear,
   4 analysts). Split on `## ` headings. Return both full markdown and
   individual sections.

2. `GET /api/agents/reports?ticker=&date=&limit=50` -- List available reports
   by scanning `trading_loop_logs/reports/` directory structure.

3. `GET /api/agents/overrides?days=7&severity=` -- Read signal_overrides.json,
   filter and return.

4. `GET /api/agents/memory/{ticker}?agent=&limit=10` -- Read agent memory files,
   return latest N entries per agent.

## Acceptance Criteria

- [ ] Report markdown is correctly split into named sections
- [ ] Reports list is sorted by date descending
- [ ] Override filtering by severity works
- [ ] Memory endpoint returns entries from all 5 agent types
