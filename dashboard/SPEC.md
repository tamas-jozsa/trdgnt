# trdagnt Dashboard -- Specification

> Version 1.0 -- April 2026

---

## Overview

A local web dashboard for the trdagnt trading system. Provides real-time
portfolio monitoring, trade history with performance analytics, full agent
reasoning visibility, research context browsing, and a control panel for
system management.

**Stack:** FastAPI (Python) + React (TypeScript, Vite) + WebSocket live updates

**Access:** `http://localhost:8080` -- accessible from any device on the local network.

**Design principle:** Read existing data files directly (JSON, Markdown). No
database. No data migration. The backend imports existing Python modules
(`alpaca_bridge`, `trading_loop`, `research_context`) for live data.

---

## Architecture

```
                 +-------------------------------------------+
                 |              React Frontend               |
                 |          (Vite + TypeScript)              |
                 |                                           |
                 |  Portfolio | Trades | Agents | Research   |
                 |  Control                                  |
                 |                                           |
                 |  Charts: Lightweight Charts (TradingView) |
                 |  Tables: TanStack Table                   |
                 |  Markdown: react-markdown                 |
                 |  Styling: Tailwind CSS                    |
                 +-------------------+-----------------------+
                                     |
                          REST API + WebSocket
                          http://localhost:8080
                                     |
                 +-------------------+-----------------------+
                 |             FastAPI Backend               |
                 |              (Python 3.13)                |
                 |                                           |
                 |  /api/portfolio    live positions + equity |
                 |  /api/trades       trade log + metrics    |
                 |  /api/agents       reports + overrides    |
                 |  /api/research     findings + watchlist   |
                 |  /api/control      actions + config       |
                 |  /ws/live          real-time log stream   |
                 |                                           |
                 |  Reads:                                   |
                 |    trading_loop_logs/*.json                |
                 |    trading_loop_logs/reports/*/*.md        |
                 |    results/RESEARCH_FINDINGS_*.md          |
                 |    positions.json                          |
                 |                                           |
                 |  Imports:                                  |
                 |    alpaca_bridge (live portfolio)          |
                 |    trading_loop (watchlist, tiers)         |
                 |    tradingagents.research_context          |
                 |    tradingagents.buy_quota                 |
                 |    tradingagents.signal_override           |
                 |    tradingagents.sector_monitor            |
                 +-------------------------------------------+
                                     |
                          Reads filesystem directly
                                     |
                 +-------------------------------------------+
                 |          Existing trdagnt Runtime          |
                 |                                           |
                 |  trading_loop_logs/                        |
                 |    YYYY-MM-DD.json       (trade logs)     |
                 |    signal_overrides.json                   |
                 |    buy_quota_log.json                      |
                 |    position_entries.json                   |
                 |    watchlist_overrides.json                |
                 |    stop_loss_history.json                  |
                 |    stdout.log / stderr.log                 |
                 |    reports/{TICKER}/{DATE}.md              |
                 |    memory/{TICKER}/*.json                  |
                 |                                           |
                 |  positions.json                            |
                 |  results/RESEARCH_FINDINGS_*.md            |
                 +-------------------------------------------+
```

---

## File Structure

```
dashboard/
+-- SPEC.md                    # This file
+-- backend/
|   +-- main.py                # FastAPI app entry point, CORS, lifespan
|   +-- config.py              # Paths, constants, settings
|   +-- routers/
|   |   +-- portfolio.py       # /api/portfolio endpoints
|   |   +-- trades.py          # /api/trades endpoints
|   |   +-- agents.py          # /api/agents endpoints
|   |   +-- research.py        # /api/research endpoints
|   |   +-- control.py         # /api/control endpoints
|   +-- services/
|   |   +-- portfolio_service.py   # Read positions, compute metrics
|   |   +-- trade_service.py       # Read trade logs, compute performance
|   |   +-- agent_service.py       # Read reports, overrides, memory
|   |   +-- research_service.py    # Read findings, watchlist changes
|   |   +-- log_streamer.py        # Tail stdout.log for WebSocket
|   +-- models/
|   |   +-- schemas.py         # Pydantic response models
|   +-- requirements.txt       # Backend Python dependencies
+-- frontend/
|   +-- package.json
|   +-- vite.config.ts
|   +-- tsconfig.json
|   +-- tailwind.config.js
|   +-- index.html
|   +-- src/
|       +-- main.tsx           # React entry point
|       +-- App.tsx            # Router + layout
|       +-- api/
|       |   +-- client.ts      # Fetch wrapper + WebSocket hook
|       +-- pages/
|       |   +-- Portfolio.tsx   # Portfolio page
|       |   +-- Trades.tsx      # Trade history + performance
|       |   +-- Agents.tsx      # Agent reasoning viewer
|       |   +-- Research.tsx    # Research findings browser
|       |   +-- Control.tsx     # Control panel
|       +-- components/
|       |   +-- Layout.tsx      # Nav bar + page shell
|       |   +-- EquityCurve.tsx # Lightweight Charts wrapper
|       |   +-- PositionsTable.tsx
|       |   +-- TradeLog.tsx
|       |   +-- PerformanceMetrics.tsx
|       |   +-- PnlChart.tsx
|       |   +-- AgentPipeline.tsx     # Visual pipeline flow
|       |   +-- ReportViewer.tsx      # Markdown renderer
|       |   +-- OverrideLog.tsx
|       |   +-- SectorPieChart.tsx
|       |   +-- LiveFeed.tsx          # WebSocket log stream
|       |   +-- WatchlistEditor.tsx
|       +-- hooks/
|       |   +-- useWebSocket.ts
|       |   +-- usePolling.ts
|       +-- types/
|           +-- index.ts       # TypeScript interfaces matching Pydantic models
```

---

## API Specification

### Portfolio Endpoints

#### `GET /api/portfolio`

Returns current portfolio state with positions and account summary.

**Response:**
```json
{
  "updated_at": "2026-04-03T14:00:01Z",
  "account": {
    "equity": 100256.92,
    "cash": 77986.69,
    "buying_power": 178243.61,
    "cash_ratio": 0.778,
    "day_pnl": 142.30,
    "day_pnl_pct": 0.14,
    "total_pnl": 256.92,
    "total_pnl_pct": 0.26
  },
  "positions": [
    {
      "ticker": "AMD",
      "sector": "AI & Semiconductors",
      "tier": "CORE",
      "qty": 15.23,
      "avg_entry_price": 205.19,
      "current_price": 217.50,
      "market_value": 3312.52,
      "unrealized_pl": 187.48,
      "unrealized_pl_pct": 6.0,
      "agent_stop": 190.00,
      "agent_target": 240.00,
      "entry_date": "2026-04-01"
    }
  ],
  "sector_exposure": {
    "TECHNOLOGY": 0.45,
    "DEFENSE": 0.20,
    "ENERGY": 0.15,
    "MATERIALS": 0.10,
    "HEDGE": 0.10
  },
  "enforcement": {
    "bypasses_today": 3,
    "overrides_reverted_today": 1,
    "quota_force_buys_today": 2,
    "stop_losses_today": 0
  }
}
```

**Data sources:** `positions.json`, `trading_loop_logs/position_entries.json`,
`trading_loop_logs/signal_overrides.json`, `trading_loop_logs/buy_quota_log.json`,
live Alpaca via `alpaca_bridge.get_portfolio_summary()` (optional, falls back to
cached `positions.json`).

#### `GET /api/portfolio/equity-history`

Returns daily equity snapshots for charting.

**Query params:** `days` (default 30)

**Response:**
```json
{
  "data": [
    { "date": "2026-03-23", "equity": 100000.00, "cash": 100000.00, "invested": 0 },
    { "date": "2026-03-24", "equity": 99980.50, "cash": 98500.00, "invested": 1480.50 },
    ...
  ]
}
```

**Data source:** Derived from daily trade logs. On first run, reconstructs from
trade history. Future: cache to `trading_loop_logs/equity_history.json`.

---

### Trades Endpoints

#### `GET /api/trades`

Returns trade log with optional filtering.

**Query params:**
- `date_from` (YYYY-MM-DD, optional)
- `date_to` (YYYY-MM-DD, optional)
- `ticker` (optional)
- `action` (BUY|SELL|HOLD, optional)
- `limit` (default 100)
- `offset` (default 0)

**Response:**
```json
{
  "total": 245,
  "trades": [
    {
      "date": "2026-04-03",
      "time": "2026-04-03T15:07:25Z",
      "ticker": "AMD",
      "tier": "CORE",
      "decision": "BUY",
      "conviction": 8,
      "size_multiplier": 1.5,
      "amount_usd": 3000.00,
      "qty": 15.23,
      "price": 205.19,
      "agent_stop": 190.00,
      "agent_target": 240.00,
      "order_id": "abc-123",
      "status": "filled",
      "source": "normal"
    }
  ]
}
```

**Data source:** `trading_loop_logs/YYYY-MM-DD.json` (all date files scanned).

#### `GET /api/trades/performance`

Returns aggregate performance metrics.

**Query params:** `days` (default 30)

**Response:**
```json
{
  "period_days": 30,
  "total_trades": 55,
  "buys": 34,
  "sells": 8,
  "holds": 13,
  "win_rate": 0.62,
  "avg_win_pct": 8.2,
  "avg_loss_pct": -4.1,
  "best_trade": { "ticker": "NVDA", "pnl_pct": 22.1, "date": "2026-04-01" },
  "worst_trade": { "ticker": "RCKT", "pnl_pct": -15.0, "date": "2026-03-28" },
  "sharpe_ratio": 0.8,
  "max_drawdown_pct": -3.2,
  "total_pnl": 256.92,
  "by_ticker": [
    { "ticker": "NVDA", "trades": 5, "pnl": 440.00, "win_rate": 0.80 },
    { "ticker": "AMD", "trades": 3, "pnl": 187.48, "win_rate": 0.67 }
  ],
  "by_tier": [
    { "tier": "CORE", "trades": 40, "pnl": 380.00, "win_rate": 0.65 },
    { "tier": "TACTICAL", "trades": 10, "pnl": -30.00, "win_rate": 0.40 }
  ]
}
```

**Data source:** Computed from daily trade logs + `positions.json` for unrealized P&L.

---

### Agents Endpoints

#### `GET /api/agents/report/{ticker}/{date}`

Returns the full agent analysis report for a ticker on a given date.

**Response:**
```json
{
  "ticker": "NVDA",
  "date": "2026-04-03",
  "decision": "BUY",
  "conviction": 8,
  "report_markdown": "# NVDA -- 2026-04-03\n\n## Decision: BUY\n...",
  "sections": {
    "research_manager": "RECOMMENDATION: BUY\nCONVICTION: 8\n...",
    "trader": "FINAL TRANSACTION PROPOSAL: **BUY**\n...",
    "risk_judge": "FINAL DECISION: BUY\nCONVICTION: 7\n...",
    "bull_case": "## Growth Thesis\n...",
    "bear_case": "## Risk Factors\n...",
    "market_analyst": "## Market Analysis\n...",
    "social_analyst": "## Social Sentiment\n...",
    "news_analyst": "## News Analysis\n...",
    "fundamentals_analyst": "## Fundamental Analysis\n..."
  },
  "bypass": { "triggered": true, "reason": "high_conviction_buy (conv=8, cash=85%)" },
  "override": null
}
```

**Data source:** `trading_loop_logs/reports/{TICKER}/{DATE}.md` (parsed into sections).

#### `GET /api/agents/reports`

Returns a list of available reports for browsing.

**Query params:** `ticker` (optional), `date` (optional), `limit` (default 50)

**Response:**
```json
{
  "reports": [
    { "ticker": "NVDA", "date": "2026-04-03", "decision": "BUY", "conviction": 8 },
    { "ticker": "AMD", "date": "2026-04-03", "decision": "BUY", "conviction": 7 },
    ...
  ]
}
```

#### `GET /api/agents/overrides`

Returns signal override history.

**Query params:** `days` (default 7), `severity` (optional: critical|high|medium)

**Response:**
```json
{
  "total": 33,
  "by_severity": { "critical": 11, "high": 15, "medium": 7 },
  "overrides": [
    {
      "timestamp": "2026-04-02T15:10:02Z",
      "ticker": "NOC",
      "upstream_signal": "SELL",
      "upstream_conviction": 8,
      "final_signal": "HOLD",
      "final_conviction": 7,
      "cash_ratio": 0.867,
      "severity": "high",
      "reverted": false,
      "reason": "The conservative analyst..."
    }
  ]
}
```

**Data source:** `trading_loop_logs/signal_overrides.json`.

#### `GET /api/agents/memory/{ticker}`

Returns agent memory entries for a ticker.

**Query params:** `agent` (optional: bull|bear|trader|invest_judge|risk_manager), `limit` (default 10)

**Response:**
```json
{
  "ticker": "NVDA",
  "agents": {
    "bull_memory": {
      "count": 12,
      "latest": [
        { "situation": "RSI was 30, MACD crossing up...", "recommendation": "BUY was correct..." }
      ]
    }
  }
}
```

**Data source:** `trading_loop_logs/memory/{TICKER}/*.json`.

---

### Research Endpoints

#### `GET /api/research/findings`

Returns the latest research findings.

**Query params:** `date` (optional, defaults to latest)

**Response:**
```json
{
  "date": "2026-04-03",
  "markdown": "## RESEARCH FINDINGS -- 2026-04-03\n...",
  "sentiment": "BULLISH",
  "vix": 23.87,
  "vix_trend": "FALLING",
  "signals": {
    "NVDA": { "decision": "HOLD", "conviction": "MEDIUM", "reason": "..." },
    "AMD": { "decision": "BUY", "conviction": "HIGH", "reason": "..." }
  },
  "sector_signals": {
    "DEFENSE": "FAVOR",
    "TECHNOLOGY": "NEUTRAL"
  },
  "new_picks": ["RGC", "CAR", "FSLY"],
  "available_dates": ["2026-04-03", "2026-04-02", "2026-04-01", ...]
}
```

**Data source:** `results/RESEARCH_FINDINGS_YYYY-MM-DD.md` parsed via
`research_context.py`.

#### `GET /api/research/watchlist`

Returns current watchlist state including dynamic overrides.

**Response:**
```json
{
  "static_count": 34,
  "effective_count": 41,
  "tickers": [
    { "ticker": "NVDA", "sector": "AI & Semiconductors", "tier": "CORE", "note": "...", "source": "static" },
    { "ticker": "LUNR", "sector": "Research Pick", "tier": "TACTICAL", "note": "...", "source": "dynamic", "added_on": "2026-04-03" }
  ],
  "overrides": {
    "adds": { "LUNR": { "sector": "Research Pick", "tier": "TACTICAL", "added_on": "2026-04-03" } },
    "removes": [{ "ticker": "RCAT", "removed_on": "2026-04-03" }]
  }
}
```

**Data source:** `trading_loop.py:WATCHLIST` + `trading_loop_logs/watchlist_overrides.json`.

#### `GET /api/research/quota`

Returns buy quota enforcement history.

**Response:**
```json
{
  "total_misses": 3,
  "recent": [
    {
      "timestamp": "2026-04-02T17:19:25Z",
      "cash_ratio": 0.833,
      "high_conviction_signals": 9,
      "buys_executed": 2,
      "quota_met": false,
      "missed_opportunities": ["AVGO", "AMD", "GOOGL"],
      "force_buy_tickers": ["AVGO", "AMD"]
    }
  ]
}
```

**Data source:** `trading_loop_logs/buy_quota_log.json`.

---

### Control Endpoints

#### `POST /api/control/run`

Trigger a trading cycle.

**Request body:**
```json
{
  "mode": "normal",
  "tickers": null,
  "dry_run": false
}
```

`mode`: `"normal"` (full cycle), `"single"` (single ticker, requires `tickers: ["NVDA"]`),
`"dry_run"` (analyse only).

**Response:**
```json
{
  "status": "started",
  "pid": 12345,
  "mode": "normal",
  "tickers": 34
}
```

**Implementation:** Spawns `trading_loop.py --once --no-wait` (or `--dry-run`,
or `--tickers X`) as a subprocess. Returns PID for monitoring.

#### `POST /api/control/research`

Force a daily research refresh.

**Response:**
```json
{ "status": "started", "pid": 12346 }
```

**Implementation:** Spawns `daily_research.py --force`.

#### `POST /api/control/sync-positions`

Sync positions from Alpaca.

**Response:**
```json
{ "status": "done", "positions": 8, "equity": 100256.92 }
```

**Implementation:** Calls `update_positions.py` directly (import, no subprocess).

#### `GET /api/control/status`

Returns system status.

**Response:**
```json
{
  "agent_running": true,
  "agent_pid": 4521,
  "last_cycle": "2026-04-03T10:02:15Z",
  "next_cycle": "2026-04-04T10:00:00Z",
  "cycle_in_progress": false,
  "tickers": 34,
  "cash_ratio": 0.778,
  "open_positions": 8,
  "today_trades": { "buy": 5, "sell": 1, "hold": 28 },
  "today_research_done": true,
  "uptime_hours": 247
}
```

#### `POST /api/control/watchlist`

Add or remove a ticker from the dynamic watchlist.

**Request body:**
```json
{
  "action": "add",
  "ticker": "AAPL",
  "tier": "TACTICAL",
  "sector": "AI Software & Cloud",
  "note": "Manual add via dashboard"
}
```

Or:
```json
{
  "action": "remove",
  "ticker": "RCAT"
}
```

**Implementation:** Writes to `trading_loop_logs/watchlist_overrides.json`
using the existing override format.

---

### WebSocket

#### `WS /ws/live`

Streams real-time events to the frontend.

**Message types:**

```json
{ "type": "log", "text": "[TRADINGAGENTS] Analysing AMD for 2026-04-03 ..." }
{ "type": "trade", "ticker": "AMD", "decision": "BUY", "conviction": 8 }
{ "type": "override", "ticker": "NOC", "severity": "high", "reverted": false }
{ "type": "stop_loss", "ticker": "RCKT", "pnl_pct": -15.2 }
{ "type": "quota", "force_buys": ["AVGO", "AMD"] }
{ "type": "cycle_start", "tickers": 34, "date": "2026-04-03" }
{ "type": "cycle_end", "buys": 5, "sells": 1, "holds": 28, "elapsed_min": 187 }
{ "type": "ticker_progress", "ticker": "AMD", "index": 3, "total": 34, "status": "analysing" }
```

**Implementation:** Backend tails `trading_loop_logs/stdout.log` using
`asyncio` file watcher, parses known line patterns into typed messages,
and broadcasts to all connected WebSocket clients.

---

## Frontend Pages

### Page 1: Portfolio (default landing page)

**URL:** `/` or `/portfolio`

**Layout:**
```
+----------------------------+----------------------------------+
|  EQUITY CURVE              |  ACCOUNT SUMMARY                 |
|  (Lightweight Charts)      |  Equity / Cash / Invested / P&L  |
|  [1W] [1M] [3M] [ALL]     |  Day P&L with color coding       |
+----------------------------+----------------------------------+
|  OPEN POSITIONS TABLE (sortable, click to go to Agents page)  |
|  Ticker | Tier | Qty | Entry | Current | P&L | P&L% | Stop    |
+----------------------------+----------------------------------+
|  SECTOR PIE CHART          |  ENFORCEMENT STATUS CARDS        |
|  (Recharts)                |  Bypasses / Overrides / Quota    |
+----------------------------+----------------------------------+
```

**Polling:** Refresh every 60 seconds via `usePolling` hook.

### Page 2: Trades

**URL:** `/trades`

**Layout:**
```
+----------------------------+----------------------------------+
|  TRADE LOG TABLE           |  PERFORMANCE METRICS CARDS       |
|  (TanStack Table)          |  Win rate / Sharpe / Drawdown    |
|  Filterable by date,       |  Avg win / Avg loss              |
|  ticker, action            |  Best trade / Worst trade        |
|  Paginated (100/page)      |                                  |
+----------------------------+----------------------------------+
|  P&L BY TICKER (horizontal bar chart, Recharts)               |
|  Sortable by P&L, win rate, trade count                       |
+----------------------------------------------------------------+
|  P&L BY TIER (grouped bar chart)                               |
+----------------------------------------------------------------+
```

### Page 3: Agents (reasoning viewer)

**URL:** `/agents` or `/agents/:ticker/:date`

**Layout:**
```
+----------------------------+----------------------------------+
|  TICKER + DATE SELECTOR    |  AGENT PIPELINE VISUALIZATION    |
|  [NVDA v] [Apr 03 v]      |  Visual flow: 4 analysts ->      |
|                            |  bull/bear -> RM -> trader ->    |
|  DECISION: BUY             |  [bypass?] -> risk debate ->     |
|  Conviction: 8/10          |  risk judge -> [override?]       |
|  Stop / Target             |  Color-coded by signal           |
+----------------------------+----------------------------------+
|  REPORT VIEWER (full markdown, collapsible sections)           |
|  [Research Manager] [Trader] [Risk Judge]                      |
|  [Bull Case] [Bear Case]                                       |
|  [Market] [Social] [News] [Fundamentals]                       |
+----------------------------+----------------------------------+
|  OVERRIDE LOG (this ticker)|  AGENT MEMORY (recent lessons)   |
+----------------------------+----------------------------------+
```

**Markdown rendering:** `react-markdown` with `remark-gfm` (tables) and
`rehype-highlight` (code blocks). Each section is an accordion/collapsible.

**Pipeline visualization:** SVG or CSS-based flow diagram showing each agent as
a node with the signal/conviction as a colored badge. Bypasses and overrides
shown as highlighted branches.

### Page 4: Research

**URL:** `/research`

**Layout:**
```
+----------------------------+----------------------------------+
|  FINDINGS VIEWER           |  SIGNALS TABLE                   |
|  (rendered markdown)       |  Ticker | Decision | Conviction  |
|  Date selector dropdown    |  Color-coded BUY/SELL/HOLD       |
|                            |  Click -> Agents page            |
+----------------------------+----------------------------------+
|  WATCHLIST CHANGES                                             |
|  Timeline of ADD/REMOVE events across days                     |
+----------------------------------------------------------------+
|  BUY QUOTA AUDIT LOG                                           |
|  Table of quota events with missed tickers and force-buys      |
+----------------------------------------------------------------+
|  SECTOR SIGNALS                                                |
|  Table: Sector | Signal | Tickers affected                    |
+----------------------------------------------------------------+
```

### Page 5: Control

**URL:** `/control`

**Layout:**
```
+----------------------------+----------------------------------+
|  SYSTEM STATUS             |  ACTIONS                         |
|  Agent running/stopped     |  [Run Cycle Now]                 |
|  PID, last/next cycle      |  [Dry Run]                       |
|  Today's trade counts      |  [Run Single Ticker: _____]      |
|                            |  [Force Research Refresh]         |
|                            |  [Sync Positions]                |
+----------------------------+----------------------------------+
|  LIVE FEED (WebSocket)                                         |
|  Real-time scrolling log output from the trading loop          |
|  Color-coded: BUY=green, SELL=red, HOLD=gray, ERROR=orange    |
+----------------------------------------------------------------+
|  WATCHLIST EDITOR                                              |
|  Add ticker: [___] Tier: [TACTICAL v] [Add]                   |
|  Current dynamic overrides with [x remove] buttons             |
+----------------------------+----------------------------------+
|  CONFIGURATION (read-only display)                             |
|  Base amount / Stop-loss / LLM models / Provider               |
+----------------------------------------------------------------+
```

---

## Technology Choices

### Backend

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ^0.111 | API framework |
| `uvicorn[standard]` | ^0.30 | ASGI server |
| `websockets` | ^12.0 | WebSocket support for FastAPI |
| `pydantic` | ^2.7 | Request/response models |
| `aiofiles` | ^23.2 | Async file reading for log streaming |

No database. All data read from existing JSON/Markdown files.

### Frontend

| Package | Purpose |
|---------|---------|
| `react` + `react-dom` | UI framework |
| `react-router-dom` | Client-side routing (5 pages) |
| `@tanstack/react-query` | Server state management + polling |
| `@tanstack/react-table` | Sortable/filterable tables |
| `lightweight-charts` | TradingView equity curve + candlestick charts |
| `recharts` | Pie charts, bar charts |
| `react-markdown` + `remark-gfm` + `rehype-highlight` | Markdown rendering |
| `tailwindcss` | Utility-first styling |
| `lucide-react` | Icons |

### Dev tooling

| Tool | Purpose |
|------|---------|
| `vite` | Frontend build + HMR |
| `typescript` | Type safety |
| `eslint` + `prettier` | Linting + formatting |

---

## Styling

**Theme:** Dark mode by default (matches terminal workflow). Optional light mode toggle.

**Color palette:**
- Background: `#0f1117` (near-black)
- Surface: `#1a1d28` (dark card)
- Border: `#2a2d3a`
- Text primary: `#e1e4eb`
- Text secondary: `#8b8fa3`
- Green (profit/BUY): `#22c55e`
- Red (loss/SELL): `#ef4444`
- Yellow (warning/HOLD): `#eab308`
- Blue (info/accent): `#3b82f6`
- Purple (enforcement): `#a855f7`

**Typography:** Monospace (`JetBrains Mono` or `Fira Code`) for numbers and data.
Sans-serif (`Inter`) for headings and prose.

---

## Running

### Development

```bash
# Backend
cd dashboard/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# Frontend (separate terminal)
cd dashboard/frontend
npm install
npm run dev    # Vite dev server on :5173, proxies /api to :8080
```

### Production (single process)

```bash
# Build frontend
cd dashboard/frontend
npm run build    # outputs to dist/

# Serve via FastAPI (mounts dist/ as static files)
cd dashboard/backend
uvicorn main:app --host 0.0.0.0 --port 8080
```

FastAPI serves the React SPA from `frontend/dist/` at `/` and the API at `/api/`.

---

## Security Notes

- **Local network only.** No auth required since it runs on localhost.
- Control panel actions (run cycle, modify watchlist) are POST endpoints that
  spawn subprocesses or write to override files -- same effect as CLI commands.
- No secrets are exposed through the API. Alpaca keys, OpenAI keys, etc. are
  never returned in any endpoint.
- The API is read-only for portfolio/trade data. Write operations are limited
  to: run cycle (subprocess), sync positions, modify watchlist overrides.
