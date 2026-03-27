# TICKET-039 — Unify ALPACA_BASE_URL Across All Files

**Priority:** MEDIUM
**Effort:** 30min
**Status:** DONE

## Problem

`ALPACA_BASE_URL` is handled three different ways:

| File | How |
|---|---|
| `alpaca_bridge.py:139` | `os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")` |
| `trading_loop.py:333` | Hardcoded `"https://paper-api.alpaca.markets/v2/clock"` |
| `update_positions.py:57-58` | Hardcoded `"https://paper-api.alpaca.markets/v2/..."` |

If `ALPACA_BASE_URL` is set to a live trading URL in `.env`, `trading_loop.py`
and `update_positions.py` will still hit the paper API silently.

## Approach

1. In `trading_loop.py::get_market_clock()`: read `ALPACA_BASE_URL` from env (same
   default as `alpaca_bridge.py`) and construct the clock URL from it.
2. In `update_positions.py::fetch_positions()` / `get_session()`: same — read
   `ALPACA_BASE_URL` and use it for both the `/v2/account` and `/v2/positions` calls.
3. No new module needed — just replace the three hardcoded strings.

## Acceptance Criteria
- [ ] `trading_loop.py::get_market_clock()` uses `os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")` to build the URL
- [ ] `update_positions.py::fetch_positions()` uses the same env var
- [ ] `ALPACA_BASE_URL` is documented in `.env.example` (it already is — verify)
- [ ] Test: `get_market_clock()` with `ALPACA_BASE_URL` env set to a mock URL uses that URL (mock `requests.get`, assert called URL)
- [ ] All existing tests pass
