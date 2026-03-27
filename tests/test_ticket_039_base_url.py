"""
Tests for TICKET-039: ALPACA_BASE_URL unified across all files.

Verifies that trading_loop.get_market_clock() and update_positions.fetch_positions()
both honour the ALPACA_BASE_URL environment variable instead of hardcoding the
paper API URL.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestGetMarketClockUsesBaseUrl:

    def _make_clock_response(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "is_open": False,
            "next_open": "2026-03-28T09:30:00-04:00",
            "next_close": "2026-03-28T16:00:00-04:00",
        }
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_uses_default_paper_url(self, monkeypatch):
        import trading_loop as tl
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
        monkeypatch.delenv("ALPACA_BASE_URL", raising=False)

        with patch("trading_loop.requests.get",
                   return_value=self._make_clock_response()) as mock_get:
            tl.get_market_clock()

        called_url = mock_get.call_args[0][0]
        assert "paper-api.alpaca.markets" in called_url

    def test_honours_alpaca_base_url_env_var(self, monkeypatch):
        import trading_loop as tl
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
        monkeypatch.setenv("ALPACA_BASE_URL",   "https://api.custom.example.com")

        with patch("trading_loop.requests.get",
                   return_value=self._make_clock_response()) as mock_get:
            tl.get_market_clock()

        called_url = mock_get.call_args[0][0]
        assert "api.custom.example.com" in called_url, (
            f"Expected custom base URL. Actual: {called_url}"
        )

    def test_url_ends_with_v2_clock(self, monkeypatch):
        import trading_loop as tl
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")

        with patch("trading_loop.requests.get",
                   return_value=self._make_clock_response()) as mock_get:
            tl.get_market_clock()

        called_url = mock_get.call_args[0][0]
        assert called_url.endswith("/v2/clock"), (
            f"Expected URL to end with /v2/clock. Actual: {called_url}"
        )


class TestFetchPositionsUsesBaseUrl:

    def _make_session(self, base_url_check: list):
        """Return a mock session that records which URLs were called."""
        def _get_response(data):
            r = MagicMock()
            r.json.return_value = data
            return r

        account = {"equity": "100000", "cash": "50000", "buying_power": "50000"}
        positions = []

        mock_session = MagicMock()
        def side_effect(url, **kwargs):
            base_url_check.append(url)
            if "/account" in url:
                return _get_response(account)
            return _get_response(positions)

        mock_session.get.side_effect = side_effect
        return mock_session

    def test_honours_alpaca_base_url_env_var(self, monkeypatch):
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
        monkeypatch.setenv("ALPACA_BASE_URL",   "https://custom.alpaca.example.com")

        called_urls: list = []
        mock_session = self._make_session(called_urls)
        with patch.object(up, "get_session", return_value=mock_session):
            up.fetch_positions()

        assert any("custom.alpaca.example.com" in u for u in called_urls), (
            f"Expected custom base URL. Actual calls: {called_urls}"
        )

    def test_uses_default_paper_url_when_env_not_set(self, monkeypatch):
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
        monkeypatch.delenv("ALPACA_BASE_URL", raising=False)

        called_urls: list = []
        mock_session = self._make_session(called_urls)
        with patch.object(up, "get_session", return_value=mock_session):
            up.fetch_positions()

        assert any("paper-api.alpaca.markets" in u for u in called_urls)
