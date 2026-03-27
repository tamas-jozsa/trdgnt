# TICKET-037 — Tests for daily_research.py Scrapers

**Priority:** HIGH
**Effort:** 2h
**Status:** DONE

## Problem

`daily_research.py` contains six live data scrapers (`fetch_yahoo_gainers`,
`fetch_vix`, `fetch_reuters_headlines`, `fetch_reddit_sentiment`,
`fetch_watchlist_prices`, `fetch_stocktwits_sentiment`) and `call_llm()` — none
have any tests. A regression in the JSON parsing would silently return empty
strings and degrade macro context without any signal.

## Acceptance Criteria
- [ ] `TestFetchYahooGainers` — mock `_fetch_url` returning a realistic JSON fixture;
      assert output contains expected ticker + change % lines; empty/malformed → ""
- [ ] `TestFetchVix` — mock URL returning VIX JSON; assert "VIX:" in output
- [ ] `TestFetchReutersHeadlines` — mock URL returning RSS XML; assert headline
      extracted; empty feed → ""
- [ ] `TestFetchRedditSentiment` — mock URL returning subreddit JSON; assert post
      titles + scores extracted; network error → ""
- [ ] `TestCallLlm` — mock `openai.OpenAI().chat.completions.create`; assert
      response content is returned; missing `OPENAI_API_KEY` → raises `EnvironmentError`
- [ ] `TestRunDailyResearch` — mock all `fetch_*` functions + `call_llm`; assert
      findings file is created in `RESULTS_DIR`; second call same day returns existing
      path without re-calling LLM (idempotent); `--force` flag overwrites
- [ ] All tests use `tmp_path` / monkeypatching, never make real network calls
- [ ] All tests pass
