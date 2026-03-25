from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news,
    get_reddit_sentiment,
    get_stocktwits_sentiment,
    get_reuters_news,
    get_reuters_global_news,
)

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


def create_init_clear():
    """
    Wipes the shared messages list before a parallel analyst branch starts.

    Cannot use RemoveMessage here because the initial HumanMessage passed
    into graph.invoke() is not registered in LangGraph's checkpoint store —
    RemoveMessage raises 'ID does not exist' for it.

    Instead we return a plain list with a single placeholder, which LangGraph
    treats as a full replacement of the messages field (overwrite semantics
    when the value is a list, not an add-reducer operation).
    """
    def init_clear(state):
        return {"messages": [HumanMessage(content="Continue")]}

    return init_clear


        