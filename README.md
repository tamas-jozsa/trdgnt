# trdagnt

Automated daily paper trading system built on the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

Runs once per day at **10:00 AM ET**. Analyses a 34-ticker curated watchlist
through a 12-agent LLM debate pipeline (analysts -> bull/bear researchers ->
risk debaters -> risk judge), then executes paper trades via
[Alpaca Markets](https://alpaca.markets).

Three enforcement layers prevent the system from sitting idle:
conviction bypass, signal override reversal, and buy quota enforcement.

> **Paper trading only.** No real money is at risk.
> Not financial advice.

---

## How it works

```
10:00 AM ET
     |
     +-- daily_research.py   scrape VIX + Reuters + Reddit + Yahoo -> gpt-4o-mini -> findings.md
     +-- stop-loss check      auto-sell any position down >= 15%
     +-- agent stop check     per-ticker stop-loss from Risk Judge
     +-- exit rules           50% profit-taking, 30-day time stop, trailing stop
     +-- sector exposure      report portfolio concentration by sector
     |
     +-- for each of 34 tickers:
           Market Analyst      -> 90d OHLCV, RSI, MACD, Bollinger, ATR, MFI ...
           Social Analyst      -> Reddit x 4, StockTwits, options P/C, short interest
           News Analyst        -> Reuters, Yahoo Finance, Finnhub, earnings calendar
           Fundamentals Analyst-> P/E, EV/EBITDA, FCF, insider buys, analyst targets
           Bull Researcher x N <-> Bear Researcher x N   (N = 2 for CORE, 1 for others)
           Research Manager    -> synthesises all reports -> investment plan  [gpt-4o]
           Trader              -> concrete proposal
               |
               +-- [CONVICTION BYPASS] conviction >= 7-8 + research agrees -> skip Risk Judge
               |
           Risk Debaters x 3   -> aggressive / conservative / neutral evaluation
           Risk Judge          -> FINAL DECISION + stop + target + position size  [gpt-4o]
               |
               +-- [OVERRIDE ENFORCEMENT] critical BUY->HOLD override reverted when cash > 80%
               +-- regex signal extraction (no secondary LLM call)
               +-- tier-based position clamping (0.25x-2x per tier)
               +-- cash boost (up to 1.5x when cash > 85%)
               +-- stop-loss cooldown check (3-day re-buy block)
               +-- portfolio limit guard (dynamic max 20-28 positions)
               +-- Alpaca market order (fractional shares)
               +-- reflect & remember (5 agent memories per ticker)
     |
     +-- [BUY QUOTA ENFORCEMENT] force-buy up to 5 missed high-conviction opportunities
```

**Cost:** ~$1.40/day (~$512/year) at default settings (`gpt-4o` decisions,
`gpt-4o-mini` analysts). Set `DEEP_LLM_MODEL=gpt-4o-mini` to cut this by ~80%.

---

## Prerequisites

- macOS (the background agent uses `launchctl`; the loop itself runs fine on Linux too)
- [conda](https://docs.conda.io/en/latest/miniconda.html) or Python 3.10+
- An [Alpaca paper trading account](https://app.alpaca.markets) (free)
- An [OpenAI API key](https://platform.openai.com/api-keys)

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-fork/trdagnt.git
cd trdagnt

conda create -n tradingagents python=3.13
conda activate tradingagents

pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

```bash
# Required
OPENAI_API_KEY=sk-...
ALPACA_API_KEY=PK...
ALPACA_API_SECRET=...

# Optional but recommended
FINNHUB_API_KEY=...          # free tier at finnhub.io -- improves news quality
ALPACA_BASE_URL=https://paper-api.alpaca.markets   # already the default

# LLM model overrides (defaults shown)
DEEP_LLM_MODEL=gpt-4o        # Research Manager + Risk Judge (decision nodes)
QUICK_LLM_MODEL=gpt-4o-mini  # 4 analysts + debaters + trader
RESEARCH_LLM_MODEL=gpt-4o-mini  # daily research pipeline
```

### 3. Shell aliases (one-time, recommended)

Add to `~/.zshrc` or `~/.bashrc`, replacing paths with yours:

```bash
_TDIR="/path/to/trdagnt"
_TPY="/path/to/miniconda3/envs/tradingagents/bin/python"

alias trading='bash $_TDIR/watch_agent.sh'
alias trading-now='cd $_TDIR && $_TPY trading_loop.py --once --no-wait'
alias trading-dry='cd $_TDIR && $_TPY trading_loop.py --once --no-wait --dry-run'
alias positions='$_TPY $_TDIR/update_positions.py'

trading-from() { cd "$_TDIR" && "$_TPY" trading_loop.py --once --no-wait --from "$@"; }
```

Reload: `source ~/.zshrc`

### 4. Background agent (macOS, one-time)

Create `~/Library/LaunchAgents/com.tradingagents.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key>
  <string>com.tradingagents</string>

  <key>ProgramArguments</key>
  <array>
    <string>/path/to/miniconda3/envs/tradingagents/bin/python</string>
    <string>-u</string>
    <string>/path/to/trdagnt/trading_loop.py</string>
    <string>--amount</string>
    <string>1000</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/path/to/trdagnt</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/path/to/miniconda3/envs/tradingagents/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key>
    <string>/Users/your-username</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
    <key>PYTHONWARNINGS</key><string>ignore</string>
    <key>OPENAI_API_KEY</key><string>sk-...</string>
    <key>ALPACA_API_KEY</key><string>PK...</string>
    <key>ALPACA_API_SECRET</key><string>...</string>
    <key>ALPACA_BASE_URL</key><string>https://paper-api.alpaca.markets</string>
    <key>FINNHUB_API_KEY</key><string>...</string>
  </dict>

  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>

  <key>StandardOutPath</key>
  <string>/path/to/trdagnt/trading_loop_logs/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/trdagnt/trading_loop_logs/stderr.log</string>
</dict></plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.tradingagents.plist
```

The agent starts on login (`RunAtLoad`), auto-restarts on crash (`KeepAlive`),
and runs one cycle per day at 10:00 AM ET. Weekends are skipped automatically.

---

## Daily usage

### Live dashboard

```bash
trading
```

Refreshes every 60 seconds. Shows:

- Agent running / stopped (launchctl status)
- Daily research status (done/pending)
- Watchlist grouped by tier (CORE / TACTICAL / SPECULATIVE / HEDGE)
- Today's trades (BUY / SELL / HOLD counts and tickers)
- Last 10 lines of agent output
- Recent stderr errors

Press `Ctrl+C` to exit.

### Run a cycle manually

```bash
trading-dry          # analyse all tickers, print decisions, place NO orders
trading-now          # analyse all tickers, place paper orders

# Resume after a crash (e.g. the process died at ticker 12/34)
trading-from AMD     # skip everything before AMD, continue from there
```

`trading-dry` costs the same as `trading-now` -- all 12 agents run; only the
final Alpaca order call is skipped.

### Manage the background agent

```bash
launchctl list | grep tradingagents          # check status and PID

launchctl unload ~/Library/LaunchAgents/com.tradingagents.plist   # stop
launchctl load   ~/Library/LaunchAgents/com.tradingagents.plist   # start/restart
```

### Check positions

```bash
positions            # sync live Alpaca state -> positions.json + research prompt
```

---

## trading_loop.py flags

```bash
python trading_loop.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--once` | off | Run one cycle then exit (default: loop forever) |
| `--no-wait` | off | Skip the 10:00 AM ET wait, run immediately |
| `--dry-run` | off | Analyse only -- no orders placed |
| `--from TICKER` | -- | Resume cycle from TICKER (skip all before it) |
| `--amount N` | `1000` | Base trade size USD (tier multipliers apply on top) |
| `--stop-loss N` | `0.15` | Auto-sell if unrealised P&L <= -N (0.15 = -15%) |
| `--tickers A B ...` | -- | Override watchlist for this cycle only |

---

## Watchlist and position sizing

34 tickers across 4 tiers, defined in `trading_loop.py:WATCHLIST`.

| Tier | Count | Base multiplier | At $1,000 base | Debate rounds |
|------|-------|----------------|----------------|---------------|
| CORE | 25 | 2.0x | $2,000 | 2 (bull/bear + risk) |
| TACTICAL | 5 | 1.0x | $1,000 | 1 |
| SPECULATIVE | 3 | 0.4x | $400 | 1 |
| HEDGE | 1 | 0.5x | $500 | 1 |

The **Risk Judge** can further scale individual orders via `POSITION SIZE` (e.g.
`POSITION SIZE: 0.5x`) in its output. Effective sizing = tier multiplier x
agent multiplier. Agent multiplier is clamped per tier:

| Tier | Min | Max |
|------|-----|-----|
| CORE | 0.50x | 2.00x |
| TACTICAL | 0.25x | 1.50x |
| SPECULATIVE | 0.10x | 0.75x |
| HEDGE | 0.25x | 1.00x |

When portfolio cash > 85%, a **cash deployment boost** of 1.5x is applied to
all BUY orders (1.25x at 80-85%, 1.10x at 70-80%).

**Current tickers:**

- **CORE (25):** NVDA AVGO AMD ARM TSM MU LITE MSFT GOOGL META PLTR GLW MDB NOW PANW CRWD RTX LMT NOC VG LNG XOM FCX MP UBER
- **TACTICAL (5):** CMC NUE APA SOC SCCO
- **SPECULATIVE (3):** RCAT MOS RCKT
- **HEDGE (1):** GLD

**Dynamic watchlist:** After each research session, the system parses ADD/REMOVE
decisions from the findings file and saves them to
`trading_loop_logs/watchlist_overrides.json`. The next cycle picks them up.
Removes expire after 5 days, max 8 removes and 10 adds at a time.
Override for one cycle only:

```bash
python trading_loop.py --once --no-wait --tickers NVDA AVGO RTX GLD
```

---

## Enforcement layers

Three mechanisms prevent the system from sitting in cash:

### 1. Conviction bypass (TICKET-068)

After the Trader proposes a trade, if Research Manager conviction >= 8 (or >= 7
when cash > 85%) and the daily research signal agrees, the trade **skips the
Risk Judge entirely** and executes immediately.

### 2. Signal override reversal (TICKET-067)

After the Risk Judge decides, the system detects if a high-conviction BUY was
overridden to HOLD. If the override is critical/high severity AND cash > 80%,
the decision is **reverted back to BUY**.

### 3. Buy quota enforcement (TICKET-072)

After all tickers are analysed, the system checks if enough BUYs were executed
relative to high-conviction research signals. If the quota is missed (cash > 80%),
it **force-buys up to 5 of the missed opportunities** as market orders.

---

## Daily research

Runs automatically at the start of each cycle. To run or inspect manually:

```bash
python daily_research.py               # run (skips if today's file exists)
python daily_research.py --force       # overwrite today's findings
python daily_research.py --dry-run     # print prompt + cost estimate, no API call
```

**What it scrapes (all free, no auth):**

| Source | What |
|--------|------|
| Yahoo Finance | VIX level, top 15 gainers |
| Reuters (XML sitemap) | Business/markets headlines |
| Reddit | r/wallstreetbets, r/stocks, r/investing, r/pennystocks -- hot post titles + scores |
| yfinance | Live prices for all 34 watchlist tickers (5d window) |

Sends everything to `gpt-4o-mini` with a structured system prompt. Saves output
to `results/RESEARCH_FINDINGS_YYYY-MM-DD.md`. All 12 agents receive the
condensed findings (<=8,000 chars) as `macro_context` in their system prompts.

**Cost:** ~$0.003/day (~$1.10/year).

---

## Stop-loss and exit rules

Run at the start of every cycle before any analysis.

**Global stop-loss:**
- Checks all open Alpaca positions
- Auto-sells any position with unrealised P&L <= -15% (`--stop-loss` default)
- Stopped tickers enter a **3-day cooldown** -- BUYs are blocked to prevent whipsaw

**Agent per-ticker stops:**
- Risk Judge's `STOP-LOSS` price is saved per position
- Checked each cycle; triggers a full exit if price breaches the stop

**Time-based exit rules:**
- **50% profit-taking:** Sell half when a position gains 50%+
- **30-day time stop:** Exit positions held > 30 days with no progress
- **Trailing stop:** Activates at 20%+ gain, sells on 10% pullback from high

---

## Portfolio safeguards

| Guard | Value | Behaviour |
|-------|-------|-----------|
| Max open positions | 20-28 (dynamic based on cash) | BUY downgraded to HOLD at cap |
| Min cash | $1 | BUY skipped (`insufficient_cash`) |
| No-position SELL | -- | SELL skipped (`no_position`) |
| Stop-loss cooldown | 3 days | Re-buy blocked after stop triggered |
| Sector exposure | 40% max per sector | Warning logged at cycle start |
| Crash-resume | per date | Each ticker runs exactly once per analysis date |

---

## Where to find agent reasoning

Every completed analysis writes a human-readable report:

```
trading_loop_logs/reports/{TICKER}/{YYYY-MM-DD}.md
```

Contains, in order: decision, Research Manager investment plan, Trader proposal,
Risk Judge verdict, Bull/Bear debate (all rounds), all 4 analyst reports.

Trade decisions are also logged to:

```
trading_loop_logs/{YYYY-MM-DD}.json
```

Additional runtime logs:

```
trading_loop_logs/signal_overrides.json    # Risk Judge override detection + reversals
trading_loop_logs/buy_quota_log.json       # BUY quota enforcement audit trail
trading_loop_logs/stop_loss_history.json   # Stop-loss cooldown tracking
trading_loop_logs/position_entries.json    # Entry tracking for exit rules
```

---

## Crash recovery

The cycle writes `trading_loop_logs/{trade_date}.checkpoint.json` after each
ticker. On restart, completed tickers are skipped automatically.

For a manual resume from a specific point:

```bash
trading-from AMD              # skip all tickers before AMD
trading-from AMD --dry-run    # same, dry-run
```

---

## Running tests

```bash
python -m pytest tests/          # all 429+ tests across 31 files
python -m pytest tests/ -q       # quiet
python -m pytest tests/ -k ssl   # filter by keyword
```

---

## Single-ticker demo

For a quick smoke test without running the full loop:

```bash
python main.py                              # NVDA, yesterday, no orders
python main.py --ticker AAPL --debug        # verbose LangGraph trace
python main.py --ticker MSFT --date 2026-03-25
```

No Alpaca calls are made. Prints the raw decision to stdout.

---

## Key files

| File | What it does |
|------|-------------|
| `trading_loop.py` | Main loop -- watchlist, scheduling, cycle, checkpoint, tier sizing, enforcement |
| `alpaca_bridge.py` | Alpaca SDK wrapper -- orders, positions, stop-loss, exit rules, decision parser |
| `daily_research.py` | Automated research -- scrape -> LLM -> findings .md |
| `update_positions.py` | Sync Alpaca positions -> `positions.json` + prompt injection |
| `watch_agent.sh` | Live terminal dashboard (60s refresh) |
| `main.py` | Single-ticker demo harness (no orders) |
| `tier_manager.py` | Monthly tier review (promote/demote based on 30-day P&L) |
| `analyze_conviction.py` | Conviction mismatch dashboard |
| `watchlist_cleaner.py` | Clean expired/stale watchlist overrides |
| `SPEC.md` | Full architecture, design decisions, cost breakdown |
| `tradingagents/` | 12-agent LangGraph framework |
| `tradingagents/conviction_bypass.py` | Skip Risk Judge on high-conviction signals |
| `tradingagents/signal_override.py` | Detect + revert Risk Judge overrides |
| `tradingagents/buy_quota.py` | BUY quota tracking and enforcement |
| `tradingagents/sector_monitor.py` | Portfolio sector exposure monitoring |
| `tradingagents/research_context.py` | Research signal parsing, sector rotation, context injection |
| `tests/` | 429+ tests across 31 files (pytest) |
| `tickets/` | TICKET-001 through TICKET-074 -- design records and fix history |
| `results/` | Daily research findings (`.md` per day) |
| `trading_loop_logs/` | Trade logs, agent memories, per-ticker reports, enforcement logs |

---

## Upstream framework

This repo is a fork of the open-source
[TradingAgents](https://github.com/TauricResearch/TradingAgents) research
framework by Tauric Research.

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
