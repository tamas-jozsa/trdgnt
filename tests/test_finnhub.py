"""Tests for TICKET-009: Finnhub news integration."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock


SAMPLE_ARTICLES = [
    {
        "headline": "NVDA reports record Q4 earnings, raises guidance",
        "source": "Reuters",
        "url": "https://reuters.com/nvda-earnings",
        "summary": "NVIDIA beat expectations with $35B in revenue driven by data center AI chips.",
        "datetime": 1711234567,
    },
    {
        "headline": "Analysts raise NVDA price target to $1000",
        "source": "Bloomberg",
        "url": "https://bloomberg.com/nvda-pt",
        "summary": "Multiple firms upgraded price targets following blowout results.",
        "datetime": 1711134567,
    },
]


def _make_mock_resp(data):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestFinnhubNews:

    def test_returns_empty_without_api_key(self):
        from tradingagents.dataflows.finnhub_utils import get_news_finnhub

        with patch.dict(os.environ, {}, clear=True):
            # Remove key if present
            os.environ.pop("FINNHUB_API_KEY", None)
            result = get_news_finnhub("NVDA", "2026-03-17", "2026-03-24")

        assert result == ""

    def test_returns_formatted_string_with_key(self):
        from tradingagents.dataflows.finnhub_utils import get_news_finnhub

        mock_resp = _make_mock_resp(SAMPLE_ARTICLES)
        with patch.dict(os.environ, {"FINNHUB_API_KEY": "test_key"}), \
             patch("tradingagents.dataflows.finnhub_utils.urlopen", return_value=mock_resp):
            result = get_news_finnhub("NVDA", "2026-03-17", "2026-03-24")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_headline(self):
        from tradingagents.dataflows.finnhub_utils import get_news_finnhub

        mock_resp = _make_mock_resp(SAMPLE_ARTICLES)
        with patch.dict(os.environ, {"FINNHUB_API_KEY": "test_key"}), \
             patch("tradingagents.dataflows.finnhub_utils.urlopen", return_value=mock_resp):
            result = get_news_finnhub("NVDA", "2026-03-17", "2026-03-24")

        assert "record Q4 earnings" in result

    def test_returns_empty_on_network_error(self):
        from tradingagents.dataflows.finnhub_utils import get_news_finnhub
        from urllib.error import URLError

        with patch.dict(os.environ, {"FINNHUB_API_KEY": "test_key"}), \
             patch("tradingagents.dataflows.finnhub_utils.urlopen",
                   side_effect=URLError("connection refused")):
            result = get_news_finnhub("NVDA", "2026-03-17", "2026-03-24")

        assert result == ""

    def test_returns_empty_when_no_articles(self):
        from tradingagents.dataflows.finnhub_utils import get_news_finnhub

        mock_resp = _make_mock_resp([])
        with patch.dict(os.environ, {"FINNHUB_API_KEY": "test_key"}), \
             patch("tradingagents.dataflows.finnhub_utils.urlopen", return_value=mock_resp):
            result = get_news_finnhub("NVDA", "2026-03-17", "2026-03-24")

        assert result == ""

    def test_includes_ticker_in_header(self):
        from tradingagents.dataflows.finnhub_utils import get_news_finnhub

        mock_resp = _make_mock_resp(SAMPLE_ARTICLES)
        with patch.dict(os.environ, {"FINNHUB_API_KEY": "test_key"}), \
             patch("tradingagents.dataflows.finnhub_utils.urlopen", return_value=mock_resp):
            result = get_news_finnhub("NVDA", "2026-03-17", "2026-03-24")

        assert "NVDA" in result


class TestFinnhubInVendorList:

    def test_finnhub_in_vendor_list(self):
        from tradingagents.dataflows.interface import VENDOR_LIST
        assert "finnhub" in VENDOR_LIST

    def test_finnhub_registered_for_get_news(self):
        from tradingagents.dataflows.interface import VENDOR_METHODS
        assert "finnhub" in VENDOR_METHODS["get_news"]

    def test_finnhub_registered_for_get_global_news(self):
        from tradingagents.dataflows.interface import VENDOR_METHODS
        assert "finnhub" in VENDOR_METHODS["get_global_news"]
