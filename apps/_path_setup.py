"""Path setup for apps to find the src/tradingagents package and shared paths."""
import sys
from pathlib import Path

# Project root is the parent of apps/ directory (repo root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add src directory to path for imports
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Also ensure project root is in path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Common paths used across apps
TRADING_LOGS_DIR = PROJECT_ROOT / "trading_loop_logs"
RESULTS_DIR = PROJECT_ROOT / "results"
MEMORY_DIR = TRADING_LOGS_DIR / "memory"
