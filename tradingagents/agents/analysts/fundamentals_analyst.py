from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_fundamentals, get_balance_sheet, get_cashflow,
    get_income_statement, get_insider_transactions, get_analyst_targets,
)
from tradingagents.dataflows.config import get_config


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        if not any(hasattr(m, "tool_calls") and m.tool_calls for m in state.get("messages", [])):
            print(f"  [AGENT] 📋 Fundamentals Analyst → financials, insiders ({ticker})")

        tools = [
            get_fundamentals,
            get_income_statement,
            get_cashflow,
            get_analyst_targets,      # Wall Street consensus — external valuation anchor
            get_insider_transactions,
            get_balance_sheet,        # only if leverage/liquidity concern
        ]

        system_message = (
            f"You are a fundamental analyst evaluating {ticker} as of {current_date}. "
            f"Use the most recent available quarterly and annual data — NOT 'past week' data (financials are quarterly).\n\n"
            f"REQUIRED STEPS:\n"
            f"1. Call get_fundamentals first for the overview\n"
            f"2. Call get_income_statement for revenue/earnings trends\n"
            f"3. Call get_cashflow for FCF analysis\n"
            f"4. Call get_analyst_targets — Wall Street consensus is an external valuation anchor\n"
            f"5. Call get_insider_transactions for recent insider activity\n"
            f"6. Call get_balance_sheet only if leverage or liquidity is a concern\n\n"
            f"Your report MUST include this valuation framework:\n"
            f"- P/E ratio vs sector median (flag if >2x sector median as expensive)\n"
            f"- EV/EBITDA vs peers\n"
            f"- Free Cash Flow yield (FCF / market cap) — flag if <2% as low\n"
            f"- Debt/Equity ratio — flag if >2.0 as high leverage\n"
            f"- Revenue growth (YoY) — is growth accelerating or decelerating?\n"
            f"- Analyst consensus: mean price target vs current price, upside %, recommendation\n\n"
            f"INSIDER TRANSACTIONS: If any insider bought >$100k in the last 30 days, "
            f"flag this as a HIGH SIGNAL — insiders rarely buy unless confident.\n\n"
            f"ANALYST TARGETS: If current price is already above the analyst mean target, "
            f"flag as potentially OVERVALUED vs consensus. If >30% upside to mean, flag as UNDERVALUED.\n\n"
            f"Do NOT make a trade recommendation. Report the fundamental facts. "
            f"State clearly whether the stock appears fundamentally CHEAP / FAIR / EXPENSIVE vs peers.\n\n"
            f"End with a Markdown table of key valuation and financial metrics."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a fundamental analyst. You have access to the following tools: {tool_names}.\n"
                    "{system_message}\n"
                    "Current date: {current_date}. Ticker: {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        macro_context = state.get("macro_context", "")
        if macro_context:
            system_message += f"\n\n{macro_context}"

        position_context = state.get("position_context", "")
        if position_context:
            system_message += f"\n\n⚠️ IMPORTANT — {position_context}. Factor this into your analysis."

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)

        # Trim messages to last 20 to prevent request body overflow.
        # Each tool call adds ~2-10KB of financial data; 6 calls × 5 tools
        # can push the payload beyond OpenAI's ~4MB request limit.
        # Always keep a complete conversation (no dangling tool_calls).
        messages = state["messages"][-20:]
        result = chain.invoke(messages)

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        tool_call_count = state.get("fundamentals_tool_calls", 0)
        if result.tool_calls:
            tool_call_count += 1

        return {
            "messages": [result],
            "fundamentals_report": report,
            "fundamentals_tool_calls": tool_call_count,
        }

    return fundamentals_analyst_node
