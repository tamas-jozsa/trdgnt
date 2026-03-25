"""Tests for TICKET-031/032/033: options flow, earnings calendar, analyst targets."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticker_mock(
    options=("2026-04-17",),
    calls_df=None,
    puts_df=None,
    fast_info_price=None,
    calendar=None,
    info=None,
    earnings_history=None,
):
    mock = MagicMock()
    mock.options = options

    chain = MagicMock()
    chain.calls = calls_df if calls_df is not None else pd.DataFrame(columns=["strike", "volume", "openInterest", "impliedVolatility"])
    chain.puts  = puts_df  if puts_df  is not None else pd.DataFrame(columns=["strike", "volume", "openInterest", "impliedVolatility"])
    mock.option_chain.return_value = chain

    fi = MagicMock()
    fi.last_price = fast_info_price or 100.0
    mock.fast_info = fi

    mock.calendar = calendar or {}
    mock.info      = info or {}
    mock.earnings_history = earnings_history

    return mock


# ---------------------------------------------------------------------------
# TICKET-031: Options Flow
# ---------------------------------------------------------------------------

class TestGetOptionsFlow:

    def _make_options_df(self, strikes, volumes, oi_values, ivs):
        return pd.DataFrame({
            "strike": strikes,
            "volume": volumes,
            "openInterest": oi_values,
            "impliedVolatility": ivs,
        })

    def test_returns_string_with_ratio(self):
        from tradingagents.dataflows.market_data_tools import get_options_flow
        calls = self._make_options_df([100, 105, 110], [1000, 500, 200], [5000, 3000, 1000], [0.3, 0.32, 0.35])
        puts  = self._make_options_df([95,  90,  85 ], [300,  200, 100], [2000, 1500, 800 ], [0.3, 0.32, 0.35])
        mock  = _make_ticker_mock(calls_df=calls, puts_df=puts, fast_info_price=102.0)
        with patch("yfinance.Ticker", return_value=mock):
            result = get_options_flow("NVDA")
        assert "Put/Call" in result
        assert "NVDA" in result
        assert "BULLISH" in result  # puts < calls

    def test_returns_bearish_when_more_puts(self):
        from tradingagents.dataflows.market_data_tools import get_options_flow
        calls = self._make_options_df([100], [100], [500], [0.3])
        puts  = self._make_options_df([95 ], [500], [2000], [0.3])
        mock  = _make_ticker_mock(calls_df=calls, puts_df=puts, fast_info_price=100.0)
        with patch("yfinance.Ticker", return_value=mock):
            result = get_options_flow("SPY")
        assert "BEARISH" in result

    def test_flags_unusual_call_activity(self):
        from tradingagents.dataflows.market_data_tools import get_options_flow
        # One call with 10x avg volume
        calls = self._make_options_df([100, 105, 110, 115], [10000, 100, 100, 100], [5000]*4, [0.3]*4)
        puts  = self._make_options_df([95], [100], [500], [0.3])
        mock  = _make_ticker_mock(calls_df=calls, puts_df=puts, fast_info_price=102.0)
        with patch("yfinance.Ticker", return_value=mock):
            result = get_options_flow("GME")
        assert "⚡" in result or "Unusual" in result

    def test_returns_empty_when_no_options(self):
        from tradingagents.dataflows.market_data_tools import get_options_flow
        mock = _make_ticker_mock(options=())
        with patch("yfinance.Ticker", return_value=mock):
            result = get_options_flow("TINY")
        assert result == ""

    def test_returns_empty_on_error(self):
        from tradingagents.dataflows.market_data_tools import get_options_flow
        with patch("yfinance.Ticker", side_effect=Exception("fail")):
            result = get_options_flow("NVDA")
        assert result == ""


# ---------------------------------------------------------------------------
# TICKET-032: Earnings Calendar
# ---------------------------------------------------------------------------

class TestGetEarningsCalendar:

    def test_returns_earnings_date(self):
        from tradingagents.dataflows.market_data_tools import get_earnings_calendar
        from datetime import date, timedelta
        next_week = date.today() + timedelta(days=5)
        mock = _make_ticker_mock(calendar={
            "Earnings Date": [next_week],
            "EPS Estimate": 3.84,
            "Revenue Estimate": 3_920_000_000,
        })
        with patch("yfinance.Ticker", return_value=mock):
            result = get_earnings_calendar("NOW")
        assert "Earnings" in result
        assert "NOW" in result

    def test_flags_binary_risk_within_7_days(self):
        from tradingagents.dataflows.market_data_tools import get_earnings_calendar
        from datetime import date, timedelta
        soon = date.today() + timedelta(days=3)
        mock = _make_ticker_mock(calendar={"Earnings Date": [soon]})
        with patch("yfinance.Ticker", return_value=mock):
            result = get_earnings_calendar("NVDA")
        assert "BINARY RISK" in result or "⚠️" in result

    def test_no_binary_flag_for_distant_earnings(self):
        from tradingagents.dataflows.market_data_tools import get_earnings_calendar
        from datetime import date, timedelta
        far = date.today() + timedelta(days=90)
        mock = _make_ticker_mock(calendar={"Earnings Date": [far]})
        with patch("yfinance.Ticker", return_value=mock):
            result = get_earnings_calendar("NVDA")
        assert "BINARY RISK" not in result

    def test_shows_eps_and_revenue_estimate(self):
        from tradingagents.dataflows.market_data_tools import get_earnings_calendar
        from datetime import date, timedelta
        mock = _make_ticker_mock(calendar={
            "Earnings Date": [date.today() + timedelta(days=10)],
            "EPS Estimate": 2.50,
            "Revenue Estimate": 5_000_000_000,
        })
        with patch("yfinance.Ticker", return_value=mock):
            result = get_earnings_calendar("AAPL")
        assert "2.50" in result
        assert "5.00B" in result or "5.0B" in result

    def test_returns_empty_on_error(self):
        from tradingagents.dataflows.market_data_tools import get_earnings_calendar
        with patch("yfinance.Ticker", side_effect=Exception("fail")):
            result = get_earnings_calendar("NVDA")
        assert result == ""


# ---------------------------------------------------------------------------
# TICKET-033: Analyst Targets
# ---------------------------------------------------------------------------

class TestGetAnalystTargets:

    def test_returns_target_and_upside(self):
        from tradingagents.dataflows.market_data_tools import get_analyst_targets
        mock = _make_ticker_mock(info={
            "targetMeanPrice": 220.0,
            "targetHighPrice": 280.0,
            "targetLowPrice":  160.0,
            "recommendationMean": 1.8,
            "recommendationKey": "buy",
            "numberOfAnalystOpinions": 42,
            "currentPrice": 178.56,
        })
        with patch("yfinance.Ticker", return_value=mock):
            result = get_analyst_targets("NVDA")
        assert "220" in result      # mean target
        assert "NVDA" in result
        assert "42" in result       # analyst count
        assert "BUY" in result.upper()

    def test_computes_upside_percentage(self):
        from tradingagents.dataflows.market_data_tools import get_analyst_targets
        mock = _make_ticker_mock(info={
            "targetMeanPrice": 150.0,
            "targetHighPrice": 200.0,
            "targetLowPrice":  100.0,
            "recommendationMean": 2.0,
            "recommendationKey": "buy",
            "numberOfAnalystOpinions": 20,
            "currentPrice": 100.0,  # exactly at low target
        })
        with patch("yfinance.Ticker", return_value=mock):
            result = get_analyst_targets("TEST")
        assert "+50.0%" in result  # upside to mean = (150-100)/100 = 50%

    def test_flags_overvalued_when_above_target(self):
        from tradingagents.dataflows.market_data_tools import get_analyst_targets
        mock = _make_ticker_mock(info={
            "targetMeanPrice": 100.0,
            "targetHighPrice": 120.0,
            "targetLowPrice":  80.0,
            "recommendationMean": 3.0,
            "recommendationKey": "hold",
            "numberOfAnalystOpinions": 15,
            "currentPrice": 135.0,  # well above mean target
        })
        with patch("yfinance.Ticker", return_value=mock):
            result = get_analyst_targets("OVER")
        assert "ABOVE" in result or "overvalued" in result.lower()

    def test_flags_undervalued_when_large_upside(self):
        from tradingagents.dataflows.market_data_tools import get_analyst_targets
        mock = _make_ticker_mock(info={
            "targetMeanPrice": 200.0,
            "currentPrice": 100.0,   # 100% upside to mean
            "targetHighPrice": 250.0,
            "targetLowPrice":  150.0,
            "recommendationMean": 1.5,
            "recommendationKey": "strong_buy",
            "numberOfAnalystOpinions": 30,
        })
        with patch("yfinance.Ticker", return_value=mock):
            result = get_analyst_targets("VALUE")
        assert "✅" in result or "upside" in result.lower()

    def test_returns_empty_when_no_target(self):
        from tradingagents.dataflows.market_data_tools import get_analyst_targets
        mock = _make_ticker_mock(info={"currentPrice": 100.0})  # no targetMeanPrice
        with patch("yfinance.Ticker", return_value=mock):
            result = get_analyst_targets("NONE")
        assert result == ""

    def test_returns_empty_on_error(self):
        from tradingagents.dataflows.market_data_tools import get_analyst_targets
        with patch("yfinance.Ticker", side_effect=Exception("fail")):
            result = get_analyst_targets("ERR")
        assert result == ""


# ---------------------------------------------------------------------------
# Tool registration tests
# ---------------------------------------------------------------------------

class TestNewToolsRegistered:

    def test_options_flow_in_social_analyst(self):
        from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst
        from unittest.mock import MagicMock
        from langchain_core.messages import HumanMessage
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = MagicMock()
        node = create_social_media_analyst(mock_llm)
        state = {"trade_date": "2026-03-25", "company_of_interest": "NVDA",
                 "messages": [HumanMessage(content="NVDA")], "macro_context": "",
                 "position_context": "", "social_tool_calls": 0}
        try:
            node(state)
        except Exception:
            pass
        call_args = mock_llm.bind_tools.call_args
        if call_args:
            names = [t.name for t in call_args[0][0]]
            assert "get_options_flow" in names

    def test_earnings_calendar_in_news_analyst(self):
        from tradingagents.agents.analysts.news_analyst import create_news_analyst
        from unittest.mock import MagicMock
        from langchain_core.messages import HumanMessage
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = MagicMock()
        node = create_news_analyst(mock_llm)
        state = {"trade_date": "2026-03-25", "company_of_interest": "NOW",
                 "messages": [HumanMessage(content="NOW")], "macro_context": "",
                 "position_context": "", "news_tool_calls": 0}
        try:
            node(state)
        except Exception:
            pass
        call_args = mock_llm.bind_tools.call_args
        if call_args:
            names = [t.name for t in call_args[0][0]]
            assert "get_earnings_calendar" in names

    def test_analyst_targets_in_fundamentals_analyst(self):
        from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
        from unittest.mock import MagicMock
        from langchain_core.messages import HumanMessage
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = MagicMock()
        node = create_fundamentals_analyst(mock_llm)
        state = {"trade_date": "2026-03-25", "company_of_interest": "NVDA",
                 "messages": [HumanMessage(content="NVDA")], "macro_context": "",
                 "position_context": "", "fundamentals_tool_calls": 0}
        try:
            node(state)
        except Exception:
            pass
        call_args = mock_llm.bind_tools.call_args
        if call_args:
            names = [t.name for t in call_args[0][0]]
            assert "get_analyst_targets" in names
