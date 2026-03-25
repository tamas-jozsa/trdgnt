# TICKET-033 — Analyst Price Targets & Consensus

**Priority:** MEDIUM
**Effort:** 1h
**Status:** TODO

## Problem

The Research Manager outputs ENTRY/STOP/TARGET based purely on technical analysis
and LLM reasoning. It has no knowledge of what Wall Street analysts think the
stock is worth. A stock at $100 with analyst consensus target of $150 is very
different from one with consensus of $90.

## Free public source

**Yahoo Finance analyst recommendations (via yfinance):**
```python
import yfinance as yf
t = yf.Ticker("NVDA")
info = t.info
# Keys: targetMeanPrice, targetHighPrice, targetLowPrice,
#        recommendationMean (1=Strong Buy, 5=Strong Sell),
#        numberOfAnalystOpinions, recommendationKey
```

## New tool: `get_analyst_targets(ticker)`

Returns:
```
Analyst Consensus for NVDA:
- Recommendation: BUY (mean score: 1.8/5 across 42 analysts)
- Price targets: Low $140 / Mean $195 / High $250
- Current price: $178.56
- Upside to mean target: +9.2%
- Upside to high target: +40.1%
```

## Acceptance Criteria
- [ ] `get_analyst_targets(ticker)` returns recommendation + price targets + upside %
- [ ] Added to Fundamentals Analyst tool list
- [ ] Returns gracefully if no analyst coverage
- [ ] Unit tests: parse mock yfinance info dict, compute upside correctly
- [ ] All tests pass
