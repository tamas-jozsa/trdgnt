# TradingAgents/graph/trading_graph.py

import os
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional

from langgraph.prebuilt import ToolNode

from tradingagents.llm_clients import create_llm_client

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.memory import FinancialSituationMemory
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.config import set_config

# Import the new abstract tool methods from agent_utils
from tradingagents.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_transactions,
    get_global_news,
    get_reddit_sentiment,
    get_stocktwits_sentiment,
)

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()
        
        # Initialize memories
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        self.risk_manager_memory = FinancialSituationMemory("risk_manager_memory", self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.risk_manager_memory,
            self.conditional_logic,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(selected_analysts)

    # ------------------------------------------------------------------
    # Memory persistence helpers
    # ------------------------------------------------------------------

    def load_memories(self, memory_dir: str) -> None:
        """Load all 5 agent memories from disk (call once at startup).

        Args:
            memory_dir: Directory containing memory JSON files.
                        Files are named {memory_dir}/{agent_name}.json
        """
        for agent_name, mem in self._memory_map().items():
            mem.load(f"{memory_dir}/{agent_name}.json")

    def save_memories(self, memory_dir: str) -> None:
        """Persist all 5 agent memories to disk (call after each trade).

        Args:
            memory_dir: Directory to write memory JSON files.
        """
        for agent_name, mem in self._memory_map().items():
            mem.save(f"{memory_dir}/{agent_name}.json")

    def _memory_map(self) -> dict:
        return {
            "bull_memory":          self.bull_memory,
            "bear_memory":          self.bear_memory,
            "trader_memory":        self.trader_memory,
            "invest_judge_memory":  self.invest_judge_memory,
            "risk_manager_memory":  self.risk_manager_memory,
        }

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        return kwargs

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # Real social sentiment tools (TICKET-006)
                    get_reddit_sentiment,
                    get_stocktwits_sentiment,
                    # News as supplementary source
                    get_news,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_global_news,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
        }

    def propagate(
        self,
        company_name,
        trade_date,
        position_context: str = "",
        macro_context: str = "",
    ):
        """Run the trading agents graph for a company on a specific date.

        Args:
            company_name:     Ticker symbol / company name.
            trade_date:       Date string (YYYY-MM-DD) to analyse.
            position_context: Formatted string for the current broker position.
            macro_context:    Condensed daily research findings for macro awareness.
        """
        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            position_context=position_context,
            macro_context=macro_context,
        )
        args = self.propagator.get_graph_args()

        # Node labels for progress display
        _STEP_LABELS = {
            "Market Analyst":       "📊 Market Analyst       (price + technicals)",
            "Social Analyst":       "💬 Social Analyst       (Reddit + StockTwits)",
            "News Analyst":         "📰 News Analyst         (headlines + macro)",
            "Fundamentals Analyst": "📋 Fundamentals Analyst (financials + insiders)",
            "Bull Researcher":      "🐂 Bull Researcher      (building bull case)",
            "Bear Researcher":      "🐻 Bear Researcher      (building bear case)",
            "Research Manager":     "🧠 Research Manager     (judging debate)",
            "Trader":               "💼 Trader               (forming plan)",
            "Aggressive Analyst":   "⚡ Risk: Aggressive     (push for upside)",
            "Conservative Analyst": "🛡️  Risk: Conservative   (protect downside)",
            "Neutral Analyst":      "⚖️  Risk: Neutral        (balanced view)",
            "Risk Judge":           "⚖️  Risk Judge           (final decision)",
        }
        _TOOL_LABELS = {
            "tools_market":       "  → fetching price data / indicators",
            "tools_social":       "  → fetching Reddit / StockTwits",
            "tools_news":         "  → fetching news articles",
            "tools_fundamentals": "  → fetching financial statements",
        }

        if self.debug:
            # Debug: print full message content per node
            final_state = None
            for chunk in self.graph.stream(init_agent_state, stream_mode="updates", **args):
                for node_name, node_output in chunk.items():
                    label = _STEP_LABELS.get(node_name) or _TOOL_LABELS.get(node_name)
                    if label:
                        print(f"  [AGENT] {label}")
                    msgs = node_output.get("messages", [])
                    if msgs:
                        msgs[-1].pretty_print()
            final_state = self.graph.invoke(init_agent_state, **args)
        else:
            # Standard: stream_mode="values" yields full accumulated state after
            # every node — gives progress labels without a second LLM invocation.
            final_state = None
            seen_nodes = set()
            for state_snapshot in self.graph.stream(
                init_agent_state, stream_mode="values", **args
            ):
                # Detect which node just ran by checking what changed
                # (stream_mode=values doesn't tell us the node name directly,
                #  so we infer from which report fields became non-empty)
                _field_to_label = {
                    "market_report":       "  [AGENT] 📊 Market Analyst       → done",
                    "sentiment_report":    "  [AGENT] 💬 Social Analyst       → done",
                    "news_report":         "  [AGENT] 📰 News Analyst         → done",
                    "fundamentals_report": "  [AGENT] 📋 Fundamentals Analyst → done",
                    "investment_plan":     "  [AGENT] 🧠 Research Manager     → done",
                    "trader_investment_plan": "  [AGENT] 💼 Trader             → done",
                    "final_trade_decision":   "  [AGENT] ⚖️  Risk Judge         → done",
                }
                for field, label in _field_to_label.items():
                    val = state_snapshot.get(field, "")
                    if val and field not in seen_nodes:
                        seen_nodes.add(field)
                        print(label)
                final_state = state_snapshot

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and processed signal
        return final_state, self.process_signal(final_state["final_trade_decision"])

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_risk_manager(
            self.curr_state, returns_losses, self.risk_manager_memory
        )

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
