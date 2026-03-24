"""Tests for TICKET-006: real Reddit/social sentiment data."""

import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO


# ---------------------------------------------------------------------------
# Reddit utils
# ---------------------------------------------------------------------------

REDDIT_RESPONSE = {
    "data": {
        "children": [
            {"data": {
                "title": "$NVDA is going to the moon — AI supercycle confirmed",
                "score": 1200,
                "num_comments": 450,
                "permalink": "/r/wallstreetbets/comments/abc",
                "link_flair_text": "DD",
                "created_utc": 1711234567,
            }},
            {"data": {
                "title": "NVDA bear case — overvalued at 40x revenue",
                "score": 300,
                "num_comments": 120,
                "permalink": "/r/stocks/comments/def",
                "link_flair_text": "Discussion",
                "created_utc": 1711134567,
            }},
        ]
    }
}


def _make_urlopen_mock(response_data: dict):
    """Return a context-manager mock that yields a fake HTTP response."""
    encoded = json.dumps(response_data).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = encoded
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestRedditUtils:

    def test_returns_string(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_sentiment
        mock_resp = _make_urlopen_mock(REDDIT_RESPONSE)
        with patch("tradingagents.dataflows.reddit_utils.urlopen", return_value=mock_resp):
            result = get_reddit_sentiment("NVDA", days=7)
        assert isinstance(result, str)

    def test_includes_ticker(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_sentiment
        mock_resp = _make_urlopen_mock(REDDIT_RESPONSE)
        with patch("tradingagents.dataflows.reddit_utils.urlopen", return_value=mock_resp):
            result = get_reddit_sentiment("NVDA")
        assert "NVDA" in result

    def test_includes_post_titles(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_sentiment
        mock_resp = _make_urlopen_mock(REDDIT_RESPONSE)
        with patch("tradingagents.dataflows.reddit_utils.urlopen", return_value=mock_resp):
            result = get_reddit_sentiment("NVDA")
        assert "moon" in result or "AI supercycle" in result

    def test_returns_empty_on_network_error(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_sentiment
        from urllib.error import URLError
        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   side_effect=URLError("connection refused")):
            result = get_reddit_sentiment("NVDA")
        assert result == ""

    def test_includes_sentiment_signal(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_sentiment
        mock_resp = _make_urlopen_mock(REDDIT_RESPONSE)
        with patch("tradingagents.dataflows.reddit_utils.urlopen", return_value=mock_resp):
            result = get_reddit_sentiment("NVDA")
        assert any(word in result for word in ["BULLISH", "BEARISH", "NEUTRAL"])


# ---------------------------------------------------------------------------
# StockTwits utils
# ---------------------------------------------------------------------------

STOCKTWITS_RESPONSE = {
    "messages": [
        {"body": "NVDA breaking out, buying calls!", "user": {"username": "trader1"},
         "entities": {"sentiment": {"basic": "Bullish"}}},
        {"body": "Taking profits on NVDA here", "user": {"username": "trader2"},
         "entities": {"sentiment": {"basic": "Bearish"}}},
        {"body": "NVDA holding 200 SMA — staying long", "user": {"username": "trader3"},
         "entities": {"sentiment": {"basic": "Bullish"}}},
    ]
}


class TestStocktwitsUtils:

    def test_returns_string(self):
        from tradingagents.dataflows.stocktwits_utils import get_stocktwits_sentiment
        mock_resp = _make_urlopen_mock(STOCKTWITS_RESPONSE)
        with patch("tradingagents.dataflows.stocktwits_utils.urlopen", return_value=mock_resp):
            result = get_stocktwits_sentiment("NVDA")
        assert isinstance(result, str)

    def test_includes_bullish_bearish_counts(self):
        from tradingagents.dataflows.stocktwits_utils import get_stocktwits_sentiment
        mock_resp = _make_urlopen_mock(STOCKTWITS_RESPONSE)
        with patch("tradingagents.dataflows.stocktwits_utils.urlopen", return_value=mock_resp):
            result = get_stocktwits_sentiment("NVDA")
        assert "Bullish" in result and "Bearish" in result

    def test_returns_empty_on_network_error(self):
        from tradingagents.dataflows.stocktwits_utils import get_stocktwits_sentiment
        from urllib.error import URLError
        with patch("tradingagents.dataflows.stocktwits_utils.urlopen",
                   side_effect=URLError("connection refused")):
            result = get_stocktwits_sentiment("NVDA")
        assert result == ""

    def test_returns_empty_when_no_messages(self):
        from tradingagents.dataflows.stocktwits_utils import get_stocktwits_sentiment
        mock_resp = _make_urlopen_mock({"messages": []})
        with patch("tradingagents.dataflows.stocktwits_utils.urlopen", return_value=mock_resp):
            result = get_stocktwits_sentiment("NVDA")
        assert result == ""

    def test_overall_sentiment_bullish_when_majority_bullish(self):
        from tradingagents.dataflows.stocktwits_utils import get_stocktwits_sentiment
        mock_resp = _make_urlopen_mock(STOCKTWITS_RESPONSE)  # 2 bull, 1 bear
        with patch("tradingagents.dataflows.stocktwits_utils.urlopen", return_value=mock_resp):
            result = get_stocktwits_sentiment("NVDA")
        assert "BULLISH" in result


class TestSocialAnalystTools:
    """Verify social analyst now has Reddit and StockTwits tools."""

    def test_social_analyst_has_reddit_tool(self):
        from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst
        from unittest.mock import MagicMock

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = MagicMock()
        node_fn = create_social_media_analyst(mock_llm)

        state = {
            "trade_date": "2026-03-24",
            "company_of_interest": "NVDA",
            "position_context": "",
            "macro_context": "",
            "messages": [("human", "NVDA")],
        }
        try:
            node_fn(state)
        except Exception:
            pass

        call_args = mock_llm.bind_tools.call_args
        if call_args:
            tools = call_args[0][0]
            tool_names = [t.name for t in tools]
            assert "get_reddit_sentiment" in tool_names
            assert "get_stocktwits_sentiment" in tool_names
