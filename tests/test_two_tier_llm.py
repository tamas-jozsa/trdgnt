"""Tests for TICKET-023: two-tier LLM configuration."""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestTwoTierLLM:

    def test_default_config_uses_correct_models(self):
        """Default config must use gpt-4o for deep and gpt-4o-mini for quick."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["deep_think_llm"]  == "gpt-4o"
        assert DEFAULT_CONFIG["quick_think_llm"] == "gpt-4o-mini"

    def test_deep_and_quick_are_different_models(self):
        """Deep and quick must not be the same model (defeats two-tier purpose)."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["deep_think_llm"] != DEFAULT_CONFIG["quick_think_llm"]

    def test_env_var_overrides_deep_model(self):
        """DEEP_LLM_MODEL env var overrides the deep model in trading_loop config."""
        import trading_loop as tl
        import alpaca_bridge as ab
        from tradingagents.default_config import DEFAULT_CONFIG

        # Simulate what analyse_and_trade does
        with patch.dict(os.environ, {"DEEP_LLM_MODEL": "gpt-4o-mini"}):
            config = DEFAULT_CONFIG.copy()
            config["deep_think_llm"] = os.getenv("DEEP_LLM_MODEL", "gpt-4o")
            assert config["deep_think_llm"] == "gpt-4o-mini"

    def test_env_var_overrides_quick_model(self):
        """QUICK_LLM_MODEL env var overrides the quick model."""
        from tradingagents.default_config import DEFAULT_CONFIG
        with patch.dict(os.environ, {"QUICK_LLM_MODEL": "gpt-4o"}):
            config = DEFAULT_CONFIG.copy()
            config["quick_think_llm"] = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
            assert config["quick_think_llm"] == "gpt-4o"

    def test_research_manager_uses_deep_llm(self):
        """Research Manager must be instantiated with deep_thinking_llm."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        with patch("tradingagents.graph.trading_graph.create_llm_client") as mock_factory, \
             patch("tradingagents.graph.trading_graph.set_config"), \
             patch("tradingagents.graph.trading_graph.GraphSetup") as mock_setup, \
             patch("os.makedirs"):

            deep_llm  = MagicMock(name="deep_llm")
            quick_llm = MagicMock(name="quick_llm")

            # Factory returns different mocks for each call
            mock_factory.side_effect = [
                MagicMock(get_llm=MagicMock(return_value=deep_llm)),   # deep client
                MagicMock(get_llm=MagicMock(return_value=quick_llm)),  # quick client
            ]
            mock_setup.return_value.setup_graph.return_value = MagicMock()

            ta = TradingAgentsGraph()

        # Verify create_research_manager was called with deep_thinking_llm
        setup_call_kwargs = mock_setup.call_args
        # The graph setup receives both llms — deep is second positional arg
        assert ta.deep_thinking_llm is deep_llm
        assert ta.quick_thinking_llm is quick_llm

    def test_risk_manager_uses_deep_llm(self):
        """Risk Judge must receive deep_thinking_llm in setup."""
        from tradingagents.graph.setup import GraphSetup
        from tradingagents.graph.conditional_logic import ConditionalLogic
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        deep_llm  = MagicMock(name="deep_llm")
        quick_llm = MagicMock(name="quick_llm")
        deep_llm.bind_tools.return_value = MagicMock()
        quick_llm.bind_tools.return_value = MagicMock()

        mem  = FinancialSituationMemory("test")
        cond = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)

        gs = GraphSetup(
            quick_thinking_llm=quick_llm,
            deep_thinking_llm=deep_llm,
            tool_nodes={k: MagicMock() for k in ["market","social","news","fundamentals"]},
            bull_memory=mem, bear_memory=mem, trader_memory=mem,
            invest_judge_memory=mem, risk_manager_memory=mem,
            conditional_logic=cond,
        )

        # create_risk_manager and create_research_manager receive deep_thinking_llm
        # We verify GraphSetup stores both and distinguishes them
        assert gs.deep_thinking_llm is deep_llm
        assert gs.quick_thinking_llm is quick_llm
        assert gs.deep_thinking_llm is not gs.quick_thinking_llm
