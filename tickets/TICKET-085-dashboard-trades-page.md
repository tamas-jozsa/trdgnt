# TICKET-085 -- Dashboard Trades Page

**Priority:** HIGH
**Effort:** 4 hours
**Status:** DONE
**Depends on:** TICKET-078, TICKET-083
**Files:**
- `dashboard/frontend/src/pages/Trades.tsx`
- `dashboard/frontend/src/components/TradeLog.tsx`
- `dashboard/frontend/src/components/PerformanceMetrics.tsx`
- `dashboard/frontend/src/components/PnlChart.tsx`

## Description

1. **Trade Log Table** -- TanStack Table with all trades. Columns: Date, Ticker,
   Tier, Action, Conviction, Amount, Qty, Price, Stop, Target, Source.
   Filterable by: date range (date picker), ticker (dropdown), action (BUY/SELL/HOLD).
   Paginated at 100 per page. Action column color-coded.

2. **Performance Metrics Cards** -- Win rate, avg win %, avg loss %, Sharpe ratio,
   max drawdown %, best trade, worst trade. Each in a card with large number.

3. **P&L by Ticker Chart** -- Recharts horizontal bar chart. Sortable by P&L,
   win rate, trade count (toggle buttons).

4. **P&L by Tier Chart** -- Grouped bar chart (CORE/TACTICAL/SPECULATIVE/HEDGE).

## Acceptance Criteria

- [ ] Trade log renders with all columns
- [ ] Filters work (date, ticker, action)
- [ ] Performance metrics computed and displayed
- [ ] P&L charts render with real data
- [ ] Handle zero trades gracefully
