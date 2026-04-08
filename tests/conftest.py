"""Pytest configuration."""

import sys
from pathlib import Path

# Add project root and apps to Python path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps"))
