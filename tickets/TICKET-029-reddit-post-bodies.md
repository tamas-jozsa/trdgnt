# TICKET-029 — Reddit Post Bodies & Comments

**Priority:** HIGH
**Effort:** 2h
**Status:** DONE

## Problem

`reddit_utils.py` only fetches post titles and upvote scores from Reddit hot listings.
The actual investment thesis is in the post body and top comments. A title like
"GME short squeeze incoming" tells us nothing — the body has the float %, catalyst,
options chain analysis, and the real conviction behind the post.

## What to add

- `get_reddit_post_body(url)`: fetch the full self-text of a post
- `get_reddit_top_comments(post_id, subreddit, limit=5)`: fetch top 5 comments
- Update `get_reddit_sentiment()` to include post bodies + top comments for the
  top 3 posts per subreddit (not all — token budget)

## Endpoints (all public, no auth)

```
# Post body + comments
https://www.reddit.com/r/{sub}/comments/{post_id}.json?limit=5&sort=top
```

Returns: post selftext, top comments with body + upvote scores.

## Acceptance Criteria
- [ ] `get_reddit_post_body(permalink)` returns the self-text of a post (empty string if link post)
- [ ] Top 3 posts per subreddit include body (first 500 chars) + top 2 comments
- [ ] Output format is readable for the LLM analyst
- [ ] Graceful fallback if body fetch fails (titles-only mode)
- [ ] Unit tests: parse post body from mock JSON, empty body for link posts
- [ ] All tests pass
