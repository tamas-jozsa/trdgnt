"""
Dashboard backend configuration.

Resolves all data paths relative to the project root (two levels up from this file).
"""

from pathlib import Path

# Project root: dashboard/backend/config.py -> ../../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Data directories
TRADING_LOGS_DIR = PROJECT_ROOT / "trading_loop_logs"
RESULTS_DIR = PROJECT_ROOT / "results"
REPORTS_DIR = TRADING_LOGS_DIR / "reports"
MEMORY_DIR = TRADING_LOGS_DIR / "memory"
NEWS_MONITOR_DIR = TRADING_LOGS_DIR / "news_monitor"

# Key data files
POSITIONS_FILE = PROJECT_ROOT / "positions.json"
SIGNAL_OVERRIDES_FILE = TRADING_LOGS_DIR / "signal_overrides.json"
BUY_QUOTA_LOG_FILE = TRADING_LOGS_DIR / "buy_quota_log.json"
POSITION_ENTRIES_FILE = TRADING_LOGS_DIR / "position_entries.json"
WATCHLIST_OVERRIDES_FILE = TRADING_LOGS_DIR / "watchlist_overrides.json"
STOP_LOSS_HISTORY_FILE = TRADING_LOGS_DIR / "stop_loss_history.json"
EQUITY_HISTORY_FILE = TRADING_LOGS_DIR / "equity_history.json"
STDOUT_LOG_FILE = TRADING_LOGS_DIR / "stdout.log"
STDERR_LOG_FILE = TRADING_LOGS_DIR / "stderr.log"

# Frontend build output (for production serving)
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# Server defaults
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8888
