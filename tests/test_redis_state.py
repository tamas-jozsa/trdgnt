"""Tests for redis_state.py — shared state management.

TICKET-113
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is on path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tradingagents.redis_state import RedisState, _key


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temp data directory for JSON backups."""
    return tmp_path / "data"


@pytest.fixture
def state_no_redis(tmp_data_dir):
    """RedisState with Redis unavailable (fallback to JSON)."""
    with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:9999"}):
        s = RedisState(redis_url="redis://localhost:9999", data_dir=tmp_data_dir)
        s._available = False
        s._redis = None
        return s


@pytest.fixture
def state_fakeredis(tmp_data_dir):
    """RedisState backed by fakeredis."""
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    s = RedisState.__new__(RedisState)
    s._data_dir = tmp_data_dir
    s._redis_url = "redis://fake"
    s._redis = fakeredis.FakeRedis(decode_responses=True)
    s._available = True
    return s


# ---------------------------------------------------------------------------
# Tests with Redis unavailable (JSON fallback)
# ---------------------------------------------------------------------------


class TestRedisStateNoRedis:
    def test_available_false(self, state_no_redis):
        assert not state_no_redis.available

    def test_get_positions_empty(self, state_no_redis):
        assert state_no_redis.get_positions() == {}

    def test_set_and_get_position_via_json(self, state_no_redis, tmp_data_dir):
        thesis = {"ticker": "NVDA", "thesis": {"rationale": "test"}}
        state_no_redis.set_position("NVDA", thesis)

        # Should be written to JSON backup
        backup = tmp_data_dir / "theses" / "NVDA.json"
        assert backup.exists()
        assert json.loads(backup.read_text())["ticker"] == "NVDA"

        # Reading should find it from backup
        result = state_no_redis.get_position("NVDA")
        assert result["ticker"] == "NVDA"

    def test_remove_position_deletes_json(self, state_no_redis, tmp_data_dir):
        state_no_redis.set_position("NVDA", {"ticker": "NVDA"})
        backup = tmp_data_dir / "theses" / "NVDA.json"
        assert backup.exists()

        state_no_redis.remove_position("NVDA")
        assert not backup.exists()

    def test_cooldown_via_json(self, state_no_redis):
        state_no_redis.set_cooldown("NVDA", days=7)
        assert state_no_redis.is_in_cooldown("NVDA")

    def test_get_cash_default(self, state_no_redis):
        assert state_no_redis.get_cash() == 0.0


# ---------------------------------------------------------------------------
# Tests with fakeredis
# ---------------------------------------------------------------------------


class TestRedisStateFakeRedis:
    def test_available_true(self, state_fakeredis):
        assert state_fakeredis.available

    def test_set_get_position(self, state_fakeredis):
        thesis = {"ticker": "AAPL", "entry_price": 150.0}
        state_fakeredis.set_position("AAPL", thesis)

        result = state_fakeredis.get_position("AAPL")
        assert result["ticker"] == "AAPL"
        assert result["entry_price"] == 150.0

    def test_get_positions_multiple(self, state_fakeredis):
        state_fakeredis.set_position("AAPL", {"ticker": "AAPL"})
        state_fakeredis.set_position("MSFT", {"ticker": "MSFT"})

        positions = state_fakeredis.get_positions()
        assert len(positions) == 2
        assert "AAPL" in positions
        assert "MSFT" in positions

    def test_remove_position(self, state_fakeredis):
        state_fakeredis.set_position("NVDA", {"ticker": "NVDA"})
        state_fakeredis.remove_position("NVDA")
        assert state_fakeredis.get_position("NVDA") is None

    def test_get_portfolio_tickers(self, state_fakeredis):
        state_fakeredis.set_position("AAPL", {"ticker": "AAPL"})
        state_fakeredis.set_position("MSFT", {"ticker": "MSFT"})
        assert state_fakeredis.get_portfolio_tickers() == {"AAPL", "MSFT"}

    def test_cash(self, state_fakeredis):
        state_fakeredis.set_cash(50000.0)
        assert state_fakeredis.get_cash() == 50000.0

    def test_analyzed_today(self, state_fakeredis):
        assert not state_fakeredis.was_analyzed_today("NVDA")
        state_fakeredis.mark_analyzed_today("NVDA")
        assert state_fakeredis.was_analyzed_today("NVDA")

    def test_cooldown(self, state_fakeredis):
        assert not state_fakeredis.is_in_cooldown("NVDA")
        state_fakeredis.set_cooldown("NVDA", days=7)
        assert state_fakeredis.is_in_cooldown("NVDA")

    def test_news_event_queue(self, state_fakeredis):
        state_fakeredis.push_news_event({"headline": "test"})
        state_fakeredis.push_news_event({"headline": "test2"})

        events = state_fakeredis.pop_news_events(10)
        assert len(events) == 2
        assert events[0]["headline"] == "test"

        # Queue should be empty after pop
        assert state_fakeredis.pop_news_events(10) == []

    def test_review_flag_queue(self, state_fakeredis):
        state_fakeredis.push_review_flag("NVDA", "weakening thesis")
        flags = state_fakeredis.pop_review_flags()
        assert len(flags) == 1
        assert flags[0]["ticker"] == "NVDA"

        # Queue should be empty after pop
        assert state_fakeredis.pop_review_flags() == []

    def test_key_prefixing(self, state_fakeredis):
        assert _key("positions") == "trdagnt:positions"
        assert _key("cash") == "trdagnt:cash"
