# AGENTS.md — TradingAgents System Guide (v2)

> **For AI Agents:** This document contains everything you need to know to work
> with the trdagnt trading system.

---

## System Overview

**trdagnt** is a thesis-driven automated paper trading system built on the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

Three independent processes handle different aspects of portfolio management:

| Process | Cadence | Purpose |
|---------|---------|---------|
| **Discovery Pipeline** | Daily 9 AM ET | Screen all US equities, debate new candidates, record thesis |
| **Portfolio Review** | Staggered weekly | Verify existing holdings' theses still hold |
| **News Reaction** | Every 5 min | Monitor news, assess portfolio impact, trade if conviction >= 8 |

### Core Philosophy

- **Paper trading only** — No real money at risk
- **Thesis-driven** — Every position has a recorded rationale, catalysts, and invalidation conditions
- **Medium-term focus** — CORE positions held 6-12 months, TACTICAL 1-3 months
- **Graduated response** — Not every event needs full analysis; severity determines depth
- **Self-improving** — Per-ticker memory system learns from P&L outcomes

---

## Architecture

### Three-Process Model

```
DISCOVERY (daily)                    PORTFOLIO REVIEW (staggered)
  |                                    |
  | Screener: all US equities          | Load original thesis
  | LLM filter: top 10-15              | Market + Fundamentals analysts
  | Full 12-agent debate               | Thesis Assessor (gpt-4o)
  | BUY → record thesis, execute       | intact / weakening / broken
  |                                    |
  +-----------> PORTFOLIO <-----------+
                   |
              +----+----+
              |  Redis  |  (shared state: positions, theses, events)
              +----+----+
                   |
            NEWS REACTION (continuous)
              |
              | Poll Reuters + Finnhub + Reddit
              | LLM triage → severity (LOW/MEDIUM/HIGH/CRITICAL)
              | Graduated response
              | Trade if conviction >= 8
```

### Shared Infrastructure

- **Redis** — Shared state (positions, theses, coordination, event queue)
- **Alpaca Markets** — Paper trade execution
- **Docker Compose** — Service orchestration

---

## Key Files and Their Roles

### Process Entry Points

| File | Purpose | When to Modify |
|------|---------|----------------|
| `apps/discovery_pipeline.py` | Daily screener + 12-agent debate on new tickers | Change screening filters, debate count |
| `apps/portfolio_review.py` | Staggered thesis review for existing holdings | Change review cadence, add review criteria |
| `apps/news_monitor.py` | Continuous news polling + graduated response | Add news sources, change severity thresholds |
| `apps/screener.py` | Pluggable stock screener interface | Add new screener sources |

### Core Modules

| File | Purpose |
|------|---------|
| `src/tradingagents/thesis.py` | Thesis data model, Redis CRUD, category management |
| `src/tradingagents/review_agents.py` | Lightweight review pipeline (Thesis Assessor agent) |
| `src/tradingagents/news_debate.py` | News-specific debate pipeline with graduated response |
| `src/tradingagents/redis_state.py` | Redis state management (positions, coordination) |
| `src/tradingagents/default_config.py` | All configuration settings |

### Unchanged from v1

| File | Purpose |
|------|---------|
| `apps/alpaca_bridge.py` | Alpaca order execution, positions, stop-loss |
| `apps/daily_research.py` | Macro research pipeline (scrape → LLM → findings) |
| `apps/update_positions.py` | Sync Alpaca positions |
| `src/tradingagents/graph/trading_graph.py` | 12-agent LangGraph orchestrator |
| `src/tradingagents/agents/` | All 12 agent implementations |
| `src/tradingagents/dataflows/` | Data vendor implementations |
| `src/tradingagents/llm_clients/` | Multi-provider LLM support |

### TradingAgents Package Structure

```
src/tradingagents/
├── thesis.py                  # Thesis data model + Redis storage
├── review_agents.py           # Thesis Assessor agent for portfolio review
├── news_debate.py             # News-specific graduated debate pipeline
├── redis_state.py             # Redis state management
├── default_config.py          # All configuration
├── research_context.py        # Load findings → macro_context
├── conviction_bypass.py       # Skip Risk Judge on high conviction (discovery)
├── sector_monitor.py          # Portfolio sector exposure monitoring
├── graph/
│   ├── trading_graph.py       # TradingAgentsGraph orchestrator
│   ├── setup.py               # LangGraph StateGraph wiring
│   ├── propagation.py         # Initial state + graph invocation
│   ├── conditional_logic.py   # Debate routing + tool-call guard
│   ├── reflection.py          # Post-trade reflection → memory
│   └── signal_processing.py   # Regex BUY/SELL/HOLD extraction
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

# RECOMMENDED
FINNHUB_API_KEY=...

# REDIS
REDIS_URL=redis://localhost:6379/0    # auto-set by Docker Compose

# OPTIONAL - Model overrides
DEEP_LLM_MODEL=gpt-4o
QUICK_LLM_MODEL=gpt-4o-mini
RESEARCH_LLM_MODEL=gpt-4o-mini

# OPTIONAL - Discovery
DISCOVERY_MAX_CANDIDATES=15
DISCOVERY_MIN_MARKET_CAP=500000000
DISCOVERY_LOOKBACK_DAYS=7

# OPTIONAL - Review
REVIEW_CORE_INTERVAL=14
REVIEW_TACTICAL_INTERVAL=7

# OPTIONAL - News
NEWS_POLL_INTERVAL=300
NEWS_CONVICTION_THRESHOLD=8
```

### DEFAULT_CONFIG Key Sections

```python
{
    # LLM
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4o",
    "quick_think_llm": "gpt-4o-mini",

    # Discovery
    "discovery": {
        "screener_source": "finviz",
        "max_debate_candidates": 15,
        "min_market_cap": 500_000_000,
        "lookback_days": 7,
    },

    # Review
    "review": {
        "core_interval_days": 14,
        "tactical_interval_days": 7,
        "weakening_recheck_days": 3,
    },

    # News Reaction
    "news_reaction": {
        "poll_interval_seconds": 300,
        "conviction_threshold": 8,
    },

    # Categories
    "categories": {
        "CORE": {"hold_months": (6, 12), "base_multiplier": 2.0},
        "TACTICAL": {"hold_months": (1, 3), "base_multiplier": 1.0},
    },

    # Exit Rules
    "exit_rules": {
        "trailing_stop": {"activation_pct": 0.20, "trail_pct": 0.15},
        "catastrophic_loss": {"threshold_pct": 0.15, "cooldown_days": 7},
    },
}
```

---

## Thesis Data Model

Every position has a thesis. This is the central data structure.

```json
{
  "ticker": "NVDA",
  "entry_date": "2026-04-10",
  "entry_price": 142.50,
  "category": "CORE",
  "expected_hold_months": 9,
  "thesis": {
    "rationale": "AI infrastructure capex cycle accelerating...",
    "key_catalysts": ["Q2 earnings", "Blackwell ramp"],
    "invalidation_conditions": [
      "DC revenue growth < 20% YoY",
      "Major customer cuts capex"
    ]
  },
  "targets": {
    "price_target": 185.00,
    "stop_loss": 120.00
  },
  "review": {
    "next_review_date": "2026-04-24",
    "review_interval_days": 14,
    "last_verdict": "intact"
  }
}
```

Stored in Redis (`portfolio:positions:{ticker}`) with JSON file backup
(`data/theses/{ticker}.json`).

---

## Process Details

### Process 1: Discovery Pipeline

```
9:00 AM ET
    |
    +-- Daily Research (macro context)
    +-- Screener (all US equities via finviz)
    |     → 50-100 raw candidates
    +-- Exclude portfolio tickers + cooldown + recently debated
    +-- LLM Filter (gpt-4o-mini) → top 10-15
    +-- Full 12-Agent Debate (per candidate)
    |     Market → Social → News → Fundamentals
    |     Bull x2 ↔ Bear x2
    |     Research Manager → Trader
    |     Risk Debaters x3 → Risk Judge
    +-- BUY → record thesis + Alpaca order
    +-- Save discovery report
```

### Process 2: Portfolio Review

```
8:00 AM ET (2-4 holdings per day, staggered)
    |
    +-- Load thesis from Redis
    +-- Market Analyst (current technicals)
    +-- Fundamentals Analyst (latest data)
    +-- Thesis Assessor (gpt-4o)
    |     → INTACT: hold, schedule next review
    |     → WEAKENING: flag, shorten review interval
    |     → BROKEN: sell if conviction >= 8, else queue for debate
    +-- Save review report
```

### Process 3: News Reaction

```
Every 5 minutes:
    |
    +-- Fetch Reuters + Finnhub + Reddit
    +-- Dedup (SHA-256, 24h window)
    +-- LLM Triage → severity + affected tickers
    +-- LOW: log only
    +-- MEDIUM: 2-agent assessment (bull + bear)
    +-- HIGH: full 12-agent debate
    +-- CRITICAL: immediate Risk Judge
    +-- Trade if conviction >= 8
```

---

## Docker Compose Services

```bash
docker compose up -d                    # start all
docker compose up -d redis discovery    # specific services
docker compose logs -f news-monitor     # follow logs
docker compose down                     # stop all
```

| Service | Port | Purpose |
|---------|------|---------|
| `redis` | 6379 | Shared state store |
| `discovery` | — | Daily discovery pipeline |
| `portfolio-review` | — | Staggered thesis review |
| `news-monitor` | — | Continuous news polling |
| `dashboard-api` | 8888 | FastAPI backend + React frontend |

---

## Common Tasks for AI Agents

### Add a Manual Position with Thesis

```python
from tradingagents.thesis import ThesisStore
store = ThesisStore()
store.create_thesis(
    ticker="NVDA",
    entry_price=142.50,
    category="CORE",
    rationale="AI infrastructure capex cycle...",
    catalysts=["Q2 earnings", "Blackwell ramp"],
    invalidation=["DC revenue < 20% YoY"],
    target=185.00,
    stop_loss=120.00,
)
```

### Trigger an Immediate Review

```bash
python apps/portfolio_review.py --ticker NVDA
```

### Change Screener Filters

Edit `src/tradingagents/default_config.py`:

```python
DEFAULT_CONFIG["discovery"]["min_market_cap"] = 1_000_000_000  # $1B
DEFAULT_CONFIG["discovery"]["max_debate_candidates"] = 20
```

### Add a New Screener Source

1. Create class implementing `ScreenerSource` protocol in `apps/screener.py`
2. Register in `default_config.py` under `discovery.screener_source`
3. Add tests in `tests/`

### Debug a Discovery Decision

```bash
# Check discovery log
cat data/discovery/2026-04-13.json | python -m json.tool

# Check full debate report
cat trading_loop_logs/reports/NVDA/2026-04-13.md

# Run single ticker through discovery
python apps/discovery_pipeline.py --once --no-wait --max-candidates 1
```

### Debug a News Reaction

```bash
# Check news events
cat data/news_events/2026-04-13.json | python -m json.tool

# Check if news triggered a trade
docker compose logs news-monitor | grep "TRADE"
```

---

## Runtime Data

```
data/
├── theses/{TICKER}.json               # Thesis backup per ticker
├── discovery/{YYYY-MM-DD}.json        # Discovery log per day
├── reviews/{TICKER}/{YYYY-MM-DD}.json # Review history
└── news_events/{YYYY-MM-DD}.json      # News event log

trading_loop_logs/
├── memory/{TICKER}/*.json             # Agent memories (5 per ticker)
├── reports/{TICKER}/{YYYY-MM-DD}.md   # Full debate reports
├── stdout.log / stderr.log            # Service output
└── (legacy v1 files preserved)

results/
└── RESEARCH_FINDINGS_{YYYY-MM-DD}.md  # Daily macro research
```

Redis keys:
```
portfolio:positions:{ticker}    → thesis JSON
portfolio:cash                  → float
portfolio:sectors               → sector exposure hash
coordination:analyzed_today     → set of tickers
coordination:cooldown           → ticker → expiry hash
events:news_queue               → pending news events list
events:review_queue             → tickers flagged for review
```

---

## Testing

```bash
python -m pytest tests/ -v                    # all tests
python -m pytest tests/ -k "discovery"        # discovery tests
python -m pytest tests/ -k "review"           # review tests
python -m pytest tests/ -k "news"             # news reaction tests
python -m pytest tests/ --cov=. --cov-report=html
```

---

## Cost Breakdown

| Component | Daily | Annual |
|-----------|-------|--------|
| Daily research (gpt-4o-mini) | ~$0.003 | ~$1 |
| Discovery: LLM filter | ~$0.01 | ~$4 |
| Discovery: 10-15 debates | ~$0.40-0.60 | ~$150-220 |
| Portfolio review: 2-4/day | ~$0.02-0.04 | ~$7-15 |
| News triage | ~$0.02 | ~$7 |
| News assessments + debates | ~$0.03 | ~$9 |
| **Total** | **~$0.50-0.70** | **~$180-260** |

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Three processes** | Different activities need different cadences; coupling in one loop forces daily re-debate |
| **Thesis-driven** | v1 had no memory of why it bought; led to whipsaw decisions |
| **Conviction >= 8 for news trades** | Prevents overtrading on noise; lower-conviction events flagged for review |
| **finviz for screening** | Free, 8000+ tickers, good filters; pluggable interface for future paid sources |
| **Redis shared state** | Three processes need atomic shared access; JSON files have locking issues |
| **Docker Compose** | Platform-independent, service isolation, replaces macOS-only launchctl |
| **Lightweight review** | Most holdings don't change day-to-day; full debate is wasteful for "thesis intact" |
| **Two categories** | CORE + TACTICAL cover the mixed holding period; SPECULATIVE/HEDGE removed for simplicity |

---

*Last updated: April 2026 (v2 — Three-Process Architecture)*
