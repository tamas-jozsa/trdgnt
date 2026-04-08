# TICKET-103 — Add Smoke Tests for Critical Paths

**Priority:** MEDIUM  
**Effort:** 2-3 hours  
**Status:** TODO  
**Files:** `tests/smoke/`

## Problem

There is no quick way to verify basic system health. A smoke test suite should catch:
- Import errors
- Path misconfigurations
- Dashboard startup issues

## Solution

Add smoke-test suite for:
1. Importing every app entrypoint
2. `dashboard.backend.main` startup
3. `mage -l` (or equivalent task runner)
4. One dry-run path through trading loop

## Acceptance Criteria

- [ ] Smoke test imports all app entrypoints without error
- [ ] Smoke test starts dashboard backend successfully
- [ ] Smoke test runs task runner command
- [ ] Smoke test runs one dry-run ticker through trading loop
- [ ] Smoke tests run in CI
- [ ] Smoke tests complete in under 60 seconds
