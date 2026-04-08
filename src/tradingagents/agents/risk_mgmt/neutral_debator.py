def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        round_num = state["risk_debate_state"].get("count", 0) // 3 + 1
        print(f"  [AGENT] ⚖️  Risk: Neutral        → balanced view (round {round_num})")
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response  = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report       = state["sentiment_report"]
        news_report            = state["news_report"]
        fundamentals_report    = state["fundamentals_report"]
        trader_decision        = state["trader_investment_plan"]

        prompt = f"""You are the Neutral Risk Analyst. Your role is to stress-test both the aggressive and conservative positions and find the most accurate risk/reward assessment.

You are NOT a compromise machine — you don't split the difference between the other two. You independently evaluate the evidence and identify which analyst is more right and where each is wrong.

Trader's proposed plan:
{trader_decision}

Your evaluation should:
1. Identify the strongest argument from each of the other two analysts
2. Point out where the aggressive analyst is overconfident (with specific evidence)
3. Point out where the conservative analyst is overly cautious (with specific evidence)
4. Provide your own probability-weighted view: "P(bull case) = X%, P(bear case) = Y%"
5. Recommend the appropriate position size and stop-loss given the true risk/reward

Market data: {market_research_report}
Sentiment: {sentiment_report}
News: {news_report}
Fundamentals: {fundamentals_report}
Debate so far: {history}
Aggressive analyst: {current_aggressive_response}
Conservative analyst: {current_conservative_response}

Output conversationally. Use numbers. Your goal is accuracy, not moderation."""

        response = llm.invoke(prompt)
        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history":                       history + "\n" + argument,
            "aggressive_history":            risk_debate_state.get("aggressive_history", ""),
            "conservative_history":          risk_debate_state.get("conservative_history", ""),
            "neutral_history":               neutral_history + "\n" + argument,
            "latest_speaker":                "Neutral",
            "current_aggressive_response":   risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response":      argument,
            "judge_decision":                risk_debate_state.get("judge_decision", ""),
            "count":                         risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
