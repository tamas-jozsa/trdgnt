# TrdAgnt -- System Specification v2

> Last updated: April 2026 (Three-Process Architecture)

---

## Overview

**trdagnt** is a fully automated paper trading system built on the
[TradingAgents](https://arxiv.org/abs/2412.20138) multi-agent LLM framework.

The system is thesis-driven and organized around three independent processes:

| Process | Cadence | Purpose |
|---------|---------|---------|
| **Discovery Pipeline** | Daily (9:00 AM ET) | Scan all US equities for new investment candidates, run full 12-agent debate, record thesis |
| **Portfolio Review** | Staggered weekly | Check if existing holdings' investment theses still hold |
| **News Reaction** | Continuous (every 5 min) | Monitor news, assess portfolio impact, execute trades autonomously when conviction >= 8 |

All three processes share state via **Redis** and execute paper trades via
**Alpaca Markets**. The entire system runs as **Docker Compose** services.

> **Paper trading only.** No real money is at risk. Not financial advice.

---

## Architecture

```
                    +-------------------+
                    |      Redis        |
                    | (shared state)    |
                    | - positions       |
                    | - theses          |
                    | - event queue     |
                    | - coordination    |
                    +--------+----------+
                             |
          +------------------+------------------+
          |                  |                  |
+---------v------+  +--------v-------+  +-------v--------+
| DISCOVERY      |  | PORTFOLIO      |  | NEWS REACTION  |
| PIPELINE       |  | REVIEW         |  | PIPELINE       |
| (daily)        |  | (staggered)    |  | (continuous)   |
|                |  |                |  |                |
| Screener       |  | Thesis check   |  | Poll sources   |
| LLM filter     |  | 2-3 agents     |  | LLM triage     |
| 12-agent debate|  | intact/weak/   |  | Graduated:     |
| Thesis record  |  |   broken       |  |  LOW→CRITICAL  |
| Alpaca BUY     |  | SELL if broken |  | Trade if >=8   |
+-------+--------+  +-------+--------+  +-------+--------+
        |                    |                   |
        +--------------------+-------------------+
                             |
                    +--------v----------+
                    |  Alpaca Markets   |
                    |  (paper trading)  |
                    +-------------------+

                    +-------------------+
                    |  Web Dashboard    |
                    |  FastAPI + React  |
                    +-------------------+
```

---

## Process 1: Discovery Pipeline

**Goal:** Find new medium-to-long-term investment candidates daily. Never
re-analyze tickers already in the portfolio.

**Schedule:** Daily at 9:00 AM ET (weekdays only).

### Pipeline Flow

```
9:00 AM ET
    |
    +-- [Daily Research] scrape VIX + Reuters + Reddit + Yahoo → macro context
    |
    +-- [Screener Phase]
    |     All US equities via finvizfinance
    |     Filters:
    |       - Unusual volume (>2x 20-day avg)
    |       - Momentum breakouts (price crossing 50/200 SMA)
    |       - Strong fundamentals shifts (earnings surprise, guidance)
    |       - Sector rotation alignment with macro themes
    |       - Market cap > $500M (excludes micro-caps)
    |     Output: 50-100 raw candidates
    |
    +-- [Portfolio Exclusion]
    |     Remove all tickers already in portfolio (from Redis)
    |     Remove tickers in cooldown (recently sold, stop-loss triggered)
    |     Remove tickers debated in last 7 days (avoid re-analysis churn)
    |
    +-- [LLM Filter] (gpt-4o-mini)
    |     Input: filtered candidates + macro context + current portfolio gaps
    |     Task: rank by fit with macro themes, sector gaps, conviction
    |     Output: top 10-15 candidates for full debate
    |
    +-- [Full 12-Agent Debate] (for each candidate)
    |     Market Analyst → Social Analyst → News Analyst → Fundamentals Analyst
    |     Bull Researcher x2 ↔ Bear Researcher x2
    |     Research Manager (gpt-4o) → investment plan + thesis
    |     Trader → concrete proposal
    |     Risk Debaters x3 → aggressive / conservative / neutral
    |     Risk Judge (gpt-4o) → FINAL DECISION
    |
    +-- [If BUY]
    |     Record thesis to Redis:
    |       - investment rationale (from Research Manager)
    |       - category: CORE (6-12mo) or TACTICAL (1-3mo)
    |       - target price, stop-loss, expected hold period
    |       - key catalysts to monitor
    |       - conditions that would invalidate thesis
    |     Execute market order on Alpaca
    |     Schedule first portfolio review
    |
    +-- [If HOLD/SELL] → log to discovery log, skip
    |
    +-- Save discovery report:
          data/discovery/{YYYY-MM-DD}.json
          trading_loop_logs/reports/{TICKER}/{YYYY-MM-DD}.md
```

### Screener Architecture

The screener uses a pluggable interface to support multiple data sources:

```python
class ScreenerSource(Protocol):
    def scan(self, filters: ScreenerFilters) -> list[ScreenerCandidate]: ...

class FinvizScreener(ScreenerSource):
    """Primary screener — finvizfinance (free, ~8000 US equities)."""

# Future integrations:
# class PolygonScreener(ScreenerSource):     # Polygon.io ($29/mo)
# class AlphaVantageScreener(ScreenerSource): # Alpha Vantage premium
# class TradingViewScreener(ScreenerSource):  # TradingView webhook
```

**Screener filters (configurable in `default_config.py`):**

| Filter | Default | Description |
|--------|---------|-------------|
| `min_market_cap` | $500M | Exclude micro-caps |
| `min_volume_ratio` | 2.0x | Unusual volume vs 20-day average |
| `min_price` | $5.00 | Exclude penny stocks |
| `max_candidates` | 100 | Raw candidates before LLM filtering |
| `max_debate_candidates` | 15 | Candidates sent to full debate |
| `exclude_sectors` | `[]` | Sectors to skip (from macro context) |
| `lookback_days` | 7 | Don't re-debate tickers analyzed within N days |

### Position Categories

Discovery assigns each new position a category based on the Research Manager's
assessment:

| Category | Hold Period | Position Size | Review Cadence | Description |
|----------|-------------|---------------|----------------|-------------|
| CORE | 6-12 months | 2.0x base | Every 2 weeks | Strong fundamentals, secular trend |
| TACTICAL | 1-3 months | 1.0x base | Weekly | Catalyst-driven, momentum play |

The Risk Judge sets position size multiplier (0.25x-2.0x), applied on top of
the category base.

---

## Process 2: Portfolio Review

**Goal:** Periodically verify that existing holdings' investment theses still
hold. Cheap and lightweight — only escalates to full debate when something is
wrong.

**Schedule:** Staggered across the week. All holdings are reviewed over a
2-4 week window depending on portfolio size.

### Scheduling Logic

```python
# Example: 20 positions, reviewed over 2 weeks (10 trading days)
# → 2 positions reviewed per day at 8:00 AM ET

review_schedule = distribute_holdings(
    holdings=get_all_positions(),  # from Redis
    window_days=10,               # spread across 10 trading days
    sort_by="next_review_date",   # oldest review first
)
```

CORE positions are reviewed every 2 weeks. TACTICAL positions are reviewed
weekly. Positions with weakening theses are reviewed more frequently.

### Review Pipeline (Lightweight — 2-3 agents, not full 12)

```
For each position under review today:
    |
    +-- Load original thesis from Redis
    |     - Why we bought, expected catalysts, invalidation conditions
    |
    +-- [Market Analyst] (gpt-4o-mini)
    |     Current price vs entry, technicals vs thesis expectations
    |     Key: has the technical picture changed?
    |
    +-- [Fundamentals Analyst] (gpt-4o-mini)
    |     Latest earnings, guidance changes, analyst revisions
    |     Key: are the fundamental drivers intact?
    |
    +-- [Thesis Assessor] (gpt-4o) — NEW agent role
    |     Input: original thesis + analyst updates + P&L + hold duration
    |     Output: one of three verdicts:
    |
    +-- THESIS INTACT
    |     → HOLD, schedule next review
    |     → Update thesis notes if minor developments
    |
    +-- THESIS WEAKENING
    |     → Flag for full 12-agent debate at next discovery cycle
    |     → Shorten review interval (review again in 3 days)
    |     → Optionally tighten stop-loss
    |
    +-- THESIS BROKEN
    |     → If conviction >= 8: immediate SELL via Alpaca
    |     → If conviction < 8: queue for full debate before selling
    |     → Record reason in review history
```

### Exit Rules (Thesis-Based)

These replace the current rigid time/profit rules:

| Rule | Trigger | Action |
|------|---------|--------|
| Thesis broken | Fundamentals invalidated, catalyst failed | SELL (or queue for debate) |
| Hold period exceeded | CORE > 12mo, TACTICAL > 3mo without thesis update | Trigger full review |
| Trailing stop | 20%+ gain, then 15% pullback from high | SELL |
| Catastrophic loss | Down >= 15% from entry | SELL (same as current global stop) |
| Profit target | Price >= thesis target | Trigger review (sell half or update target) |

### Review Output

```
data/reviews/{TICKER}/{YYYY-MM-DD}.json
{
  "ticker": "NVDA",
  "review_date": "2026-04-13",
  "verdict": "intact",  // intact | weakening | broken
  "days_held": 45,
  "entry_price": 142.50,
  "current_price": 158.30,
  "unrealized_pnl_pct": 11.1,
  "thesis_status": "AI capex cycle remains strong. Q1 guidance raised.",
  "next_review": "2026-04-27",
  "action_taken": "none"
}
```

---

## Process 3: News Reaction Pipeline

**Goal:** Protect the portfolio from material news events. Full autonomy to
trade when conviction >= 8.

**Schedule:** Continuous — polls every 5 minutes during market hours, every
15 minutes outside hours, paused on weekends.

### Pipeline Flow

```
Every 5 minutes:
    |
    +-- [Fetch News] (concurrent)
    |     Reuters (XML sitemap) → headlines with ticker tags
    |     Finnhub (REST API) → company news with summaries
    |     Reddit (JSON API) → r/wallstreetbets, r/stocks, r/investing
    |
    +-- [Dedup] SHA-256 hash, 24-hour window
    |
    +-- [LLM Triage] (gpt-4o-mini, structured output)
    |     For each news item:
    |       - Which portfolio tickers are affected?
    |       - Impact severity: LOW / MEDIUM / HIGH / CRITICAL
    |       - Sentiment: positive / negative / mixed
    |       - Recommended action: monitor / assess / debate / immediate
    |
    +-- [Graduated Response]
          |
          +-- LOW IMPACT
          |     Log to dashboard, no action
          |     Example: routine analyst note, minor price target change
          |
          +-- MEDIUM IMPACT
          |     Quick 2-agent assessment:
          |       Bull Analyst: how does this news support the thesis?
          |       Bear Analyst: how does this news threaten the thesis?
          |     Record assessment, update thesis notes
          |     No trade unless assessment reveals HIGH impact
          |     Example: sector rotation signal, competitor earnings
          |
          +-- HIGH IMPACT
          |     Full debate pipeline on affected tickers:
          |       Load thesis → 4 analysts → bull/bear debate →
          |       Research Manager → Trader → Risk debate → Risk Judge
          |     Can trade if conviction >= 8
          |     Example: earnings miss, guidance cut, downgrade
          |
          +-- CRITICAL IMPACT
                Immediate action path:
                  Load thesis → quick assessment → Risk Judge (gpt-4o)
                If SELL conviction >= 8: execute immediately
                If BUY conviction >= 8: execute immediately (rare — e.g., flash crash)
                Example: fraud allegation, FDA rejection, war/sanctions
```

### Conviction Threshold Guardrail

The news reaction pipeline has **full autonomy** but is gated by a conviction
threshold:

```
conviction >= 8  →  execute trade (BUY or SELL)
conviction 6-7   →  flag for next portfolio review (accelerated)
conviction < 6   →  log only, no action
```

This prevents knee-jerk reactions to noisy news while allowing decisive action
on material events.

### Thesis-Aware Assessment

The key difference from the current news monitor: every assessment is done in
the context of the position's thesis.

```
System prompt includes:
  "We hold {ticker} because: {thesis}.
   Key catalysts: {catalysts}.
   Thesis would be invalidated if: {invalidation_conditions}.

   Given this news: {news_summary}
   Does this news affect our investment thesis? How?"
```

This prevents the system from overreacting to news that's irrelevant to why
we hold the position.

### News Event Log

```
data/news_events/{YYYY-MM-DD}.json
[
  {
    "timestamp": "2026-04-13T14:30:00Z",
    "source": "reuters",
    "headline": "NVDA Q2 guidance below expectations",
    "severity": "HIGH",
    "affected_tickers": ["NVDA", "AMD", "TSM"],
    "assessment": "Thesis weakened — capex cycle may be decelerating",
    "action": "SELL NVDA (conviction 9), FLAG AMD for review",
    "trade_executed": {"ticker": "NVDA", "side": "sell", "conviction": 9}
  }
]
```

---

## Data Models

### Thesis Record (Redis + JSON backup)

The thesis is the central data structure. Every position has one.

```json
{
  "ticker": "NVDA",
  "entry_date": "2026-04-10",
  "entry_price": 142.50,
  "shares": 14.035,
  "position_size_usd": 2000,
  "category": "CORE",
  "expected_hold_months": 9,
  "thesis": {
    "rationale": "AI infrastructure capex cycle accelerating. Data center revenue growing 40% YoY. Blackwell GPU ramp provides 18-month visibility.",
    "key_catalysts": [
      "Q2 earnings (July) — expected beat on data center",
      "Blackwell production ramp Q3-Q4",
      "Hyperscaler capex announcements"
    ],
    "invalidation_conditions": [
      "Data center revenue growth decelerates below 20% YoY",
      "Major customer (MSFT/GOOGL/META) cuts capex guidance",
      "Competitive threat from AMD MI400 or custom ASICs"
    ],
    "sector": "Technology",
    "macro_theme": "AI infrastructure buildout"
  },
  "targets": {
    "price_target": 185.00,
    "stop_loss": 120.00,
    "trailing_stop_activation": 0.20,
    "trailing_stop_trail": 0.15
  },
  "review": {
    "next_review_date": "2026-04-24",
    "review_interval_days": 14,
    "review_count": 0,
    "last_verdict": null
  },
  "history": {
    "review_history": [],
    "news_events": [],
    "thesis_updates": []
  }
}
```

### Discovery Log

```json
{
  "date": "2026-04-13",
  "macro_context_summary": "Risk-on, VIX 14.2, AI/defense themes strong",
  "screener": {
    "source": "finviz",
    "raw_candidates": 87,
    "after_portfolio_exclusion": 72,
    "after_cooldown_exclusion": 68
  },
  "llm_filter": {
    "model": "gpt-4o-mini",
    "candidates_reviewed": 68,
    "selected_for_debate": 12,
    "selection_rationale": "Focused on AI supply chain + defense rotation"
  },
  "debates": [
    {
      "ticker": "SMCI",
      "decision": "BUY",
      "conviction": 8,
      "category": "TACTICAL",
      "thesis_summary": "Server demand surge from AI buildout..."
    },
    {
      "ticker": "ANET",
      "decision": "HOLD",
      "conviction": 5,
      "reason": "Valuation stretched despite strong fundamentals"
    }
  ],
  "positions_opened": 3,
  "cost_estimate_usd": 0.52
}
```

### Portfolio State (Redis)

```
redis keys:
  portfolio:positions          → hash of ticker → thesis JSON
  portfolio:cash               → current cash balance
  portfolio:total_value        → total portfolio value
  portfolio:sectors            → hash of sector → exposure %
  coordination:analyzed_today  → set of tickers analyzed today
  coordination:cooldown        → hash of ticker → cooldown_until date
  events:news_queue            → list of pending news events
  events:review_queue          → list of tickers flagged for accelerated review
```

---

## Docker Architecture

### Services

```yaml
services:
  redis:
    # Shared state store
    # Persists to disk via AOF

  discovery:
    # Daily discovery pipeline
    # Runs at 9:00 AM ET via internal scheduler
    # Depends on: redis

  portfolio-review:
    # Staggered weekly review
    # Runs at 8:00 AM ET via internal scheduler
    # Depends on: redis

  news-monitor:
    # Continuous news polling daemon
    # Runs 24/7 (pauses on weekends)
    # Depends on: redis

  dashboard-api:
    # FastAPI backend
    # Reads from Redis + log files
    # Depends on: redis

  dashboard-ui:
    # React frontend served by nginx
    # Connects to dashboard-api
    # Depends on: dashboard-api
```

### Shared Volumes

```yaml
volumes:
  trading-data:
    # Mounted at /app/data in all trading services
    # Contains: theses, discovery logs, review history, news events
    # Backed up to host: ./data/

  trading-logs:
    # Mounted at /app/trading_loop_logs in all trading services
    # Contains: agent memories, reports, checkpoints
    # Backed up to host: ./trading_loop_logs/

  research-results:
    # Mounted at /app/results
    # Contains: daily research findings
    # Backed up to host: ./results/
```

### Environment Variables

All services share a common `.env` file:

```bash
# Required
OPENAI_API_KEY=sk-...
ALPACA_API_KEY=PK...
ALPACA_API_SECRET=...

# Optional
FINNHUB_API_KEY=...
DEEP_LLM_MODEL=gpt-4o
QUICK_LLM_MODEL=gpt-4o-mini
RESEARCH_LLM_MODEL=gpt-4o-mini

# Redis (auto-configured by Docker Compose)
REDIS_URL=redis://redis:6379/0

# Discovery settings
DISCOVERY_MAX_CANDIDATES=15
DISCOVERY_MIN_MARKET_CAP=500000000
DISCOVERY_LOOKBACK_DAYS=7

# Review settings
REVIEW_WINDOW_DAYS=10
REVIEW_CORE_INTERVAL=14
REVIEW_TACTICAL_INTERVAL=7

# News settings
NEWS_POLL_INTERVAL=300
NEWS_CONVICTION_THRESHOLD=8
```

---

## Configuration Reference

### default_config.py Additions

```python
DEFAULT_CONFIG = {
    # ... existing LLM and provider config ...

    # === Discovery Pipeline ===
    "discovery": {
        "screener_source": "finviz",       # finviz | polygon | alpha_vantage
        "max_raw_candidates": 100,
        "max_debate_candidates": 15,
        "min_market_cap": 500_000_000,     # $500M
        "min_price": 5.00,
        "min_volume_ratio": 2.0,           # vs 20-day average
        "lookback_days": 7,                # don't re-debate within N days
        "run_hour": 9,
        "run_minute": 0,
        "timezone": "US/Eastern",
    },

    # === Portfolio Review ===
    "review": {
        "window_days": 10,                 # spread all reviews over N trading days
        "core_interval_days": 14,          # CORE reviewed every 2 weeks
        "tactical_interval_days": 7,       # TACTICAL reviewed weekly
        "weakening_recheck_days": 3,       # weakening thesis rechecked in 3 days
        "run_hour": 8,
        "run_minute": 0,
        "timezone": "US/Eastern",
    },

    # === News Reaction ===
    "news_reaction": {
        "poll_interval_seconds": 300,      # 5 minutes during market hours
        "off_hours_interval_seconds": 900, # 15 minutes outside hours
        "conviction_threshold": 8,         # minimum to execute a trade
        "dedup_window_hours": 24,
        "sources": {
            "reuters": True,
            "finnhub": True,
            "reddit": True,
        },
        "severity_thresholds": {
            "medium_assessment": True,     # run 2-agent assessment on MEDIUM
            "high_full_debate": True,      # run full debate on HIGH
            "critical_immediate": True,    # immediate action on CRITICAL
        },
    },

    # === Position Categories ===
    "categories": {
        "CORE": {
            "hold_months": (6, 12),
            "base_multiplier": 2.0,
            "size_limits": {"min": 0.5, "max": 2.0},
            "review_interval_days": 14,
            "debate_rounds": 2,
        },
        "TACTICAL": {
            "hold_months": (1, 3),
            "base_multiplier": 1.0,
            "size_limits": {"min": 0.25, "max": 1.5},
            "review_interval_days": 7,
            "debate_rounds": 1,
        },
    },

    # === Exit Rules (thesis-based) ===
    "exit_rules": {
        "trailing_stop": {
            "enabled": True,
            "activation_pct": 0.20,        # activate at 20% gain
            "trail_pct": 0.15,             # sell on 15% pullback from high
        },
        "catastrophic_loss": {
            "enabled": True,
            "threshold_pct": 0.15,         # -15% from entry
            "cooldown_days": 7,            # block re-buy for 7 days
        },
        "hold_period_exceeded": {
            "enabled": True,
            "action": "review",            # trigger review, not auto-sell
        },
    },

    # === Redis ===
    "redis": {
        "url": "redis://localhost:6379/0",  # overridden by REDIS_URL env var
        "key_prefix": "trdagnt:",
    },
}
```

---

## Screener Interface

The screener uses a pluggable protocol for data sources:

```python
@dataclass
class ScreenerCandidate:
    ticker: str
    company_name: str
    sector: str
    market_cap: float
    price: float
    volume_ratio: float       # vs 20-day average
    price_change_1d: float
    price_change_5d: float
    sma50_cross: bool         # price recently crossed 50 SMA
    sma200_cross: bool        # price recently crossed 200 SMA
    earnings_surprise: float | None
    signal_source: str        # "volume" | "momentum" | "fundamental" | "news"

class ScreenerSource(Protocol):
    def scan(self, filters: dict) -> list[ScreenerCandidate]: ...
    def get_source_name(self) -> str: ...

# Implementations:
# - FinvizScreener (default, free)
# - PolygonScreener (future, $29/mo, faster + real-time)
# - YFinanceScreener (fallback, free but slow for full universe)
# - CompositeScreener (merges results from multiple sources)
```

**Current implementation:** `FinvizScreener` using the `finvizfinance` Python
library. Scans ~8,000 US equities with configurable filters. Free, no API key
required, rate-limited to ~1 request/second.

**Future integration points:**
- Polygon.io Snapshots API for real-time volume/price data
- Alpha Vantage Screener for fundamental filters
- TradingView Webhooks for custom technical alerts
- Custom quantitative models (factor-based, ML-driven)

---

## Review Agent: Thesis Assessor

A new agent role for the portfolio review process. Unlike the full 12-agent
pipeline, this is a single LLM call with structured output.

```
System Prompt:
  You are a portfolio review analyst. Your job is to assess whether an
  existing investment thesis still holds.

  ORIGINAL THESIS:
  {thesis.rationale}

  KEY CATALYSTS:
  {thesis.key_catalysts}

  INVALIDATION CONDITIONS:
  {thesis.invalidation_conditions}

  CURRENT DATA:
  - Entry: ${entry_price} on {entry_date} ({days_held} days ago)
  - Current: ${current_price} ({pnl_pct}% P&L)
  - Trailing high: ${trailing_high}
  - Market Analyst findings: {market_update}
  - Fundamentals Analyst findings: {fundamentals_update}
  - Recent news events: {news_summary}

  OUTPUT (structured):
  VERDICT: INTACT | WEAKENING | BROKEN
  CONFIDENCE: 1-10
  REASONING: <2-3 sentences>
  THESIS_UPDATE: <any modifications to the thesis>
  ACTION: HOLD | TIGHTEN_STOP | FLAG_FOR_DEBATE | SELL
```

**Model:** `gpt-4o` (same tier as Research Manager — this is a decision node).

**Cost:** ~$0.01 per review. At 2-4 reviews/day = ~$0.02-0.04/day.

---

## News Severity Classification

The triage LLM classifies news into four severity levels:

| Severity | Criteria | Response | Example |
|----------|----------|----------|---------|
| LOW | Routine, no thesis impact | Log only | Minor analyst note, routine filing |
| MEDIUM | Potentially relevant, uncertain impact | 2-agent quick assessment | Sector rotation signal, competitor news |
| HIGH | Likely thesis impact, requires analysis | Full 12-agent debate | Earnings miss, guidance cut, downgrade |
| CRITICAL | Clear and immediate thesis threat/opportunity | Immediate Risk Judge decision | Fraud, FDA rejection, war/sanctions, flash crash |

**Triage prompt includes portfolio context:**
```
Current portfolio: {list of held tickers with thesis summaries}
News item: {headline + summary}

Classify: Which portfolio tickers are affected? Severity? Sentiment?
```

---

## Cost Estimate

| Component | Daily | Annual |
|-----------|-------|--------|
| Daily research (gpt-4o-mini) | ~$0.003 | ~$1 |
| Discovery: LLM filter (gpt-4o-mini) | ~$0.01 | ~$4 |
| Discovery: 10-15 full debates (~$0.04/ticker) | ~$0.40-0.60 | ~$150-220 |
| Portfolio review: 2-4 lightweight reviews | ~$0.02-0.04 | ~$7-15 |
| News triage (gpt-4o-mini, ~50 items/day) | ~$0.02 | ~$7 |
| News assessments (MEDIUM, ~5/day) | ~$0.02 | ~$7 |
| News full debates (HIGH, ~1/week) | ~$0.006 | ~$2 |
| **Total** | **~$0.50-0.70** | **~$180-260** |

This is significantly cheaper than the current system (~$512/year) because
we're not re-debating 34 tickers daily. The full debate pipeline only runs on
genuinely new candidates and material news events.

---

## Migration from v1

### What's Preserved

- All 12 agents and their prompts (tradingagents/agents/*)
- TradingAgentsGraph orchestrator (tradingagents/graph/*)
- All data vendor implementations (tradingagents/dataflows/*)
- LLM client factory (tradingagents/llm_clients/*)
- Alpaca bridge (apps/alpaca_bridge.py)
- Daily research pipeline (apps/daily_research.py)
- Agent memory system (BM25 + embeddings)
- Web dashboard (dashboard/*)
- All existing tests

### What's Replaced

| v1 Component | v2 Replacement |
|-------------|---------------|
| Static WATCHLIST (34 tickers) | Dynamic discovery via screener |
| Daily re-debate of all tickers | Discovery (new only) + staggered review (existing) |
| trading_loop.py (monolithic) | discovery_pipeline.py + portfolio_review.py + news_monitor.py |
| 3 enforcement layers (bypass/override/quota) | Thesis-driven framework (less fighting with Risk Judge) |
| position_entries.json | Redis thesis store with full history |
| Time-based exit rules (30-day stop) | Thesis-based exits (hold period + thesis integrity) |
| Fixed tier system (CORE/TACTICAL/SPECULATIVE/HEDGE) | Two categories: CORE (6-12mo) + TACTICAL (1-3mo) |
| NewsMonitor spawns trading_loop.py | NewsMonitor has its own graduated pipeline |
| JSON file-based state | Redis shared state + JSON backup |
| macOS launchctl | Docker Compose |

### Migration Steps

1. Export current positions from Alpaca → create thesis records for each
2. Assign categories (CORE/TACTICAL) based on current tier + hold duration
3. Generate initial thesis from most recent agent report per ticker
4. Load into Redis
5. Start Docker Compose services
6. Verify portfolio state matches Alpaca

### Backward Compatibility

`apps/trading_loop.py` is preserved for backward compatibility and can still be
run standalone:

```bash
python apps/trading_loop.py --once --no-wait --tickers NVDA AMD
```

However, it will not participate in the thesis-tracking or Redis coordination
system. For production use, the Docker Compose deployment is recommended.

---

## File Structure (v2)

```
trdagnt/
├── docker-compose.yml              # All services
├── Dockerfile                      # Base Python image
├── dashboard/
│   ├── Dockerfile                  # Dashboard-specific image
│   ├── backend/                    # FastAPI API server
│   └── frontend/                   # React SPA
│
├── apps/
│   ├── discovery_pipeline.py       # NEW — daily screener + debate
│   ├── portfolio_review.py         # NEW — staggered thesis review
│   ├── screener.py                 # NEW — pluggable stock screener
│   ├── news_monitor.py             # REFACTORED — graduated response
│   ├── news_monitor_triage.py      # UPDATED — severity classification
│   ├── news_monitor_config.py      # Config for news sources
│   ├── alpaca_bridge.py            # Unchanged — order execution
│   ├── daily_research.py           # Unchanged — macro research
│   ├── update_positions.py         # Unchanged — position sync
│   ├── trading_loop.py             # PRESERVED — backward compat
│   └── main.py                     # Unchanged — single-ticker demo
│
├── src/tradingagents/
│   ├── thesis.py                   # NEW — thesis data model + Redis CRUD
│   ├── review_agents.py            # NEW — thesis assessor agent
│   ├── news_debate.py              # NEW — news-specific debate pipeline
│   ├── redis_state.py              # NEW — Redis state management
│   ├── default_config.py           # UPDATED — new config sections
│   ├── research_context.py         # Unchanged
│   ├── conviction_bypass.py        # PRESERVED — used by discovery
│   ├── signal_override.py          # DEPRECATED — replaced by thesis
│   ├── buy_quota.py                # DEPRECATED — replaced by thesis
│   ├── sector_monitor.py           # Unchanged — used by review
│   ├── graph/                      # Unchanged — 12-agent pipeline
│   ├── agents/                     # Unchanged — all agent prompts
│   ├── dataflows/                  # Unchanged — data vendors
│   └── llm_clients/                # Unchanged — LLM providers
│
├── data/                           # NEW — structured data store
│   ├── theses/                     # Thesis JSON backups
│   ├── discovery/                  # Discovery logs per day
│   ├── reviews/                    # Review history per ticker
│   └── news_events/                # News event logs per day
│
├── trading_loop_logs/              # Unchanged — agent memories + reports
├── results/                        # Unchanged — research findings
├── tests/                          # UPDATED — new test files
├── tickets/                        # Unchanged — design records
└── docs/
    ├── SPEC.md                     # This file
    ├── README.md                   # Updated for v2
    └── AGENTS.md                   # Updated for v2
```

---

## CLI Commands (v2)

### Discovery Pipeline

```bash
# Run discovery (daily, auto-scheduled)
docker compose up discovery

# Manual run
python apps/discovery_pipeline.py --once --no-wait

# Dry run (no orders)
python apps/discovery_pipeline.py --once --no-wait --dry-run

# Limit candidates
python apps/discovery_pipeline.py --max-candidates 5
```

### Portfolio Review

```bash
# Run review (staggered, auto-scheduled)
docker compose up portfolio-review

# Manual run (review all holdings today)
python apps/portfolio_review.py --all

# Review specific ticker
python apps/portfolio_review.py --ticker NVDA

# Dry run
python apps/portfolio_review.py --dry-run
```

### News Monitor

```bash
# Start news monitoring daemon
docker compose up news-monitor

# Manual start
python apps/news_monitor.py

# Check status
python apps/news_monitor.py --status
```

### Docker Compose

```bash
# Start everything
docker compose up -d

# Start specific services
docker compose up -d discovery portfolio-review news-monitor

# Start with dashboard
docker compose up -d dashboard-api dashboard-ui

# View logs
docker compose logs -f discovery
docker compose logs -f news-monitor

# Stop everything
docker compose down

# Rebuild after code changes
docker compose build && docker compose up -d
```

### Legacy (backward compatible)

```bash
python apps/trading_loop.py --once --no-wait          # still works
python apps/main.py --ticker NVDA --debug             # still works
python apps/daily_research.py                         # still works
```

---

## Design Decisions (v2)

**Why three separate processes?** Different investment activities have different
natural cadences. Discovery is a daily creative task. Portfolio review is
periodic maintenance. News reaction is continuous monitoring. Coupling them in
one loop (as v1 did) forces everything to the same daily cadence, which is
wrong for medium-term investing.

**Why thesis-driven?** The v1 system re-debated the same tickers daily from
scratch, with no memory of why it bought them. This led to whipsaw decisions
(buy Monday, sell Tuesday on the same fundamentals). Recording a thesis and
reviewing against it mirrors how professional fund managers operate.

**Why Redis?** Three independent processes need shared state (positions, theses,
coordination). JSON files on a shared volume work but have file-locking issues
under concurrent access. Redis provides atomic operations, pub/sub for
inter-process events, and is already a dependency in pyproject.toml.

**Why Docker Compose?** The v1 system used macOS launchctl, which is
platform-specific and doesn't scale to multiple services. Docker Compose
provides platform-independent deployment, service isolation, health checks,
and easy log management.

**Why finvizfinance for screening?** Free, covers ~8,000 US equities, good
filter options, well-maintained Python library. The pluggable interface allows
upgrading to Polygon.io or other paid sources when the free tier becomes
limiting (rate limits, data freshness).

**Why conviction >= 8 for news trades?** Setting the bar high prevents
overtrading on noisy news. The system should only act autonomously when it's
very confident. Lower-conviction events are flagged for the next review cycle,
which adds a human-like "sleep on it" buffer.

**Why keep the 12-agent pipeline for discovery?** New position decisions are
high-stakes — we're committing capital for months. The full debate pipeline
provides the depth of analysis needed. Portfolio reviews use a cheaper
lightweight pipeline because the thesis provides strong prior context.

**Why two categories instead of four tiers?** The v1 SPECULATIVE and HEDGE
tiers added complexity without clear benefit for a medium-term strategy. CORE
(strong fundamentals, long hold) and TACTICAL (catalyst-driven, shorter hold)
capture the full range of the mixed holding period approach.

---

*v2 specification — April 2026*
