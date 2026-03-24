from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import get_news, get_reddit_sentiment, get_stocktwits_sentiment
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
            get_news,
        ]

        system_message = (
            "You are a social media sentiment analyst tasked with analyzing real-time retail investor sentiment for a specific company. "
            "Your primary tools are:\n"
            "1. get_reddit_sentiment(ticker, days) — searches r/wallstreetbets, r/stocks, r/investing, r/options for posts mentioning the ticker. Call this FIRST.\n"
            "2. get_stocktwits_sentiment(ticker) — fetches the StockTwits message stream with bullish/bearish breakdown. Call this SECOND.\n"
            "3. get_news(query, start_date, end_date) — search for recent company-specific news as supplementary context.\n\n"
            "Write a comprehensive report covering: Reddit mention volume and sentiment, StockTwits bullish/bearish ratio, top posts and what retail investors are saying, "
            "any meme stock setups or short squeeze narratives, and how social sentiment aligns or conflicts with the fundamental outlook. "
            "If Reddit or StockTwits return empty results, note this clearly and rely on news data instead. "
            "Do not simply state the trends are mixed — provide detailed, actionable insights for traders."
            "\n\nMake sure to append a Markdown table at the end organising key sentiment metrics."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. The current company we want to analyze is {ticker}",
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

        result = chain.invoke(state["messages"])

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
