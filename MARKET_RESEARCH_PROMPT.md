run `positions` command to sync live positions from your broker

# Market Research Prompt

Use this prompt when asking an AI assistant (OpenCode, Claude, ChatGPT, etc.)
to do a deep market research session and update the trading watchlist.

---

## HOW TO USE

1. Copy everything from the `---BEGIN PROMPT---` line to the end of this file
2. Paste it into your AI assistant chat
3. The assistant will research current market conditions and return an updated watchlist
4. Paste the updated watchlist back here or ask it to update `trading_loop.py` directly

---BEGIN PROMPT---

You are a quantitative research analyst and aggressive momentum trader helping me maintain a
macro-aware, alpha-seeking stock watchlist for an automated paper trading system.

The system runs daily after US market close, analyses each ticker using a multi-agent LLM
framework (TradingAgents), and executes paper trades on Alpaca Markets.

Your job today is to conduct a **full deep-dive market research session** across every available
source, find the highest-conviction plays for the next 1-30 days, and identify both:
- **Core holds**: high-conviction, thesis-driven, lower-volatility plays
- **High-risk/high-reward opportunities**: momentum plays, short squeezes, meme stocks, biotech
  binary events, macro catalysts — where 50-300%+ moves are possible in days/weeks

Be aggressive. Be thorough. Think like a hedge fund PM running a multi-strategy book.

---

## CURRENT OPEN POSITIONS

> This section is auto-updated by `update_positions.py`. Last updated: see positions.json

<!-- POSITIONS_PLACEHOLDER -->
_Last updated: 2026-03-24T00:06:26.839768Z_

**Portfolio:** Equity $100,000.00 | Cash $100,000.00 | Buying Power $199,004.55

**No open positions. Portfolio is 100% cash.**
<!-- /POSITIONS_PLACEHOLDER -->

---

## CURRENT WATCHLIST

These are the tickers currently being analysed daily. Evaluate each one — should any
be removed, added to, or replaced given today's market conditions?

| Ticker | Sector | Reason Added |
|--------|--------|-------------|
| NVDA   | AI & Semiconductors   | GPU monopoly for AI training |
| AVGO   | AI & Semiconductors   | Custom AI chips, networking ASICs |
| AMD    | AI & Semiconductors   | GPU #2, datacenter CPUs |
| ARM    | AI & Semiconductors   | CPU architecture licensing, edge AI |
| TSM    | AI & Semiconductors   | Fabricates all leading-edge chips (ADR) |
| MU     | AI & Semiconductors   | Wedbush: AI memory prices up 100%+ |
| LITE   | AI Photonics          | BNP PT $1000; Nvidia/Google transceiver wins |
| MSFT   | AI Software & Cloud   | Azure + OpenAI partnership |
| GOOGL  | AI Software & Cloud   | Gemini, TPUs, cloud |
| META   | AI Software & Cloud   | Massive AI infra spend, ad targeting |
| PLTR   | AI Software & Cloud   | Wedbush: Maven AI federal program of record |
| BIP    | AI Infrastructure     | Morgan Stanley upgrade: leading DC developer |
| MDB    | AI Infrastructure     | Mizuho upgrade: database layer for AI apps |
| CRM    | Productivity SaaS     | Salesforce AI agents, hiring freeze winner |
| NOW    | Productivity SaaS     | ServiceNow workflow automation |
| PANW   | Cybersecurity         | Iran war winner + agentic AI browser launch |
| CRWD   | Cybersecurity         | Iran war winner, endpoint security leader |
| RTX    | Defense               | Missiles, radar, Patriot systems |
| LMT    | Defense               | F-35, hypersonics, space |
| NOC    | Defense               | B-21 bomber, space systems |
| LNG    | LNG / Energy          | Morgan Stanley Buy; structural LNG story |
| VG     | LNG / Energy          | Morgan Stanley Buy + Vitol 5yr deal |
| XOM    | Energy Hedge          | Largest US oil major, geopolitical hedge |
| FCX    | Copper / Materials    | AI data centers + defense copper demand |
| MP     | Rare Earths           | Only US rare earth producer; defense magnets |
| UBER   | Mobility / AV         | Citi: AV facilitator thesis |
| GLD    | Gold / Macro Hedge    | Safe haven, geopolitical volatility buffer |

---

## MACRO CONTEXT (update this section with current conditions)

**Last updated:** March 24, 2026

**Active themes:**
- AI capex supercycle — hyperscalers spending $500B+ on AI infrastructure
- Hiring freezes across tech — productivity/agentic AI software wins
- US/Iran tensions ("Operation Epic Fury") — defense, cyber, satellite bid
- Iran de-escalation risk — Trump announced talks March 23, oil dropped -8.91%
- LNG structural demand — Europe/Asia diversifying away from Middle East energy
- Rising oil prices (WTI >$100/bbl during conflict, pulled back on talk of talks)
- Market volatility driven by Reuters, X/Twitter news flow

**Sectors to avoid:**
- Airlines / transport logistics (oil price exposure)
- Staffing agencies (hiring freeze secular headwind)
- Commercial real estate (remote work + rate sensitivity)
- Pure China-facing consumer (US-China tension + tariff risk)

---

## YOUR RESEARCH TASKS

You will execute all of the following research tasks in a single session. Be systematic,
be exhaustive, and synthesise across all sources. Do not skip sources.

---

### PHASE 1 — MULTI-SOURCE INTELLIGENCE GATHERING

Scrape, read, and extract signal from every source below. For each source note:
any ticker mentioned, any analyst call, any unusual volume/options, any sentiment shift.

#### 1A. Financial News & Analysis

- **Yahoo Finance News**: https://finance.yahoo.com/news
  - Focus: breaking news, earnings surprises, analyst calls, M&A rumours
- **Yahoo Finance Markets**: https://finance.yahoo.com/markets
  - Focus: market movers, gainers/losers, most active, 52-week highs/lows
- **Reuters Finance**: https://www.reuters.com/business/finance
  - Focus: macro events, central bank, geopolitical, commodities
- **Bloomberg Markets**: https://www.bloomberg.com/markets
  - Focus: macro overview, rate moves, credit spreads, currency moves
- **CNBC Investing**: https://www.cnbc.com/investing
  - Focus: retail sentiment, FOMO stocks, fast money picks
- **MarketWatch**: https://www.marketwatch.com
  - Focus: economy/politics, sector rotation signals
- **Barron's**: https://www.barrons.com
  - Focus: deep analysis, weekend calls, contrarian ideas
- **Seeking Alpha Market News**: https://seekingalpha.com/market-news
  - Focus: analyst upgrades/downgrades, earnings analysis
- **Investopedia News**: https://www.investopedia.com/financial-news-and-analysis-5217976
  - Focus: retail-facing trend analysis, explainer-level insight on new narratives

#### 1B. Analyst Upgrades, Downgrades & Price Target Changes

- **Stock Analysis Upgrades/Downgrades**: https://stockanalysis.com/stocks/upgrades-downgrades
  - Capture: all upgrades/downgrades in past 5 trading days
  - Flag any where: (a) multiple firms upgraded same stock, (b) PT raised >20%, (c) rare upgrades on beaten-down names
- **Yahoo Finance Analyst Upgrades**: https://finance.yahoo.com/news/analyst-upgrades
- **Benzinga Pre-Market Activity**: https://www.benzinga.com/trading-ideas/long-ideas
  - Focus: high-conviction long setups with catalyst

#### 1C. Social Sentiment & Retail Flow

Retail sentiment is a leading indicator for momentum stocks and meme plays.

- **Reddit r/wallstreetbets HOT**: https://www.reddit.com/r/wallstreetbets/hot
  - Look for: tickers with 50+ upvotes, short squeeze setups, YOLO plays with options data,
    any ticker appearing in multiple posts, "DD" (due diligence) posts on unknown names
- **Reddit r/stocks HOT**: https://www.reddit.com/r/stocks/hot
  - Look for: earnings previews, sector debates, high-quality DD posts
- **Reddit r/investing HOT**: https://www.reddit.com/r/investing/hot
  - Look for: institutional-retail crossover ideas, macro discussions
- **Reddit r/options HOT**: https://www.reddit.com/r/options/hot
  - Look for: unusual options plays, gamma squeeze setups, high IV situations
- **Reddit r/pennystocks HOT**: https://www.reddit.com/r/pennystocks/hot
  - Look for: catalysts on micro-caps, FDA approvals, contract wins, short squeezes
- **Reddit r/smallstreetbets HOT**: https://www.reddit.com/r/smallstreetbets/hot
  - Look for: small/mid-cap momentum with retail following

For X/Twitter: search for the following to find live market intelligence:
- `$TICKER` cashtag searches for any ticker already on our watchlist
- `"short squeeze" -is:retweet lang:en` — active squeeze narratives
- `"earnings beat" OR "blowout earnings" lang:en` — recent earnings movers
- `"FDA approval" OR "FDA approved" lang:en` — biotech binary events
- `"government contract" OR "DoD contract" lang:en` — defense/gov catalysts
- `"buyout" OR "acquisition" OR "merger" lang:en` — M&A rumours
- Top financial accounts to check: @jimcramer (contrarian signal), @unusual_whales,
  @DeItaone (breaking news), @stocktwits trending tickers

#### 1D. Financial Data APIs

Use the following APIs to pull quantitative data signals:

**EODHD (End of Day Historical Data):**
- Fundamentals endpoint: `https://eodhd.com/api/fundamentals/{TICKER}.US?api_token={KEY}`
  - Pull for any new ticker candidates: P/E, EV/EBITDA, short float %, insider ownership
- News endpoint: `https://eodhd.com/api/news?s={TICKER}.US&api_token={KEY}`
  - Pull latest news sentiment scores for watchlist tickers
- Screener: use EODHD screener to find:
  - Stocks with short float > 20% (squeeze candidates)
  - Stocks with price < $10 and volume spike > 3x average (momentum micro-caps)
  - Stocks with insider buying in last 30 days

**Finnhub:**
- News sentiment: `https://finnhub.io/api/v1/news-sentiment?symbol={TICKER}&token={KEY}`
  - Pull sentiment scores for all watchlist tickers; flag any turning significantly positive/negative
- Insider transactions: `https://finnhub.io/api/v1/stock/insider-transactions?symbol={TICKER}&token={KEY}`
  - Flag any insider buys > $100k in last 30 days
- Earnings calendar: `https://finnhub.io/api/v1/calendar/earnings?from={TODAY}&to={TODAY+14d}&token={KEY}`
  - Identify all earnings in next 14 days — these are binary event opportunities

**Yahoo Finance API (unofficial):**
- For any ticker: `https://query1.finance.yahoo.com/v10/finance/quoteSummary/{TICKER}?modules=summaryDetail,defaultKeyStatistics,financialData`
  - Pull: short % of float, forward P/E, analyst target price vs current, 52-week high/low position

#### 1E. Energy & Commodities

- **OilPrice.com**: https://oilprice.com/latest-energy-news
  - Focus: WTI/Brent price direction, OPEC decisions, geopolitical supply shocks
- **Reuters Energy**: https://www.reuters.com/business/energy
  - Focus: LNG deals, refinery outages, pipeline news
- **Gold/Silver news**: search for gold price catalyst — central bank buying, real rates, USD direction

#### 1F. ETF Flows (Institutional Money Rotation)

ETF flows are among the strongest signals for sector rotation.

- **ETF DB Volume**: https://etfdb.com/compare/volume
  - Identify top 20 ETFs by volume today — what sectors are seeing inflows?
- **ETF.com Fund Flows**: https://www.etf.com/etfanalytics/etf-fund-flows-tool
  - 1-week and 1-month flows by sector — which sectors are getting new money?
- Key ETFs to monitor for rotation signals:
  - SPY/QQQ/IWM — broad market direction
  - XLK/SMH/SOXX — tech/semis rotation
  - XLE/OIH — energy
  - XLF/KBE — financials/banks
  - XLV/IBB/XBI — healthcare/biotech
  - XLI/ITA — industrials/defense
  - GDX/GDXJ — gold miners (leading indicator for gold)
  - ARKK/ARKG/ARKW — speculative growth (retail sentiment proxy)
  - SQQQ/SPXS — inverse ETFs (if volume spike = fear rising)

---

### PHASE 2 — HIGH-RISK / HIGH-REWARD OPPORTUNITY HUNT

This section is specifically about finding **asymmetric plays** — situations where
the risk/reward is heavily skewed to the upside. These are NOT safe plays.
They are conviction bets where 50-300%+ gain is possible if the thesis plays out.

#### 2A. Meme Stock & Short Squeeze Candidates

Classic meme/squeeze setup requires:
- High short interest (>20% of float)
- Rising retail attention (Reddit, X mentions trending up)
- Low float (under 50M shares preferred)
- Recent catalyst or potential catalyst incoming

**Where to look:**
- Finviz screener: https://finviz.com/screener.ashx?v=111&f=sh_short_o20,ta_change_u5
  - Filter: short float >20%, price change >5% today
- Shortsqueeze.com: https://shortsqueeze.com (if accessible)
- Reddit r/wallstreetbets DD posts from last 48 hours
- X/Twitter searches: `"short squeeze" 2026` `"high short interest"`
- Unusual options flow on unusualwhales.com or similar

**Classic meme stock checklist:**
- [ ] Is there an active Reddit thread with 500+ upvotes?
- [ ] Has daily volume exceeded 3x the 30-day average?
- [ ] Is short interest above 20%?
- [ ] Is there a news catalyst (earnings, contract, regulatory)?
- [ ] Has it made a 52-week high recently or broken out of consolidation?

#### 2B. Biotech Binary Events

Biotech offers the highest risk/reward in the market. A single FDA decision can
move a stock 200%+ or -80% in one day.

**Where to look:**
- FDA calendar: https://www.fda.gov/patients/drug-approvals-and-databases/biotech-and-pharma-news
- BioPharma Catalyst: https://www.biopharmacatalyst.com/calendars/fda-calendar
  - Look for: PDUFA dates in next 30 days, Phase 3 readouts, AdComm meetings
- Seeking Alpha Biotech: https://seekingalpha.com/market-news/biotech
- Reddit r/biotech and r/investing biotech threads

**Key signals:**
- Any stock with PDUFA date within 14 days — these move regardless of approval
- Small caps (<$2B market cap) with Phase 3 data readouts
- Any recent positive Phase 2 data announcement — look for Phase 3 readout timing
- Orphan drug designations (fast-track = catalyst)

#### 2C. Macro Catalyst Plays

Sometimes the biggest wins come from macro events, not individual company news.

Look for:
- **Tariff/trade war escalation** — who wins? (domestic manufacturers, reshoring plays)
- **Federal Reserve surprise** — rate cut = growth stocks, REITs, utilities surge
- **Dollar moves** — weak dollar = emerging markets, commodities, gold
- **Bond yield spikes** — who gets hurt? (long duration growth stocks)
- **Geopolitical escalation** — defense, cybersecurity, energy
- **AI spending announcement** — which suppliers, chip makers, data center REITs benefit
- **Drug pricing policy** — pharma stocks react violently to policy news

#### 2D. Technical Breakout Candidates

Look for tickers setting up for technical breakouts:
- 52-week high breakouts with volume confirmation
- Cup-and-handle patterns
- Bull flags on daily chart after strong move
- MACD crossing signal line on weekly chart
- RSI recovering from 30 to above 50 (momentum turning)

Sources for technical screens:
- Finviz: https://finviz.com/screener.ashx?v=111&f=ta_highlow52w_nh,ta_change_u3
  (new 52-week highs with >3% today gain)
- TradingView public screener ideas (search for trending screeners)

#### 2E. Insider Buying Clusters

When multiple insiders buy in the same month, it's one of the strongest signals in the market.

- OpenInsider: https://openinsider.com/screener
  - Filter: cluster buys (3+ insiders), purchase >$100k, within 30 days
- SEC Form 4 filings via EDGAR: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4&dateb=&owner=include&count=40

---

### PHASE 3 — WATCHLIST EVALUATION

#### 3A. Review Current Watchlist

For each ticker in the current watchlist above:

1. **Is the original thesis still intact?** Check for any news that breaks the thesis
2. **Has the stock underperformed without a catalyst change?** (deadweight — remove it)
3. **Is there a better play in the same sector?** (upgrade the watchlist)
4. **Has the macro context changed?** (e.g., if Iran de-escalation is confirmed, review defense longs)

#### 3B. Review Open Positions

For each open position listed in the CURRENT OPEN POSITIONS section:
1. Is the thesis intact?
2. Has the stock hit its target or stopped out?
3. Is there any news that changes the risk profile?
4. Should we add on a dip, hold, or close?

#### 3C. Watchlist Sizing Guidance

The watchlist should have:
- **10-15 core holds** (high conviction, macro-aligned, liquid)
- **5-10 tactical plays** (momentum, catalyst-driven, 1-4 week horizon)
- **3-5 high-risk/high-reward speculative plays** (short squeeze, biotech, meme)
- **1-2 macro hedges** (gold, inverse ETFs, volatility plays if market is extended)

Total watchlist size: 20-32 tickers is optimal. Do not over-diversify. Conviction over coverage.

---

### PHASE 4 — RISK ASSESSMENT

Before finalising the list, assess the overall risk environment:

1. **VIX level** — above 20 = elevated fear, above 30 = crisis mode
   - Check: https://finance.yahoo.com/quote/%5EVIX
2. **Market breadth** — are most stocks participating in any rally or just a few?
3. **Fed policy** — any FOMC meeting or Fed speaker in next 7 days?
4. **Earnings season** — are we in earnings season? Which mega-caps report this week?
5. **Options expiration** — is there a major OPEX (options expiration) this week? (3rd Friday)
   - Major OPEX can cause wild pinning or gamma squeezes
6. **Geopolitical risk** — any escalating situation that could gap the market down overnight?

For each high-risk speculative play, provide:
- Estimated probability of the bull case playing out (%)
- Maximum loss if thesis is completely wrong (%)
- Timeline for thesis to play out (days/weeks)
- Exit trigger (what event or price level closes the position)

---

### PHASE 5 — RETURN STRUCTURED RESULTS

Return your findings in this exact format. Do not abbreviate. Be specific.

```
## RESEARCH FINDINGS — [DATE]

### Overall Market Sentiment: [STRONGLY BULLISH / BULLISH / NEUTRAL / BEARISH / STRONGLY BEARISH]
### VIX: [value] | Trend: [rising/falling/stable]
### Earnings Season: [YES/NO — next major reports: ticker (date)]
### FOMC / Fed Events This Week: [YES/NO — details]
### Major OPEX This Week: [YES/NO — date]

---

### TOP MACRO THEMES RIGHT NOW:
1. Theme — what it means for markets — which tickers benefit / hurt
2. ...

---

### TOP 5 HIGH-CONVICTION CORE PICKS:
(Liquid, thesis-driven, lower volatility, 2-8 week horizon)

1. TICKER — Company — Sector
   - Catalyst: [specific catalyst]
   - Analyst support: [who, what call, what price target]
   - Risk: [main risk to thesis]
   - Suggested position size: [% of portfolio]

---

### TOP 3 HIGH-RISK / HIGH-REWARD SPECULATIVE PICKS:
(These could 2-5x or go to zero. Size accordingly — max 2-3% per position.)

1. TICKER — Company — Type: [Meme/Squeeze/Biotech/Momentum/Macro]
   - Setup: [specific setup description]
   - Bull case: [% upside, timeline, trigger]
   - Bear case: [% downside, what breaks it]
   - Probability of bull case: [%]
   - Reddit/X sentiment: [hot/warm/cold]
   - Short interest: [% of float]
   - Volume signal: [normal/elevated/spike]
   - Entry: [price level or condition]
   - Exit: [target price or stop]

---

### MEME/SQUEEZE WATCHLIST:
(Tickers showing meme/squeeze characteristics — not necessarily to buy today,
but to monitor for entry)

| Ticker | Short Float % | Reddit Mentions (24h) | Recent Catalyst | Setup Quality |
|--------|--------------|----------------------|-----------------|---------------|
| ...    | ...          | ...                  | ...             | ...           |

---

### BIOTECH BINARY EVENTS (next 30 days):
| Ticker | Company | Event | Date | Bull Case | Bear Case |
|--------|---------|-------|------|-----------|-----------|
| ...    | ...     | ...   | ...  | ...       | ...       |

---

### INSIDER BUYING ALERTS (last 30 days):
| Ticker | Insider | Role | Amount | Date | Note |
|--------|---------|------|--------|------|------|
| ...    | ...     | ...  | ...    | ...  | ...  |

---

### ANALYST CALLS (last 5 days — notable only):
| Ticker | Firm | Action | Old PT | New PT | Note |
|--------|------|--------|--------|--------|------|
| ...    | ...  | ...    | ...    | ...    | ...  |

---

### WATCHLIST CHANGES:

**REMOVE:**
- TICKER — reason (thesis broken / better alternative / sector headwind)

**ADD:**
- TICKER — reason — category (core/tactical/speculative)

**KEEP (with thesis update):**
- TICKER — original thesis — update — conviction: [HIGH/MEDIUM/LOW]

---

### OPEN POSITION REVIEW:
(For each position listed in CURRENT OPEN POSITIONS)
- TICKER — Status: [HOLD / ADD / REDUCE / CLOSE] — Reason — Updated Stop / Target

---

### KEY MACRO SHIFTS SINCE LAST RESEARCH:
- [bullet: what changed and what it means for the portfolio]

---

### SECTORS TO WATCH CLOSELY THIS WEEK:
1. Sector — why — how to play it

---

### SECTORS TO AVOID THIS WEEK:
1. Sector — why

---

### UPDATED WATCHLIST (full list for trading_loop.py):
(Use this exact format — these tickers will be pasted directly into the trading loop)

CORE HOLDS:
TICKER: "Sector"  # thesis summary — conviction: HIGH

TACTICAL PLAYS:
TICKER: "Sector"  # catalyst — horizon: X weeks

SPECULATIVE / HIGH-RISK:
TICKER: "Sector"  # setup — risk: HIGH — max 2% position

HEDGES:
TICKER: "Macro Hedge"  # hedge rationale

---

### RESEARCH CONFIDENCE: [HIGH / MEDIUM / LOW]
### Sources Successfully Accessed: [list]
### Sources Unavailable: [list]
### Next Research Recommended: [date/trigger — e.g., "before earnings on DATE" or "daily"]
```

---

## IMPORTANT NOTES FOR THE AI ASSISTANT

- **Be specific**: name actual tickers, actual analyst firms, actual price targets. Never be vague.
- **Timestamp everything**: every piece of intelligence should be dated. Markets move fast.
- **Prioritise recency**: a 3-day-old analyst call matters more than a 3-week-old article.
- **Flag conflicts**: if two sources contradict each other, note the conflict and explain which to trust more.
- **Social sentiment is a leading indicator**: if Reddit WSB is going crazy about a ticker with no news, that IS the signal.
- **Do not hallucinate tickers or prices**: if you cannot access a source, say so explicitly. Do not fabricate data.
- **Size guidance**: speculative plays should be max 2-3% of portfolio. Core holds can be 5-10%. Hedges 5%.
- **The goal is alpha, not safety**: we want outsized returns. We accept that some speculative plays will fail.
  The win rate on speculative plays only needs to be ~40% if the wins are large enough.
- **API keys**: if EODHD or Finnhub API keys are available in the environment (check `.env` file),
  use them to pull live data. If not, note that API data was unavailable and rely on scraped sources.

---END PROMPT---
