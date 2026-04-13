# TICKET-107 — Pluggable Stock Screener

**Priority:** HIGH
**Effort:** 0.5 days
**Status:** TODO
**Related:** TICKET-108
**Spec:** docs/SPEC.md — "Screener Interface"

## Summary

Create `apps/screener.py` — a pluggable stock screener that scans all US
equities for new investment candidates. Default implementation uses
finvizfinance (free). Interface supports future paid sources (Polygon.io,
Alpha Vantage, etc.).

## Requirements

1. **ScreenerCandidate dataclass:**
   ```python
   @dataclass
   class ScreenerCandidate:
       ticker: str
       company_name: str
       sector: str
       industry: str
       market_cap: float
       price: float
       volume_ratio: float       # vs 20-day average
       price_change_1d: float
       price_change_5d: float
       sma50_cross: bool
       sma200_cross: bool
       earnings_surprise: float | None
       signal_source: str        # "volume" | "momentum" | "fundamental" | "news"
   ```

2. **ScreenerSource protocol:**
   ```python
   class ScreenerSource(Protocol):
       def scan(self, filters: dict) -> list[ScreenerCandidate]: ...
       def get_source_name(self) -> str: ...
   ```

3. **FinvizScreener implementation:**
   - Uses `finvizfinance` Python library
   - Scans ~8,000 US equities
   - Applies configurable filters:
     - Market cap >= $500M (configurable)
     - Price >= $5.00 (configurable)
     - Average volume >= 500K
   - Multiple scan strategies run in sequence:
     - **Volume scan:** Unusual volume > 2x 20-day average
     - **Momentum scan:** New 52-week highs, price crossing 50/200 SMA
     - **Fundamental scan:** Earnings surprise > 5%, analyst upgrades
   - Rate limiting: 1 request/second to avoid Finviz blocks
   - Returns deduplicated, merged candidates

4. **CompositeScreener:**
   - Merges results from multiple ScreenerSource implementations
   - Deduplicates by ticker
   - Future-ready for adding Polygon.io, Alpha Vantage, etc.

5. **Filter configuration from default_config.py:**
   ```python
   DEFAULT_CONFIG["discovery"]["screener_source"] = "finviz"
   DEFAULT_CONFIG["discovery"]["min_market_cap"] = 500_000_000
   DEFAULT_CONFIG["discovery"]["min_price"] = 5.00
   DEFAULT_CONFIG["discovery"]["min_volume_ratio"] = 2.0
   DEFAULT_CONFIG["discovery"]["max_raw_candidates"] = 100
   ```

## Files

- **Create:** `apps/screener.py`
- **Modify:** `pyproject.toml` — add `finvizfinance` dependency
- **Modify:** `src/tradingagents/default_config.py` — add discovery config

## Dependencies

- `finvizfinance` (new dependency)

## Tests

- FinvizScreener with mocked HTTP responses
- Filter logic (market cap, price, volume thresholds)
- Deduplication across scan strategies
- CompositeScreener merging
- Graceful handling of rate limits / network errors
