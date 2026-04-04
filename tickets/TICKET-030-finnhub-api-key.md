# TICKET-030 — Add Finnhub API Key & Enable Richer News

**Priority:** HIGH
**Effort:** 30 min
**Status:** DONE

## Problem

`finnhub_utils.py` is fully implemented and wired into the news analyst as the
primary source — but `FINNHUB_API_KEY` is not set in `.env` so it silently falls
back to Yahoo Finance news for every ticker.

Finnhub provides:
- Full article summaries (not just headlines)
- Precise date filtering
- Sentiment scores per article
- Company-specific news with higher relevance than Yahoo

## What to do

1. Register for a free Finnhub account at https://finnhub.io (free tier: 60 calls/min)
2. Add `FINNHUB_API_KEY=your_key` to `.env` and `~/zsh/env-vars`
3. Add it to the launchctl plist `EnvironmentVariables`
4. Verify the news analyst is now using Finnhub by checking logs for "Finnhub" in tool output

## Acceptance Criteria
- [ ] `FINNHUB_API_KEY` set in `.env`, `~/zsh/env-vars`, and launchctl plist
- [ ] `tpython -c "from tradingagents.dataflows.finnhub_utils import get_news_finnhub; print(get_news_finnhub('NVDA','2026-03-20','2026-03-25')[:200])"` returns real articles
- [ ] News analyst logs show Finnhub data in reports
