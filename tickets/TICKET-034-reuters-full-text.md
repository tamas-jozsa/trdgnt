# TICKET-034 — Reuters Full Article Text (Subscription)

**Priority:** LOW
**Effort:** 2h
**Status:** TODO

## Problem

Reuters sitemap gives us headlines and ticker tags but no article body.
A headline "Nvidia AI chip demand surges" tells us the direction but not
the magnitude, the specific customers, or the analyst quotes that make it
actionable.

## Approach

Use a browser session cookie from reuters.com subscription to fetch full
article HTML, then extract the article body text.

**How to get the cookie:**
1. Log in to reuters.com in Chrome
2. Open DevTools → Application → Cookies → reuters.com
3. Copy the value of `_session` or equivalent auth cookie
4. Add to `.env` as `REUTERS_SESSION_COOKIE=...`

**Fetching:**
```python
import requests
headers = {
    "User-Agent": "Mozilla/5.0 ...",
    "Cookie": f"_session={os.getenv('REUTERS_SESSION_COOKIE')}"
}
resp = requests.get(article_url, headers=headers)
# Extract article body from <div class="article-body__content">
```

**Integration:**
- `get_reuters_article_body(url)` — fetches and parses article body
- In `get_reuters_news_for_ticker()`: for the top 3 most relevant articles,
  also fetch the body (max 1000 chars each)
- Cache article bodies in `data_cache/reuters_{hash}.txt` (1-day TTL)

## Acceptance Criteria
- [ ] `REUTERS_SESSION_COOKIE` documented in `.env.example`
- [ ] `get_reuters_article_body(url)` returns article text or empty string if fails
- [ ] Top 3 Reuters articles per ticker now include body excerpt
- [ ] Falls back gracefully to headline-only if cookie not set or fetch fails
- [ ] Article bodies cached to avoid re-fetching on retry
- [ ] Unit tests: parse mock HTML, graceful fallback
- [ ] All tests pass

## Note

Cookie-based auth is fragile (expires, may violate ToS). This ticket should
only be implemented if the subscription clearly permits programmatic access.
Check reuters.com ToS before implementing.
