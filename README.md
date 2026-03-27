# trdagnt

Automated daily paper trading system built on the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

Runs once per day at **10:00 AM ET**. Analyses a 28-ticker curated watchlist
through a 12-agent LLM debate pipeline (analysts → bull/bear researchers →
risk debaters → risk judge), then executes paper trades via
[Alpaca Markets](https://alpaca.markets).

> **Paper trading only.** No real money is at risk.
> Not financial advice.

---

## How it works

```
10:00 AM ET
     │
     ├─ daily_research.py   scrape VIX + Reuters + Reddit + Yahoo → gpt-4o-mini → findings.md
     ├─ stop-loss check      auto-sell any position down ≥ 15%
     │
     └─ for each of 28 tickers:
           Market Analyst      → 90d OHLCV, RSI, MACD, Bollinger, ATR, MFI ...
           Social Analyst      → Reddit × 4, StockTwits, options P/C, short interest
           News Analyst        → Reuters, Yahoo Finance, Finnhub, earnings calendar
           Fundamentals Analyst→ P/E, EV/EBITDA, FCF, insider buys, analyst targets
           Bull Researcher × N ↔ Bear Researcher × N   (N = 2 for CORE, 1 for others)
           Research Manager    → synthesises all reports → investment plan  [gpt-4o]
           Trader              → concrete proposal
           Risk Debaters × 3   → aggressive / conservative / neutral evaluation
           Risk Judge          → FINAL DECISION + stop-loss + target + position size  [gpt-4o]
                │
                ├─ regex signal extraction (no secondary LLM call)
                ├─ portfolio limit guard (max 20 open positions)
                └─ Alpaca market order (fractional shares)
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
FINNHUB_API_KEY=...          # free tier at finnhub.io — improves news quality
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

# Resume after a crash (e.g. the process died at ticker 12/28)
trading-from AMD     # skip everything before AMD, continue from there
```

`trading-dry` costs the same as `trading-now` — all 12 agents run; only the
final Alpaca order call is skipped.

### Manage the background agent

```bash
launchctl list | grep tradingagents          # check status and PID

launchctl unload ~/Library/LaunchAgents/com.tradingagents.plist   # stop
launchctl load   ~/Library/LaunchAgents/com.tradingagents.plist   # start/restart
```

### Check positions

```bash
positions            # sync live Alpaca state → positions.json + research prompt
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
| `--dry-run` | off | Analyse only — no orders placed |
| `--from TICKER` | — | Resume cycle from TICKER (skip all before it) |
| `--amount N` | `1000` | Base trade size USD (tier multipliers apply on top) |
| `--stop-loss N` | `0.15` | Auto-sell if unrealised P&L ≤ -N (0.15 = -15%) |
| `--tickers A B …` | — | Override watchlist for this cycle only |

---

## Watchlist and position sizing

28 tickers across 4 tiers, defined in `trading_loop.py:WATCHLIST`.

| Tier | Count | Base multiplier | At $1,000 base | Debate rounds |
|------|-------|----------------|----------------|---------------|
| CORE | 25 | 2.0× | $2,000 | 2 (bull/bear + risk) |
| TACTICAL | 5 | 1.0× | $1,000 | 1 |
| SPECULATIVE | 3 | 0.4× | $400 | 1 |
| HEDGE | 1 | 0.5× | $500 | 1 |

The **Risk Judge** can further scale individual orders via `POSITION SIZE` (e.g.
`POSITION SIZE: 0.5x`) in its output. Effective sizing = tier multiplier ×
agent multiplier. Agent multiplier is clamped to 0.25×–2.0×.

**Current tickers:**

- **CORE (25):** NVDA AVGO AMD ARM TSM MU LITE MSFT GOOGL META PLTR GLW MDB NOW PANW CRWD RTX LMT NOC VG LNG XOM FCX MP UBER
- **TACTICAL (5):** CMC NUE APA SOC SCCO
- **SPECULATIVE (3):** RCAT MOS RCKT
- **HEDGE (1):** GLD

**Dynamic watchlist:** After each research session, the system parses ADD/REMOVE
decisions from the findings file and saves them to
`trading_loop_logs/watchlist_overrides.json`. The next cycle picks them up.
Override for one cycle only:

```bash
python trading_loop.py --once --no-wait --tickers NVDA AVGO RTX GLD
```

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
| Reddit | r/wallstreetbets, r/stocks, r/investing, r/pennystocks — hot post titles + scores |
| yfinance | Live prices for all 28 watchlist tickers (5d window) |

Sends everything to `gpt-4o-mini` with a structured system prompt. Saves output
to `results/RESEARCH_FINDINGS_YYYY-MM-DD.md`. All 12 agents receive the
condensed findings (≤8,000 chars) as `macro_context` in their system prompts.

**Cost:** ~$0.003/day (~$1.10/year).

---

## Stop-loss system

Runs at the start of every cycle before any analysis.

- Checks all open Alpaca positions
- Auto-sells any position with unrealised P&L ≤ −15% (`--stop-loss` default)
- Full position exit (market order, DAY TIF)
- Dry-run safe — logs what would be sold but places no orders
- Every triggered stop is written to the daily trade log JSON

---

## Portfolio safeguards

| Guard | Value | Behaviour |
|-------|-------|-----------|
| Max open positions | 20 | BUY downgraded to HOLD if live portfolio ≥ 20 positions |
| Min cash | $1 | BUY skipped (`insufficient_cash`) |
| No-position SELL | — | SELL skipped (`no_position`) |
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
python -m pytest tests/          # all 398 tests
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
| `trading_loop.py` | Main loop — watchlist, scheduling, cycle, checkpoint, tier sizing |
| `alpaca_bridge.py` | Alpaca SDK wrapper — orders, positions, stop-loss, decision parser |
| `daily_research.py` | Automated research — scrape → LLM → findings .md |
| `update_positions.py` | Sync Alpaca positions → `positions.json` + prompt injection |
| `watch_agent.sh` | Live terminal dashboard (60s refresh) |
| `main.py` | Single-ticker demo harness (no orders) |
| `SPEC.md` | Full architecture, design decisions, cost breakdown |
| `tradingagents/` | 12-agent LangGraph framework |
| `tests/` | 398 tests (pytest) |
| `tickets/` | TICKET-001 through TICKET-044 — design records and fix history |
| `results/` | Daily research findings (`.md` per day) |
| `trading_loop_logs/` | Trade logs, agent memories, per-ticker analysis reports |

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
