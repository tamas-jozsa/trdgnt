from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import get_news, get_global_news
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        if not any(hasattr(m, "tool_calls") and m.tool_calls for m in state.get("messages", [])):
            print(f"  [AGENT] 📰 News Analyst         → headlines, macro news ({ticker})")

        tools = [
            get_news,
            get_global_news,
        ]

        system_message = (
            f"You are a news and macroeconomics analyst focused on the 3-30 day trading horizon. "
            f"Analyse news for {ticker} and the broader macro environment as of {current_date}.\n\n"
            f"REQUIRED STEPS:\n"
            f"1. Call get_news('{ticker}', start_date, end_date) — use last 7 days\n"
            f"2. Call get_global_news('{current_date}', look_back_days=7, limit=20) for macro context\n\n"
            f"Your report MUST cover:\n"
            f"- Any company-specific news in the last 7 days (earnings, contracts, guidance, legal)\n"
            f"- Flag any earnings report due within the next 7 days as a BINARY RISK EVENT\n"
            f"- Macro factors relevant to this sector: Fed/rates, geopolitical risk, sector rotation\n"
            f"- Sentiment shift: has news coverage turned more positive or negative this week vs last?\n"
            f"- Overall news bias: POSITIVE / NEUTRAL / NEGATIVE for this ticker\n\n"
            f"Do NOT make a trade recommendation. Report facts accurately. "
            f"If no relevant news exists, state this clearly.\n\n"
            f"End with a Markdown table of the most important news events and their market implications."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a news analyst. You have access to the following tools: {tool_names}.\n"
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
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        tool_call_count = state.get("news_tool_calls", 0)
        if result.tool_calls:
            tool_call_count += 1

        return {
            "messages": [result],
            "news_report": report,
            "news_tool_calls": tool_call_count,
        }

    return news_analyst_node
