# TICKET-086 -- Dashboard Agents Page

**Priority:** HIGH
**Effort:** 5 hours
**Status:** DONE
**Depends on:** TICKET-079, TICKET-083
**Files:**
- `dashboard/frontend/src/pages/Agents.tsx`
- `dashboard/frontend/src/components/AgentPipeline.tsx`
- `dashboard/frontend/src/components/ReportViewer.tsx`
- `dashboard/frontend/src/components/OverrideLog.tsx`

## Description

The most complex page -- full agent reasoning visibility.

1. **Ticker + Date Selector** -- Two dropdowns populated from `/api/agents/reports`.
   URL synced: `/agents/:ticker/:date`. Defaults to latest report.

2. **Decision Header** -- Large display of BUY/SELL/HOLD with conviction badge,
   stop price, target price. Color-coded.

3. **Agent Pipeline Visualization** -- CSS/SVG flow diagram showing:
   - 4 analyst nodes (with signal badges)
   - Bull/Bear debate nodes (with conviction scores)
   - Research Manager node (decision + conviction)
   - Trader node
   - Bypass check (highlighted if triggered)
   - 3 Risk debater nodes
   - Risk Judge node (final decision)
   - Override check (highlighted if reverted)
   Each node color-coded: green=BUY, red=SELL, gray=HOLD.

4. **Report Viewer** -- Full markdown report rendered with react-markdown.
   Collapsible accordion sections: Research Manager, Trader, Risk Judge,
   Bull Case, Bear Case, Market, Social, News, Fundamentals.

5. **Override Log** -- Filtered to selected ticker. Shows severity, upstream
   signal, final signal, reverted status.

6. **Agent Memory** -- Latest 5 lessons from each agent type for selected ticker.

## Acceptance Criteria

- [ ] Ticker/date selection loads correct report
- [ ] Pipeline visualization shows all 12 nodes with signals
- [ ] Bypass and override branches highlighted when applicable
- [ ] Markdown renders correctly with tables and formatting
- [ ] Accordion sections expand/collapse
- [ ] Override log shows ticker-specific overrides
