# TICKET-035 — Remove Global SSL Monkey-Patch

**Priority:** HIGH
**Effort:** 1h
**Status:** DONE

## Problem

`alpaca_bridge.py` (lines 20-42) and `update_positions.py` (lines 15-34) both
monkey-patch `requests.Session.__init__` at module import time, disabling SSL
verification for **every** HTTP request in the Python process — not just Alpaca
calls. This is a broad security hole introduced as a corporate-proxy workaround.

The identical code is also duplicated verbatim between the two files.

Specific issues:
1. `ssl._create_default_https_context = ssl._create_unverified_context` (both files) — global for the whole process
2. `requests.Session.__init__` is monkey-patched globally (alpaca_bridge.py only) — affects yfinance, OpenAI, Reddit, Reuters, StockTwits, Finnhub calls too
3. `NoVerifyAdapter` class is copy-pasted identically in both files

## Approach

**Phase 1 (initial fix):**
1. Remove `ssl._create_default_https_context` global override from both files.
2. Remove `requests.Session.__init__` global monkey-patch from `alpaca_bridge.py`.
3. Apply `verify=False` directly to the Alpaca REST calls in
   `trading_loop.py::get_market_clock()` and `update_positions.py::fetch_positions()`
   (both already used `verify=False` on the raw `requests.get()` call).
4. Keep `NoVerifyAdapter` + `get_session()` local to `update_positions.py` —
   it was already scoped correctly there.

**Phase 2 (regression fix — alpaca-py SDK sessions):**
The Alpaca SDK (`alpaca-py`) creates its own `requests.Session` internally
(`client._session`). With the global patch removed, SDK calls to
`paper-api.alpaca.markets` started failing with
`ssl.SSLCertVerificationError: CA cert does not include key usage extension`.

Fix: define `_NoVerifyAdapter` in `alpaca_bridge.py` and apply it to each SDK
client's `_session` immediately after construction via `_disable_ssl_on_sdk_client()`.
This restores SSL bypass **only for Alpaca SDK traffic**, leaving all other HTTP
clients (yfinance, OpenAI, Reddit, Reuters, StockTwits, Finnhub) unaffected.

```python
def _disable_ssl_on_sdk_client(client) -> None:
    session = getattr(client, "_session", None)
    if session is not None:
        session.verify = False
        session.mount("https://", _NoVerifyAdapter())
```

Called in `_get_trading_client()` and `_get_data_client()` after construction.

## Acceptance Criteria
- [x] `ssl._create_default_https_context` override removed from both files
- [x] Global `requests.Session.__init__` monkey-patch removed from `alpaca_bridge.py`
- [x] `NoVerifyAdapter` kept local to each file that needs it (not shared module)
- [x] `verify=False` applied only to Alpaca-specific sessions (SDK + REST helpers)
- [x] yfinance, OpenAI, Reddit, Reuters, StockTwits, Finnhub use verified SSL
- [x] All tests pass (398)
- [x] New test: importing `alpaca_bridge` does not patch `requests.Session.__init__`
- [x] New test: importing `alpaca_bridge` does not change `ssl._create_default_https_context`
