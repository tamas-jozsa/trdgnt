# TICKET-038 — Tests for update_positions.py

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE

## Problem

`update_positions.py` has no tests. The `fetch_positions()` function does raw
`dict` access on the Alpaca API response (`p["symbol"]`, `account["equity"]`
etc.) without any guard — if the API returns an error JSON instead of a list,
it will crash with `TypeError` or `KeyError`.

## Acceptance Criteria
- [ ] `TestFetchPositions` — mock `requests.Session.get` to return realistic
      account + positions JSON; assert returned dict has correct structure and values
- [ ] `TestFetchPositionsApiError` — mock API returning `{"code": 40110000, "message":
      "..."}` (error dict, not a list); assert function raises a clear exception rather
      than `TypeError`; or returns empty positions gracefully — pick one and implement it
- [ ] `TestBuildPositionsMarkdown` — unit test with a known positions dict; assert
      markdown contains ticker, qty, avg cost, P/L
- [ ] `TestBuildPositionsMarkdownEmpty` — zero positions → "100% cash" message present
- [ ] `TestInjectIntoPrompt` — write a fake `MARKET_RESEARCH_PROMPT.md` with placeholder
      tags; call `inject_into_prompt`; assert placeholder content replaced
- [ ] All tests pass
