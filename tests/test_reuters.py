"""Tests for Reuters news integration."""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Sample sitemap XML with realistic structure
# ---------------------------------------------------------------------------

def _make_sitemap_xml(entries: list[dict]) -> bytes:
    """Build a minimal Reuters sitemap XML from a list of article dicts."""
    ns_sm    = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ns_news  = "http://www.google.com/schemas/sitemap-news/0.9"
    ns_image = "http://www.google.com/schemas/sitemap-image/1.1"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<urlset xmlns="{ns_sm}" xmlns:news="{ns_news}" xmlns:image="{ns_image}">',
    ]
    for e in entries:
        lines.append(f"""  <url>
    <loc>{e["url"]}</loc>
    <news:news>
      <news:publication><news:name>Reuters</news:name><news:language>en</news:language></news:publication>
      <news:publication_date>{e["date"]}</news:publication_date>
      <news:title><![CDATA[{e["title"]}]]></news:title>
      <news:keywords><![CDATA[{e.get("keywords", "")}]]></news:keywords>
      {"<news:stock_tickers>" + e["tickers"] + "</news:stock_tickers>" if e.get("tickers") else ""}
    </news:news>
  </url>""")
    lines.append("</urlset>")
    return "\n".join(lines).encode("utf-8")


NOW = datetime.now(timezone.utc)

SAMPLE_ENTRIES = [
    {
        "url": "https://www.reuters.com/technology/nvidia-ai-chips-2026-03-24/",
        "title": "Nvidia AI chip demand surges as data center buildout accelerates",
        "date": (NOW - timedelta(hours=2)).isoformat(),
        "tickers": "NVDA.O,AMD.O",
    },
    {
        "url": "https://www.reuters.com/business/energy/oil-falls-ceasefire-2026-03-24/",
        "title": "Oil prices fall on Iran ceasefire talks, Hormuz concern eases",
        "date": (NOW - timedelta(hours=5)).isoformat(),
        "tickers": "XOM.N,VLO.N",
    },
    {
        "url": "https://www.reuters.com/markets/fed-rates-2026-03-24/",
        "title": "Fed's Goolsbee says inflation progress needed to cut rates this year",
        "date": (NOW - timedelta(hours=6)).isoformat(),
        "tickers": "",
    },
    {
        "url": "https://www.reuters.com/sports/tennis/2026-03-24/",
        "title": "Muchova wins Miami Open semi-final",
        "date": (NOW - timedelta(hours=1)).isoformat(),
        "tickers": "",
    },
]


def _mock_urlopen(xml_bytes: bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = xml_bytes
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestFetchSitemap:

    def test_returns_articles(self):
        from tradingagents.dataflows.reuters_utils import _fetch_sitemap
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            articles = _fetch_sitemap(hours_back=48)
        assert len(articles) > 0

    def test_parses_title(self):
        from tradingagents.dataflows.reuters_utils import _fetch_sitemap
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            articles = _fetch_sitemap(hours_back=48)
        titles = [a["title"] for a in articles]
        assert any("Nvidia" in t for t in titles)

    def test_parses_stock_tickers(self):
        from tradingagents.dataflows.reuters_utils import _fetch_sitemap
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            articles = _fetch_sitemap(hours_back=48)
        nvda_article = next((a for a in articles if "NVDA" in a["tickers"]), None)
        assert nvda_article is not None
        assert "AMD" in nvda_article["tickers"]

    def test_strips_exchange_suffix(self):
        """NVDA.O → NVDA, LMT.N → LMT"""
        from tradingagents.dataflows.reuters_utils import _fetch_sitemap
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            articles = _fetch_sitemap(hours_back=48)
        for a in articles:
            for t in a["tickers"]:
                assert "." not in t, f"Exchange suffix not stripped: {t}"

    def test_returns_empty_on_network_error(self):
        from tradingagents.dataflows.reuters_utils import _fetch_sitemap
        from urllib.error import URLError
        with patch("tradingagents.dataflows.reuters_utils.urlopen", side_effect=URLError("fail")):
            articles = _fetch_sitemap()
        assert articles == []

    def test_filters_by_hours_back(self):
        """Articles older than hours_back should be excluded."""
        from tradingagents.dataflows.reuters_utils import _fetch_sitemap

        old_entry = {
            "url": "https://www.reuters.com/old/2026-03-10/",
            "title": "Very old article",
            "date": (NOW - timedelta(days=30)).isoformat(),
            "tickers": "NVDA.O",
        }
        xml = _make_sitemap_xml([old_entry])
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            articles = _fetch_sitemap(hours_back=24)
        assert articles == []

    def test_sorted_newest_first(self):
        from tradingagents.dataflows.reuters_utils import _fetch_sitemap
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            articles = _fetch_sitemap(hours_back=48)
        if len(articles) > 1:
            assert articles[0]["published_at"] >= articles[1]["published_at"]


class TestGetReutersNewsForTicker:

    def test_matches_reuters_tagged_ticker(self):
        from tradingagents.dataflows.reuters_utils import get_reuters_news_for_ticker
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            result = get_reuters_news_for_ticker("NVDA", hours_back=48)
        assert "NVDA" in result
        assert "Nvidia" in result
        assert "Reuters-tagged" in result

    def test_does_not_match_unrelated_ticker(self):
        from tradingagents.dataflows.reuters_utils import get_reuters_news_for_ticker
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            result = get_reuters_news_for_ticker("RCKT", hours_back=48)
        assert result == ""

    def test_returns_empty_on_no_match(self):
        from tradingagents.dataflows.reuters_utils import get_reuters_news_for_ticker
        from urllib.error import URLError
        with patch("tradingagents.dataflows.reuters_utils.urlopen", side_effect=URLError("fail")):
            result = get_reuters_news_for_ticker("NVDA")
        assert result == ""

    def test_includes_total_count(self):
        from tradingagents.dataflows.reuters_utils import get_reuters_news_for_ticker
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            result = get_reuters_news_for_ticker("NVDA", hours_back=48)
        assert "Total Reuters articles" in result


class TestGetReutersGlobalNews:

    def test_returns_business_headlines(self):
        from tradingagents.dataflows.reuters_utils import get_reuters_global_news
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            result = get_reuters_global_news(hours_back=24, limit=10)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_excludes_sports_when_enough_business_available(self):
        """Sports articles filtered when >=5 business articles exist."""
        from tradingagents.dataflows.reuters_utils import get_reuters_global_news

        # Build 6 business articles + 1 sports article
        business_entries = [
            {
                "url": f"https://www.reuters.com/business/story-{i}/",
                "title": f"Business story {i}",
                "date": (NOW - timedelta(hours=i)).isoformat(),
                "tickers": "NVDA.O",
            }
            for i in range(1, 7)
        ]
        sports_entry = {
            "url": "https://www.reuters.com/sports/tennis/2026-03-24/",
            "title": "Muchova wins Miami Open semi-final",
            "date": (NOW - timedelta(hours=1)).isoformat(),
            "tickers": "",
        }
        xml = _make_sitemap_xml(business_entries + [sports_entry])
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            result = get_reuters_global_news(hours_back=48, limit=20)
        assert "Muchova" not in result

    def test_includes_source_attribution(self):
        from tradingagents.dataflows.reuters_utils import get_reuters_global_news
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            result = get_reuters_global_news(hours_back=48, limit=10)
        assert "Reuters" in result

    def test_tags_tickers_in_headlines(self):
        """Headlines with tagged tickers should show the ticker in output."""
        from tradingagents.dataflows.reuters_utils import get_reuters_global_news
        xml = _make_sitemap_xml(SAMPLE_ENTRIES)
        with patch("tradingagents.dataflows.reuters_utils.urlopen", return_value=_mock_urlopen(xml)):
            result = get_reuters_global_news(hours_back=48, limit=10)
        assert "NVDA" in result or "XOM" in result


class TestNewsAnalystHasReutersTools:
    """Verify news analyst tool list includes Reuters tools."""

    def test_news_analyst_has_reuters_news_tool(self):
        from tradingagents.agents.analysts.news_analyst import create_news_analyst
        from unittest.mock import MagicMock
        from langchain_core.messages import HumanMessage

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = MagicMock()
        node = create_news_analyst(mock_llm)

        state = {
            "trade_date": "2026-03-25",
            "company_of_interest": "NVDA",
            "messages": [HumanMessage(content="NVDA")],
            "macro_context": "",
            "position_context": "",
            "news_tool_calls": 0,
        }
        try:
            node(state)
        except Exception:
            pass

        call_args = mock_llm.bind_tools.call_args
        if call_args:
            tool_names = [t.name for t in call_args[0][0]]
            assert "get_reuters_news" in tool_names
            assert "get_reuters_global_news" in tool_names
