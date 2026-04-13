"""Tests for screener.py — pluggable stock screener.

TICKET-113
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screener import (
    ScreenerCandidate,
    ScreenerFilters,
    FinvizScreener,
    CompositeScreener,
    create_screener,
    exclude_portfolio,
    exclude_cooldown,
    exclude_recently_debated,
    _parse_market_cap,
    _parse_float,
    _parse_pct,
)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


class TestParsingHelpers:
    def test_parse_market_cap_billions(self):
        assert _parse_market_cap("1.5B") == 1_500_000_000
        assert _parse_market_cap("100B") == 100_000_000_000

    def test_parse_market_cap_millions(self):
        assert _parse_market_cap("500M") == 500_000_000

    def test_parse_market_cap_trillions(self):
        assert _parse_market_cap("2.5T") == 2_500_000_000_000

    def test_parse_market_cap_numeric(self):
        assert _parse_market_cap(1_000_000_000) == 1_000_000_000

    def test_parse_market_cap_invalid(self):
        assert _parse_market_cap("invalid") == 0.0

    def test_parse_float(self):
        assert _parse_float("142.50") == 142.5
        assert _parse_float(42) == 42.0
        assert _parse_float("1,234.56") == 1234.56
        assert _parse_float("invalid") == 0.0

    def test_parse_pct(self):
        assert _parse_pct("2.5%") == 2.5
        assert _parse_pct("-1.3%") == -1.3
        assert _parse_pct("bad") == 0.0


# ---------------------------------------------------------------------------
# Exclusion helpers
# ---------------------------------------------------------------------------


class TestExclusionHelpers:
    @pytest.fixture
    def candidates(self):
        return [
            ScreenerCandidate(ticker="NVDA", price=140),
            ScreenerCandidate(ticker="AAPL", price=200),
            ScreenerCandidate(ticker="MSFT", price=400),
            ScreenerCandidate(ticker="GOOGL", price=170),
        ]

    def test_exclude_portfolio(self, candidates):
        result = exclude_portfolio(candidates, {"NVDA", "AAPL"})
        tickers = {c.ticker for c in result}
        assert tickers == {"MSFT", "GOOGL"}

    def test_exclude_portfolio_empty(self, candidates):
        result = exclude_portfolio(candidates, set())
        assert len(result) == 4

    def test_exclude_cooldown(self, candidates):
        result = exclude_cooldown(candidates, {"MSFT"})
        assert len(result) == 3
        assert all(c.ticker != "MSFT" for c in result)

    def test_exclude_recently_debated(self, candidates):
        result = exclude_recently_debated(candidates, {"NVDA", "GOOGL"})
        assert len(result) == 2
        tickers = {c.ticker for c in result}
        assert tickers == {"AAPL", "MSFT"}


# ---------------------------------------------------------------------------
# ScreenerFilters
# ---------------------------------------------------------------------------


class TestScreenerFilters:
    def test_defaults(self):
        f = ScreenerFilters()
        assert f.min_market_cap == 500_000_000
        assert f.min_price == 5.0
        assert f.max_raw_candidates == 100

    def test_custom(self):
        f = ScreenerFilters(min_market_cap=1_000_000_000, min_price=10.0)
        assert f.min_market_cap == 1_000_000_000
        assert f.min_price == 10.0


# ---------------------------------------------------------------------------
# CompositeScreener
# ---------------------------------------------------------------------------


class TestCompositeScreener:
    def test_merge_dedup(self):
        source1 = MagicMock()
        source1.get_source_name.return_value = "src1"
        source1.scan.return_value = [
            ScreenerCandidate(ticker="NVDA", price=140, score=1.0),
            ScreenerCandidate(ticker="AAPL", price=200, score=1.0),
        ]

        source2 = MagicMock()
        source2.get_source_name.return_value = "src2"
        source2.scan.return_value = [
            ScreenerCandidate(ticker="NVDA", price=140, score=1.0),  # dup
            ScreenerCandidate(ticker="MSFT", price=400, score=1.0),
        ]

        screener = CompositeScreener([source1, source2])
        result = screener.scan(ScreenerFilters())

        tickers = {c.ticker for c in result}
        assert tickers == {"NVDA", "AAPL", "MSFT"}

        # NVDA should have boosted score (found by both sources)
        nvda = next(c for c in result if c.ticker == "NVDA")
        assert nvda.score == 2.0

    def test_empty_sources(self):
        screener = CompositeScreener([])
        result = screener.scan(ScreenerFilters())
        assert result == []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestScreenerFactory:
    def test_create_finviz(self):
        s = create_screener("finviz")
        assert isinstance(s, FinvizScreener)

    def test_create_composite(self):
        s = create_screener("composite")
        assert isinstance(s, CompositeScreener)

    def test_create_unknown_fallback(self):
        s = create_screener("unknown_source")
        assert isinstance(s, FinvizScreener)
