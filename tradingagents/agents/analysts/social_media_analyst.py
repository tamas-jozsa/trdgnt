from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import get_news, get_reddit_sentiment, get_stocktwits_sentiment, get_options_flow, get_short_interest
from tradingagents.dataflows.config import get_config


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        if not any(hasattr(m, "tool_calls") and m.tool_calls for m in state.get("messages", [])):
            print(f"  [AGENT] 💬 Social Analyst       → Reddit, StockTwits ({ticker})")

        tools = [
            get_reddit_sentiment,
            get_stocktwits_sentiment,
            get_options_flow,
            get_short_interest,  # short float % + days to cover = squeeze potential
            get_news,
        ]

        system_message = (
            f"You are a retail sentiment analyst for {ticker} as of {current_date}. "
            f"Your job is to measure what retail investors think RIGHT NOW.\n\n"
            f"REQUIRED STEPS:\n"
            f"1. Call get_reddit_sentiment('{ticker}', days=7) FIRST — includes post bodies and top comments\n"
            f"2. Call get_stocktwits_sentiment('{ticker}') SECOND\n"
            f"3. Call get_options_flow('{ticker}') THIRD — put/call ratio reveals retail conviction\n"
            f"4. Call get_short_interest('{ticker}') FOURTH — needed for squeeze risk assessment\n"
            f"5. Only call get_news if Reddit/StockTwits return empty results\n\n"
            f"Your report MUST state:\n"
            f"- Reddit: total mentions, upvote sentiment, top post titles AND body excerpts\n"
            f"- StockTwits: bullish %, bearish %, total messages\n"
            f"- Options: put/call ratio, any unusual activity, implied volatility\n"
            f"- SHORT SQUEEZE CHECK: if short float ≥15% AND Reddit mention volume rising AND "
            f"  call/put ratio < 0.7 AND days-to-cover ≥5, flag as HIGH SQUEEZE RISK\n"
            f"- Sentiment trend: is retail mood improving or deteriorating vs last week?\n"
            f"- Overall retail sentiment: BULLISH / NEUTRAL / BEARISH\n\n"
            f"Do NOT make a trade recommendation. Report sentiment facts. "
            f"If all sources return empty, state 'No social signal found' clearly.\n\n"
            f"End with a Markdown table of sentiment metrics."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a sentiment analyst. You have access to the following tools: {tool_names}.\n"
                    "{system_message}\n"
                    "Current date: {current_date}. Ticker: {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        system_message = system_message[0] if isinstance(system_message, tuple) else system_message

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

        messages = state["messages"][-20:]
        result = chain.invoke(messages)

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        tool_call_count = state.get("social_tool_calls", 0)
        if result.tool_calls:
            tool_call_count += 1

        return {
            "messages": [result],
            "sentiment_report": report,
            "social_tool_calls": tool_call_count,
        }

    return social_media_analyst_node
