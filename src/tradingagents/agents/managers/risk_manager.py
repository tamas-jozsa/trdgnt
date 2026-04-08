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

        # TICKET-057: Get portfolio context if available
        portfolio_context_dict = state.get("portfolio_context", {})
        portfolio_context = ""
        if portfolio_context_dict:
            cash_ratio = portfolio_context_dict.get("cash_ratio", 0)
            pos_count = portfolio_context_dict.get("position_count", 0)
            portfolio_context = f"""PORTFOLIO CONTEXT:
- Cash ratio: {cash_ratio:.1%}
- Open positions: {pos_count}
"""
            if cash_ratio > 0.80:
                portfolio_context += "- CAPITAL DEPLOYMENT ALERT: Portfolio is >80% cash. Bias toward executing high-conviction opportunities.\n"
            portfolio_context += "[/PORTFOLIO CONTEXT]"

        # TICKET-060: Get research signal for this ticker
        research_signal = ""
        if company_name:
            from tradingagents.research_context import build_research_signal_prompt
            research_signal = build_research_signal_prompt(company_name)

        # TICKET-065: Get sector context
        sector_context = ""
        if company_name:
            from tradingagents.research_context import build_sector_context
            sector_context = build_sector_context(company_name)

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

{research_signal}

{sector_context}

LESSONS FROM PAST SIMILAR SITUATIONS:
{past_memory_str}

{portfolio_context}

Decision rules:
1. Pick the position that offers the best risk-adjusted return given the debate evidence
2. HOLD is correct when: evidence is genuinely mixed, a binary event is within 7 days, or the stop-loss cannot be placed cleanly
3. Do NOT force BUY or SELL when the data is thin — a wrong trade is worse than no trade
4. If past lessons warn against this type of setup, weight them heavily

OVERRIDE RULES (CRITICAL — your decision will be audited):
- Earnings avoidance: ONLY avoid if earnings are within 7 calendar days. Earnings 8+ days away is NOT a valid reason to HOLD.
- High conviction respect: If Research Manager conviction >= 7 and Trader agrees BUY, you MUST execute UNLESS 2 of 3 risk debaters provide SPECIFIC, DATA-BACKED reasons against (not just "volatility" or "general risk").
- Capital deployment: When portfolio cash > 80%, you are FAILING if you output HOLD on high-conviction setups. The cost of missing a good trade at 94% cash exceeds the cost of a bad entry. EXECUTE unless there is a concrete, imminent risk.
- The Conservative Analyst often cites "upcoming earnings" or "proximity to support" as generic reasons to HOLD. These are NOT sufficient when cash > 80% and conviction >= 7.
- If you override a strong BUY/SELL signal with HOLD, you MUST state: "OVERRIDE REASON: [specific, falsifiable reason]"
- Vague override reasons like "volatility risk" or "market uncertainty" are NOT acceptable.

SECTOR RULES (TICKET-065):
- If a sector is marked AVOIDED, require higher conviction to BUY (conviction ≥ 7) or consider SELLing existing positions
- If a sector is marked FAVORED, bias toward deploying capital on setups in this sector
- Never exceed 40% portfolio exposure to any single sector

Your output MUST follow this exact format:

FINAL DECISION: [BUY / SELL / HOLD]
CONVICTION: [1-10]
ENTRY: [price or "market"]
STOP-LOSS: [specific price]
TARGET: [30-day price target]
POSITION SIZE: [0.5x / 1x / 1.5x / 2x base allocation]
REASONING: [3-5 sentences. Which analyst made the strongest point? What past lesson is most relevant? Why does risk/reward justify this decision?]

TARGET rules:
- TARGET must be YOUR OWN 30-day price estimate — NOT the Wall St analyst consensus target.
- Anchor to a meaningful technical level reachable in 30 days (resistance, Bollinger upper, 50-day SMA).
- Realistic range: 5-20% from current price unless earnings are within 7 days.
- Do NOT copy the analyst mean/high price target.

CRITICAL — stop and target MUST be directionally consistent with your decision:
- BUY:  STOP-LOSS must be BELOW current price (downside exit).
         TARGET must be ABOVE current price (upside objective).
- SELL: STOP-LOSS must be ABOVE current price (cover trigger if wrong).
         TARGET must be BELOW current price (profit-take level).
- HOLD: STOP-LOSS must be BELOW current price (level at which you would exit a long).
         TARGET must be ABOVE current price (level at which the upside thesis is confirmed).
If you are overruling a SELL to HOLD or a BUY to HOLD, recalculate stop and target
from scratch for the HOLD decision. Do NOT inherit them from the prior SELL/BUY proposal.

The last line of your response must be exactly one of:
FINAL DECISION: **BUY**
FINAL DECISION: **SELL**
FINAL DECISION: **HOLD**
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
