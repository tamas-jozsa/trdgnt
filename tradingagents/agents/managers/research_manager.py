def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        print(f"  [AGENT] 🧠 Research Manager     → judging bull vs bear debate")
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")

        # Inject raw analyst reports directly — not just what debaters chose to cite
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

        prompt = f"""You are the Portfolio Manager and final judge of this investment debate. Your job is to make a clear, decisive investment decision for the next 3-30 days.

You have access to the full analyst reports AND the bull/bear debate. Use both — debaters sometimes cherry-pick data; check the raw reports for facts they may have omitted.

RAW ANALYST REPORTS:
--- Market Analysis ---
{market_research_report}

--- Social Sentiment ---
{sentiment_report}

--- News & Macro ---
{news_report}

--- Fundamentals ---
{fundamentals_report}

--- Bull vs Bear Debate ---
{history}

--- Lessons from Similar Past Situations ---
{past_memory_str}

Your output MUST follow this exact format:

RECOMMENDATION: [BUY / SELL / HOLD]
CONVICTION: [1-10]
THESIS: [One sentence — the single strongest reason for your recommendation]
ENTRY: [Suggested entry price or "market price"]
STOP: [Suggested stop-loss price level]
TARGET: [30-day price target]
POSITION SIZE: [0.5x / 1x / 1.5x / 2x relative to base allocation]
RATIONALE: [2-4 sentences explaining why the winning argument prevails over the losing one. Be specific — cite numbers.]

Rules:
- HOLD is valid when evidence is genuinely mixed OR when a major binary event (earnings, FDA) is imminent and risk/reward is unclear.
- Do NOT default to HOLD simply because both sides made valid points. Commit to the stronger argument.
- If past lessons contradict the current thesis, acknowledge this explicitly.
"""
        response = llm.invoke(prompt)

        new_investment_debate_state = {
            "judge_decision":   response.content,
            "history":          investment_debate_state.get("history", ""),
            "bear_history":     investment_debate_state.get("bear_history", ""),
            "bull_history":     investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count":            investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan":         response.content,
        }

    return research_manager_node
