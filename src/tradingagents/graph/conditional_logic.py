# TradingAgents/graph/conditional_logic.py

from tradingagents.agents.utils.agent_states import AgentState

# Maximum tool-call loop iterations per analyst.
# Prevents runaway loops if the LLM keeps emitting tool calls.
MAX_ANALYST_TOOL_CALLS = 6


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def _should_continue_analyst(
        self,
        state: AgentState,
        tools_node: str,
        clear_node: str,
        counter_field: str,
    ) -> str:
        """Generic continuation check — routes to tools or clear node.

        If the last message has tool calls AND the counter is under the cap,
        route to the tool node. Otherwise route to the clear node (done).
        """
        last_message = state["messages"][-1]
        count = state.get(counter_field, 0)
        if last_message.tool_calls and count < MAX_ANALYST_TOOL_CALLS:
            return tools_node
        if last_message.tool_calls and count >= MAX_ANALYST_TOOL_CALLS:
            print(
                f"  [GUARD] {counter_field} hit max {MAX_ANALYST_TOOL_CALLS} "
                f"tool calls — forcing report"
            )
        return clear_node

    def should_continue_market(self, state: AgentState):
        return self._should_continue_analyst(
            state, "tools_market", "Msg Clear Market", "market_tool_calls"
        )

    def should_continue_social(self, state: AgentState):
        return self._should_continue_analyst(
            state, "tools_social", "Msg Clear Social", "social_tool_calls"
        )

    def should_continue_news(self, state: AgentState):
        return self._should_continue_analyst(
            state, "tools_news", "Msg Clear News", "news_tool_calls"
        )

    def should_continue_fundamentals(self, state: AgentState):
        return self._should_continue_analyst(
            state, "tools_fundamentals", "Msg Clear Fundamentals", "fundamentals_tool_calls"
        )

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # 3 rounds of back-and-forth between 2 agents
            return "Research Manager"
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # 3 rounds of back-and-forth between 3 agents
            return "Risk Judge"
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return "Conservative Analyst"
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return "Neutral Analyst"
        return "Aggressive Analyst"
