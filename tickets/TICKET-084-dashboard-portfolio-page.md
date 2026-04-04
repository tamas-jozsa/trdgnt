# TICKET-084 -- Dashboard Portfolio Page

**Priority:** HIGH
**Effort:** 4 hours
**Status:** DONE
**Depends on:** TICKET-077, TICKET-083
**Files:**
- `dashboard/frontend/src/pages/Portfolio.tsx`
- `dashboard/frontend/src/components/EquityCurve.tsx`
- `dashboard/frontend/src/components/PositionsTable.tsx`
- `dashboard/frontend/src/components/SectorPieChart.tsx`

## Description

Build the default landing page:

1. **Account Summary** -- Card grid showing equity, cash, cash ratio, day P&L,
   total P&L. Color-coded green/red for positive/negative.

2. **Equity Curve** -- Lightweight Charts line chart showing equity over time.
   Time range buttons: 1W, 1M, 3M, ALL. Fetches from `/api/portfolio/equity-history`.

3. **Positions Table** -- TanStack Table with columns: Ticker, Tier, Qty,
   Entry Price, Current Price, Market Value, P&L, P&L%, Agent Stop, Agent Target.
   Sortable by any column. Click ticker -> navigate to Agents page.

4. **Sector Pie Chart** -- Recharts pie chart showing sector allocation.

5. **Enforcement Status** -- 4 small cards: bypasses, overrides reverted,
   quota force-buys, stop-losses triggered (today's counts).

6. **Auto-refresh** every 60 seconds.

## Acceptance Criteria

- [ ] All panels render with real data from API
- [ ] Equity curve renders with time range selection
- [ ] Positions table is sortable
- [ ] Clicking ticker navigates to `/agents/{ticker}/{date}`
- [ ] Page handles empty portfolio gracefully
