import functools


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        print(f"  [AGENT] 💼 Trader               → forming trade plan ({company_name})")
        investment_plan = state["investment_plan"]

        market_research_report = state["market_report"]
        sentiment_report       = state["sentiment_report"]
        news_report            = state["news_report"]
        fundamentals_report    = state["fundamentals_report"]

        curr_situation = (
            f"{market_research_report}\n\n{sentiment_report}\n\n"
            f"{news_report}\n\n{fundamentals_report}"
        )
        past_memories = memory.get_memories(curr_situation, n_matches=5)
        past_memory_str = (
            "\n\n".join(r["recommendation"] for r in past_memories)
            if past_memories else "No past memories found."
        )

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a disciplined swing trader making the final trade decision for {company_name}. "
                    f"Your time horizon is 3-30 days. "
                    f"Study the investment plan from the Research Manager and translate it into a concrete trade proposal.\n\n"
                    f"Your proposal MUST include:\n"
                    f"1. Decision: BUY, SELL, or HOLD\n"
                    f"2. Entry: specific price level or 'market'\n"
                    f"3. Stop-loss: specific price level (max 15% below entry for longs)\n"
                    f"4. Target: 30-day price target\n"
                    f"5. Position size: use the sizing from the Research Manager's plan\n"
                    f"6. One-sentence rationale\n\n"
                    f"Always end with: FINAL TRANSACTION PROPOSAL: **BUY** or **SELL** or **HOLD**\n\n"
                    f"Here are lessons from similar past trading situations:\n{past_memory_str}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Investment plan from Research Manager for {company_name}:\n\n"
                    f"{investment_plan}\n\n"
                    f"Based on this plan, provide your trade proposal including entry, stop-loss, and target."
                ),
            },
        ]

        result = llm.invoke(messages)

        return {
            "messages":              [result],
            "trader_investment_plan": result.content,
            "sender":                name,
        }

    return functools.partial(trader_node, name="Trader")
