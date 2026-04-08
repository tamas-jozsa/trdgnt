"""
news_monitor_config.py
======================
Configuration constants for the real-time news monitor.

The news monitor polls multiple sources every 5 minutes, uses LLM triage
to identify material news events, and triggers trading analysis for
affected tickers.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
TRADING_LOGS_DIR = PROJECT_ROOT / "trading_loop_logs"
NEWS_MONITOR_DIR = TRADING_LOGS_DIR / "news_monitor"

# Ensure directories exist
NEWS_MONITOR_DIR.mkdir(parents=True, exist_ok=True)

# State files
ENABLED_STATE_FILE = NEWS_MONITOR_DIR / "enabled.json"
SEEN_ARTICLES_FILE = NEWS_MONITOR_DIR / "seen_articles.json"
EVENTS_LOG_FILE = NEWS_MONITOR_DIR / "events.jsonl"
TRIGGERS_LOG_FILE = NEWS_MONITOR_DIR / "triggers.jsonl"
QUEUED_TRIGGERS_FILE = NEWS_MONITOR_DIR / "queued_triggers.json"
ACTIVE_ANALYSES_FILE = NEWS_MONITOR_DIR / "active.json"
STATS_FILE = NEWS_MONITOR_DIR / "stats.json"

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS = 300  # 5 minutes
DEDUP_WINDOW_HOURS = 24      # How long to remember seen articles
COOLDOWN_MINUTES = 15        # Don't re-analyze same ticker within this time (reduced for volatile markets)
QUEUE_DRAIN_INTERVAL = 60    # Check for queued triggers every 60 seconds when market opens

# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------
MAX_CONCURRENT_ANALYSES = 2  # Max parallel trading_loop.py processes
MAX_QUEUE_SIZE = 50          # Max queued triggers (off-hours)

# ---------------------------------------------------------------------------
# News Sources
# ---------------------------------------------------------------------------
ENABLE_REUTERS = True
ENABLE_FINNHUB = True
ENABLE_REDDIT = True

REDDIT_SUBREDDITS = ["wallstreetbets", "stocks"]  # For news monitor (hot posts)
REDDIT_POSTS_PER_SUB = 10

FINNHUB_CATEGORY = "general"  # general, forex, crypto, merger
FINNHUB_LIMIT = 20

REUTERS_HOURS_BACK = 1  # Only fetch articles from last hour (we poll every 5 min)

# ---------------------------------------------------------------------------
# LLM Triage
# ---------------------------------------------------------------------------
TRIAGE_LLM_MODEL = "gpt-4o-mini"
TRIAGE_MAX_TOKENS = 2000
TRIAGE_TEMPERATURE = 0.1  # Low for consistent structured output

# Urgency thresholds
URGENCY_HIGH = "HIGH"
URGENCY_MEDIUM = "MEDIUM"
URGENCY_LOW = "LOW"

# Only trigger analysis for HIGH urgency with action_recommended=True
MIN_URGENCY_TO_TRIGGER = URGENCY_HIGH

# ---------------------------------------------------------------------------
# Ticker Discovery
# ---------------------------------------------------------------------------
AUTO_ADD_NEW_TICKERS = True
NEW_TICKER_TIER = "TACTICAL"
NEW_TICKER_SECTOR = "News Discovery"

# Validate new tickers with yfinance before adding (quick .info check)
VALIDATE_NEW_TICKERS = True

# ---------------------------------------------------------------------------
# Market Hours (Eastern Time)
# ---------------------------------------------------------------------------
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

EXTENDED_PRE_HOUR = 6
EXTENDED_POST_HOUR = 20

TIMEZONE = "America/New_York"

# ---------------------------------------------------------------------------
# Cost Tracking
# ---------------------------------------------------------------------------
# gpt-4o-mini pricing (as of Apr 2026): ~$0.15/mTok input, $0.60/mTok output
TRIAGE_INPUT_COST_PER_1K = 0.00015
TRIAGE_OUTPUT_COST_PER_1K = 0.00060
ESTIMATED_TRIAGE_COST_PER_CALL = 0.001  # $0.001 per triage call (batch of articles)

ANALYSIS_COST_PER_TICKER = 0.10  # Estimated cost for full trading_loop analysis
