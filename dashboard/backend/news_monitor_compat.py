"""Compatibility module to import news_monitor from apps directory."""
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add apps directory to path
APPS_DIR = Path(__file__).resolve().parent.parent.parent / "apps"
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))

# Now import
try:
    from news_monitor import get_news_monitor, TriageEvent, Trigger
    from news_monitor_config import (
        EVENTS_LOG_FILE,
        TRIGGERS_LOG_FILE,
        QUEUED_TRIGGERS_FILE,
        POLL_INTERVAL_SECONDS as DEFAULT_POLL_INTERVAL_SECONDS,
        POLL_INTERVAL_OPTIONS,
        get_poll_interval,
        set_poll_interval,
        load_settings,
        save_settings,
    )
    MIN_URGENCY_TO_TRIGGER = 7  # Default value
except ImportError as e:
    print(f"Warning: Could not import news_monitor: {e}")
    # Define placeholders
    def get_news_monitor():
        return None

    TriageEvent = dict
    Trigger = dict

    EVENTS_LOG_FILE = Path("/tmp/events.log")
    TRIGGERS_LOG_FILE = Path("/tmp/triggers.log")
    QUEUED_TRIGGERS_FILE = Path("/tmp/queued.json")
    DEFAULT_POLL_INTERVAL_SECONDS = 300
    POLL_INTERVAL_OPTIONS = {
        "1_min": 60,
        "2_min": 120,
        "5_min": 300,
        "10_min": 600,
        "15_min": 900,
        "30_min": 1800,
    }
    def get_poll_interval():
        return 300
    def set_poll_interval(seconds: int) -> int:
        return seconds
    def load_settings():
        return {"poll_interval_seconds": 300, "enabled_by_default": False}
    def save_settings(settings):
        return settings
    MIN_URGENCY_TO_TRIGGER = 7
