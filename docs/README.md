# trdagnt

Automated paper trading system built on the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

Three independent processes work together to discover, hold, and protect
medium-term investments:

| Process | Cadence | What it does |
|---------|---------|-------------|
| **Discovery** | Daily 9 AM ET | Screens all US equities for new candidates, runs full 12-agent debate on top picks |
| **Portfolio Review** | Staggered weekly | Checks if existing holdings' investment theses still hold |
| **News Reaction** | Every 5 minutes | Monitors news, assesses portfolio impact, trades autonomously when conviction >= 8 |

Every position has a recorded **thesis** — why we bought it, what catalysts to
watch, and what would invalidate it. Reviews and news reactions are always
assessed against this thesis.

> **Paper trading only.** No real money is at risk. Not financial advice.

---

## How it works

```
DISCOVERY (daily)                    PORTFOLIO REVIEW (staggered)
  |                                    |
  | Screener: all US equities          | Load original thesis
  | LLM filter: top 10-15              | Market + Fundamentals analysts
  | Full 12-agent debate               | Thesis Assessor (gpt-4o)
  | BUY → record thesis, execute       | intact/weakening/broken
  | HOLD → skip                        | SELL if broken + conviction >= 8
  |                                    |
  +-----------> PORTFOLIO <-----------+
                   |
            +------+------+
            |   Redis     |
            | (positions, |
            |  theses,    |
            |  events)    |
            +------+------+
                   |
            NEWS REACTION (continuous)
              |
              | Poll Reuters + Finnhub + Reddit
              | LLM triage → severity classification
              | LOW: log only
              | MEDIUM: 2-agent quick assessment
              | HIGH: full 12-agent debate
              | CRITICAL: immediate Risk Judge decision
              | Trade if conviction >= 8
```

**Cost:** ~$0.50-0.70/day (~$180-260/year). Significantly cheaper than
re-debating the same tickers daily.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- An [Alpaca paper trading account](https://app.alpaca.markets) (free)
- An [OpenAI API key](https://platform.openai.com/api-keys)

For local development (no Docker):
- Python 3.10+
- Redis server

---

## Quick Start (Docker)

```bash
git clone https://github.com/your-fork/trdagnt.git
cd trdagnt

# Configure API keys
cp .env.example .env
# Edit .env with your keys

# Build and start everything
docker compose build
docker compose up -d

# View logs
docker compose logs -f discovery
docker compose logs -f news-monitor

# Open dashboard
open http://localhost:8888
```

### Start specific services

```bash
# Just discovery + news monitoring (no dashboard)
docker compose up -d redis discovery news-monitor

# Just the dashboard (read-only, view existing data)
docker compose up -d redis dashboard-api

# Everything
docker compose up -d
```

### Manage services

```bash
docker compose ps                          # check status
docker compose logs -f discovery           # follow discovery logs
docker compose restart news-monitor        # restart a service
docker compose down                        # stop everything
docker compose build && docker compose up -d  # rebuild after code changes
```

---

## Setup (Local Development)

### 1. Clone and install

```bash
git clone https://github.com/your-fork/trdagnt.git
cd trdagnt

conda create -n tradingagents python=3.13
conda activate tradingagents

pip install -e ".[dev]"
```

### 2. Start Redis

```bash
# macOS
brew install redis && brew services start redis

# Or via Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Required
OPENAI_API_KEY=sk-...
ALPACA_API_KEY=PK...
ALPACA_API_SECRET=...

# Optional but recommended
FINNHUB_API_KEY=...          # free tier at finnhub.io

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM model overrides (defaults shown)
DEEP_LLM_MODEL=gpt-4o
QUICK_LLM_MODEL=gpt-4o-mini
```

### 4. Run services locally

```bash
# Discovery pipeline (manual run)
python apps/discovery_pipeline.py --once --no-wait

# Portfolio review (manual run)
python apps/portfolio_review.py --all

# News monitor (daemon)
python apps/news_monitor.py

# Dashboard
cd dashboard/backend && uvicorn main:app --reload --port 8888
```

---

## Three Processes

### 1. Discovery Pipeline

Runs daily at 9:00 AM ET. Finds new investment candidates.

```bash
# Via Docker (auto-scheduled)
docker compose up -d discovery

# Manual run
python apps/discovery_pipeline.py --once --no-wait

# Dry run (no orders)
python apps/discovery_pipeline.py --once --no-wait --dry-run

# Limit candidates
python apps/discovery_pipeline.py --max-candidates 5
```

**Flow:** Screener (all US equities via finviz) -> portfolio exclusion ->
LLM filter (top 10-15) -> full 12-agent debate -> BUY with thesis or PASS.

Each BUY records a thesis: rationale, catalysts, invalidation conditions,
target price, stop-loss, expected hold period (CORE: 6-12mo, TACTICAL: 1-3mo).

### 2. Portfolio Review

Staggered across the week. All holdings reviewed over a 2-4 week window.

```bash
# Via Docker (auto-scheduled)
docker compose up -d portfolio-review

# Manual: review all holdings
python apps/portfolio_review.py --all

# Manual: review specific ticker
python apps/portfolio_review.py --ticker NVDA

# Dry run
python apps/portfolio_review.py --dry-run
```

**Flow:** Load thesis -> Market Analyst update -> Fundamentals Analyst update ->
Thesis Assessor verdict: INTACT (hold) / WEAKENING (flag) / BROKEN (sell).

CORE positions reviewed every 2 weeks. TACTICAL every week. Weakening theses
rechecked in 3 days.

### 3. News Reaction

Continuous daemon. Polls every 5 minutes during market hours.

```bash
# Via Docker (auto-scheduled)
docker compose up -d news-monitor

# Manual start
python apps/news_monitor.py
```

**Flow:** Poll Reuters/Finnhub/Reddit -> LLM triage -> graduated response:

| Severity | Action | Example |
|----------|--------|---------|
| LOW | Log only | Routine analyst note |
| MEDIUM | 2-agent assessment | Sector rotation signal |
| HIGH | Full 12-agent debate | Earnings miss, downgrade |
| CRITICAL | Immediate Risk Judge | Fraud, FDA rejection |

Trades execute only when conviction >= 8.

---

## Position Categories

| Category | Hold Period | Position Size | Review Cadence |
|----------|-------------|---------------|----------------|
| CORE | 6-12 months | 2.0x base | Every 2 weeks |
| TACTICAL | 1-3 months | 1.0x base | Weekly |

The Risk Judge can further adjust position size (0.25x-2.0x) based on
conviction.

---

## Dashboard

```bash
# Via Docker
docker compose up -d dashboard-api
open http://localhost:8888

# Local development
cd dashboard/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8888

cd dashboard/frontend  # separate terminal
npm install && npm run dev
```

**Pages:**
- **Portfolio** — Equity curve, positions with thesis summary, sector exposure
- **Discovery** — Today's screener results, debate outcomes, new positions
- **Reviews** — Thesis review history, upcoming reviews, flagged positions
- **News** — News event feed, severity classification, triggered actions
- **Control** — Service status, manual triggers, live log feed

---

## Configuration

All settings in `src/tradingagents/default_config.py`. Key sections:

| Section | Key Settings |
|---------|-------------|
| Discovery | `max_debate_candidates=15`, `min_market_cap=$500M`, `lookback_days=7` |
| Review | `core_interval_days=14`, `tactical_interval_days=7`, `weakening_recheck_days=3` |
| News | `poll_interval=300s`, `conviction_threshold=8`, sources toggle |
| Categories | CORE (6-12mo, 2.0x) and TACTICAL (1-3mo, 1.0x) |
| Exit Rules | Trailing stop (20%/15%), catastrophic loss (-15%), thesis-based |

Environment variables in `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | LLM inference + embeddings |
| `ALPACA_API_KEY` | Yes | Paper trading |
| `ALPACA_API_SECRET` | Yes | Paper trading |
| `REDIS_URL` | No | Default: `redis://localhost:6379/0` |
| `FINNHUB_API_KEY` | Recommended | Better news quality |
| `DEEP_LLM_MODEL` | No | Default: `gpt-4o` |
| `QUICK_LLM_MODEL` | No | Default: `gpt-4o-mini` |

---

## Running Tests

```bash
python -m pytest tests/ -v              # all tests
python -m pytest tests/ -k "discovery"  # filter
python -m pytest tests/ --cov=. --cov-report=html  # coverage
```

---

## Key Files

| File | Purpose |
|------|---------|
| `apps/discovery_pipeline.py` | Daily screener + debate for new tickers |
| `apps/portfolio_review.py` | Staggered thesis review for existing holdings |
| `apps/screener.py` | Pluggable stock screener (finviz default) |
| `apps/news_monitor.py` | Continuous news polling + graduated response |
| `apps/alpaca_bridge.py` | Alpaca order execution |
| `apps/daily_research.py` | Macro research pipeline |
| `src/tradingagents/thesis.py` | Thesis data model + Redis storage |
| `src/tradingagents/review_agents.py` | Lightweight review pipeline |
| `src/tradingagents/news_debate.py` | News-specific debate pipeline |
| `src/tradingagents/redis_state.py` | Redis state management |
| `src/tradingagents/graph/` | 12-agent LangGraph framework |
| `docker-compose.yml` | Service orchestration |
| `docs/SPEC.md` | Full system specification |

---

## Legacy Compatibility

The v1 `trading_loop.py` still works for one-off analysis:

```bash
python apps/trading_loop.py --once --no-wait --tickers NVDA AMD
python apps/main.py --ticker AAPL --debug
```

These bypass the thesis and Redis systems.

---

## Upstream Framework

Fork of [TradingAgents](https://github.com/TauricResearch/TradingAgents) by
Tauric Research.

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework},
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138},
}
```
