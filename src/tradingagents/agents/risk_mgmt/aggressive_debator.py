def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
        round_num = state["risk_debate_state"].get("count", 0) // 3 + 1
        print(f"  [AGENT] ⚡ Risk: Aggressive     → pushing for upside (round {round_num})")
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response      = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report       = state["sentiment_report"]
        news_report            = state["news_report"]
        fundamentals_report    = state["fundamentals_report"]
        trader_decision        = state["trader_investment_plan"]

        prompt = f"""You are the Aggressive Risk Analyst. Your role is to independently evaluate whether the proposed trade offers sufficient upside to justify execution.

You are NOT a cheerleader for the trader's decision. You are an advocate for capturing high-reward opportunities — which sometimes means recommending a MORE aggressive position than proposed, or flagging that the proposed entry is too conservative.

Trader's proposed plan:
{trader_decision}

Your evaluation should:
1. Assess whether the upside target is realistic given the data
2. Identify any catalysts the trader may have underweighted (earnings, macro, momentum)
3. Challenge the conservative analyst's caution with specific data: what is the actual probability-weighted downside vs upside?
4. Express risk in quantitative terms: "If thesis fails, estimated loss is X%. If thesis plays out, estimated gain is Y%."
5. Recommend whether to execute as proposed, increase position size, or modify entry

Market data: {market_research_report}
Sentiment: {sentiment_report}
News: {news_report}
Fundamentals: {fundamentals_report}
Debate so far: {history}
Conservative analyst: {current_conservative_response}
Neutral analyst: {current_neutral_response}

Output conversationally. Be specific with numbers. Do not simply restate the trader's plan."""

        response = llm.invoke(prompt)
        argument = f"Aggressive Analyst: {response.content}"

        new_risk_debate_state = {
            "history":                      history + "\n" + argument,
            "aggressive_history":           aggressive_history + "\n" + argument,
            "conservative_history":         risk_debate_state.get("conservative_history", ""),
            "neutral_history":              risk_debate_state.get("neutral_history", ""),
            "latest_speaker":               "Aggressive",
            "current_aggressive_response":  argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response":     risk_debate_state.get("current_neutral_response", ""),
            "judge_decision":               risk_debate_state.get("judge_decision", ""),
            "count":                        risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
