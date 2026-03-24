def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        round_num = state["risk_debate_state"].get("count", 0) // 3 + 1
        print(f"  [AGENT] 🛡️  Risk: Conservative   → protecting downside (round {round_num})")
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response    = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report       = state["sentiment_report"]
        news_report            = state["news_report"]
        fundamentals_report    = state["fundamentals_report"]
        trader_decision        = state["trader_investment_plan"]

        prompt = f"""You are the Conservative Risk Analyst. Your role is to independently evaluate whether the proposed trade exposes the portfolio to unacceptable downside risk.

You are NOT a pessimist who always says no. You are a risk guardian — your job is to ensure the stop-loss is appropriate, position size is justified, and the downside scenario is understood.

Trader's proposed plan:
{trader_decision}

Your evaluation should:
1. Identify the single biggest risk to this trade that the trader may have underweighted
2. Verify the stop-loss is reasonable: is it above key support? Is it tight enough to limit damage?
3. Challenge the aggressive analyst's probability estimates with specific counter-evidence
4. Express risk in quantitative terms: "The maximum loss at proposed stop is X%. Is this acceptable given the portfolio?"
5. Recommend: execute as proposed, reduce position size, tighten stop, or hold off

Market data: {market_research_report}
Sentiment: {sentiment_report}
News: {news_report}
Fundamentals: {fundamentals_report}
Debate so far: {history}
Aggressive analyst: {current_aggressive_response}
Neutral analyst: {current_neutral_response}

Output conversationally. Be specific with numbers. HOLD is a valid recommendation if risk/reward is genuinely poor."""

        response = llm.invoke(prompt)
        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history":                       history + "\n" + argument,
            "aggressive_history":            risk_debate_state.get("aggressive_history", ""),
            "conservative_history":          conservative_history + "\n" + argument,
            "neutral_history":               risk_debate_state.get("neutral_history", ""),
            "latest_speaker":                "Conservative",
            "current_aggressive_response":   risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": argument,
            "current_neutral_response":      risk_debate_state.get("current_neutral_response", ""),
            "judge_decision":                risk_debate_state.get("judge_decision", ""),
            "count":                         risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
