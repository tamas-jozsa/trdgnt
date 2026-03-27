# TrdAgnt — System Specification

> Last updated: March 2026 (reflects TICKET-001 through TICKET-044)

---

## Overview

**trdagnt** is a fully automated daily paper trading system built on top of the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

It runs once per day at 10:00 AM ET, analyses a curated 28-ticker watchlist
using a 12-agent LLM debate pipeline, executes paper trades on Alpaca Markets,
and learns from past decisions through a persistent per-ticker memory system.

---

## Architecture

```
10:00 AM ET (weekdays only)
       │
       ▼
[daily_research.py]
  1. sync live positions → positions.json + MARKET_RESEARCH_PROMPT.md
  2. scrape: VIX, Yahoo gainers, watchlist prices, Reuters, Reddit × 4
  3. call gpt-4o-mini with compact system prompt → structured findings .md
  4. parse ADD/REMOVE ticker decisions → watchlist_overrides.json
  Idempotent: skips if today's findings file already exists (--force to redo)
       │
       ▼
[stop_loss_monitor]
  check all open Alpaca positions
  auto-SELL any with unrealised P&L ≤ -15% (configurable via --stop-loss)
       │
       ▼
[checkpoint guard]
  load trading_loop_logs/{trade_date}.checkpoint.json
  skip any tickers already completed in a prior run today (crash-resume)
       │
       ▼
for each of 28 tickers:
       │
       ├─ [load_memories]     BM25 + embedding memory from prior sessions
       ├─ [position_context]  live Alpaca position (entry, P&L)
       │                      OR "NO POSITION — SELL not actionable"
       ├─ [macro_context]     condensed daily findings (≤8,000 chars):
       │                      SENTIMENT, VIX, MACRO THEMES, WATCHLIST
       │                      DECISIONS, NEW PICKS, SECTORS TO AVOID
       │
       ▼
  ┌─────────────────────────────────────────────────────┐
  │           12-AGENT ANALYSIS PIPELINE                │
  │                                                     │
  │  Market Analyst      (quick_think_llm)              │
  │    90d OHLCV, 10 indicators, earnings calendar      │
  │              ↓                                      │
  │  Social Analyst      (quick_think_llm)              │
  │    Reddit × 4 (titles + bodies + top comments)      │
  │    StockTwits, options P/C ratio, short interest    │
  │              ↓                                      │
  │  News Analyst        (quick_think_llm)              │
  │    earnings date/binary risk, Reuters sitemap       │
  │    Yahoo Finance news, Finnhub (if key set)         │
  │              ↓                                      │
  │  Fundamentals Analyst (quick_think_llm)             │
  │    P/E, EV/EBITDA, EV/Revenue, FCF, D/E             │
  │    revenue/earnings growth YoY, analyst targets     │
  │    insider transactions, balance sheet              │
  │              ↓                                      │
  │  Bull Researcher     (quick_think_llm) × N rounds   │
  │  Bear Researcher     (quick_think_llm) × N rounds   │
  │    structured debate — N = tier debate rounds       │
  │              ↓                                      │
  │  Research Manager    (deep_think_llm)               │
  │    sees ALL 4 analyst reports + full debate         │
  │    HOLD tiebreaker rule applied if conviction tied  │
  │    outputs: RECOMMENDATION / CONVICTION / ENTRY /   │
  │             STOP / TARGET / SIZE                    │
  │              ↓                                      │
  │  Trader              (quick_think_llm)              │
  │    concrete trade proposal with stop + target       │
  │              ↓                                      │
  │  Risk: Aggressive    (quick_think_llm) × N rounds   │
  │  Risk: Conservative  (quick_think_llm) × N rounds   │
  │  Risk: Neutral       (quick_think_llm) × N rounds   │
  │    independent evaluation (not defence)             │
  │    N = tier risk rounds                             │
  │              ↓                                      │
  │  Risk Judge          (deep_think_llm)               │
  │    final FINAL DECISION: BUY/SELL/HOLD              │
  │    CONVICTION: 1-10                                 │
  │    STOP-LOSS: $X.XX                                 │
  │    TARGET: $X.XX                                    │
  │    POSITION SIZE: 0.25x–2x                          │
  └─────────────────────────────────────────────────────┘
       │
       ▼
[signal_processor]          regex extraction of BUY/SELL/HOLD from Risk Judge text
                            no secondary LLM call
       │
       ▼
[parse_agent_decision]      extract stop, target, conviction, size_multiplier
                            multiplier clamped to 0.25x–2.0x
       │
       ▼
[portfolio limit guard]     if live positions ≥ 20: downgrade BUY → HOLD
       │
       ▼
[execute_decision]          Alpaca market order (fractional shares, DAY TIF)
                            effective amount = base tier amount × size_multiplier
                            SELL exits full position (not partial)
       │
       ▼
[reflect_and_remember]      LLM writes lesson from P&L outcome → 5 agent memories
       │
       ▼
[save_memories]             trading_loop_logs/memory/{TICKER}/{agent}.json
       │
       ▼
[save_checkpoint]           trading_loop_logs/{trade_date}.checkpoint.json
       │
       ▼
[save_report]               trading_loop_logs/reports/{TICKER}/{date}.md
```

---

## Watchlist

28 tickers across 4 conviction tiers. Defined in `trading_loop.py:WATCHLIST`.

| Tier | Count | Position size | Debate rounds | Description |
|------|-------|---------------|---------------|-------------|
| CORE | 25 | 2.0× base | 2 (bull/bear + risk) | High conviction, macro-aligned, liquid |
| TACTICAL | 5 | 1.0× base | 1 | Momentum / catalyst-driven, 1–4 week horizon |
| SPECULATIVE | 3 | 0.4× base | 1 | Squeeze/biotech/meme, max 2–3% of portfolio |
| HEDGE | 1 | 0.5× base | 1 | GLD — geopolitical/volatility buffer |

> The tier multiplier is the **base** scaling. The Risk Judge can further adjust
> individual orders 0.25×–2× via `POSITION SIZE` in its output. Effective sizing =
> tier multiplier × agent size multiplier.
> Example: CORE + "POSITION SIZE: 0.5x" → 2.0 × 0.5 = 1.0× effective.

**CORE (25):** NVDA, AVGO, AMD, ARM, TSM, MU, LITE, MSFT, GOOGL, META, PLTR, GLW,
MDB, NOW, PANW, CRWD, RTX, LMT, NOC, VG, LNG, XOM, FCX, MP, UBER

**TACTICAL (5):** CMC, NUE, APA, SOC, SCCO

**SPECULATIVE (3):** RCAT, MOS, RCKT

**HEDGE (1):** GLD

**Dynamic watchlist:** The daily research findings are automatically parsed for
ADD/REMOVE decisions, which are persisted to
`trading_loop_logs/watchlist_overrides.json` and applied to the next cycle.
Static `WATCHLIST` in `trading_loop.py` is never mutated; overrides are merged
at runtime via `load_watchlist_overrides()`.

---

## Data Sources

| Source | Used by | Auth | What |
|--------|---------|------|------|
| **Yahoo Finance** (`yfinance`) | Market Analyst, Fundamentals, News, Options, Earnings, Analyst Targets, Short Interest, Daily Research | None | OHLCV (90d), 10 indicators, financials, news feed, options chain, earnings calendar, analyst consensus targets, insider transactions, short float |
| **Reuters** (public XML sitemap) | News Analyst, Daily Research | None | Breaking news with `news:stock_tickers` tags; hourly updates; 12–24h lookback |
| **Reddit** (public `.json` API) | Social Analyst, Daily Research | None | r/wallstreetbets, r/stocks, r/investing, r/pennystocks — hot post titles + bodies (500 chars) + top 2 comments |
| **StockTwits** (public REST) | Social Analyst | None | Bullish/bearish ratio, message stream |
| **Finnhub** (REST API) | News Analyst | `FINNHUB_API_KEY` (optional) | Company news with full summaries; graceful skip if key absent |
| **Alpha Vantage** | All data categories | `ALPHA_VANTAGE_API_KEY` (optional) | Legacy/fallback path for OHLCV, indicators, fundamentals, news; largely superseded by yfinance |
| **Alpaca Markets** (paper REST + SDK) | Order execution, stop-loss, portfolio | `ALPACA_API_KEY` + `ALPACA_API_SECRET` (required) | Paper trade orders, live positions, portfolio state, market clock |
| **OpenAI API** | All 12 agents, Daily Research, Memory | `OPENAI_API_KEY` (required) | LLM inference (gpt-4o, gpt-4o-mini) + `text-embedding-3-small` for semantic memory |
| **Anthropic / Google / xAI / OpenRouter / Ollama** | All agents (optional) | Provider-specific key | Alternative LLM providers via `llm_clients/` factory |

**Data depth per analyst:**

| Analyst | Tools | What they see |
|---------|-------|---------------|
| Market | `get_stock_data`, `get_indicators` | 90d OHLCV; RSI, MACD, MACDs, 50 SMA, 200 SMA, 10 EMA, ATR, VWMA, Bollinger lower, MFI |
| Social | `get_reddit_sentiment`, `get_stocktwits_sentiment`, `get_options_flow`, `get_short_interest` | Reddit post bodies + top 2 comments; StockTwits bull/bear ratio; P/C ratio; short float % + days-to-cover |
| News | `get_earnings_calendar`, `get_reuters_news`, `get_global_news`, `get_news` | Earnings date/estimates/surprise + binary risk flag; Reuters headlines (ticker-tagged); Yahoo Finance news |
| Fundamentals | `get_fundamentals`, `get_income_statement`, `get_cashflow`, `get_balance_sheet`, `get_analyst_targets`, `get_insider_transactions` | P/E, EV/EBITDA, EV/Revenue, FCF yield, D/E; revenue/earnings growth YoY; Wall St consensus targets; insider buy/sell activity |

---

## LLM Configuration

Two-tier model design — decision nodes get the capable model, data-retrieval nodes get the cheap model.

| Role | Default model | Env var override |
|------|--------------|-----------------|
| Research Manager (decision) | `gpt-4o` | `DEEP_LLM_MODEL` |
| Risk Judge (decision) | `gpt-4o` | `DEEP_LLM_MODEL` |
| 4 Analysts | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
| Bull/Bear Researchers | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
| Trader | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
| Risk Debaters (×3) | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
| Daily Research | `gpt-4o-mini` | `RESEARCH_LLM_MODEL` |

**Alternative providers:** Anthropic Claude, Google Gemini, xAI Grok, OpenRouter,
and local Ollama are all supported via the `tradingagents/llm_clients/` factory.
Provider is selected via `llm_provider` in config (default: `"openai"`).

**Message trimming:** Each analyst node trims the LangGraph messages list to the
last 20 entries before invoking the LLM, preventing request body overflow when
tool responses are large (financial statement CSVs, news articles).

**Max tool calls per analyst:** 6 calls per analyst node (TICKET-028). Prevents
runaway tool-call loops from malformed LLM responses.

---

## Memory System

Five agent memories per ticker — one for each decision-making agent.

| Agent memory | Stored at |
|---|---|
| `bull_memory` | `trading_loop_logs/memory/{TICKER}/bull_memory.json` |
| `bear_memory` | `trading_loop_logs/memory/{TICKER}/bear_memory.json` |
| `trader_memory` | `trading_loop_logs/memory/{TICKER}/trader_memory.json` |
| `invest_judge_memory` | `trading_loop_logs/memory/{TICKER}/invest_judge_memory.json` |
| `risk_manager_memory` | `trading_loop_logs/memory/{TICKER}/risk_manager_memory.json` |

- **Cap:** 500 entries per agent per ticker (`MAX_MEMORY_ENTRIES = 500`); oldest evicted
- **Retrieval — BM25 (default):** `rank-bm25`, keyword tokenization, no API cost
- **Retrieval — Embeddings (opt-in):** OpenAI `text-embedding-3-small`, cosine
  similarity; activates automatically when `OPENAI_API_KEY` is set; falls back
  to BM25 on any embedding failure
- **Pre-computed embeddings:** Cached to `{agent}.embeddings.json` alongside the
  main `.json` to avoid re-embedding on restart
- **Reflection:** After each trade, the LLM writes a lesson from the P&L outcome.
  Lessons are retrieved in future cycles when a similar market situation arises.

---

## Daily Research Pipeline

Runs automatically at the start of each trading cycle (before any ticker analysis).
Entry point: `daily_research.py::run_daily_research()`.

1. **Sync positions** — `update_positions.py::fetch_positions()` → `positions.json`
   + injects live holdings into `MARKET_RESEARCH_PROMPT.md` placeholder tags
2. **Scrape live data** — VIX (Yahoo Finance v8), Yahoo Finance top gainers,
   watchlist prices (yfinance, 5d), Reuters global headlines (sitemap),
   Reddit hot posts (r/wallstreetbets, r/stocks, r/investing, r/pennystocks)
3. **Call OpenAI** — `gpt-4o-mini` with a compact `~1,200-token` system prompt
   (under 2,000 tokens total input for most days)
4. **Save findings** — `results/RESEARCH_FINDINGS_YYYY-MM-DD.md`
5. **Parse watchlist changes** — regex extracts ADD/REMOVE decisions from findings;
   persisted to `trading_loop_logs/watchlist_overrides.json`
6. **Inject into agents** — `research_context.py` loads the findings file, extracts
   priority sections (SENTIMENT, VIX, MACRO THEMES, WATCHLIST DECISIONS, NEW PICKS,
   SECTORS TO AVOID), and truncates to ≤8,000 chars as `macro_context`

**Idempotent:** Skips with existing path if today's findings file already exists.
Force-redo with `run_daily_research(force=True)` or `python daily_research.py --force`.

**Cost:** ~$0.003/day (~$1.10/year) at `gpt-4o-mini` default.

**Manual workflow:** `MARKET_RESEARCH_PROMPT.md` is a 636-line structured prompt
that can be pasted directly into any AI chat interface as an alternative to the
automated pipeline.

---

## Stop-Loss System

Runs at the start of every cycle, before any ticker analysis.

- **Default threshold:** -15% unrealised P&L (`--stop-loss 0.15`)
- **Action:** Alpaca market SELL order for the full position
- **Logged:** `STOP_LOSS_TRIGGERED` written to daily trade log JSON
- **macOS notification:** sent on each triggered stop
- **Dry-run safe:** `--dry-run` logs what would be sold but places no orders

---

## Trade Execution

All orders are placed on **Alpaca paper trading** (no real money).

- **Order type:** Market order, DAY time-in-force
- **Fractional shares:** qty = `effective_amount / price`, 6 decimal places
- **Position sizing:** `base tier amount × agent POSITION SIZE multiplier`
  - Tier multiplier: CORE=2.0×, TACTICAL=1.0×, SPECULATIVE=0.4×, HEDGE=0.5×
  - Agent multiplier (from Risk Judge): 0.25×–2.0× (clamped)
- **BUY guards:**
  - Available cash < $1 → SKIPPED (`"reason": "insufficient_cash"`)
  - Live positions ≥ 20 → BUY downgraded to HOLD (portfolio limit guard)
- **SELL guard:** No open position → SKIPPED (`"reason": "no_position"`)
- **SELL behaviour:** exits the entire position (not `trade_amount_usd` worth)
- **Price fallback chain:** ask → bid → last trade → yfinance close (handles after-hours)
- **Agent stop/target:** Risk Judge's `STOP-LOSS` and `TARGET` are extracted and
  saved to the trade log. Not yet enforced as broker bracket orders.

---

## Crash-Resume / Checkpoint

Every ticker that completes (including on error) is written to:

```
trading_loop_logs/{trade_date}.checkpoint.json
```

On restart, completed tickers are skipped — each ticker runs exactly once per
analysis date regardless of how many times the process restarts.

- Keyed by analysis date: a new calendar day starts a fresh checkpoint
- Error tickers are checkpointed and not retried within the same day
- `--from TICKER` CLI flag: skip all tickers before the specified one (manual resume)

---

## Portfolio Limits

| Guard | Value | Location | Behaviour |
|-------|-------|----------|-----------|
| Max open positions | 20 | `run_daily_cycle()` | BUY downgraded to HOLD if live portfolio ≥ 20 positions; checked against live Alpaca state at execution time |
| Min cash for BUY | $1 | `execute_decision()` | BUY skipped with reason `insufficient_cash` |
| No-position SELL | — | `execute_decision()` | SELL skipped with reason `no_position` |

---

## HOLD Bias Tiebreaker

Applied by the Research Manager when bull/bear conviction scores are within 1
point of each other and no binary event (earnings, FDA) is within 3 days:

> Technicals break the tie in order: (1) price vs 200 SMA, (2) MACD direction,
> (3) RSI vs 50. A HOLD recommendation must include an "opportunity cost" statement.

---

## Scheduling

The background agent runs as a macOS `launchctl` service.

- **Plist:** `~/Library/LaunchAgents/com.tjozsa.tradingagents.plist`
- **Run time:** 10:00 AM ET daily (`_RUN_HOUR = 10`, `_RUN_MIN = 0`)
- **Weekends:** auto-skip (Friday after 10am → Monday 10am)
- **Analysis date:** Previous completed trading session:
  - Monday → Friday; Tuesday–Friday → yesterday; Saturday/Sunday → Friday
- **Restart:** Auto-restarts on crash (`KeepAlive: true`)
- **On login:** Starts automatically (`RunAtLoad: true`)
- **FD limit:** Raised to min(4096, hard limit) at startup — macOS default of
  256 is exhausted by ticker 12+ when opening multiple CSV + memory files
- **Live dashboard:** `watch_agent.sh` — terminal dashboard that refreshes every
  60s, showing: launchctl status, today's trade summary, watchlist tiers, daily
  research status, last 10 lines of agent output, recent stderr errors

---

## Report Files

After each ticker completes, `_log_state()` in `trading_graph.py` writes:

```
trading_loop_logs/reports/{TICKER}/{date}.md
```

Contains in order: Decision header, Research Manager investment plan, Trader
proposal, Risk Judge decision, Bull case (all rounds), Bear case (all rounds),
all 4 analyst reports.

---

## Cost

| Component | Daily | Annual |
|-----------|-------|--------|
| Daily research (`gpt-4o-mini`) | ~$0.003 | ~$1.10 |
| 28 tickers × ~$0.05/ticker (gpt-4o decision nodes) | ~$1.40 | ~$511 |
| **Total** | **~$1.40** | **~$512** |

Costs are approximate. `--dry-run` costs the same (analysis is identical).
Reduce cost by setting `DEEP_LLM_MODEL=gpt-4o-mini` (lower decision quality).

---

## File Structure

```
trdagnt/
├── trading_loop.py          # Daily loop — watchlist, scheduling, cycle,
│                            #   checkpoint, position guard, notifications
├── alpaca_bridge.py         # Alpaca integration — orders, positions,
│                            #   stop-loss, parse_agent_decision
├── daily_research.py        # Automated market research pipeline
├── update_positions.py      # Sync broker positions → positions.json
│                            #   + inject into MARKET_RESEARCH_PROMPT.md
├── main.py                  # Single-ticker demo harness (no orders placed)
├── watch_agent.sh           # Live terminal dashboard (60s refresh)
│
├── MARKET_RESEARCH_PROMPT.md  # 636-line manual research prompt template
│                               # (also used for automated position injection)
├── SPEC.md                    # This file
├── README.md                  # Setup and usage guide
│
├── tradingagents/             # Core LangGraph agent framework (package)
│   ├── default_config.py      # DEFAULT_CONFIG — all tunable settings
│   ├── research_context.py    # Load + truncate findings → macro_context (≤8,000 chars)
│   ├── graph/
│   │   ├── trading_graph.py   # TradingAgentsGraph orchestrator class
│   │   ├── setup.py           # LangGraph StateGraph wiring
│   │   ├── propagation.py     # Initial state + graph invocation
│   │   ├── conditional_logic.py  # Debate routing + tool-call guard (max 6)
│   │   ├── reflection.py      # Post-trade LLM reflection → memory writes
│   │   └── signal_processing.py  # Regex-only BUY/SELL/HOLD extraction
│   ├── agents/
│   │   ├── analysts/          # market, social, news, fundamentals
│   │   ├── researchers/       # bull, bear
│   │   ├── managers/          # research_manager (tiebreaker), risk_manager
│   │   ├── trader/
│   │   ├── risk_mgmt/         # aggressive, conservative, neutral debaters
│   │   └── utils/
│   │       ├── memory.py      # FinancialSituationMemory (BM25 + embeddings)
│   │       │                  # MAX_MEMORY_ENTRIES = 500
│   │       ├── agent_states.py
│   │       ├── agent_utils.py # Tool re-exports, message-trim helpers
│   │       ├── core_stock_tools.py
│   │       ├── technical_indicators_tools.py
│   │       ├── fundamental_data_tools.py
│   │       └── news_data_tools.py
│   ├── dataflows/
│   │   ├── interface.py          # Vendor routing (yfinance / alpha_vantage / finnhub)
│   │   ├── y_finance.py          # yfinance wrapper — OHLCV, indicators,
│   │   │                         #   fundamentals, news; CSV cache with
│   │   │                         #   3-day TTL + 15-year-file detection
│   │   ├── reuters_utils.py      # Reuters public XML sitemap scraper
│   │   ├── reddit_utils.py       # Reddit public JSON API (bodies + comments)
│   │   ├── stocktwits_utils.py   # StockTwits public API
│   │   ├── finnhub_utils.py      # Finnhub REST API (optional key)
│   │   ├── market_data_tools.py  # Options flow, earnings calendar,
│   │   │                         #   analyst targets, short interest
│   │   ├── alpha_vantage*.py     # Alpha Vantage legacy/fallback path
│   │   └── config.py             # Global config getter/setter
│   └── llm_clients/
│       ├── factory.py            # Provider router → concrete client
│       ├── base_client.py
│       ├── openai_client.py      # OpenAI + xAI + Ollama + OpenRouter
│       ├── anthropic_client.py
│       ├── google_client.py
│       └── validators.py         # Model name allowlists per provider
│
├── cli/
│   └── main.py                # Typer CLI (`tradingagents` entrypoint)
│
├── tests/                     # 398 tests across 28 test files (pytest)
├── tickets/                   # TICKET-001 through TICKET-044
│
├── results/                   # Daily research (gitignored runtime data)
│   └── RESEARCH_FINDINGS_YYYY-MM-DD.md
│
└── trading_loop_logs/         # Runtime data
    ├── YYYY-MM-DD.json              # Daily trade log
    ├── YYYY-MM-DD.checkpoint.json   # Crash-resume checkpoint
    ├── watchlist_overrides.json     # Dynamic watchlist ADD/REMOVE state
    ├── stdout.log / stderr.log      # LaunchAgent captured output
    ├── memory/{TICKER}/             # 5 agent memories per ticker
    │   ├── bull_memory.json
    │   ├── bull_memory.embeddings.json
    │   └── ... (bear, trader, invest_judge, risk_manager)
    └── reports/{TICKER}/            # Human-readable per-ticker reports
        └── YYYY-MM-DD.md
```

---

## Configuration Reference

All settings in `tradingagents/default_config.py`. Key runtime settings:

| Key | Default | Description |
|-----|---------|-------------|
| `deep_think_llm` | `gpt-4o` | Model for Research Manager + Risk Judge |
| `quick_think_llm` | `gpt-4o-mini` | Model for analysts, debaters, trader |
| `llm_provider` | `"openai"` | Provider: `openai`, `anthropic`, `google`, `xai`, `openrouter`, `ollama` |
| `max_debate_rounds` | 2 (CORE) / 1 (others) | Bull/Bear debate rounds |
| `max_risk_discuss_rounds` | 2 (CORE) / 1 (others) | Risk debate rounds |
| `data_vendors.core_stock_apis` | `"yfinance"` | OHLCV data source |
| `data_vendors.technical_indicators` | `"yfinance"` | Indicator source |
| `data_vendors.fundamental_data` | `"yfinance"` | Fundamentals source |
| `data_vendors.news_data` | `"yfinance"` | News source |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | LLM inference (agents + research) + `text-embedding-3-small` |
| `ALPACA_API_KEY` | Yes | — | Alpaca paper account key |
| `ALPACA_API_SECRET` | Yes | — | Alpaca paper account secret |
| `ALPACA_BASE_URL` | No | `https://paper-api.alpaca.markets` | Used by `alpaca_bridge.py`, `trading_loop.py`, `update_positions.py` |
| `DEEP_LLM_MODEL` | No | `gpt-4o` | Research Manager + Risk Judge model |
| `QUICK_LLM_MODEL` | No | `gpt-4o-mini` | Analysts + debaters + trader model |
| `RESEARCH_LLM_MODEL` | No | `gpt-4o-mini` | Daily research LLM model |
| `FINNHUB_API_KEY` | Recommended | — | Richer news summaries (free tier at finnhub.io); graceful skip if absent |
| `ANTHROPIC_API_KEY` | No | — | For Claude provider |
| `GOOGLE_API_KEY` | No | — | For Gemini provider |
| `XAI_API_KEY` | No | — | For Grok provider |
| `OPENROUTER_API_KEY` | No | — | For OpenRouter provider |
| `ALPHA_VANTAGE_API_KEY` | No | — | Legacy fallback data path |

All variables loaded via `.env` (python-dotenv). See `.env.example` for a
documented template.

---

## CLI Usage

```bash
# Primary entry points
python trading_loop.py                        # run forever, daily at 10:00 AM ET
python trading_loop.py --amount 500           # $500 base per trade
python trading_loop.py --dry-run              # analyse only, no orders
python trading_loop.py --once                 # single cycle then exit
python trading_loop.py --no-wait              # skip wait, run immediately
python trading_loop.py --tickers NVDA MSFT    # override ticker list
python trading_loop.py --stop-loss 0.10       # tighten stop to -10%
python trading_loop.py --from AMD             # resume cycle from AMD

# Single-ticker demo (no orders)
python main.py
python main.py --ticker AAPL --date 2026-03-25 --debug

# Research pipeline
python daily_research.py                      # run or skip if done today
python daily_research.py --dry-run            # print prompt, no API call
python daily_research.py --force              # overwrite today's findings

# Position sync
python update_positions.py                    # sync → positions.json + prompt

# Alpaca single-ticker (with order execution)
python alpaca_bridge.py --ticker NVDA --amount 1000

# Live dashboard
bash watch_agent.sh

# Installed CLI (via pyproject.toml entrypoint)
tradingagents                                 # interactive TUI
```

---

## Design Decisions

**Why 10 AM ET?** Market is open, the prior session is complete, pre-market
sentiment is live from Reuters/Reddit. Orders execute immediately at market price.

**Why gpt-4o only for Research Manager and Risk Judge?** These two nodes make
the actual investment decision. The 4 analysts are data retrieval and
summarisation tasks; gpt-4o-mini is sufficient and significantly cheaper.
Upgrading just the 2 decision nodes costs ~$36/year extra for meaningfully
better final decisions.

**Why sequential analysts (not parallel)?** LangGraph's `MessagesState` uses an
add-reducer that accumulates across all nodes — parallel branches
cross-contaminate each other's `tool_call` message chains, causing OpenAI 400
errors. Sequential is correct and reliable.

**Why Reuters sitemap instead of RSS?** Reuters shut down public RSS in 2023.
The sitemap is public, updates hourly, and includes `news:stock_tickers` tags —
Reuters editors explicitly tag which stocks each article covers, giving
high-precision ticker → article matching with no keyword parsing required.

**Why BM25 + embeddings?** BM25 works offline at zero API cost. Embeddings
(`text-embedding-3-small`) handle semantic similarity — "Iran war oil spike"
matches "geopolitical supply shock commodity rally" even with no word overlap.
Embeddings activate automatically when `OPENAI_API_KEY` is set.

**Why regex-only signal extraction?** The Risk Judge is explicitly instructed to
output `FINAL DECISION: **BUY**`. A secondary LLM call to re-extract the same
signal adds cost (~$12/year) and a failure point with no quality benefit.

**Why agent position size multiplier?** The Risk Judge outputs conviction-based
sizing (e.g. `POSITION SIZE: 0.5x` on a mixed-signal setup). Discarding this
and using full tier allocation ignores the system's own risk assessment.
Multiplier is clamped 0.25×–2× to prevent extreme positions from malformed output.

**Why max 20 open positions?** Prevents all 28 tickers from being bought on a
broad BUY sweep. With $100K equity and $2K/trade CORE sizing, 20 positions =
$40K invested (40% of portfolio), preserving adequate cash for opportunistic adds.

**Why crash-resume checkpoint?** A mid-cycle crash previously caused tickers to
be re-analysed and re-traded 3–5× in a day. The checkpoint ensures each ticker
runs exactly once per analysis date regardless of process restarts.

**Why paper trading only?** The system is designed for research and learning.
Alpaca paper trading uses real market data and realistic order execution without
risking real capital. To switch to live trading, set `ALPACA_BASE_URL` to the
live endpoint and use live API keys — but that decision is yours to make.

**Why no global SSL verification bypass?** The original codebase patched
`requests.Session.__init__` globally at import time as a corporate proxy
workaround. This was removed (TICKET-035): the fix disables SSL verification
only on the specific Alpaca REST calls that need it, leaving all other HTTP
clients (yfinance, OpenAI, Reddit, Reuters) using verified connections.
