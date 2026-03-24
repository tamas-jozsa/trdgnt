# TICKET-010 — Gitignore Runtime Data + Cache Cleanup + API Key Security

**Priority:** LOW  
**Effort:** 30 min  
**Status:** TODO  
**Files:** `.gitignore`, `alpaca_bridge.py`, `trading_loop.py`, `update_positions.py`

## Problem

1. `eval_results/`, `positions.json`, `results/` are runtime data that should never be
   committed. They are currently untracked but will accumulate.

2. The yfinance data cache (`dataflows/data_cache/`) creates a new CSV file every day and
   never cleans up old ones. Over time this fills disk.

3. Alpaca API keys are hardcoded as fallback defaults in `alpaca_bridge.py`,
   `trading_loop.py`, and `update_positions.py`. Even for paper trading this is a
   security anti-pattern — they're already in git history.

## Acceptance Criteria

### Gitignore
- [ ] `eval_results/` added to `.gitignore`
- [ ] `results/` added to `.gitignore` (except `results/RESEARCH_FINDINGS_*.md` — keep those)
- [ ] `positions.json` added to `.gitignore`
- [ ] `trading_loop_logs/` added to `.gitignore`
- [ ] `tradingagents/dataflows/data_cache/` added to `.gitignore`
- [ ] `Miniconda3-*.sh` added to `.gitignore`

### Cache Cleanup
- [ ] `get_stock_data_yfinance()` deletes cache files older than 2 days on load

### API Key Security
- [ ] Hardcoded fallback API keys removed from all 3 files
- [ ] All 3 files use `os.getenv("ALPACA_API_KEY")` with no fallback
- [ ] If key not found: raise `EnvironmentError` with clear message pointing to `.env`
- [ ] `.env.example` updated with placeholder values for all required keys

## Implementation

`.gitignore` additions:
```
eval_results/
results/
positions.json
trading_loop_logs/
tradingagents/dataflows/data_cache/
Miniconda3-*.sh
*.egg-info/
__pycache__/
*.pyc
```

In each file replace:
```python
# Before
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "PKCE6UTF35ARLE5IAXHREVTAZT")
# After
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY") or (_ for _ in ()).throw(
    EnvironmentError("ALPACA_API_KEY not set. Add it to your .env file."))
```
