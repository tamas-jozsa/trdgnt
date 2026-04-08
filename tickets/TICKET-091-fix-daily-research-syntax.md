# TICKET-091 — Fix Syntax Error in daily_research.py

**Priority:** CRITICAL  
**Effort:** 15 min  
**Status:** TODO  
**Files:** `apps/daily_research.py`

## Problem

`apps/daily_research.py` is currently a syntax error. `from __future__ import annotations` appears after `import _path_setup`, which Python rejects. The trading loop imports `run_daily_research` from this file at `apps/trading_loop.py:1091-1092`, so the research phase is brittle or broken in the current layout.

## Affected Location

- `apps/daily_research.py:24-28` — import order violation

## Solution

Move `from __future__ import annotations` to the absolute top of the file, before any other imports.

## Acceptance Criteria

- [ ] `python -c "import apps.daily_research"` succeeds without SyntaxError
- [ ] `apps/trading_loop.py` can import `run_daily_research` successfully
- [ ] Daily research phase runs without import errors
