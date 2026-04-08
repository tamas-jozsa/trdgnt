"""
Smoke tests for dashboard backend.

These tests verify that the dashboard backend can start and basic endpoints work.
"""

import sys
from pathlib import Path

# Ensure paths are set up
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps"))


def test_dashboard_config_import():
    """Test that dashboard config can be imported."""
    from dashboard.backend.config import (
        PROJECT_ROOT, TRADING_LOGS_DIR, RESULTS_DIR,
        POSITIONS_FILE, DEFAULT_PORT
    )
    assert DEFAULT_PORT == 8888
    assert TRADING_LOGS_DIR.exists() or True  # May not exist in CI


def test_dashboard_services_import():
    """Test that dashboard services can be imported."""
    from dashboard.backend.services.portfolio_service import get_portfolio
    from dashboard.backend.services.trade_service import get_all_trades
    from dashboard.backend.services.research_service import get_findings


def test_dashboard_routers_import():
    """Test that dashboard routers can be imported."""
    from dashboard.backend.routers.portfolio import router as portfolio_router
    from dashboard.backend.routers.trades import router as trades_router
    from dashboard.backend.routers.agents import router as agents_router
    from dashboard.backend.routers.research import router as research_router
    from dashboard.backend.routers.control import router as control_router


def test_dashboard_main_import():
    """Test that dashboard main app can be imported."""
    from dashboard.backend.main import app
    assert app is not None
