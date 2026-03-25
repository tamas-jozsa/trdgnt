# TrdAgnt — System Specification

> Last updated: March 2026

---

## Overview

**trdagnt** is a fully automated daily paper trading system built on top of the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

It runs once per day, analyses a curated 34-ticker watchlist using a 12-agent LLM
debate pipeline, executes paper trades on Alpaca Markets, and learns from past
decisions through a persistent memory system.

---

## Architecture

```
10:00 AM ET daily
       │
       ▼
[daily_research.py]          ← scrape live data + call OpenAI → save findings .md
       │
       ▼
[stop_loss_monitor]          ← check all positions, auto-sell anything ≤ -15%
       │
       ▼
for each of 34 tickers:
       │
       ├─ [load_memories]    ← BM25 + embedding memory from prior trading sessions
       ├─ [position_context] ← live Alpaca position if held (entry, P&L)
       ├─ [macro_context]    ← condensed daily research findings (VIX, themes, tickers)
       │
       ▼
  ┌──────────────────────────────────────────────┐
  │           12-AGENT ANALYSIS PIPELINE          │
  │                                              │
  │  📊 Market Analyst    (gpt-4o-mini)          │
  │     price, RSI, MACD, SMA, ATR, volume       │
  │                 ↓                            │
  │  💬 Social Analyst    (gpt-4o-mini)          │
  │     Reddit × 4 subreddits, StockTwits        │
  │                 ↓                            │
  │  📰 News Analyst      (gpt-4o-mini)          │
  │     Reuters sitemap + Yahoo Finance          │
  │                 ↓                            │
  │  📋 Fundamentals      (gpt-4o-mini)          │
  │     P/E, EV/EBITDA, FCF, insiders            │
  │                 ↓                            │
  │  🐂 Bull Researcher   (gpt-4o-mini)  ×2      │
  │  🐻 Bear Researcher   (gpt-4o-mini)  ×2      │
  │     structured debate, concession allowed    │
  │                 ↓                            │
  │  🧠 Research Manager  (gpt-4o)               │
  │     sees ALL 4 raw reports + debate          │
  │     outputs: RECOMMENDATION/CONVICTION/      │
  │              ENTRY/STOP/TARGET/SIZE          │
  │                 ↓                            │
  │  💼 Trader            (gpt-4o-mini)          │
  │     concrete proposal with stop + target     │
  │                 ↓                            │
  │  ⚡ Risk: Aggressive  (gpt-4o-mini)  ×2      │
  │  🛡️  Risk: Conservative (gpt-4o-mini) ×2     │
  │  ⚖️  Risk: Neutral     (gpt-4o-mini)  ×2     │
  │     independent evaluation (not defence)    │
  │                 ↓                            │
  │  🏛️  Risk Judge        (gpt-4o)              │
  │     final DECISION + STOP-LOSS + TARGET      │
  └──────────────────────────────────────────────┘
       │
       ▼
[signal_processor]           ← extract BUY/SELL/HOLD robustly (regex fallback)
       │
       ▼
[execute_decision]           ← Alpaca paper order (fractional shares, tier-sized)
       │
       ▼
[reflect_and_remember]       ← LLM writes lesson from P&L outcome to memory
       │
       ▼
[save_memories]              ← 5 agent memory files per ticker, persisted to disk
       │
       ▼
[save_report]                ← trading_loop_logs/reports/{TICKER}/{date}.md
```

---

## Watchlist

34 tickers across 4 conviction tiers. Defined in `trading_loop.py:WATCHLIST`.

| Tier | Count | Position size | Description |
|------|-------|--------------|-------------|
| CORE | 25 | 2× base | High conviction, macro-aligned, liquid |
| TACTICAL | 5 | 1× base | Momentum / catalyst-driven, 1-4 week horizon |
| SPECULATIVE | 3 | 0.4× base | Meme/squeeze/biotech, max 2-3% of portfolio |
| HEDGE | 1 | 0.5× base | GLD — geopolitical/volatility buffer |

**Dynamic watchlist:** After each daily research session, the system automatically
parses ADD/REMOVE decisions from the findings file and persists them to
`trading_loop_logs/watchlist_overrides.json`. The next cycle uses the updated list.

**Debate rounds by tier:**
- CORE: 2 debate rounds (Bull/Bear × 2, Risk × 2) — full scrutiny
- TACTICAL / SPECULATIVE / HEDGE: 1 debate round — faster, catalyst-focused

---

## Data Sources

| Source | Used by | What |
|--------|---------|------|
| **Reuters** (public sitemap) | News Analyst, Daily Research | Breaking news, ticker-tagged, hourly updates |
| **Yahoo Finance** (yfinance) | Market Analyst, Fundamentals, News fallback | Price/OHLCV, financials, news |
| **Reddit** (public JSON API) | Social Analyst, Daily Research | WSB/stocks/investing/options/pennystocks hot posts |
| **StockTwits** (public API) | Social Analyst | Bullish/bearish ratio, message stream |
| **Finnhub** (optional key) | News Analyst | Richer news with summaries |
| **Alpaca Markets** (paper API) | Order execution, stop-loss, clock | Paper trades, positions, portfolio |
| **OpenAI API** | All 12 agents, Daily Research | LLM inference |

---

## LLM Configuration

Two-tier model design to balance cost and quality:

| Role | Model | Reason |
|------|-------|--------|
| Research Manager | `gpt-4o` | Synthesises all 4 analyst reports + debate → investment plan |
| Risk Judge | `gpt-4o` | Final binding BUY/SELL/HOLD decision |
| All 4 Analysts | `gpt-4o-mini` | Data summarisation, tool calls |
| Bull/Bear Researchers | `gpt-4o-mini` | Debate arguments |
| Trader | `gpt-4o-mini` | Trade proposal from investment plan |
| Risk Debaters (×3) | `gpt-4o-mini` | Risk evaluation |
| Daily Research | `gpt-4o-mini` | Structured research findings |

Override via env vars: `DEEP_LLM_MODEL`, `QUICK_LLM_MODEL`, `RESEARCH_LLM_MODEL`.

---

## Memory System

Each of 5 agents (Bull, Bear, Trader, InvestJudge, RiskManager) maintains an
independent memory per ticker.

- **Storage:** `trading_loop_logs/memory/{TICKER}/{agent}.json`
- **Retrieval:** OpenAI `text-embedding-3-small` (semantic similarity) when
  `OPENAI_API_KEY` is set; falls back to BM25 keyword matching
- **Cap:** 500 entries per agent per ticker (oldest evicted)
- **Reflection:** After each trade, the LLM writes a lesson based on the P&L
  outcome. This lesson is retrieved in future cycles when a similar situation arises.
- **Persistence:** Pre-computed embeddings saved as `{agent}.embeddings.json`
  alongside the JSON to avoid re-embedding on restart.

---

## Daily Research Pipeline

Runs automatically at the start of each trading cycle (before any ticker analysis).

1. **Sync positions** — `update_positions.py` writes live broker state to prompt
2. **Scrape live data** — VIX, Yahoo gainers, watchlist prices (yfinance), Reuters
   global headlines, Reddit hot posts (4 subreddits)
3. **Call OpenAI** — `gpt-4o-mini` with compact structured prompt (~1,600 tokens in)
4. **Save findings** — `results/RESEARCH_FINDINGS_YYYY-MM-DD.md`
5. **Parse watchlist changes** — ADD/REMOVE tickers from findings, persist overrides
6. **Inject into agents** — findings are condensed to ≤3,000 chars and prepended to
   all 4 analyst system prompts as `macro_context`

**Cost:** ~$0.0014/day (~$0.52/year) at `gpt-4o-mini` default.

**Skip if done today:** Idempotent — uses existing file if today's already exists.
Force-redo with `--force`.

---

## Stop-Loss System

Runs at the start of every cycle, before any ticker analysis.

- **Threshold:** -15% unrealised P&L (configurable via `--stop-loss`)
- **Action:** Auto-submit market SELL order via Alpaca
- **Notification:** macOS notification on trigger
- **Dry-run safe:** `--dry-run` flag logs what would be sold but places no orders
- **Logged:** `STOP_LOSS_TRIGGERED` written to daily trade log JSON

---

## Trade Execution

All orders are placed on **Alpaca paper trading** (no real money).

- **Order type:** Market order, DAY time-in-force
- **Fractional shares:** Yes — amount / price, down to 4 decimal places
- **BUY guard:** skipped if available cash < $1
- **SELL guard:** skipped if position doesn't exist
- **Price fallback:** ask → bid → last trade → yfinance close (handles after-hours)

---

## Scheduling

The background agent runs as a macOS `launchctl` service.

- **Plist:** `~/Library/LaunchAgents/com.tjozsa.tradingagents.plist`
- **Run time:** 10:00 AM ET daily (weekdays only — weekends auto-skip to Monday)
- **Analysis date:** Previous completed trading session (Mon→Fri, Tue-Fri→yesterday)
- **Restart:** Auto-restarts on crash (`KeepAlive: true`)
- **On login:** Starts automatically (`RunAtLoad: true`)

---

## Report Files

After each ticker completes, a human-readable report is written:

```
trading_loop_logs/reports/{TICKER}/{date}.md
```

Contains in order: Decision, Research Manager plan, Trader proposal, Risk Judge
decision, Bull case (both rounds), Bear case (both rounds), all 4 analyst reports.

---

## Cost

| Component | Daily | Annual |
|-----------|-------|--------|
| Daily research (gpt-4o-mini) | ~$0.0014 | ~$0.52 |
| 34 tickers × ~$0.045/ticker (gpt-4o decision nodes) | ~$1.53 | ~$559 |
| **Total** | **~$1.53** | **~$560** |

Costs shown per full cycle. `trading-dry` costs the same (analysis is identical).
Reduce cost by switching `DEEP_LLM_MODEL=gpt-4o-mini` (lower quality decisions).

---

## File Structure

```
trdagnt/
├── trading_loop.py          # Main daily loop, watchlist, scheduling
├── alpaca_bridge.py         # Alpaca integration (orders, positions, stop-loss)
├── daily_research.py        # Automated market research pipeline
├── watch_agent.sh           # Live terminal dashboard
├── update_positions.py      # Sync broker positions to prompt
├── main.py                  # Single-ticker demo (original framework usage)
│
├── MARKET_RESEARCH_PROMPT.md  # Human-readable research prompt template
├── SPEC.md                    # This file
├── README.md                  # Setup and usage guide
│
├── tradingagents/             # Core LangGraph agent framework
│   ├── graph/                 # LangGraph setup, state, propagation, reflection
│   ├── agents/                # 12 agent implementations + memory
│   │   ├── analysts/          # market, social, news, fundamentals
│   │   ├── researchers/       # bull, bear
│   │   ├── managers/          # research_manager, risk_manager
│   │   ├── trader/            # trader
│   │   ├── risk_mgmt/         # aggressive, conservative, neutral debaters
│   │   └── utils/             # memory, agent_states, tools
│   ├── dataflows/             # Data source integrations
│   │   ├── reuters_utils.py   # Reuters sitemap scraper
│   │   ├── reddit_utils.py    # Reddit public JSON API
│   │   ├── stocktwits_utils.py
│   │   ├── finnhub_utils.py
│   │   └── y_finance.py       # yfinance wrapper with caching
│   ├── llm_clients/           # LLM provider adapters
│   └── default_config.py      # Default configuration
│
├── tests/                     # ~250 tests (pytest)
├── tickets/                   # TICKET-001 through TICKET-028
│
├── results/                   # Daily research findings (gitignored except .md)
│   └── RESEARCH_FINDINGS_YYYY-MM-DD.md
│
└── trading_loop_logs/         # Runtime data (committed to git)
    ├── YYYY-MM-DD.json        # Daily trade log
    ├── memory/{TICKER}/       # Per-ticker agent memories
    └── reports/{TICKER}/      # Per-ticker analysis reports
```

---

## Configuration Reference

All options in `tradingagents/default_config.py`. Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `deep_think_llm` | `gpt-4o` | Model for Research Manager + Risk Judge |
| `quick_think_llm` | `gpt-4o-mini` | Model for analysts + debaters |
| `max_debate_rounds` | 2 (CORE) / 1 (others) | Bull/Bear debate rounds per ticker |
| `max_risk_discuss_rounds` | 2 (CORE) / 1 (others) | Risk debate rounds |
| `data_vendors.*` | `yfinance` | Data source per category |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API (agents + research + embeddings) |
| `ALPACA_API_KEY` | Yes | Alpaca paper account key |
| `ALPACA_API_SECRET` | Yes | Alpaca paper account secret |
| `ALPACA_BASE_URL` | No | Default: `https://paper-api.alpaca.markets` |
| `DEEP_LLM_MODEL` | No | Override decision model (default: `gpt-4o`) |
| `QUICK_LLM_MODEL` | No | Override analyst model (default: `gpt-4o-mini`) |
| `RESEARCH_LLM_MODEL` | No | Override research model (default: `gpt-4o-mini`) |
| `FINNHUB_API_KEY` | No | Improves news quality (free tier at finnhub.io) |

---

## Design Decisions

**Why 10 AM ET?** Market is open, yesterday's session is complete, pre-market
sentiment is available from Reuters/Reddit. Orders execute at market price.

**Why gpt-4o only for Research Manager and Risk Judge?** These two nodes make the
actual investment decision. The 4 analysts are data-retrieval tasks; gpt-4o-mini
is sufficient. Upgrading just the 2 decision nodes costs ~$36/year extra for
significantly better final decisions.

**Why sequential analysts (not parallel)?** LangGraph's MessagesState uses an
add-reducer that accumulates across all nodes — parallel branches cross-contaminate
each other's tool_call message chains, causing OpenAI 400 errors. Sequential is
correct and reliable.

**Why Reuters sitemap instead of RSS?** Reuters shut down public RSS in 2023. The
sitemap is public, updates hourly, and crucially includes `news:stock_tickers` tags
— Reuters editors explicitly tag which stocks each article covers, giving us
high-precision ticker → article matching with no keyword parsing required.

**Why BM25 + embeddings?** BM25 works offline, no API cost. Embeddings
(text-embedding-3-small) handle semantic similarity — "Iran war oil spike" matches
"geopolitical supply shock commodity rally" even though no words overlap.
Embeddings activate automatically when `OPENAI_API_KEY` is set.

**Why paper trading only?** The system is designed for research and learning.
Alpaca paper trading uses real market data and realistic order execution without
risking real capital. Switch to live trading by changing `ALPACA_BASE_URL` to the
live endpoint and using live API keys — but that's your decision to make.
