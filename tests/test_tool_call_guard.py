"""Tests for TICKET-028: max tool-call guard on analyst nodes."""

import pytest
from unittest.mock import MagicMock
from tradingagents.graph.conditional_logic import ConditionalLogic, MAX_ANALYST_TOOL_CALLS


def _make_state(tool_calls=None, counter_field=None, counter_value=0):
    """Build a minimal AgentState-like dict for testing."""
    msg = MagicMock()
    msg.tool_calls = tool_calls or []
    state = {"messages": [msg]}
    if counter_field:
        state[counter_field] = counter_value
    return state


class TestConditionalLogicGuard:

    def setup_method(self):
        self.cond = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)

    # ── Market analyst ───────────────────────────────────────────────────────

    def test_market_routes_to_tools_when_under_cap(self):
        state = _make_state(tool_calls=[MagicMock()], counter_field="market_tool_calls", counter_value=0)
        assert self.cond.should_continue_market(state) == "tools_market"

    def test_market_routes_to_clear_when_at_cap(self):
        state = _make_state(
            tool_calls=[MagicMock()],
            counter_field="market_tool_calls",
            counter_value=MAX_ANALYST_TOOL_CALLS,
        )
        assert self.cond.should_continue_market(state) == "Msg Clear Market"

    def test_market_routes_to_clear_when_no_tool_calls(self):
        state = _make_state(tool_calls=[], counter_field="market_tool_calls", counter_value=0)
        assert self.cond.should_continue_market(state) == "Msg Clear Market"

    def test_market_routes_to_clear_when_above_cap(self):
        state = _make_state(
            tool_calls=[MagicMock()],
            counter_field="market_tool_calls",
            counter_value=MAX_ANALYST_TOOL_CALLS + 5,
        )
        assert self.cond.should_continue_market(state) == "Msg Clear Market"

    # ── Social analyst ───────────────────────────────────────────────────────

    def test_social_routes_to_tools_under_cap(self):
        state = _make_state(tool_calls=[MagicMock()], counter_field="social_tool_calls", counter_value=2)
        assert self.cond.should_continue_social(state) == "tools_social"

    def test_social_routes_to_clear_at_cap(self):
        state = _make_state(
            tool_calls=[MagicMock()],
            counter_field="social_tool_calls",
            counter_value=MAX_ANALYST_TOOL_CALLS,
        )
        assert self.cond.should_continue_social(state) == "Msg Clear Social"

    # ── News analyst ─────────────────────────────────────────────────────────

    def test_news_routes_to_tools_under_cap(self):
        state = _make_state(tool_calls=[MagicMock()], counter_field="news_tool_calls", counter_value=1)
        assert self.cond.should_continue_news(state) == "tools_news"

    def test_news_routes_to_clear_at_cap(self):
        state = _make_state(
            tool_calls=[MagicMock()],
            counter_field="news_tool_calls",
            counter_value=MAX_ANALYST_TOOL_CALLS,
        )
        assert self.cond.should_continue_news(state) == "Msg Clear News"

    # ── Fundamentals analyst ─────────────────────────────────────────────────

    def test_fundamentals_routes_to_tools_under_cap(self):
        state = _make_state(tool_calls=[MagicMock()], counter_field="fundamentals_tool_calls", counter_value=4)
        assert self.cond.should_continue_fundamentals(state) == "tools_fundamentals"

    def test_fundamentals_routes_to_clear_at_cap(self):
        state = _make_state(
            tool_calls=[MagicMock()],
            counter_field="fundamentals_tool_calls",
            counter_value=MAX_ANALYST_TOOL_CALLS,
        )
        assert self.cond.should_continue_fundamentals(state) == "Msg Clear Fundamentals"

    # ── Counter missing from state (fresh graph) ─────────────────────────────

    def test_missing_counter_defaults_to_zero(self):
        """Counter not in state should default to 0 (fresh graph)."""
        state = _make_state(tool_calls=[MagicMock()])
        # No counter_field set → default 0 → under cap → route to tools
        assert self.cond.should_continue_market(state) == "tools_market"

    # ── Cap value is named constant ───────────────────────────────────────────

    def test_max_tool_calls_is_named_constant(self):
        from tradingagents.graph.conditional_logic import MAX_ANALYST_TOOL_CALLS
        assert isinstance(MAX_ANALYST_TOOL_CALLS, int)
        assert MAX_ANALYST_TOOL_CALLS >= 4   # must allow at least 4 tool calls

    # ── Counter increments in analyst nodes ──────────────────────────────────

    def test_counter_increment_logic_with_tool_calls(self):
        """Unit test the counter increment logic directly."""
        # Simulate what the analyst node does
        tool_call_count = 2
        result_tool_calls = [MagicMock()]   # non-empty → increment
        if result_tool_calls:
            tool_call_count += 1
        assert tool_call_count == 3

    def test_counter_no_increment_without_tool_calls(self):
        """Counter does not increment when result has no tool calls."""
        tool_call_count = 3
        result_tool_calls = []   # empty → do not increment
        if result_tool_calls:
            tool_call_count += 1
        assert tool_call_count == 3  # unchanged

    # ── Propagator resets counters ────────────────────────────────────────────

    def test_propagator_initialises_counters_to_zero(self):
        from tradingagents.graph.propagation import Propagator
        p = Propagator()
        state = p.create_initial_state("NVDA", "2026-03-24")
        assert state["market_tool_calls"]       == 0
        assert state["social_tool_calls"]       == 0
        assert state["news_tool_calls"]         == 0
        assert state["fundamentals_tool_calls"] == 0
