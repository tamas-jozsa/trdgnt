# TrdAgnt -- System Specification

> Last updated: April 2026 (reflects TICKET-001 through TICKET-074)

---

## Overview

**trdagnt** is a fully automated daily paper trading system built on top of the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

It runs once per day at 10:00 AM ET, analyses a curated 34-ticker watchlist
using a 12-agent LLM debate pipeline, executes paper trades on Alpaca Markets,
and learns from past decisions through a persistent per-ticker memory system.

Three enforcement layers (conviction bypass, signal override reversal, buy quota
enforcement) ensure the system actively deploys capital rather than defaulting
to HOLD.

---

## Architecture

```
10:00 AM ET (weekdays only)
       |
       v
[daily_research.py]
  1. sync live positions -> positions.json + MARKET_RESEARCH_PROMPT.md
  2. scrape: VIX, Yahoo gainers, watchlist prices, Reuters, Reddit x 4
  3. call gpt-4o-mini with compact system prompt -> structured findings .md
  4. parse ADD/REMOVE ticker decisions -> watchlist_overrides.json
  Idempotent: skips if today's findings file already exists (--force to redo)
       |
       v
[safety checks]
  1. agent stop check     per-ticker stop-loss prices from Risk Judge
  2. global stop-loss     auto-SELL any with unrealised P&L <= -15%
  3. exit rules           50% profit-taking, 30-day time stop, trailing stop
  4. sector exposure      report portfolio concentration by sector (warn > 40%)
       |
       v
[checkpoint guard]
  load trading_loop_logs/{trade_date}.checkpoint.json
  skip any tickers already completed in a prior run today (crash-resume)
       |
       v
for each of 34 tickers:
       |
       +-- [load_memories]     BM25 + embedding memory from prior sessions
       +-- [position_context]  live Alpaca position (entry, P&L)
       |                       OR "NO POSITION -- SELL not actionable"
       +-- [macro_context]     condensed daily findings (<=8,000 chars):
       |                       SENTIMENT, VIX, MACRO THEMES, WATCHLIST
       |                       DECISIONS, NEW PICKS, SECTORS TO AVOID
       +-- [research_signal]   per-ticker BUY/SELL/HOLD from daily research
       +-- [sector_context]    sector FAVOR/AVOID from macro themes
       |
       v
  +-----------------------------------------------------+
  |           12-AGENT ANALYSIS PIPELINE                 |
  |                                                      |
  |  Market Analyst      (quick_think_llm)               |
  |    90d OHLCV, 10 indicators, earnings calendar       |
  |              |                                       |
  |  Social Analyst      (quick_think_llm)               |
  |    Reddit x 4 (titles + bodies + top comments)       |
  |    StockTwits, options P/C ratio, short interest     |
  |              |                                       |
  |  News Analyst        (quick_think_llm)               |
  |    earnings date/binary risk, Reuters sitemap        |
  |    Yahoo Finance news, Finnhub (if key set)          |
  |              |                                       |
  |  Fundamentals Analyst (quick_think_llm)              |
  |    P/E, EV/EBITDA, EV/Revenue, FCF, D/E              |
  |    revenue/earnings growth YoY, analyst targets      |
  |    insider transactions, balance sheet               |
  |              |                                       |
  |  Bull Researcher     (quick_think_llm) x N rounds    |
  |  Bear Researcher     (quick_think_llm) x N rounds    |
  |    structured debate -- N = tier debate rounds       |
  |              |                                       |
  |  Research Manager    (deep_think_llm)                |
  |    sees ALL 4 analyst reports + full debate          |
  |    HOLD tiebreaker rule applied if conviction tied   |
  |    outputs: RECOMMENDATION / CONVICTION / ENTRY /    |
  |             STOP / TARGET / SIZE                     |
  |              |                                       |
  |  Trader              (quick_think_llm)               |
  |    concrete trade proposal with stop + target        |
  |              |                                       |
  |  [CONVICTION BYPASS CHECK] (TICKET-068)              |
  |    conv >= 8 (or >= 7 when cash > 85%)               |
  |    + research signal agrees + cash > 70%             |
  |    YES -> skip Risk Judge, execute immediately       |
  |    NO  -> continue to Risk Debate                    |
  |              |                                       |
  |  Risk: Aggressive    (quick_think_llm) x N rounds    |
  |  Risk: Conservative  (quick_think_llm) x N rounds    |
  |  Risk: Neutral       (quick_think_llm) x N rounds    |
  |    independent evaluation (not defence)              |
  |    N = tier risk rounds                              |
  |              |                                       |
  |  Risk Judge          (deep_think_llm)                |
  |    final FINAL DECISION: BUY/SELL/HOLD               |
  |    CONVICTION: 1-10                                  |
  |    STOP-LOSS: $X.XX                                  |
  |    TARGET: $X.XX                                     |
  |    POSITION SIZE: 0.25x-2x                           |
  +-----------------------------------------------------+
       |
       v
[signal_override check]     detect Risk Judge overrides (TICKET-067)
                            critical BUY->HOLD + cash > 80% -> revert to BUY
       |
       v
[signal_processor]          regex extraction of BUY/SELL/HOLD from Risk Judge text
                            no secondary LLM call
       |
       v
[parse_agent_decision]      extract stop, target, conviction, size_multiplier
                            multiplier clamped to tier-specific limits (TICKET-058)
       |
       v
[cash_boost]                cash > 85%: 1.5x boost; 80-85%: 1.25x; 70-80%: 1.10x
                            (TICKET-070, BUY orders only)
       |
       v
[stop_loss_cooldown]        ticker stopped in last 3 days? block BUY (TICKET-059)
       |
       v
[portfolio limit guard]     dynamic max positions: 28 (cash>80%), 25 (50-80%), 20 (<50%)
                            BUY downgraded to HOLD at cap (TICKET-063)
       |
       v
[execute_decision]          Alpaca market order (fractional shares, DAY TIF)
                            effective amount = base tier amount x size_multiplier x cash_boost
                            SELL exits full position (not partial)
       |
       v
[record_position_entry]     save entry price, stop, target for exit rule tracking
       |
       v
[reflect_and_remember]      LLM writes lesson from P&L outcome -> 5 agent memories
       |
       v
[save_memories]             trading_loop_logs/memory/{TICKER}/{agent}.json
       |
       v
[save_checkpoint]           trading_loop_logs/{trade_date}.checkpoint.json
       |
       v
[save_report]               trading_loop_logs/reports/{TICKER}/{date}.md

--- END OF TICKER LOOP ---
       |
       v
[BUY QUOTA ENFORCEMENT]    (TICKET-072)
  if cash > 80% and high-conviction BUY signals > 5 but actual BUYs < 5:
  force-buy up to 5 missed opportunities as market orders
       |
       v
[monthly tier review]       (TICKET-066, 1st-5th of month)
  review 30-day P&L per ticker, recommend tier promotions/demotions
```

---

## Enforcement Layers

Three mechanisms prevent the system from sitting idle in cash:

### 1. Conviction Bypass (TICKET-068)

After the Trader proposes a trade, the system checks if the Research Manager's
conviction is high enough to skip the Risk Judge entirely:

| Condition | Threshold |
|-----------|-----------|
| Standard bypass | conviction >= 8 + research agrees + cash > 70% |
| Aggressive bypass (cash emergency) | conviction >= 7 + research agrees + cash > 85% |
| SELL bypass | conviction >= 8 + research agrees + has position |

REDUCE signals from research are treated as SELL for agreement purposes.

Implementation: `tradingagents/conviction_bypass.py`, wired into
`tradingagents/graph/setup.py:_check_bypass()`.

### 2. Signal Override Reversal (TICKET-067)

After the Risk Judge decides, the system detects if a strong upstream BUY signal
was overridden to HOLD. Override severity is based on upstream conviction:

| Upstream conviction | Severity |
|----|------|
| >= 9 | critical |
| >= 8 | high |
| >= 7 | medium |
| < 7 | not flagged |

**Enforcement:** Critical and high severity BUY->HOLD overrides are automatically
**reverted back to BUY** when cash > 80%. SELL->HOLD overrides are never reverted
(too risky to force exits). All overrides are logged to
`trading_loop_logs/signal_overrides.json`.

Implementation: `tradingagents/signal_override.py` (`should_revert_override()`),
called from `trading_loop.py`.

### 3. Buy Quota Enforcement (TICKET-072)

After all tickers are analysed, the system checks if enough BUYs were executed
relative to high-conviction research signals:

- Only enforced when cash > 80%
- Requires >= 5 high-conviction BUY research signals to activate
- If quota is missed, **force-buys up to 5 of the missed opportunities** as
  market orders at tier-appropriate sizing
- Capped at 5 forced BUYs per cycle to prevent runaway buying

Implementation: `tradingagents/buy_quota.py` (`get_force_buy_tickers()`),
called from `trading_loop.py`.

---

## Risk Judge Anti-HOLD-Bias Prompt (TICKET-057)

The Risk Judge's system prompt contains explicit rules to prevent default-to-HOLD
behaviour:

- Earnings avoidance only valid within 7 calendar days (not 30)
- Must execute high-conviction BUYs (>= 7) unless 2/3 debaters provide specific,
  data-backed counter-arguments
- When cash > 80%, HOLD on high-conviction setups is explicitly flagged as failure
- The Conservative Analyst's generic "earnings risk" or "volatility" arguments
  are called out as insufficient when cash is high
- Override reasons must be specific and falsifiable ("volatility risk" is rejected)

---

## Watchlist

34 tickers across 4 conviction tiers. Defined in `trading_loop.py:WATCHLIST`.

| Tier | Count | Position size | Debate rounds | Description |
|------|-------|---------------|---------------|-------------|
| CORE | 25 | 2.0x base | 2 (bull/bear + risk) | High conviction, macro-aligned, liquid |
| TACTICAL | 5 | 1.0x base | 1 | Momentum / catalyst-driven, 1-4 week horizon |
| SPECULATIVE | 3 | 0.4x base | 1 | Squeeze/biotech/meme, max 2-3% of portfolio |
| HEDGE | 1 | 0.5x base | 1 | GLD -- geopolitical/volatility buffer |

> The tier multiplier is the **base** scaling. The Risk Judge can further adjust
> individual orders within tier-specific limits:
>
> | Tier | Min | Max |
> |------|-----|-----|
> | CORE | 0.50x | 2.00x |
> | TACTICAL | 0.25x | 1.50x |
> | SPECULATIVE | 0.10x | 0.75x |
> | HEDGE | 0.25x | 1.00x |
>
> Example: CORE + "POSITION SIZE: 0.5x" -> 2.0 x 0.5 = 1.0x effective.
> A SPECULATIVE ticker requesting 1.75x is clamped to 0.75x.

When portfolio cash is high, a **cash deployment boost** is applied to BUY orders:

| Cash ratio | Boost |
|-----------|-------|
| > 85% | 1.50x |
| 80-85% | 1.25x |
| 70-80% | 1.10x |
| < 70% | 1.00x (no boost) |

**CORE (25):** NVDA, AVGO, AMD, ARM, TSM, MU, LITE, MSFT, GOOGL, META, PLTR, GLW,
MDB, NOW, PANW, CRWD, RTX, LMT, NOC, VG, LNG, XOM, FCX, MP, UBER

**TACTICAL (5):** CMC, NUE, APA, SOC, SCCO

**SPECULATIVE (3):** RCAT, MOS, RCKT

**HEDGE (1):** GLD

**Dynamic watchlist:** The daily research findings are automatically parsed for
ADD/REMOVE decisions, which are persisted to
`trading_loop_logs/watchlist_overrides.json` and applied to the next cycle.
Static `WATCHLIST` in `trading_loop.py` is never mutated; overrides are merged
at runtime via `load_watchlist_overrides()`. Removes expire after 5 days.
Max 8 removes and 10 adds at a time.

---

## Data Sources

| Source | Used by | Auth | What |
|--------|---------|------|------|
| **Yahoo Finance** (`yfinance`) | Market Analyst, Fundamentals, News, Options, Earnings, Analyst Targets, Short Interest, Daily Research | None | OHLCV (90d), 10 indicators, financials, news feed, options chain, earnings calendar, analyst consensus targets, insider transactions, short float |
| **Reuters** (public XML sitemap) | News Analyst, Daily Research | None | Breaking news with `news:stock_tickers` tags; hourly updates; 12-24h lookback |
| **Reddit** (public `.json` API) | Social Analyst, Daily Research | None | r/wallstreetbets, r/stocks, r/investing, r/pennystocks -- hot post titles + bodies (500 chars) + top 2 comments |
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

Two-tier model design -- decision nodes get the capable model, data-retrieval nodes get the cheap model.

| Role | Default model | Env var override |
|------|--------------|-----------------|
| Research Manager (decision) | `gpt-4o` | `DEEP_LLM_MODEL` |
| Risk Judge (decision) | `gpt-4o` | `DEEP_LLM_MODEL` |
| 4 Analysts | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
| Bull/Bear Researchers | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
| Trader | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
| Risk Debaters (x3) | `gpt-4o-mini` | `QUICK_LLM_MODEL` |
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

Five agent memories per ticker -- one for each decision-making agent.

| Agent memory | Stored at |
|---|---|
| `bull_memory` | `trading_loop_logs/memory/{TICKER}/bull_memory.json` |
| `bear_memory` | `trading_loop_logs/memory/{TICKER}/bear_memory.json` |
| `trader_memory` | `trading_loop_logs/memory/{TICKER}/trader_memory.json` |
| `invest_judge_memory` | `trading_loop_logs/memory/{TICKER}/invest_judge_memory.json` |
| `risk_manager_memory` | `trading_loop_logs/memory/{TICKER}/risk_manager_memory.json` |

- **Cap:** 500 entries per agent per ticker (`MAX_MEMORY_ENTRIES = 500`); oldest evicted
- **Retrieval -- BM25 (default):** `rank-bm25`, keyword tokenization, no API cost
- **Retrieval -- Embeddings (opt-in):** OpenAI `text-embedding-3-small`, cosine
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

1. **Sync positions** -- `update_positions.py::fetch_positions()` -> `positions.json`
   + injects live holdings into `MARKET_RESEARCH_PROMPT.md` placeholder tags
2. **Scrape live data** -- VIX (Yahoo Finance v8), Yahoo Finance top gainers,
   watchlist prices (yfinance, 5d), Reuters global headlines (sitemap),
   Reddit hot posts (r/wallstreetbets, r/stocks, r/investing, r/pennystocks)
3. **Call OpenAI** -- `gpt-4o-mini` with a compact `~1,200-token` system prompt
   (under 2,000 tokens total input for most days)
4. **Save findings** -- `results/RESEARCH_FINDINGS_YYYY-MM-DD.md`
5. **Parse watchlist changes** -- regex extracts ADD/REMOVE decisions from findings;
   persisted to `trading_loop_logs/watchlist_overrides.json`
6. **Parse research signals** -- `research_context.py:parse_research_signals()` extracts
   per-ticker BUY/SELL/HOLD signals with conviction levels for bypass and quota logic
7. **Parse sector signals** -- `research_context.py:parse_sector_signals()` extracts
   sector-level FAVOR/AVOID signals for position sizing bias
8. **Inject into agents** -- `research_context.py` loads the findings file, extracts
   priority sections (SENTIMENT, VIX, MACRO THEMES, WATCHLIST DECISIONS, NEW PICKS,
   SECTORS TO AVOID), and truncates to <=8,000 chars as `macro_context`

**Idempotent:** Skips with existing path if today's findings file already exists.
Force-redo with `run_daily_research(force=True)` or `python daily_research.py --force`.

**Cost:** ~$0.003/day (~$1.10/year) at `gpt-4o-mini` default.

**Manual workflow:** `MARKET_RESEARCH_PROMPT.md` is a 636-line structured prompt
that can be pasted directly into any AI chat interface as an alternative to the
automated pipeline.

---

## Stop-Loss and Exit Rules

### Global Stop-Loss

Runs at the start of every cycle, before any ticker analysis.

- **Default threshold:** -15% unrealised P&L (`--stop-loss 0.15`)
- **Action:** Alpaca market SELL order for the full position
- **Cooldown:** Stopped tickers enter a 3-day cooldown period (TICKET-059); BUY
  orders are blocked during cooldown to prevent whipsaw re-buys
- **Logged:** `STOP_LOSS_TRIGGERED` written to daily trade log JSON; cooldown
  tracked in `trading_loop_logs/stop_loss_history.json`
- **macOS notification:** sent on each triggered stop
- **Dry-run safe:** `--dry-run` logs what would be sold but places no orders

### Agent Per-Ticker Stops (TICKET-071)

The Risk Judge's `STOP-LOSS` price is saved per position in
`trading_loop_logs/position_entries.json`. Each cycle:

- All open positions with logged stop prices are checked
- If current price <= agent stop price, a full exit is triggered
- Stop directional validation: BUY stops must be below entry, SELL stops above

### Time-Based Exit Rules (TICKET-062)

| Rule | Condition | Action |
|------|-----------|--------|
| Profit-taking | Unrealised gain >= 50% | Sell position |
| Time stop | Held > 30 days | Exit position |
| Trailing stop | 20%+ gain, then 10% pullback from high | Sell position |

---

## Trade Execution

All orders are placed on **Alpaca paper trading** (no real money).

- **Order type:** Market order, DAY time-in-force
- **Fractional shares:** qty = `effective_amount / price`, 6 decimal places
- **Position sizing:**
  1. Base tier amount (e.g. $2,000 for CORE at $1,000 base)
  2. x Risk Judge size multiplier (clamped to tier limits, TICKET-058)
  3. x Cash deployment boost (1.0x-1.5x based on cash ratio, TICKET-070)
  4. = Effective trade amount
- **BUY guards:**
  - Available cash < $1 -> SKIPPED (`"reason": "insufficient_cash"`)
  - Live positions >= dynamic max (20-28) -> BUY downgraded to HOLD (TICKET-063)
  - Ticker in stop-loss cooldown -> SKIPPED (`"reason": "stop_loss_cooldown"`)
- **SELL guard:** No open position -> SKIPPED (`"reason": "no_position"`)
- **SELL behaviour:** exits the entire position (not `trade_amount_usd` worth)
- **Price fallback chain:** ask -> bid -> last trade -> yfinance close (handles after-hours)

---

## Crash-Resume / Checkpoint

Every ticker that completes (including on error) is written to:

```
trading_loop_logs/{trade_date}.checkpoint.json
```

On restart, completed tickers are skipped -- each ticker runs exactly once per
analysis date regardless of how many times the process restarts.

- Keyed by analysis date: a new calendar day starts a fresh checkpoint
- Error tickers are checkpointed and not retried within the same day
- `--from TICKER` CLI flag: skip all tickers before the specified one (manual resume)

---

## Portfolio Limits

| Guard | Value | Location | Behaviour |
|-------|-------|----------|-----------|
| Max open positions | 20-28 (dynamic) | `run_daily_cycle()` | 28 when cash>80%, 25 when 50-80%, 20 when <50% (TICKET-063) |
| Min cash for BUY | $1 | `execute_decision()` | BUY skipped with reason `insufficient_cash` |
| No-position SELL | -- | `execute_decision()` | SELL skipped with reason `no_position` |
| Stop-loss cooldown | 3 days | `execute_decision()` | BUY blocked after stop triggered (TICKET-059) |
| Sector exposure | 40% max/sector | `run_daily_cycle()` | Warning logged at cycle start (TICKET-073) |

---

## Sector Awareness

### Sector Rotation (TICKET-065)

Research context parsing extracts sector-level FAVOR/AVOID signals from macro themes.
Each ticker is mapped to a sector via `TICKER_SECTORS` in `research_context.py`.

| Sector | Tickers |
|--------|---------|
| TECHNOLOGY | NVDA, AVGO, AMD, ARM, TSM, MU, LITE, MSFT, GOOGL, META, PLTR, GLW, MDB, NOW, PANW, CRWD, VG, UBER |
| DEFENSE | RTX, LMT, NOC |
| ENERGY | LNG, XOM, APA |
| MATERIALS | FCX, MP, CMC, NUE, SCCO, SOC |
| HEDGE | GLD |

FAVORED sectors get a +25% position size bias. AVOIDED sectors get -25%.

### Sector Exposure Monitoring (TICKET-073)

At the start of each cycle, the system reports portfolio concentration by sector
and warns if any single sector exceeds 40% of invested capital.

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
- **Weekends:** auto-skip (Friday after 10am -> Monday 10am)
- **Analysis date:** Previous completed trading session:
  - Monday -> Friday; Tuesday-Friday -> yesterday; Saturday/Sunday -> Friday
- **Restart:** Auto-restarts on crash (`KeepAlive: true`)
- **On login:** Starts automatically (`RunAtLoad: true`)
- **FD limit:** Raised to min(4096, hard limit) at startup -- macOS default of
  256 is exhausted by ticker 12+ when opening multiple CSV + memory files
- **Live dashboard:** `watch_agent.sh` -- terminal dashboard that refreshes every
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

## Runtime Logs

```
trading_loop_logs/
  {YYYY-MM-DD}.json              # Daily trade log (all decisions + orders)
  {YYYY-MM-DD}.checkpoint.json   # Crash-resume checkpoint
  watchlist_overrides.json       # Dynamic watchlist ADD/REMOVE state
  signal_overrides.json          # Risk Judge override detection + reversals
  buy_quota_log.json             # BUY quota enforcement audit trail
  stop_loss_history.json         # Stop-loss cooldown tracking
  position_entries.json          # Entry prices for exit rule tracking
  stdout.log / stderr.log       # LaunchAgent captured output
  memory/{TICKER}/               # 5 agent memories per ticker
    bull_memory.json
    bull_memory.embeddings.json
    ... (bear, trader, invest_judge, risk_manager)
  reports/{TICKER}/              # Human-readable per-ticker reports
    YYYY-MM-DD.md
```

---

## Cost

| Component | Daily | Annual |
|-----------|-------|--------|
| Daily research (`gpt-4o-mini`) | ~$0.003 | ~$1.10 |
| 34 tickers x ~$0.04/ticker (mixed gpt-4o + gpt-4o-mini) | ~$1.40 | ~$511 |
| **Total** | **~$1.40** | **~$512** |

Costs are approximate. `--dry-run` costs the same (analysis is identical).
Reduce cost by setting `DEEP_LLM_MODEL=gpt-4o-mini` (lower decision quality).

---

## File Structure

```
trdagnt/
+-- trading_loop.py          # Daily loop -- watchlist, scheduling, cycle,
|                            #   checkpoint, position guard, enforcement
+-- alpaca_bridge.py         # Alpaca integration -- orders, positions,
|                            #   stop-loss, exit rules, cooldown, decision parser
+-- daily_research.py        # Automated market research pipeline
+-- update_positions.py      # Sync broker positions -> positions.json
|                            #   + inject into MARKET_RESEARCH_PROMPT.md
+-- main.py                  # Single-ticker demo harness (no orders placed)
+-- watch_agent.sh           # Live terminal dashboard (60s refresh)
+-- tier_manager.py          # Monthly tier review (promote/demote by P&L)
+-- analyze_conviction.py    # Conviction mismatch dashboard
+-- watchlist_cleaner.py     # Clean expired/stale watchlist overrides
|
+-- MARKET_RESEARCH_PROMPT.md  # 636-line manual research prompt template
|                               # (also used for automated position injection)
+-- SPEC.md                    # This file
+-- README.md                  # Setup and usage guide
|
+-- tradingagents/             # Core LangGraph agent framework (package)
|   +-- default_config.py      # DEFAULT_CONFIG -- all tunable settings
|   |                          #   tier limits, exit rules, dynamic max positions,
|   |                          #   cash boost thresholds
|   +-- research_context.py    # Load + truncate findings -> macro_context (<=8,000 chars)
|   |                          #   parse_research_signals() -- per-ticker signals
|   |                          #   parse_sector_signals() -- sector FAVOR/AVOID
|   |                          #   build_sector_context() -- sector bias for prompts
|   +-- conviction_bypass.py   # Skip Risk Judge on high-conviction signals (TICKET-068)
|   +-- signal_override.py     # Detect + revert Risk Judge overrides (TICKET-067)
|   +-- buy_quota.py           # BUY quota tracking and enforcement (TICKET-072)
|   +-- sector_monitor.py      # Portfolio sector exposure monitoring (TICKET-073)
|   +-- graph/
|   |   +-- trading_graph.py   # TradingAgentsGraph orchestrator class
|   |   +-- setup.py           # LangGraph StateGraph wiring + conviction bypass check
|   |   +-- propagation.py     # Initial state + graph invocation
|   |   +-- conditional_logic.py  # Debate routing + tool-call guard (max 6)
|   |   +-- reflection.py      # Post-trade LLM reflection -> memory writes
|   |   +-- signal_processing.py  # Regex-only BUY/SELL/HOLD extraction
|   +-- agents/
|   |   +-- analysts/          # market, social, news, fundamentals
|   |   +-- researchers/       # bull, bear
|   |   +-- managers/          # research_manager (tiebreaker), risk_manager (anti-HOLD)
|   |   +-- trader/
|   |   +-- risk_mgmt/         # aggressive, conservative, neutral debaters
|   |   +-- utils/
|   |       +-- memory.py      # FinancialSituationMemory (BM25 + embeddings)
|   |       |                  # MAX_MEMORY_ENTRIES = 500
|   |       +-- agent_states.py
|   |       +-- agent_utils.py # Tool re-exports, message-trim helpers
|   |       +-- core_stock_tools.py
|   |       +-- technical_indicators_tools.py
|   |       +-- fundamental_data_tools.py
|   |       +-- news_data_tools.py
|   +-- dataflows/
|   |   +-- interface.py          # Vendor routing (yfinance / alpha_vantage / finnhub)
|   |   +-- y_finance.py          # yfinance wrapper -- OHLCV, indicators,
|   |   |                         #   fundamentals, news; CSV cache with
|   |   |                         #   3-day TTL + 15-year-file detection
|   |   +-- reuters_utils.py      # Reuters public XML sitemap scraper
|   |   +-- reddit_utils.py       # Reddit public JSON API (bodies + comments)
|   |   +-- stocktwits_utils.py   # StockTwits public API
|   |   +-- finnhub_utils.py      # Finnhub REST API (optional key)
|   |   +-- market_data_tools.py  # Options flow, earnings calendar,
|   |   |                         #   analyst targets, short interest
|   |   +-- alpha_vantage*.py     # Alpha Vantage legacy/fallback path
|   |   +-- config.py             # Global config getter/setter
|   +-- llm_clients/
|       +-- factory.py            # Provider router -> concrete client
|       +-- base_client.py
|       +-- openai_client.py      # OpenAI + xAI + Ollama + OpenRouter
|       +-- anthropic_client.py
|       +-- google_client.py
|       +-- validators.py         # Model name allowlists per provider
|
+-- cli/
|   +-- main.py                # Typer CLI (`tradingagents` entrypoint)
|
+-- tests/                     # 429+ tests across 31 test files (pytest)
+-- tickets/                   # TICKET-001 through TICKET-074
|
+-- results/                   # Daily research (gitignored runtime data)
|   +-- RESEARCH_FINDINGS_YYYY-MM-DD.md
|
+-- trading_loop_logs/         # Runtime data (see Runtime Logs section)
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
| `exit_rules.profit_taking_50` | enabled, 50% | Sell on 50%+ gain |
| `exit_rules.time_stop` | enabled, 30 days | Exit stale positions |
| `exit_rules.trailing_stop` | enabled, 20% activate, 10% trail | Trailing stop |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | -- | LLM inference (agents + research) + `text-embedding-3-small` |
| `ALPACA_API_KEY` | Yes | -- | Alpaca paper account key |
| `ALPACA_API_SECRET` | Yes | -- | Alpaca paper account secret |
| `ALPACA_BASE_URL` | No | `https://paper-api.alpaca.markets` | Used by `alpaca_bridge.py`, `trading_loop.py`, `update_positions.py` |
| `DEEP_LLM_MODEL` | No | `gpt-4o` | Research Manager + Risk Judge model |
| `QUICK_LLM_MODEL` | No | `gpt-4o-mini` | Analysts + debaters + trader model |
| `RESEARCH_LLM_MODEL` | No | `gpt-4o-mini` | Daily research LLM model |
| `FINNHUB_API_KEY` | Recommended | -- | Richer news summaries (free tier at finnhub.io); graceful skip if absent |
| `ANTHROPIC_API_KEY` | No | -- | For Claude provider |
| `GOOGLE_API_KEY` | No | -- | For Gemini provider |
| `XAI_API_KEY` | No | -- | For Grok provider |
| `OPENROUTER_API_KEY` | No | -- | For OpenRouter provider |
| `ALPHA_VANTAGE_API_KEY` | No | -- | Legacy fallback data path |

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
python update_positions.py                    # sync -> positions.json + prompt

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
add-reducer that accumulates across all nodes -- parallel branches
cross-contaminate each other's `tool_call` message chains, causing OpenAI 400
errors. Sequential is correct and reliable.

**Why Reuters sitemap instead of RSS?** Reuters shut down public RSS in 2023.
The sitemap is public, updates hourly, and includes `news:stock_tickers` tags --
Reuters editors explicitly tag which stocks each article covers, giving
high-precision ticker -> article matching with no keyword parsing required.

**Why BM25 + embeddings?** BM25 works offline at zero API cost. Embeddings
(`text-embedding-3-small`) handle semantic similarity -- "Iran war oil spike"
matches "geopolitical supply shock commodity rally" even with no word overlap.
Embeddings activate automatically when `OPENAI_API_KEY` is set.

**Why regex-only signal extraction?** The Risk Judge is explicitly instructed to
output `FINAL DECISION: **BUY**`. A secondary LLM call to re-extract the same
signal adds cost (~$12/year) and a failure point with no quality benefit.

**Why agent position size multiplier?** The Risk Judge outputs conviction-based
sizing (e.g. `POSITION SIZE: 0.5x` on a mixed-signal setup). Discarding this
and using full tier allocation ignores the system's own risk assessment.
Multiplier is clamped per tier to prevent extreme positions from malformed output.

**Why three enforcement layers?** The Risk Judge was observed overriding 78% of
high-conviction BUY signals, leaving 94.6% of capital as cash. Prompt engineering
alone was insufficient -- the Conservative Debater's generic arguments about
"earnings risk" consistently dominated. Hard code-level enforcement (bypass,
revert, quota) ensures capital is actually deployed.

**Why dynamic max positions?** A static cap of 20 made sense at 28 tickers. With
34 tickers and enforcement pushing more BUYs, the cap dynamically adjusts from
20 (at low cash) to 28 (at high cash) to avoid conflicting with the deployment
mandate.

**Why crash-resume checkpoint?** A mid-cycle crash previously caused tickers to
be re-analysed and re-traded 3-5x in a day. The checkpoint ensures each ticker
runs exactly once per analysis date regardless of process restarts.

**Why paper trading only?** The system is designed for research and learning.
Alpaca paper trading uses real market data and realistic order execution without
risking real capital. To switch to live trading, set `ALPACA_BASE_URL` to the
live endpoint and use live API keys -- but that decision is yours to make.

**Why no global SSL verification bypass?** The original codebase patched
`requests.Session.__init__` globally at import time as a corporate proxy
workaround. This was removed (TICKET-035): the fix disables SSL verification
only on the specific Alpaca REST calls that need it, leaving all other HTTP
clients (yfinance, OpenAI, Reddit, Reuters) using verified connections.
