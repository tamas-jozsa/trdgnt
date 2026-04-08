def create_bear_researcher(llm, memory):
    def bear_node(state) -> dict:
        round_num = state["investment_debate_state"].get("count", 0) // 2 + 1
        print(f"  [AGENT] 🐻 Bear Researcher      → building bear case (round {round_num})")
        investment_debate_state = state["investment_debate_state"]
        history          = investment_debate_state.get("history", "")
        bear_history     = investment_debate_state.get("bear_history", "")
        current_response = investment_debate_state.get("current_response", "")

        market_research_report = state["market_report"]
        sentiment_report       = state["sentiment_report"]
        news_report            = state["news_report"]
        fundamentals_report    = state["fundamentals_report"]

        curr_situation = (
            f"{market_research_report}\n\n{sentiment_report}\n\n"
            f"{news_report}\n\n{fundamentals_report}"
        )
        past_memories = memory.get_memories(curr_situation, n_matches=5)
        past_memory_str = "\n\n".join(r["recommendation"] for r in past_memories) if past_memories else ""

        prompt = f"""You are a Bear Analyst making the case AGAINST investing in this stock over a 3-30 day swing trading horizon.

Your job is to build a rigorous, evidence-driven bear case using the research below. Be specific: cite actual numbers, price levels, and dates from the reports.

Key responsibilities:
1. **Primary risk**: Identify the single strongest reason NOT to enter or hold this position right now.
2. **Technical weakness**: Highlight any bearish signals (e.g. RSI overbought, price below 200 SMA, bearish MACD cross, volume declining on rallies).
3. **Valuation or fundamental concern**: Reference overvaluation vs sector, declining FCF, high leverage, or earnings risk if relevant.
4. **Counter the bull**: Respond directly to the bull's argument. Do not ignore strong bull points — if a bull point is valid, acknowledge it briefly and explain why the risk still outweighs it.
5. **Conviction score**: End with "Bear conviction: X/10" and one sentence summarising the risk thesis.

IMPORTANT: If the evidence is genuinely weak for the bear case, say so. A credible bear case acknowledges real upside. Over-claiming damages your argument.

Research available:
Market analysis: {market_research_report}
Social sentiment: {sentiment_report}
News & macro: {news_report}
Fundamentals: {fundamentals_report}
Debate history: {history}
Bull's last argument: {current_response}
Lessons from similar past situations: {past_memory_str}
"""
        response = llm.invoke(prompt)
        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history":          history + "\n" + argument,
            "bear_history":     bear_history + "\n" + argument,
            "bull_history":     investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count":            investment_debate_state["count"] + 1,
            "judge_decision":   investment_debate_state.get("judge_decision", ""),
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
