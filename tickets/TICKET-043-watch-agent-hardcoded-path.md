# TICKET-043 — Remove Hardcoded Path from watch_agent.sh

**Priority:** LOW
**Effort:** 10min
**Status:** DONE

## Problem

`watch_agent.sh:11` contains:

```bash
_CONDA_PYTHON="/Users/tjozsa/miniconda3/envs/tradingagents/bin/python3"
```

This is an absolute path to a specific user's conda environment. It breaks
silently on any other machine (falls back to system `python3` which may lack
the dependencies) and leaks a username into the repository.

The fallback logic on lines 12-18 already handles the case where the path
doesn't exist, but the hardcoded value makes the intent unclear and is
confusing to other contributors.

## Approach

Replace the hardcoded path with a cross-platform auto-detection approach:
1. Check `$CONDA_PREFIX/bin/python3` (set when conda env is active)
2. Check `$VIRTUAL_ENV/bin/python3` (set when venv is active)
3. Fall back to `python3`

This way the script works correctly whether invoked from an activated conda
env, a venv, or bare system Python.

## Acceptance Criteria
- [ ] Hardcoded `/Users/tjozsa/...` path removed from `watch_agent.sh`
- [ ] Python auto-detection uses `$CONDA_PREFIX` and `$VIRTUAL_ENV` env vars
- [ ] Falls back to `python3` if neither is set
- [ ] Script still runs correctly when invoked from an active conda env
- [ ] All existing tests pass
