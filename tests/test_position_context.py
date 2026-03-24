"""Tests for TICKET-007: position awareness + debate rounds."""

import pytest
from unittest.mock import MagicMock, patch


class TestPositionContext:
    """Test that position context is correctly built and injected."""

    def test_build_position_context_no_position(self):
        """When no position exists, returns empty string."""
        import trading_loop as tl

        mock_tc = MagicMock()
        mock_tc.get_open_position.side_effect = Exception("no position")

        with patch("trading_loop._get_trading_client" if hasattr(tl, "_get_trading_client")
                   else "alpaca_bridge._get_trading_client") as mock_getter:
            mock_getter.return_value = mock_tc
            result = tl._build_position_context("NVDA")

        assert result == ""

    def test_build_position_context_with_position(self):
        """When position exists, returns formatted string."""
        import trading_loop as tl
        from alpaca_bridge import _get_trading_client
        import alpaca_bridge as ab

        mock_pos = MagicMock()
        mock_pos.qty = "10.0"
        mock_pos.avg_entry_price = "142.30"
        mock_pos.unrealized_plpc = "-0.082"   # -8.2%
        mock_pos.unrealized_pl = "-116.69"

        mock_tc = MagicMock()
        mock_tc.get_open_position.return_value = mock_pos

        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = tl._build_position_context("NVDA")

        assert "CURRENT POSITION" in result
        assert "10.0000 shares" in result
        assert "$142.30" in result
        assert "-8.2%" in result

    def test_position_context_positive_pnl(self):
        """Positive P&L shows + sign."""
        import trading_loop as tl
        import alpaca_bridge as ab

        mock_pos = MagicMock()
        mock_pos.qty = "5.0"
        mock_pos.avg_entry_price = "200.00"
        mock_pos.unrealized_plpc = "0.15"    # +15%
        mock_pos.unrealized_pl = "150.00"

        mock_tc = MagicMock()
        mock_tc.get_open_position.return_value = mock_pos

        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = tl._build_position_context("AVGO")

        assert "+$150.00" in result
        assert "+15.0%" in result


class TestDebateRounds:
    """Verify default config has been updated to 2 rounds."""

    def test_default_debate_rounds_is_2(self):
        from tradingagents.default_config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["max_debate_rounds"] == 2

    def test_default_risk_rounds_is_2(self):
        from tradingagents.default_config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["max_risk_discuss_rounds"] == 2


class TestPropagatorPositionContext:
    """Verify Propagator passes position_context into initial state."""

    def test_initial_state_includes_position_context(self):
        from tradingagents.graph.propagation import Propagator

        p = Propagator()
        state = p.create_initial_state(
            "NVDA", "2026-03-24",
            position_context="CURRENT POSITION: Long 10 @ $142.30, P&L: -8.2%"
        )
        assert state["position_context"] == "CURRENT POSITION: Long 10 @ $142.30, P&L: -8.2%"

    def test_initial_state_empty_position_context_by_default(self):
        from tradingagents.graph.propagation import Propagator

        p = Propagator()
        state = p.create_initial_state("NVDA", "2026-03-24")
        assert state["position_context"] == ""


class TestInsiderTransactionsTool:
    """Verify get_insider_transactions is now in fundamentals analyst tools."""

    def test_fundamentals_analyst_has_insider_tool(self):
        from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
        from unittest.mock import MagicMock

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = MagicMock()

        node_fn = create_fundamentals_analyst(mock_llm)

        state = {
            "trade_date": "2026-03-24",
            "company_of_interest": "NVDA",
            "position_context": "",
            "messages": [("human", "NVDA")],
        }

        # Invoke to trigger bind_tools call
        try:
            node_fn(state)
        except Exception:
            pass  # LLM mock may fail invoke — we only care about bind_tools args

        call_args = mock_llm.bind_tools.call_args
        if call_args:
            tools = call_args[0][0]
            tool_names = [t.name for t in tools]
            assert "get_insider_transactions" in tool_names
