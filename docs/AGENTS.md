# AGENTS.md — TradingAgents System Guide

> **For AI Agents:** This document contains everything you need to know to work with the trdagnt trading system.

---

## System Overview

**trdagnt** is a fully automated daily paper trading system built on the [TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework. It runs once per day at 9:00 AM ET, analyzes a 34-ticker curated watchlist through a 12-agent LLM debate pipeline, and executes paper trades via Alpaca Markets.

### Core Philosophy

- **Paper trading only** — No real money at risk
- **Active capital deployment** — Three enforcement layers prevent idle cash
- **Explainable decisions** — Every trade has full reasoning captured
- **Self-improving** — Per-ticker memory system learns from P&L outcomes

---

## Architecture

### Daily Cycle Flow

```
9:00 AM ET (weekdays)
    │
    ├── Daily Research ──→ scrape VIX + Reuters + Reddit + Yahoo → gpt-4o-mini → findings.md
    ├── Safety Checks ───→ agent stops → global stop-loss (-15%) → exit rules → sector exposure
    ├── Checkpoint Load ─→ skip already-completed tickers (crash-resume)
    │
    ├── For each ticker (PARALLEL analysis phase):
    │   ├── Load memories (BM25 + embeddings)
    │   ├── Market Analyst ──→ 90d OHLCV, RSI, MACD, Bollinger, ATR, MFI
    │   ├── Social Analyst ──→ Reddit x 4, StockTwits, options P/C, short interest
    │   ├── News Analyst ────→ Reuters, Yahoo Finance, Finnhub, earnings calendar
    │   ├── Fundamentals Analyst → P/E, EV/EBITDA, FCF, insider buys, analyst targets
    │   ├── Bull Researcher x N ←→ Bear Researcher x N (N = tier debate rounds)
    │   ├── Research Manager ──→ synthesizes all → investment plan [gpt-4o]
    │   ├── Trader ────────────→ concrete proposal
    │   ├── [CONVICTION BYPASS] → high conviction + research agrees → skip Risk Judge
    │   ├── Risk Debaters x 3 ─→ aggressive / conservative / neutral evaluation
    │   └── Risk Judge ────────→ FINAL DECISION + stop + target + size [gpt-4o]
    │
    ├── Sequential Execution Phase:
    │   ├── Signal override check ─→ revert critical BUY→HOLD when cash > 80%
    │   ├── Parse decision ────────→ extract stop/target/conviction/size
    │   ├── Apply position sizing ─→ tier multiplier × size multiplier × cash boost
    │   ├── Portfolio limit guard ─→ dynamic max 20-28 positions
    │   ├── Execute on Alpaca ─────→ market order (fractional shares)
    │   ├── Reflect & remember ────→ LLM writes lesson from P&L
    │   └── Save checkpoint ───────→ mark ticker complete
    │
    ├── BUY QUOTA ENFORCEMENT ───→ force-buy up to 5 missed high-conviction opportunities
    └── Monthly Tier Review ─────→ promote/demote based on 30-day P&L
```

---

## Key Files and Their Roles

### Main Entry Points

| File | Purpose | When to Modify |
|------|---------|----------------|
| `apps/trading_loop.py` | Main daily loop, watchlist, scheduling, checkpoint, parallel execution | Add tickers, change timing, modify enforcement |
| `apps/alpaca_bridge.py` | Alpaca SDK wrapper — orders, positions, stop-loss, exit rules | Change order types, add broker features |
| `apps/daily_research.py` | Automated research pipeline — scrape → LLM → findings | Add new data sources, change prompt |
| `apps/main.py` | Single-ticker demo harness (no orders) | Testing new features |

### Supporting Modules

| File | Purpose |
|------|---------|
| `apps/update_positions.py` | Sync Alpaca positions → positions.json + prompt injection |
| `apps/tier_manager.py` | Monthly tier review (promote/demote by P&L) |
| `apps/analyze_conviction.py` | Conviction mismatch dashboard |
| `apps/watchlist_cleaner.py` | Clean expired/stale watchlist overrides |
| `apps/news_monitor.py` | Real-time news monitoring daemon (async) |
| `apps/news_monitor_triage.py` | LLM triage for news events |
| `apps/news_monitor_config.py` | News monitor configuration |

### TradingAgents Package

```
tradingagents/
├── default_config.py          # DEFAULT_CONFIG — all tunable settings
├── research_context.py        # Load findings → macro_context, parse signals
├── conviction_bypass.py       # Skip Risk Judge on high conviction (TICKET-068)
├── signal_override.py         # Detect + revert Risk Judge overrides (TICKET-067)
├── buy_quota.py               # BUY quota tracking and enforcement (TICKET-072)
├── sector_monitor.py          # Portfolio sector exposure monitoring (TICKET-073)
├── graph/
│   ├── trading_graph.py       # TradingAgentsGraph orchestrator
│   ├── setup.py               # LangGraph StateGraph wiring + bypass check
│   ├── propagation.py         # Initial state + graph invocation
│   ├── conditional_logic.py   # Debate routing + tool-call guard
│   ├── reflection.py          # Post-trade reflection → memory
│   ├── signal_processing.py   # Regex-only BUY/SELL/HOLD extraction
│   └── reflection.py          # Memory management
├── agents/
│   ├── analysts/              # market, social, news, fundamentals
│   ├── researchers/           # bull, bear
│   ├── managers/              # research_manager, risk_manager
│   ├── trader/                # trader
│   ├── risk_mgmt/             # aggressive, conservative, neutral debaters
│   └── utils/                 # memory, tools, states
├── dataflows/                 # Data vendor implementations
│   ├── y_finance.py           # Primary data source
│   ├── reuters_utils.py       # Reuters sitemap scraper
│   ├── reddit_utils.py        # Reddit JSON API
│   ├── finnhub_utils.py       # Finnhub REST API
│   └── ...
└── llm_clients/               # Multi-provider LLM support
    ├── factory.py             # Provider router
    ├── openai_client.py
    ├── anthropic_client.py
    └── google_client.py
```

---

## Configuration

### Environment Variables (.env)

```bash
# REQUIRED
OPENAI_API_KEY=sk-...
ALPACA_API_KEY=PK...
ALPACA_API_SECRET=...

# OPTIONAL BUT RECOMMENDED
FINNHUB_API_KEY=...          # Improves news quality (free tier)

# OPTIONAL - Model overrides
DEEP_LLM_MODEL=gpt-4o        # Research Manager + Risk Judge
QUICK_LLM_MODEL=gpt-4o-mini  # Analysts + debaters + trader
RESEARCH_LLM_MODEL=gpt-4o-mini  # Daily research

# OPTIONAL - Alternative providers
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
XAI_API_KEY=...
OPENROUTER_API_KEY=...

# OPTIONAL - Alpaca
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Default: paper
```

### DEFAULT_CONFIG (tradingagents/default_config.py)

```python
{
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4o",        # Decision nodes
    "quick_think_llm": "gpt-4o-mini",  # Data nodes
    "max_debate_rounds": 2,            # CORE tier
    "max_risk_discuss_rounds": 2,      # CORE tier
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "max_positions": 28,
    "max_positions_conservative": 20,
    "capital_deployment_cash_threshold": 0.80,
    "tier_position_limits": {
        "CORE": {"min": 0.5, "max": 2.0},
        "TACTICAL": {"min": 0.25, "max": 1.5},
        "SPECULATIVE": {"min": 0.1, "max": 0.75},
        "HEDGE": {"min": 0.25, "max": 1.0},
    },
    "exit_rules": {
        "profit_taking_50": {"enabled": True, "trigger": "pnl >= 50%"},
        "time_stop": {"enabled": True, "days_held": 30},
        "trailing_stop": {"enabled": True, "activation": 10, "trail": 15},
    },
}
```

---

## Watchlist System

### Static Watchlist (trading_loop.py:WATCHLIST)

34 tickers across 4 tiers:

| Tier | Count | Multiplier | Debate Rounds | Tickers |
|------|-------|------------|---------------|---------|
| CORE | 25 | 2.0x | 2 | NVDA, AVGO, AMD, ARM, TSM, MU, LITE, MSFT, GOOGL, META, PLTR, GLW, MDB, NOW, PANW, CRWD, RTX, LMT, NOC, VG, LNG, XOM, FCX, MP, UBER |
| TACTICAL | 5 | 1.0x | 1 | CMC, NUE, APA, SOC, SCCO |
| SPECULATIVE | 3 | 0.4x | 1 | RCAT, MOS, RCKT |
| HEDGE | 1 | 0.5x | 1 | GLD |

### Dynamic Watchlist Overrides

- **File:** `trading_loop_logs/watchlist_overrides.json`
- **Adds:** Up to 10 tickers (oldest dropped when full)
- **Removes:** Up to 8 tickers (expire after 5 days)
- **CORE protection:** Single-day SELL on CORE requires prior-day confirmation

---

## Parallel Execution (NEW)

The system now supports parallel analysis for faster cycle completion:

```bash
# Sequential (default, safe)
python trading_loop.py --once

# Parallel with 2 workers
python trading_loop.py --parallel 2 --once

# Parallel with 3 workers (max recommended)
python trading_loop.py --parallel 3 --once --no-wait
```

### Architecture

- **Phase 1 (Parallel):** Analysis only — LLM calls, data fetching, memory ops
- **Phase 2 (Sequential):** Trade execution — Alpaca orders, file writes, checkpoint updates

### Safety Measures

- Each worker function returns all data needed for execution
- Portfolio state refreshed between each sequential execution
- 10-minute timeout per ticker analysis
- Errors isolated per ticker

---

## Enforcement Layers

Three mechanisms prevent idle cash:

### 1. Conviction Bypass (TICKET-068)

```python
# Skip Risk Judge when:
conviction >= 8 + research_agrees + cash > 70%     # Standard
conviction >= 7 + research_agrees + cash > 85%     # Aggressive (emergency)
conviction >= 8 + research_agrees + has_position   # SELL bypass
```

**Implementation:** `tradingagents/conviction_bypass.py:_check_bypass()`

### 2. Signal Override Reversal (TICKET-067)

```python
# Revert BUY→HOLD override when:
severity in ("critical", "high") + cash > 80%
```

**Logged to:** `trading_loop_logs/signal_overrides.json`

**Implementation:** `tradingagents/signal_override.py:should_revert_override()`

### 3. Buy Quota Enforcement (TICKET-072)

```python
# Force-buy when:
cash > 80% + high_conviction_signals >= 5 + actual_buys < 5
# → Force-buy up to 5 missed opportunities
```

**Logged to:** `trading_loop_logs/buy_quota_log.json`

**Implementation:** `tradingagents/buy_quota.py:get_force_buy_tickers()`

---

## Position Sizing Math

```
effective_amount = base_amount × tier_multiplier × size_multiplier × cash_boost

Where:
- base_amount = --amount flag (default $1000)
- tier_multiplier = {CORE: 2.0, TACTICAL: 1.0, SPECULATIVE: 0.4, HEDGE: 0.5}
- size_multiplier = Risk Judge output (clamped to tier limits)
- cash_boost = {>85%: 1.5, 80-85%: 1.25, 70-80%: 1.10, <70%: 1.0}

Final qty = effective_amount / current_price
```

---

## Memory System

Five agent memories per ticker:

```
trading_loop_logs/memory/{TICKER}/
├── bull_memory.json          (+ .embeddings.json)
├── bear_memory.json
├── trader_memory.json
├── invest_judge_memory.json
└── risk_manager_memory.json
```

- **Cap:** 500 entries per agent per ticker
- **Retrieval:** BM25 (default) + OpenAI embeddings (opt-in)
- **Reflection:** After each trade, LLM writes lesson from P&L

---

## Runtime Logs

```
trading_loop_logs/
├── {YYYY-MM-DD}.json              # Daily trade log
├── {YYYY-MM-DD}.checkpoint.json   # Crash-resume checkpoint
├── watchlist_overrides.json       # Dynamic watchlist state
├── signal_overrides.json          # Override detection + reversals
├── buy_quota_log.json             # Quota enforcement audit
├── stop_loss_history.json         # Stop-loss cooldown tracking
├── position_entries.json          # Entry prices for exit rules
├── stdout.log / stderr.log        # LaunchAgent output
├── memory/{TICKER}/*.json         # Agent memories
└── reports/{TICKER}/{DATE}.md     # Human-readable reports
```

---

## Testing

```bash
# Run all tests (429+ across 31 files)
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_trading_loop_core.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Filter by keyword
python -m pytest tests/ -k "ssl or bypass"
```

### Key Test Files

| File | Tests |
|------|-------|
| `test_trading_loop_core.py` | Cycle logic, checkpoint, portfolio guards |
| `test_execute_decision.py` | Alpaca order execution, sizing, limits |
| `test_tickets_057_074.py` | Enforcement layers, overrides, quota |
| `test_daily_research.py` | Research pipeline, parsing |
| `test_signal_processing.py` | Regex extraction |
| `test_stop_loss.py` | Stop-loss and exit rules |
| `test_embedding_memory.py` | Memory system |
| `test_dynamic_watchlist.py` | Watchlist overrides |

---

## CLI Commands

### Trading Loop

```bash
python apps/trading_loop.py                      # Run forever, daily at 9 AM ET
python apps/trading_loop.py --once               # Single cycle then exit
python apps/trading_loop.py --once --no-wait     # Run immediately
python apps/trading_loop.py --dry-run            # Analyze only, no orders
python apps/trading_loop.py --parallel 2         # Parallel analysis (2 workers)
python apps/trading_loop.py --amount 500         # $500 base per trade
python apps/trading_loop.py --tickers NVDA AMD   # Override watchlist
python apps/trading_loop.py --from AMD           # Resume from ticker
python apps/trading_loop.py --stop-loss 0.10     # Tighten stop to -10%
```

### Daily Research

```bash
python apps/daily_research.py                    # Run (skip if today exists)
python apps/daily_research.py --force            # Overwrite today's findings
python apps/daily_research.py --dry-run          # Print prompt, no API call
```

### Other Utilities

```bash
python apps/update_positions.py                  # Sync positions → positions.json
python apps/tier_manager.py                      # Monthly tier review
python apps/analyze_conviction.py                # Conviction mismatch dashboard
python apps/main.py --ticker AAPL                # Single-ticker demo (no orders)
bash scripts/watch_agent.sh                      # Live terminal dashboard
```

### Installed CLI

```bash
tradingagents analyze                       # Interactive TUI analysis
```

---

## News Monitor (Real-time)

The news monitor runs as an asyncio background task for real-time news monitoring:

```python
from news_monitor import NewsMonitor
monitor = NewsMonitor()
asyncio.create_task(monitor.poll_loop())
```

**Features:**
- Polls Reuters, Finnhub, Reddit every 5 minutes
- LLM triage for material news events
- Auto-triggers analysis for affected tickers
- Dashboard control: start(), stop(), get_status()

---

## Dashboard

Local web dashboard at `http://localhost:8888`:

```bash
cd dashboard/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8888

# Frontend (separate terminal)
cd dashboard/frontend
npm install
npm run dev
```

**Pages:**
- `/` — Portfolio (equity curve, positions, sector exposure)
- `/trades` — Trade history + performance metrics
- `/agents` — Agent reasoning viewer (per-ticker reports)
- `/research` — Research findings browser
- `/control` — System control panel + live feed

---

## Common Tasks for AI Agents

### Add a New Ticker to Watchlist

```python
# Temporary (one cycle)
python trading_loop.py --once --tickers NVDA NEWTKR

# Permanent (dynamic add)
# Edit trading_loop.py WATCHLIST dict, or:
python -c "
from trading_loop import save_watchlist_overrides
save_watchlist_overrides(
    adds={'NEWTKR': {'sector': 'Technology', 'tier': 'TACTICAL', 'note': 'Reason'}},
    removes=[]
)
"
```

### Change Position Sizing

```python
# Edit tradingagents/default_config.py
DEFAULT_CONFIG["tier_position_limits"]["CORE"]["max"] = 2.5

# Or modify tier multiplier in trading_loop.py
TIER_MULTIPLIER["CORE"] = 2.5
```

### Adjust Enforcement Thresholds

```python
# tradingagents/conviction_bypass.py
BYPASS_THRESHOLDS["standard"]["conviction"] = 7  # Was 8

# tradingagents/buy_quota.py
QUOTA_MIN_CASH_RATIO = 0.75  # Was 0.80
QUOTA_MIN_SIGNALS = 3        # Was 5
```

### Add New Data Source

1. Create module in `tradingagents/dataflows/`
2. Add tool in `tradingagents/agents/utils/`
3. Import in relevant analyst
4. Add tests in `tests/`

### Debug a Failed Ticker

```bash
# Run single ticker with full output
python main.py --ticker FAILED --debug

# Check logs
cat trading_loop_logs/reports/FAILED/2026-04-08.md
cat trading_loop_logs/2026-04-08.json | jq '.trades[] | select(.ticker=="FAILED")'
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Sequential analysts** | LangGraph's MessagesState accumulates across parallel branches, causing OpenAI 400 errors from cross-contaminated tool_call chains |
| **Regex signal extraction** | Risk Judge outputs `FINAL DECISION: **BUY**`; secondary LLM call adds cost (~$12/year) with no quality benefit |
| **BM25 + embeddings** | BM25 works offline at zero cost; embeddings handle semantic similarity; fallback on embedding failures |
| **Three enforcement layers** | Risk Judge overrode 78% of high-conviction BUYs; prompt engineering alone insufficient |
| **Two-tier LLM** | Decision nodes (Manager, Judge) need capability; data nodes (analysts) work fine with cheaper model; saves ~$36/year |
| **Crash-resume checkpoint** | Mid-cycle crashes caused 3-5x re-trading; checkpoint ensures each ticker runs once per date |
| **ProcessPoolExecutor** | Threads blocked on GIL during LLM I/O; processes give true parallelism for CPU-bound analysis |

---

## Ticket Reference

Tickets are design records and fix history in `tickets/`:

| Ticket | Description |
|--------|-------------|
| TICKET-035 | SSL verification fix (scoped to Alpaca only) |
| TICKET-057 | Anti-HOLD-bias prompt for Risk Judge |
| TICKET-058 | Tier-based position sizing limits |
| TICKET-059 | Stop-loss cooldown (3-day re-buy block) |
| TICKET-062 | Time-based exit rules (profit-taking, trailing stop) |
| TICKET-063 | Dynamic max positions (20-28 based on cash) |
| TICKET-065 | Sector rotation signals |
| TICKET-066 | Monthly tier review |
| TICKET-067 | Signal override reversal |
| TICKET-068 | Conviction bypass |
| TICKET-070 | Cash deployment boost |
| TICKET-071 | Agent per-ticker stop-loss |
| TICKET-072 | BUY quota enforcement |
| TICKET-073 | Sector exposure monitoring |
| TICKET-074 | Parallel analysis execution |

---

## Cost Breakdown

| Component | Daily | Annual |
|-----------|-------|--------|
| Daily research (gpt-4o-mini) | ~$0.003 | ~$1.10 |
| 34 tickers × ~$0.04/ticker | ~$1.40 | ~$511 |
| **Total** | **~$1.40** | **~$512** |

**Cost reduction:** Set `DEEP_LLM_MODEL=gpt-4o-mini` to cut ~80% (lower decision quality).

---

## Getting Help

1. **Check logs:** `trading_loop_logs/stdout.log`, `stderr.log`
2. **Run tests:** `python -m pytest tests/ -v`
3. **Dry run:** `python trading_loop.py --once --no-wait --dry-run`
4. **Single ticker:** `python main.py --ticker NVDA --debug`
5. **Dashboard:** `bash watch_agent.sh` or `http://localhost:8080`

---

*Last updated: April 2026 (TICKET-001 through TICKET-074)*
