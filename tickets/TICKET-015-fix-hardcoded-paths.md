# TICKET-015 — Fix Hardcoded Absolute Paths in watch_agent.sh

**Priority:** MEDIUM
**Effort:** 30 min
**Status:** DONE
**Files:** `watch_agent.sh`

## Problem

`watch_agent.sh` has two hardcoded absolute paths that break on any machine
other than the original developer's:

1. Python path: `/Users/tjozsa/miniconda3/envs/tradingagents/bin/python3`
2. Log dir: `LOG_DIR="/Users/tjozsa/cf-repos/github/trdagnt/trading_loop_logs"`
3. Project dir: `sys.path.insert(0, "/Users/tjozsa/cf-repos/github/trdagnt")`

## Acceptance Criteria

- [ ] Python resolved via `PYTHON="${PYTHON:-python3}"` with override support
      falling back to the conda env path if that specific path exists
- [ ] `SCRIPT_DIR` computed as `$(cd "$(dirname "$0")" && pwd)` at script top
- [ ] `LOG_DIR` set relative to `SCRIPT_DIR`
- [ ] Python `sys.path` insert uses `SCRIPT_DIR` passed as env var or argv
- [ ] Script still works when run from any directory
- [ ] Existing dashboard output unchanged
