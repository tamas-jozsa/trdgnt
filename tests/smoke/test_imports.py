"""
Smoke tests for critical imports.

These tests verify that all entry points can be imported without errors.
"""

import sys
from pathlib import Path

# Ensure paths are set up
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps"))


def test_import_path_setup():
    """Test that _path_setup can be imported."""
    import _path_setup
    assert hasattr(_path_setup, 'PROJECT_ROOT')
    assert hasattr(_path_setup, 'TRADING_LOGS_DIR')
    assert hasattr(_path_setup, 'RESULTS_DIR')


def test_import_trading_loop():
    """Test that trading_loop can be imported."""
    from trading_loop import WATCHLIST, get_analysis_date, load_watchlist_overrides
    assert len(WATCHLIST) > 0


def test_import_daily_research():
    """Test that daily_research can be imported."""
    from daily_research import run_daily_research, fetch_watchlist_prices


def test_import_alpaca_bridge():
    """Test that alpaca_bridge can be imported (if dependencies available)."""
    pytest = __import__('pytest')
    try:
        from alpaca_bridge import execute_trade, get_positions
    except ModuleNotFoundError as e:
        if "alpaca" in str(e):
            pytest.skip("alpaca module not installed")
        raise


def test_import_update_positions():
    """Test that update_positions can be imported."""
    from update_positions import fetch_positions, save_positions


def test_import_news_monitor():
    """Test that news_monitor can be imported."""
    from news_monitor import NewsMonitor


def test_import_tier_manager():
    """Test that tier_manager can be imported."""
    # Just test the module imports
    import tier_manager


def test_import_tradingagents_package():
    """Test that the tradingagents package can be imported."""
    import tradingagents


def test_import_graph_module():
    """Test that the trading graph can be imported (if dependencies available)."""
    pytest = __import__('pytest')
    try:
        from tradingagents.graph import TradingAgentsGraph
    except ModuleNotFoundError as e:
        if "langgraph" in str(e) or "langchain" in str(e):
            pytest.skip("langgraph module not installed")
        raise
