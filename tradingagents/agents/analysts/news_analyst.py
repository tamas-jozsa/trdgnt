from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_news, get_global_news, get_reuters_news, get_reuters_global_news
)
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        if not any(hasattr(m, "tool_calls") and m.tool_calls for m in state.get("messages", [])):
            print(f"  [AGENT] 📰 News Analyst         → Reuters + Yahoo news ({ticker})")

        tools = [
            get_reuters_news,        # Reuters sitemap — primary, highest quality, hourly updates
            get_reuters_global_news, # Reuters macro context
            get_news,                # Yahoo Finance — company-specific fallback
            get_global_news,         # Yahoo Finance global macro fallback
        ]

        system_message = (
            f"You are a news and macroeconomics analyst focused on the 3-30 day trading horizon. "
            f"Analyse news for {ticker} and the broader macro environment as of {current_date}.\n\n"
            f"REQUIRED STEPS (in order):\n"
            f"1. Call get_reuters_news('{ticker}', hours_back=48) FIRST — Reuters is the gold standard "
            f"   for breaking news and tags articles with stock tickers precisely\n"
            f"2. Call get_reuters_global_news(hours_back=24, limit=25) for macro context\n"
            f"3. If Reuters returns empty for {ticker}, call get_news('{ticker}', start_date, end_date) "
            f"   as a fallback — use last 7 days\n"
            f"4. Optionally call get_global_news for additional macro context\n\n"
            f"Your report MUST cover:\n"
            f"- Any Reuters-tagged headlines for {ticker} (Reuters-tagged = high precision)\n"
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
        messages = state["messages"][-20:]
        result = chain.invoke(messages)

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
