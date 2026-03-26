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
[checkpoint guard]           ← skip tickers already completed today (crash-resume)
       │
       ▼
for each of 34 tickers:
       │
       ├─ [load_memories]    ← BM25 + embedding memory from prior trading sessions
       ├─ [position_context] ← live Alpaca position if held (entry, P&L)
       │                        OR explicit "NO POSITION — SELL not actionable" msg
       ├─ [macro_context]    ← condensed daily research findings (VIX, themes, tickers)
       │
       ▼
  ┌──────────────────────────────────────────────┐
  │           12-AGENT ANALYSIS PIPELINE          │
  │                                              │
  │  📊 Market Analyst    (gpt-4o-mini)          │
  │     price, RSI, MACD, SMA, ATR, volume       │
  │     Bollinger Bands lower, MFI               │
  │                 ↓                            │
  │  💬 Social Analyst    (gpt-4o-mini)          │
  │     Reddit × 4 subreddits (post bodies       │
  │     + top comments), StockTwits,             │
  │     options flow (P/C ratio), short interest │
  │                 ↓                            │
  │  📰 News Analyst      (gpt-4o-mini)          │
  │     earnings calendar (binary risk flag),    │
  │     Reuters sitemap + Yahoo Finance          │
  │                 ↓                            │
  │  📋 Fundamentals      (gpt-4o-mini)          │
  │     P/E, EV/EBITDA, EV/Revenue, FCF,         │
  │     insiders, analyst consensus targets      │
  │                 ↓                            │
  │  🐂 Bull Researcher   (gpt-4o-mini)  ×2      │
  │  🐻 Bear Researcher   (gpt-4o-mini)  ×2      │
  │     structured debate, tiebreaker rule       │
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
  │     + POSITION SIZE multiplier              │
  └──────────────────────────────────────────────┘
       │
       ▼
[signal_processor]           ← extract BUY/SELL/HOLD via regex (no LLM call)
       │
       ▼
[parse_agent_decision]       ← extract stop, target, conviction, size multiplier
       │
       ▼
[portfolio limit guard]      ← cap at 20 open positions; downgrade BUY → HOLD if full
       │
       ▼
[execute_decision]           ← Alpaca paper order (fractional shares)
                               amount scaled by agent's POSITION SIZE multiplier
                               SELL exits full position (not partial)
       │
       ▼
[reflect_and_remember]       ← LLM writes lesson from P&L outcome to memory
       │
       ▼
[save_memories]              ← 5 agent memory files per ticker, persisted to disk
       │
       ▼
[save_checkpoint]            ← mark ticker done; crash-resume skips completed tickers
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

**Note:** The 2× / 1× / 0.4× / 0.5× is the *base* multiplier. The Risk Judge can
further scale individual orders from 0.25× to 2× via `POSITION SIZE` in its output
(e.g. "POSITION SIZE: 0.5x" on a CORE ticker → 2.0 × 0.5 = 1.0× effective).

**Current CORE tickers (25):**
NVDA, AVGO, AMD, ARM, TSM, MU, LITE, MSFT, GOOGL, META, PLTR, GLW, MDB, NOW,
PANW, CRWD, RTX, LMT, NOC, VG, LNG, XOM, FCX, MP, UBER

**Current TACTICAL tickers (5):** CMC, NUE, APA, SOC, SCCO

**Current SPECULATIVE tickers (3):** RCAT, MOS, RCKT

**Current HEDGE tickers (1):** GLD

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
| **Yahoo Finance** (yfinance) | Market Analyst, Fundamentals, News fallback, Options, Earnings, Analyst targets, Short interest | Price/OHLCV, financials, news, options chain, earnings calendar |
| **Reddit** (public JSON API) | Social Analyst, Daily Research | WSB/stocks/investing/options hot posts — **titles + post bodies + top comments** |
| **StockTwits** (public API) | Social Analyst | Bullish/bearish ratio, message stream |
| **Finnhub** (key required) | News Analyst | Richer news with full summaries (fallback to Yahoo Finance if key not set) |
| **Alpaca Markets** (paper API) | Order execution, stop-loss, portfolio state | Paper trades, positions, portfolio |
| **OpenAI API** | All 12 agents, Daily Research | LLM inference + text-embedding-3-small for memory |

**Data depth per analyst:**

| Analyst | Primary tools | What they see |
|---------|--------------|---------------|
| Market | get_stock_data, get_indicators | 90d OHLCV, 10 indicators: RSI, MACD, MACDs, 50/200 SMA, 10 EMA, ATR, VWMA, Bollinger lower, MFI |
| Social | get_reddit_sentiment, get_stocktwits_sentiment, get_options_flow, get_short_interest | Post titles + bodies (500 chars) + top 2 comments per post; P/C ratio; short float % + days-to-cover |
| News | get_earnings_calendar, get_reuters_news, get_global_news, get_news | Earnings date/estimates/surprise; Reuters headlines + ticker tags; Yahoo Finance news |
| Fundamentals | get_fundamentals, get_income_statement, get_cashflow, get_analyst_targets, get_insider_transactions, get_balance_sheet | P/E, EV/EBITDA, EV/Revenue, FCF yield, D/E, revenue/earnings growth YoY, Wall St consensus targets, insider buys |

---

## LLM Configuration

Two-tier model design to balance cost and quality:

| Role | Model | Reason |
|------|-------|--------|
| Research Manager | `gpt-4o` | Synthesises all 4 analyst reports + debate → investment plan |
| Risk Judge | `gpt-4o` | Final binding BUY/SELL/HOLD + stop/target/size decision |
| All 4 Analysts | `gpt-4o-mini` | Data summarisation, tool calls |
| Bull/Bear Researchers | `gpt-4o-mini` | Debate arguments |
| Trader | `gpt-4o-mini` | Trade proposal from investment plan |
| Risk Debaters (×3) | `gpt-4o-mini` | Risk evaluation |
| Daily Research | `gpt-4o-mini` | Structured research findings |

Override via env vars: `DEEP_LLM_MODEL`, `QUICK_LLM_MODEL`, `RESEARCH_LLM_MODEL`.

**Message trimming:** Each analyst node trims the LangGraph messages list to the
last 20 entries before invoking the LLM. Prevents request body overflow when
tool responses are large (financial statement CSVs, news articles).

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
6. **Inject into agents** — findings condensed to ≤8,000 chars and prepended to
   all 4 analyst system prompts as `macro_context`

**Cost:** ~$0.0014/day (~$0.52/year) at `gpt-4o-mini` default.

**Skip if done today:** Idempotent — uses existing file if today's already exists.
Force-redo with `--force`.

---

## Stop-Loss System

Runs at the start of every cycle, before any ticker analysis.

- **Threshold:** -15% unrealised P&L (configurable via `--stop-loss`)
- **Action:** Auto-submit market SELL order via Alpaca (full position exit)
- **Notification:** macOS notification on trigger
- **Dry-run safe:** `--dry-run` flag logs what would be sold but places no orders
- **Logged:** `STOP_LOSS_TRIGGERED` written to daily trade log JSON

---

## Trade Execution

All orders are placed on **Alpaca paper trading** (no real money).

- **Order type:** Market order, DAY time-in-force
- **Fractional shares:** Yes — amount / price, down to 4 decimal places
- **Position sizing:** base tier amount × agent's `POSITION SIZE` multiplier (0.25×–2×)
- **BUY guard:** skipped if available cash < $1
- **BUY guard:** skipped if portfolio already holds ≥ 20 open positions (max-positions cap)
- **SELL guard:** skipped if position doesn't exist
- **SELL behaviour:** exits the full position (not just `trade_amount_usd` worth)
- **Price fallback:** ask → bid → last trade → yfinance close (handles after-hours)
- **Agent stop/target logged:** Risk Judge's `STOP-LOSS` and `TARGET` are extracted
  and saved to the trade log for monitoring (not yet enforced in broker as bracket orders)

---

## Crash-Resume / Checkpoint

The cycle writes `trading_loop_logs/{trade_date}.checkpoint.json` after each
ticker completes (including errors). On restart, completed tickers are skipped.

- Prevents the same ticker from being analysed and traded 3-5× on a single day
- Works per analysis-date, so a new calendar day starts a fresh checkpoint
- On error, the ticker is still checkpointed — it is not retried within the same day

---

## Portfolio Limits

Hard guards enforced at the execution layer in `execute_decision()`:

| Guard | Value | Behaviour |
|-------|-------|-----------|
| Max open positions | 20 | BUY downgraded to HOLD if live portfolio ≥ 20 positions |
| Min cash | $1 | BUY skipped if available cash < $1 |
| No-position SELL | — | SELL skipped if no Alpaca position exists |

The max-positions check queries the live Alpaca portfolio at execution time (not
from a cached snapshot) so it reflects any same-day buys.

---

## HOLD Bias Tiebreaker

The Research Manager applies this rule when bull/bear conviction scores are tied:

> If bull and bear conviction are within 1 point of each other AND no binary event
> (earnings, FDA) is within 3 days, the technicals break the tie: (1) price vs 200
> SMA, (2) MACD direction, (3) RSI vs 50. HOLD must include an "opportunity cost"
> statement.

---

## Scheduling

The background agent runs as a macOS `launchctl` service.

- **Plist:** `~/Library/LaunchAgents/com.tjozsa.tradingagents.plist`
- **Run time:** 10:00 AM ET daily (weekdays only — weekends auto-skip to Monday)
- **Analysis date:** Previous completed trading session (Mon→Fri, Tue-Fri→yesterday)
- **Restart:** Auto-restarts on crash (`KeepAlive: true`)
- **On login:** Starts automatically (`RunAtLoad: true`)
- **FD limit:** Raised to 4096 at startup (macOS default 256 was exhausted by ticker 12+)

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
| 34 tickers × ~$0.048/ticker (gpt-4o decision nodes, new tools add ~7%) | ~$1.63 | ~$595 |
| **Total** | **~$1.63** | **~$596** |

Costs shown per full cycle. `--dry-run` costs the same (analysis is identical).
Reduce cost by switching `DEEP_LLM_MODEL=gpt-4o-mini` (lower quality decisions).

The Signal Processor no longer makes a secondary LLM call — BUY/SELL/HOLD is
extracted from the Risk Judge output via regex only.

---

## File Structure

```
trdagnt/
├── trading_loop.py          # Main daily loop, watchlist, scheduling, checkpoint
├── alpaca_bridge.py         # Alpaca integration (orders, positions, stop-loss,
│                            #   parse_agent_decision for stop/target/size)
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
│   │   └── signal_processing.py  # Regex-only signal extraction (no LLM call)
│   ├── agents/                # 12 agent implementations + memory
│   │   ├── analysts/          # market, social, news, fundamentals
│   │   ├── researchers/       # bull, bear
│   │   ├── managers/          # research_manager (tiebreaker rule), risk_manager
│   │   ├── trader/            # trader
│   │   ├── risk_mgmt/         # aggressive, conservative, neutral debaters
│   │   └── utils/             # memory, agent_states, tools
│   ├── dataflows/             # Data source integrations
│   │   ├── reuters_utils.py   # Reuters sitemap scraper
│   │   ├── reddit_utils.py    # Reddit public JSON API (bodies + comments)
│   │   ├── stocktwits_utils.py
│   │   ├── finnhub_utils.py
│   │   ├── market_data_tools.py  # options flow, earnings calendar,
│   │   │                         #   analyst targets, short interest
│   │   └── y_finance.py       # yfinance wrapper with streaming CSV cache
│   │                          #   (500KB size guard, 15-year file detection)
│   ├── llm_clients/           # LLM provider adapters
│   ├── research_context.py    # Loads + truncates findings for macro_context
│   └── default_config.py      # Default configuration
│
├── tests/                     # 309 tests (pytest)
├── tickets/                   # TICKET-001 through TICKET-034
│
├── results/                   # Daily research findings (gitignored except .md)
│   └── RESEARCH_FINDINGS_YYYY-MM-DD.md
│
└── trading_loop_logs/         # Runtime data (committed to git)
    ├── YYYY-MM-DD.json        # Daily trade log (includes agent stop/target/size)
    ├── YYYY-MM-DD.checkpoint.json  # Crash-resume checkpoint
    ├── memory/{TICKER}/       # Per-ticker agent memories + embeddings
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
| `FINNHUB_API_KEY` | Recommended | Richer news with full summaries (free tier at finnhub.io) |

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

**Why regex-only signal extraction?** The Risk Judge is explicitly instructed to end
with `FINAL DECISION: **BUY**`. A secondary LLM call to re-extract the same signal
adds cost (~$12/year) and a failure point with no quality benefit.

**Why agent position size multiplier?** The Risk Judge outputs conviction-based
sizing (e.g. "0.5x" on a mixed-signal setup). Discarding this and using full tier
allocation ignores the system's own risk assessment. The multiplier is clamped to
0.25x–2x to prevent extreme positions from malformed output.

**Why max 20 open positions?** Prevents all 34 tickers from being bought on a
broad BUY sweep. With $100K equity and $2K/trade CORE sizing, 20 positions = $40K
invested (40% of portfolio), leaving adequate cash for opportunistic additions.

**Why crash-resume checkpoint?** A mid-cycle crash previously caused tickers to be
re-analysed and re-traded 3-5× in a day. The checkpoint ensures each ticker runs
exactly once per analysis date regardless of how many times the process restarts.

**Why paper trading only?** The system is designed for research and learning.
Alpaca paper trading uses real market data and realistic order execution without
risking real capital. Switch to live trading by changing `ALPACA_BASE_URL` to the
live endpoint and using live API keys — but that's your decision to make.
