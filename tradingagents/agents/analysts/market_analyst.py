from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import get_stock_data, get_indicators
from tradingagents.dataflows.config import get_config


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        if not any(hasattr(m, "tool_calls") and m.tool_calls for m in state.get("messages", [])):
            print(f"  [AGENT] 📊 Market Analyst       → price data, technicals ({ticker})")

        tools = [
            get_stock_data,
            get_indicators,
        ]

        system_message = (
            f"You are a swing trading market analyst focused on the 3-30 day trading horizon. "
            f"Analyse the last 90 days of price and volume data for {ticker} as of {current_date}.\n\n"
            f"REQUIRED STEPS:\n"
            f"1. Call get_stock_data first to fetch the price CSV\n"
            f"2. Call get_indicators with these 10 indicators: "
            f"close_50_sma, close_200_sma, close_10_ema, macd, macds, rsi, atr, vwma, boll_lb, mfi\n"
            f"3. Write your report using the data returned\n\n"
            f"Your report MUST explicitly state:\n"
            f"- Current price vs 50 SMA and 200 SMA (above/below and by how much)\n"
            f"- RSI value and interpretation (below 35 = potentially oversold, above 65 = potentially overbought)\n"
            f"- MFI (Money Flow Index): below 20 = oversold with volume confirmation, above 80 = overbought with volume\n"
            f"- Bollinger Band lower (boll_lb): if price is at or below the lower band, flag as potential reversal entry\n"
            f"- MACD line vs signal line (bullish cross / bearish cross / neutral)\n"
            f"- ATR value — use this to suggest a stop-loss distance (1.5-2× ATR below entry)\n"
            f"- Volume trend: is today's volume above or below the 20-day average?\n"
            f"- Overall technical bias: BULLISH / NEUTRAL / BEARISH with specific reasoning\n\n"
            f"Do NOT make a trade recommendation — that is the job of the debate team. "
            f"Your job is to report the technical facts accurately.\n\n"
            f"End with a Markdown table summarising key indicator values and their signals."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a market analyst. You have access to the following tools: {tool_names}.\n"
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
            system_message += f"\n\n⚠️ IMPORTANT — {position_context}. Factor this into your analysis: consider whether the thesis still supports the existing position, or if the position should be reduced or exited."

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)

        messages = state["messages"][-20:]
        result = chain.invoke(messages)

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        # Increment tool-call counter for the guard in conditional_logic
        tool_call_count = state.get("market_tool_calls", 0)
        if result.tool_calls:
            tool_call_count += 1

        return {
            "messages": [result],
            "market_report": report,
            "market_tool_calls": tool_call_count,
        }

    return market_analyst_node
