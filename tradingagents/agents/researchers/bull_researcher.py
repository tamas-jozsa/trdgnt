def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        round_num = state["investment_debate_state"].get("count", 0) // 2 + 1
        print(f"  [AGENT] 🐂 Bull Researcher      → building bull case (round {round_num})")
        investment_debate_state = state["investment_debate_state"]
        history          = investment_debate_state.get("history", "")
        bull_history     = investment_debate_state.get("bull_history", "")
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

        prompt = f"""You are a Bull Analyst making the case FOR investing in this stock over a 3-30 day swing trading horizon.

Your job is to build a rigorous, evidence-driven bull case using the research below. Be specific: cite actual numbers, price levels, and dates from the reports.

Key responsibilities:
1. **Growth thesis**: Identify the single strongest catalyst for upside in the next 3-30 days. Be specific.
2. **Technical support**: Highlight any bullish technical signals (e.g. RSI recovering from oversold, MACD cross, price above 50 SMA).
3. **Fundamental strength**: Reference revenue growth, FCF yield, or valuation vs sector peers if relevant.
4. **Counter the bear**: Respond directly to the bear's argument with specific data. Do not ignore strong bear points — if a bear point is valid, acknowledge it briefly and explain why it doesn't change the overall thesis.
5. **Conviction score**: End with "Bull conviction: X/10" and one sentence summarising the thesis.

IMPORTANT: If the evidence is genuinely weak, say so. A credible bull case acknowledges real risks. Over-claiming credibility damages your argument.

Research available:
Market analysis: {market_research_report}
Social sentiment: {sentiment_report}
News & macro: {news_report}
Fundamentals: {fundamentals_report}
Debate history: {history}
Bear's last argument: {current_response}
Lessons from similar past situations: {past_memory_str}
"""
        response = llm.invoke(prompt)
        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history":          history + "\n" + argument,
            "bull_history":     bull_history + "\n" + argument,
            "bear_history":     investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count":            investment_debate_state["count"] + 1,
            "judge_decision":   investment_debate_state.get("judge_decision", ""),
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
