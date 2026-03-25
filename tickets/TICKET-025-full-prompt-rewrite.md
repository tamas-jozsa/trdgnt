# TICKET-025 — Full Agent Prompt Rewrite

**Priority:** HIGH
**Effort:** 3-4h
**Status:** DONE

## Problem

TICKET-019 was written but never implemented. All 12 agent prompts still have:
- Wrong outer boilerplate ("FINAL TRANSACTION PROPOSAL" on non-trader agents)
- Missing trading frameworks (no valuation, no timeframe, no stop-loss instruction)
- Typo: "situatiosn" in trader.py (live in production)
- News analyst has a one-sentence instruction
- Fundamentals analyst says "over the past week" (balance sheets are quarterly)
- Research Manager never sees raw analyst reports — only debate transcript
- Risk debaters defend the trader's decision rather than independently evaluate it
- n_matches=2 hardcoded on all memory retrievals (too few learned lessons)

## Changes Per Agent

### Outer wrapper (all 4 analysts)
- **Remove** "FINAL TRANSACTION PROPOSAL: BUY/HOLD/SELL" boilerplate entirely —
  analysts write reports, they don't make trade decisions

### Market Analyst
- Add: "You are analysing a **swing trading opportunity** with a 3-30 day horizon"
- Add: "Use the last 90 days of price data"
- Require explicitly: RSI, MACD, 50 SMA, 200 SMA, ATR, volume vs 20-day avg
- Add: "If RSI < 35 note as potentially oversold. If RSI > 70 note as overbought"
- Add fallback: if report is empty string, return a warning placeholder

### Social Analyst  
- Already improved in TICKET-006 — verify tool list is correct
- Add: "Note any short squeeze setup: short float >15%, rising volume, Reddit mentions"

### News Analyst
- Expand from 1 sentence to structured instruction
- Require BOTH tools: `get_news(ticker, ...)` AND `get_global_news(date, 7, 20)`
- Specify topics: Fed/rates, earnings calendar, geopolitical risk, sector rotation
- Add: "Note any earnings report within the next 7 days as a binary risk event"

### Fundamentals Analyst
- Fix "over the past week" → "using the most recent available quarterly/annual data"
- Add valuation framework:
  - P/E vs sector median (flag if >2x sector median as expensive)
  - EV/EBITDA
  - Free Cash Flow yield
  - Debt/Equity ratio (flag if >2.0 as high leverage)
- Add: "Insider buying >$100k in last 30 days = HIGH SIGNAL — highlight prominently"
- Change call order: get_fundamentals first, then specific statements as needed

### Bull Researcher
- Add: "If the evidence overwhelmingly contradicts your bull case, concede those
  specific points — a credible advocate acknowledges weaknesses"
- Add: "State your conviction score 1-10 and a one-line thesis at the end"
- Add: "Focus on the 3-30 day trading horizon, not multi-year investment thesis"

### Bear Researcher
- Same concession instruction as Bull
- Same conviction score requirement
- Same timeframe instruction

### Research Manager
- **Inject raw analyst reports** directly into the prompt (not just debate history):
  ```
  MARKET REPORT: {market_report}
  SENTIMENT REPORT: {sentiment_report}
  NEWS REPORT: {news_report}
  FUNDAMENTALS REPORT: {fundamentals_report}
  ```
- Add structured output requirement:
  ```
  RECOMMENDATION: BUY / SELL / HOLD
  CONVICTION: 1-10
  THESIS: [one sentence]
  ENTRY: [price or "market"]
  STOP: [stop-loss price]
  TARGET: [30-day price target]
  POSITION SIZE: [0.5x / 1x / 1.5x / 2x base amount]
  ```
- Remove "Present conversationally without special formatting"

### Trader
- Fix typo: "situatiosn" → "situations"
- Fix grammar: "Here is some reflections" → "Here are some reflections"
- Add: "Include a specific stop-loss level and 30-day price target"
- Add: "Use the position sizing from the Research Manager's plan"

### Risk Debaters (Aggressive / Conservative / Neutral)
- Change from "create a compelling case for the trader's decision" →
  "independently evaluate whether the proposed trade is sound given the evidence"
- Add: "Express your risk assessment in quantitative terms: estimated % loss
  if thesis fails, probability of thesis playing out"
- Remove explicit anti-Hold bias from Conservative prompt

### Risk Manager
- Verify it reads `trader_investment_plan` not `investment_plan`
- Add structured output matching Research Manager format
- Add: "HOLD is a valid and often correct answer — do not force a direction
  when evidence is mixed or thin"

### Memory retrieval (all 5 agents)
- Change `n_matches=2` → `n_matches=5` to retrieve more learned lessons

## Acceptance Criteria
- [ ] No analyst prompt contains "FINAL TRANSACTION PROPOSAL"
- [ ] Trader prompt has zero typos
- [ ] News analyst prompt has multi-paragraph structured instruction
- [ ] Fundamentals analyst prompt has valuation framework section
- [ ] Research Manager prompt injects all 4 raw analyst reports
- [ ] Research Manager output has RECOMMENDATION/CONVICTION/ENTRY/STOP/TARGET
- [ ] Bull/Bear researchers can concede points
- [ ] Risk debaters evaluate independently, not defensively
- [ ] All memory retrievals use n_matches=5
- [ ] All 115 tests still pass
