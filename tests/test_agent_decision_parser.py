"""
Tests for alpaca_bridge.parse_agent_decision() — TICKET B1.

Verifies that structured Risk Judge output (stop, target, position size,
conviction) is correctly extracted and used to scale trade sizes.
"""

import pytest
from alpaca_bridge import parse_agent_decision


FULL_BUY = """
FINAL DECISION: BUY
CONVICTION: 7
ENTRY: market
STOP-LOSS: $167.38
TARGET: $195.00
POSITION SIZE: 1.5x base allocation
REASONING: Strong technical setup with geopolitical tailwind.

FINAL DECISION: **BUY**
"""

FULL_SELL = """
FINAL DECISION: SELL
CONVICTION: 8
ENTRY: market
STOP-LOSS: $95.00
TARGET: $72.00
POSITION SIZE: 1x base allocation
REASONING: Breakdown below 200 SMA, negative earnings surprise expected.

FINAL DECISION: **SELL**
"""

REDUCED_SIZE = """
FINAL DECISION: BUY
CONVICTION: 5
ENTRY: market
STOP-LOSS: $230.00
TARGET: $280.00
POSITION SIZE: 0.5x base allocation
REASONING: Mixed signals — smaller size appropriate.

FINAL DECISION: **BUY**
"""

HOLD_OUTPUT = """
FINAL DECISION: HOLD
CONVICTION: 4
ENTRY: market
STOP-LOSS: $100.00
TARGET: $130.00
POSITION SIZE: 1x base allocation
REASONING: Binary earnings event imminent.

FINAL DECISION: **HOLD**
"""

EMPTY = ""
NONE_INPUT = None


class TestParseAgentDecision:

    def test_extracts_buy_signal(self):
        r = parse_agent_decision(FULL_BUY)
        assert r["signal"] == "BUY"

    def test_extracts_sell_signal(self):
        r = parse_agent_decision(FULL_SELL)
        assert r["signal"] == "SELL"

    def test_extracts_hold_signal(self):
        r = parse_agent_decision(HOLD_OUTPUT)
        assert r["signal"] == "HOLD"

    def test_extracts_stop_loss(self):
        r = parse_agent_decision(FULL_BUY)
        assert r["stop"] == pytest.approx(167.38)

    def test_extracts_target(self):
        r = parse_agent_decision(FULL_BUY)
        assert r["target"] == pytest.approx(195.00)

    def test_extracts_conviction(self):
        r = parse_agent_decision(FULL_BUY)
        assert r["conviction"] == 7

    def test_extracts_size_multiplier_1_5x(self):
        r = parse_agent_decision(FULL_BUY)
        assert r["size_multiplier"] == pytest.approx(1.5)

    def test_extracts_size_multiplier_0_5x(self):
        r = parse_agent_decision(REDUCED_SIZE)
        assert r["size_multiplier"] == pytest.approx(0.5)

    def test_defaults_on_empty_string(self):
        r = parse_agent_decision(EMPTY)
        assert r["signal"] == "HOLD"
        assert r["stop"] is None
        assert r["target"] is None
        assert r["size_multiplier"] == pytest.approx(1.0)
        assert r["conviction"] == 5

    def test_defaults_on_none(self):
        r = parse_agent_decision(None)
        assert r["signal"] == "HOLD"
        assert r["size_multiplier"] == pytest.approx(1.0)

    def test_clamps_size_multiplier_above_max(self):
        text = "FINAL DECISION: BUY\nPOSITION SIZE: 10x\nFINAL DECISION: **BUY**"
        r = parse_agent_decision(text)
        assert r["size_multiplier"] <= 2.0

    def test_clamps_size_multiplier_below_min(self):
        text = "FINAL DECISION: BUY\nPOSITION SIZE: 0.1x\nFINAL DECISION: **BUY**"
        r = parse_agent_decision(text)
        assert r["size_multiplier"] >= 0.25

    def test_handles_stop_with_comma(self):
        text = "FINAL DECISION: BUY\nSTOP-LOSS: $1,234.56\nFINAL DECISION: **BUY**"
        r = parse_agent_decision(text)
        assert r["stop"] == pytest.approx(1234.56)

    def test_handles_no_dollar_sign_stop(self):
        text = "FINAL DECISION: BUY\nSTOP-LOSS: 167.00\nFINAL DECISION: **BUY**"
        r = parse_agent_decision(text)
        assert r["stop"] == pytest.approx(167.00)


class TestSignalProcessorNoLLM:
    """Verify the SignalProcessor no longer makes an LLM call."""

    def test_process_signal_uses_regex_only(self):
        from tradingagents.graph.signal_processing import SignalProcessor
        from unittest.mock import MagicMock

        mock_llm = MagicMock()
        sp = SignalProcessor(mock_llm)

        result = sp.process_signal("FINAL DECISION: **BUY**")
        assert result == "BUY"
        # LLM should NOT have been called
        mock_llm.invoke.assert_not_called()

    def test_process_signal_returns_hold_for_none(self):
        from tradingagents.graph.signal_processing import SignalProcessor
        from unittest.mock import MagicMock

        sp = SignalProcessor(MagicMock())
        assert sp.process_signal(None) == "HOLD"
        assert sp.process_signal("") == "HOLD"

    def test_process_signal_regex_fallback(self):
        from tradingagents.graph.signal_processing import SignalProcessor
        from unittest.mock import MagicMock
        sp = SignalProcessor(MagicMock())
        assert sp.process_signal("After careful analysis, I recommend to SELL.") == "SELL"
        assert sp.process_signal("The final answer is hold.") == "HOLD"


class TestShortInterestTool:

    def test_returns_formatted_string(self):
        from tradingagents.dataflows.market_data_tools import get_short_interest
        from unittest.mock import patch, MagicMock

        mock_ticker = MagicMock()
        mock_ticker.info = {
            "shortPercentOfFloat": 0.22,
            "shortRatio": 4.5,
            "sharesShort": 5_000_000,
            "sharesShortPriorMonth": 4_200_000,
            "floatShares": 22_700_000,
        }

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_short_interest("GME")

        assert "22.0%" in result
        assert "4.5" in result
        assert "GME" in result
        assert "🔥" in result  # HIGH SHORT FLOAT flag

    def test_elevated_flag_at_15_percent(self):
        from tradingagents.dataflows.market_data_tools import get_short_interest
        from unittest.mock import patch, MagicMock

        mock_ticker = MagicMock()
        mock_ticker.info = {"shortPercentOfFloat": 0.16, "shortRatio": 3.0}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_short_interest("TEST")

        assert "⚠️" in result or "ELEVATED" in result

    def test_no_flag_for_low_short_float(self):
        from tradingagents.dataflows.market_data_tools import get_short_interest
        from unittest.mock import patch, MagicMock

        mock_ticker = MagicMock()
        mock_ticker.info = {"shortPercentOfFloat": 0.03, "shortRatio": 1.0}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_short_interest("AAPL")

        assert "🔥" not in result
        assert "Low short float" in result

    def test_returns_empty_on_error(self):
        from tradingagents.dataflows.market_data_tools import get_short_interest
        from unittest.mock import patch

        with patch("yfinance.Ticker", side_effect=Exception("fail")):
            result = get_short_interest("ERR")

        assert result == ""

    def test_returns_empty_when_no_data(self):
        from tradingagents.dataflows.market_data_tools import get_short_interest
        from unittest.mock import patch, MagicMock

        mock_ticker = MagicMock()
        mock_ticker.info = {}  # no shortPercentOfFloat key

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_short_interest("NONE")

        assert result == ""
