# TICKET-076 -- Dashboard Pydantic Response Models

**Priority:** HIGH
**Effort:** 1 hour
**Status:** DONE
**Depends on:** TICKET-075
**Files:**
- `dashboard/backend/models/schemas.py`

## Description

Define all Pydantic v2 models for API responses. Models match the schemas
defined in `dashboard/SPEC.md` API section.

Key models:
- `AccountSummary`, `Position`, `PortfolioResponse`
- `EquityPoint`, `EquityHistoryResponse`
- `TradeEntry`, `TradeListResponse`
- `PerformanceMetrics`, `TickerPerformance`, `TierPerformance`
- `AgentReport`, `ReportSection`, `ReportListEntry`
- `SignalOverride`, `OverrideListResponse`
- `ResearchFindings`, `ResearchSignal`, `WatchlistEntry`
- `QuotaEvent`, `SystemStatus`

## Acceptance Criteria

- [ ] All models importable from `dashboard.backend.models.schemas`
- [ ] All fields typed with appropriate defaults
- [ ] Optional fields use `Optional[T] = None`
