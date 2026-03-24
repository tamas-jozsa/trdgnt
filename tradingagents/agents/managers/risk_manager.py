def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:
        company_name = state["company_of_interest"]
        print(f"  [AGENT] 🏛️  Risk Judge           → final decision ({company_name})")

        history           = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        trader_plan       = state["trader_investment_plan"]

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

        prompt = f"""You are the Risk Judge making the final, binding trading decision for {company_name}.

You have reviewed the trader's plan and a three-way risk debate. Your job is to make a clear, actionable decision.

TRADER'S PLAN:
{trader_plan}

RISK DEBATE:
{history}

LESSONS FROM PAST SIMILAR SITUATIONS:
{past_memory_str}

Decision rules:
1. Pick the position that offers the best risk-adjusted return given the debate evidence
2. HOLD is correct when: evidence is genuinely mixed, a binary event is imminent, or the stop-loss cannot be placed cleanly
3. Do NOT force BUY or SELL when the data is thin — a wrong trade is worse than no trade
4. If past lessons warn against this type of setup, weight them heavily

Your output MUST follow this exact format:

FINAL DECISION: [BUY / SELL / HOLD]
CONVICTION: [1-10]
ENTRY: [price or "market"]
STOP-LOSS: [specific price — if BUY, this is the max loss level; if SELL, the cover level]
TARGET: [30-day price target]
POSITION SIZE: [0.5x / 1x / 1.5x / 2x base allocation]
REASONING: [3-5 sentences. Which analyst made the strongest point? What past lesson is most relevant? Why does risk/reward justify this decision?]

FINAL TRANSACTION PROPOSAL: **[BUY / SELL / HOLD]**
"""
        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision":                response.content,
            "history":                       risk_debate_state["history"],
            "aggressive_history":            risk_debate_state.get("aggressive_history", ""),
            "conservative_history":          risk_debate_state.get("conservative_history", ""),
            "neutral_history":               risk_debate_state.get("neutral_history", ""),
            "latest_speaker":                "Judge",
            "current_aggressive_response":   risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response":      risk_debate_state.get("current_neutral_response", ""),
            "count":                         risk_debate_state["count"],
        }

        return {
            "risk_debate_state":   new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return risk_manager_node
