"""Tests for TICKET-008: parallel analyst fan-out in LangGraph."""

import pytest
from unittest.mock import MagicMock, patch


def _make_graph_setup():
    """Create a GraphSetup instance with fully mocked LLMs and tool nodes."""
    from tradingagents.graph.setup import GraphSetup
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.agents.utils.memory import FinancialSituationMemory

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = MagicMock()

    mock_tool_node = MagicMock()
    tool_nodes = {
        "market":       mock_tool_node,
        "social":       mock_tool_node,
        "news":         mock_tool_node,
        "fundamentals": mock_tool_node,
    }
    mem = FinancialSituationMemory("test")
    cond = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)

    return GraphSetup(
        quick_thinking_llm=mock_llm,
        deep_thinking_llm=mock_llm,
        tool_nodes=tool_nodes,
        bull_memory=mem,
        bear_memory=mem,
        trader_memory=mem,
        invest_judge_memory=mem,
        risk_manager_memory=mem,
        conditional_logic=cond,
    )


class TestParallelAnalysts:

    def test_graph_compiles_with_all_analysts(self):
        """Graph compilation should succeed with all 4 analysts in parallel."""
        gs = _make_graph_setup()
        graph = gs.setup_graph(["market", "social", "news", "fundamentals"])
        assert graph is not None

    def test_graph_compiles_with_single_analyst(self):
        """Graph compilation should work with just one analyst."""
        gs = _make_graph_setup()
        graph = gs.setup_graph(["market"])
        assert graph is not None

    def test_graph_compiles_with_two_analysts(self):
        """Graph compilation should work with any subset."""
        gs = _make_graph_setup()
        graph = gs.setup_graph(["market", "news"])
        assert graph is not None

    def test_sync_node_in_graph_nodes(self):
        """The 'Sync Analysts' node must be present in the compiled graph."""
        gs = _make_graph_setup()
        graph = gs.setup_graph(["market", "social", "news", "fundamentals"])
        # LangGraph compiled graph exposes nodes via .nodes or internal graph attribute
        node_names = list(graph.get_graph().nodes.keys())
        assert "Sync Analysts" in node_names

    def test_raises_with_no_analysts(self):
        """Empty analyst list should raise ValueError."""
        gs = _make_graph_setup()
        with pytest.raises(ValueError, match="no analysts selected"):
            gs.setup_graph([])

    def test_all_analyst_nodes_present(self):
        """All 4 analyst node names should appear in the graph."""
        gs = _make_graph_setup()
        graph = gs.setup_graph(["market", "social", "news", "fundamentals"])
        node_names = list(graph.get_graph().nodes.keys())
        for expected in ["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst"]:
            assert expected in node_names, f"'{expected}' missing from graph nodes"
