# TICKET-019 — Full Agent Prompt Rewrite

**Priority:** HIGH
**Effort:** 3-4h
**Status:** DONE

## Problem

All 12 agent prompts have issues ranging from wrong boilerplate, missing trading
frameworks, typos, and impossible instructions. This is the highest-ROI improvement
in the entire system — better prompts directly improve trade decision quality.

## Changes Per Agent

### Market Analyst
- Remove wrong "FINAL TRANSACTION PROPOSAL" boilerplate from outer wrapper
- Add explicit 90-day lookback instruction
- Specify swing trading timeframe (3-30 day horizon)
- Require: RSI, MACD, volume ratio vs 20-day avg, 50/200 SMA position, ATR
- Fix silent failure: if report is empty, write a fallback warning string

### Social Analyst
- Fix `get_news` parameter name: "query" → "ticker" in description
- Add `days=7` explicit instruction
- Remove impossible "compare to fundamental outlook" instruction
- Strengthen position context handling

### News Analyst
- Expand from 1 sentence to structured multi-part instruction
- Require both `get_news` AND `get_global_news` explicitly
- Specify macro topics: Fed/rates, earnings calendar, geopolitical, sector rotation
- Set `look_back_days=7`, `limit=20` in the tool call instructions

### Fundamentals Analyst
- Fix "over the past week" → "most recent available quarter/annual"
- Add valuation framework: P/E vs sector median, EV/EBITDA, FCF yield, D/E ratio
- Add explicit call order: get_fundamentals first, then targeted statements
- Add: flag any insider buying >$100k in last 30 days as a HIGH SIGNAL

### Bull / Bear Researchers
- Add: "If evidence overwhelmingly contradicts your position, concede those
  specific points explicitly rather than ignoring them — this makes your
  remaining arguments more credible"
- Add timeframe: "Your analysis covers a 3-30 day trading horizon"
- Add: "Conclude with a specific conviction score 1-10 and a one-line thesis"

### Research Manager
- Inject raw analyst reports directly into prompt (not just debate history)
- Add structured output format:
  RECOMMENDATION: BUY/SELL/HOLD
  CONVICTION: 1-10
  THESIS: one sentence
  ENTRY: suggested price range or "market"
  STOP: suggested stop-loss level
  TARGET: 30-day price target
  POSITION SIZE: % of base allocation (0.5x / 1x / 1.5x / 2x)
- Remove "Present conversationally without special formatting" (works against structure)

### Trader
- Fix typo: "situatiosn" → "situations"
- Fix grammar: "Here is some reflections" → "Here are some reflections"
- Add position sizing instruction: "Express your trade in dollar terms using the
  position sizing from the research manager's plan"
- Add: "Include a stop-loss level and a 30-day price target in your proposal"

### Risk Debaters (Aggressive / Conservative / Neutral)
- Change from "defend the trader's decision" → "independently evaluate whether
  the proposed trade is sound given the evidence"
- Remove "create a compelling case for the trader's decision"
- Add quantitative framing: "Express risk as % of position that could be lost
  if the thesis fails"
- Remove anti-Hold language where present

### Risk Manager
- Fix: reads `trader_investment_plan` not `investment_plan`
- Fix: bold-wrapping of empty memory `**{past_memory_str}**`
- Add structured final output format matching research manager's format
- Add: "If the analysts' evidence is mixed or thin, HOLD is a valid answer —
  do not force a direction"

## Acceptance Criteria
- [ ] No agent prompt contains "FINAL TRANSACTION PROPOSAL" except the Trader
- [ ] Market analyst prompt specifies 90-day lookback and swing trading timeframe
- [ ] Fundamentals analyst prompt has a valuation framework section
- [ ] Bull/Bear researchers can concede points
- [ ] Research manager receives raw analyst reports in its prompt
- [ ] Research manager produces structured output with ENTRY/STOP/TARGET fields
- [ ] Trader prompt has no typos or grammar errors
- [ ] Risk debaters independently evaluate rather than defend
- [ ] Risk manager reads the correct state field
- [ ] All dead variables and dead imports removed from all 12 agent files
- [ ] All 88 tests still pass
