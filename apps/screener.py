"""Pluggable stock screener for investment candidate discovery.

Scans a broad universe of US equities using configurable filters and returns
ranked candidates for full debate analysis.

Default implementation: FinvizScreener (free, ~8000 tickers).
Interface designed for future paid sources (Polygon.io, Alpha Vantage, etc.).

TICKET-107
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ScreenerCandidate:
    """A stock that passed the screener filters."""

    ticker: str
    company_name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: float = 0.0
    price: float = 0.0
    volume: float = 0.0
    avg_volume: float = 0.0
    volume_ratio: float = 0.0  # vs 20-day average
    price_change_1d: float = 0.0
    price_change_5d: float = 0.0
    price_change_1m: float = 0.0
    sma50_cross: bool = False
    sma200_cross: bool = False
    earnings_surprise: float | None = None
    signal_source: str = ""  # "volume" | "momentum" | "fundamental" | "news"
    score: float = 0.0  # composite ranking score


@dataclass
class ScreenerFilters:
    """Configurable filters for the screener."""

    min_market_cap: float = 500_000_000  # $500M
    min_price: float = 5.0
    min_avg_volume: int = 500_000
    min_volume_ratio: float = 2.0  # for volume scan
    max_raw_candidates: int = 100
    exclude_sectors: list[str] = field(default_factory=list)
    exclude_tickers: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Protocol — pluggable interface
# ---------------------------------------------------------------------------


@runtime_checkable
class ScreenerSource(Protocol):
    """Interface for stock screener implementations.

    Implementations:
    - FinvizScreener (default, free)
    - YFinanceScreener (fallback)

    Future:
    - PolygonScreener ($29/mo, real-time snapshots)
    - AlphaVantageScreener (premium tier)
    - TradingViewScreener (webhook-based)
    """

    def scan(self, filters: ScreenerFilters) -> list[ScreenerCandidate]: ...

    def get_source_name(self) -> str: ...


# ---------------------------------------------------------------------------
# FinvizScreener — primary implementation (free)
# ---------------------------------------------------------------------------


class FinvizScreener:
    """Stock screener using finvizfinance (free, ~8000 US equities).

    Runs multiple scan strategies and merges results:
    - Volume scan: unusual volume spikes
    - Momentum scan: 52-week highs, SMA crossovers
    - Fundamental scan: earnings surprises, analyst upgrades

    Rate-limited to 1 request/second to avoid Finviz blocks.
    """

    def __init__(self, rate_limit_seconds: float = 1.5):
        self._rate_limit = rate_limit_seconds
        self._last_request_time = 0.0

    def get_source_name(self) -> str:
        return "finviz"

    def scan(self, filters: ScreenerFilters) -> list[ScreenerCandidate]:
        """Run all scan strategies and return merged, deduplicated candidates."""
        candidates: dict[str, ScreenerCandidate] = {}

        # Run each strategy, merging results
        for strategy_name, strategy_fn in [
            ("volume", self._scan_unusual_volume),
            ("momentum", self._scan_momentum),
            ("fundamental", self._scan_fundamental),
        ]:
            try:
                results = strategy_fn(filters)
                for c in results:
                    if c.ticker not in candidates:
                        c.signal_source = strategy_name
                        candidates[c.ticker] = c
                    else:
                        # Boost score if found by multiple strategies
                        candidates[c.ticker].score += 1.0
                logger.info(
                    "Finviz %s scan: %d candidates", strategy_name, len(results)
                )
            except Exception as exc:
                logger.warning("Finviz %s scan failed: %s", strategy_name, exc)

        # Apply exclusions
        result = [
            c
            for c in candidates.values()
            if c.ticker not in filters.exclude_tickers
            and c.sector not in filters.exclude_sectors
        ]

        # Sort by score (descending), then by volume ratio
        result.sort(key=lambda c: (-c.score, -c.volume_ratio))

        # Cap to max candidates
        return result[: filters.max_raw_candidates]

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting between Finviz requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request_time = time.time()

    def _scan_unusual_volume(
        self, filters: ScreenerFilters
    ) -> list[ScreenerCandidate]:
        """Find stocks with unusual volume (>2x 20-day average)."""
        try:
            from finvizfinance.screener.overview import Overview

            self._rate_limit_wait()
            screener = Overview()
            screener.set_filter(
                filters_dict={
                    "Market Cap.": "+Mid (over $2bln)",
                    "Average Volume": "Over 500K",
                    "Relative Volume": "Over 2",
                    "Price": "Over $5",
                    "Country": "USA",
                }
            )
            df = screener.screener_view()

            if df is None or df.empty:
                return []

            return self._dataframe_to_candidates(df, "volume", filters)

        except ImportError:
            logger.warning(
                "finvizfinance not installed — run: pip install finvizfinance"
            )
            return []
        except Exception as exc:
            logger.warning("Finviz volume scan error: %s", exc)
            return []

    def _scan_momentum(
        self, filters: ScreenerFilters
    ) -> list[ScreenerCandidate]:
        """Find stocks with momentum breakouts (new highs, SMA crossovers)."""
        try:
            from finvizfinance.screener.overview import Overview

            self._rate_limit_wait()
            screener = Overview()
            screener.set_filter(
                filters_dict={
                    "Market Cap.": "+Mid (over $2bln)",
                    "Average Volume": "Over 500K",
                    "20-Day Simple Moving Average": "Price above SMA20",
                    "50-Day Simple Moving Average": "Price above SMA50",
                    "Price": "Over $5",
                    "Country": "USA",
                }
            )
            df = screener.screener_view()

            if df is None or df.empty:
                return []

            return self._dataframe_to_candidates(df, "momentum", filters)

        except ImportError:
            return []
        except Exception as exc:
            logger.warning("Finviz momentum scan error: %s", exc)
            return []

    def _scan_fundamental(
        self, filters: ScreenerFilters
    ) -> list[ScreenerCandidate]:
        """Find stocks with positive fundamental signals."""
        try:
            from finvizfinance.screener.overview import Overview

            self._rate_limit_wait()
            screener = Overview()
            screener.set_filter(
                filters_dict={
                    "Market Cap.": "+Mid (over $2bln)",
                    "Average Volume": "Over 500K",
                    "EPS growththis year": "Over 20%",
                    "Sales growthqtr over qtr": "Over 20%",
                    "Price": "Over $5",
                    "Country": "USA",
                }
            )
            df = screener.screener_view()

            if df is None or df.empty:
                return []

            return self._dataframe_to_candidates(df, "fundamental", filters)

        except ImportError:
            return []
        except Exception as exc:
            logger.warning("Finviz fundamental scan error: %s", exc)
            return []

    def _dataframe_to_candidates(
        self, df, signal_source: str, filters: ScreenerFilters
    ) -> list[ScreenerCandidate]:
        """Convert a finvizfinance DataFrame to ScreenerCandidate list."""
        candidates = []
        for _, row in df.iterrows():
            try:
                ticker = str(row.get("Ticker", "")).strip()
                if not ticker:
                    continue

                # Parse market cap (finviz returns strings like "1.5B")
                market_cap = _parse_market_cap(row.get("Market Cap", "0"))
                if market_cap < filters.min_market_cap:
                    continue

                price = _parse_float(row.get("Price", 0))
                if price < filters.min_price:
                    continue

                change = _parse_pct(row.get("Change", "0%"))
                volume = _parse_float(row.get("Volume", 0))

                candidates.append(
                    ScreenerCandidate(
                        ticker=ticker,
                        company_name=str(row.get("Company", "")),
                        sector=str(row.get("Sector", "")),
                        industry=str(row.get("Industry", "")),
                        market_cap=market_cap,
                        price=price,
                        volume=volume,
                        price_change_1d=change,
                        signal_source=signal_source,
                        score=1.0,
                    )
                )
            except Exception:
                continue  # Skip malformed rows

        return candidates


# ---------------------------------------------------------------------------
# YFinanceScreener — fallback implementation (free but slower)
# ---------------------------------------------------------------------------


class YFinanceScreener:
    """Fallback screener using yfinance for S&P 500 + NASDAQ 100.

    Slower than Finviz (fetches data per-ticker) but requires no extra
    dependency. Used when finvizfinance is unavailable.
    """

    # Major index constituents to scan
    SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    def get_source_name(self) -> str:
        return "yfinance"

    def scan(self, filters: ScreenerFilters) -> list[ScreenerCandidate]:
        """Scan S&P 500 constituents for unusual activity."""
        try:
            import pandas as pd
            import yfinance as yf

            # Get S&P 500 ticker list
            try:
                tables = pd.read_html(self.SP500_URL)
                sp500_tickers = list(tables[0]["Symbol"].str.replace(".", "-"))
            except Exception:
                logger.warning("Failed to fetch S&P 500 list, using hardcoded subset")
                sp500_tickers = _FALLBACK_TICKERS

            # Filter out excluded tickers
            tickers = [
                t for t in sp500_tickers if t not in filters.exclude_tickers
            ][:200]  # Cap at 200 for speed

            # Batch download
            logger.info("YFinance screening %d tickers...", len(tickers))
            data = yf.download(
                tickers, period="1mo", group_by="ticker", progress=False, threads=True
            )

            candidates = []
            for ticker in tickers:
                try:
                    if len(tickers) == 1:
                        ticker_data = data
                    else:
                        ticker_data = data[ticker] if ticker in data.columns.get_level_values(0) else None
                    if ticker_data is None or ticker_data.empty:
                        continue

                    close = ticker_data["Close"].dropna()
                    volume = ticker_data["Volume"].dropna()
                    if len(close) < 5 or len(volume) < 5:
                        continue

                    current_price = float(close.iloc[-1])
                    if current_price < filters.min_price:
                        continue

                    avg_vol = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else float(volume.mean())
                    last_vol = float(volume.iloc[-1])
                    vol_ratio = last_vol / avg_vol if avg_vol > 0 else 0

                    change_1d = (
                        (float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100
                        if len(close) >= 2 else 0
                    )

                    candidates.append(
                        ScreenerCandidate(
                            ticker=ticker,
                            price=current_price,
                            volume=last_vol,
                            avg_volume=avg_vol,
                            volume_ratio=vol_ratio,
                            price_change_1d=change_1d,
                            signal_source="yfinance",
                            score=vol_ratio,
                        )
                    )
                except Exception:
                    continue

            # Filter by volume ratio
            candidates = [c for c in candidates if c.volume_ratio >= filters.min_volume_ratio]
            candidates.sort(key=lambda c: -c.volume_ratio)
            return candidates[: filters.max_raw_candidates]

        except ImportError:
            logger.error("yfinance not installed")
            return []
        except Exception as exc:
            logger.error("YFinance screener error: %s", exc)
            return []


# ---------------------------------------------------------------------------
# CompositeScreener — merges multiple sources
# ---------------------------------------------------------------------------


class CompositeScreener:
    """Merges results from multiple screener sources.

    Usage::

        screener = CompositeScreener([FinvizScreener(), YFinanceScreener()])
        candidates = screener.scan(filters)
    """

    def __init__(self, sources: list[ScreenerSource] | None = None):
        self._sources = sources or []

    def add_source(self, source: ScreenerSource) -> None:
        self._sources.append(source)

    def get_source_name(self) -> str:
        names = [s.get_source_name() for s in self._sources]
        return "+".join(names)

    def scan(self, filters: ScreenerFilters) -> list[ScreenerCandidate]:
        """Run all sources and merge results."""
        merged: dict[str, ScreenerCandidate] = {}

        for source in self._sources:
            try:
                results = source.scan(filters)
                for c in results:
                    if c.ticker in merged:
                        merged[c.ticker].score += c.score
                        # Keep the richer record
                        if not merged[c.ticker].company_name and c.company_name:
                            merged[c.ticker].company_name = c.company_name
                        if not merged[c.ticker].sector and c.sector:
                            merged[c.ticker].sector = c.sector
                    else:
                        merged[c.ticker] = c

                logger.info(
                    "%s returned %d candidates", source.get_source_name(), len(results)
                )
            except Exception as exc:
                logger.warning(
                    "%s scan failed: %s", source.get_source_name(), exc
                )

        result = list(merged.values())
        result.sort(key=lambda c: (-c.score, -c.volume_ratio))
        return result[: filters.max_raw_candidates]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_screener(source: str = "finviz") -> ScreenerSource:
    """Create a screener instance by name.

    Args:
        source: "finviz" (default), "yfinance", or "composite"
    """
    if source == "finviz":
        return FinvizScreener()
    elif source == "yfinance":
        return YFinanceScreener()
    elif source == "composite":
        return CompositeScreener([FinvizScreener(), YFinanceScreener()])
    else:
        logger.warning("Unknown screener source '%s', falling back to finviz", source)
        return FinvizScreener()


# ---------------------------------------------------------------------------
# Portfolio exclusion helpers
# ---------------------------------------------------------------------------


def exclude_portfolio(
    candidates: list[ScreenerCandidate], portfolio_tickers: set[str]
) -> list[ScreenerCandidate]:
    """Remove candidates already in the portfolio."""
    before = len(candidates)
    result = [c for c in candidates if c.ticker not in portfolio_tickers]
    excluded = before - len(result)
    if excluded:
        logger.info("Excluded %d portfolio tickers from candidates", excluded)
    return result


def exclude_cooldown(
    candidates: list[ScreenerCandidate], cooldown_tickers: set[str]
) -> list[ScreenerCandidate]:
    """Remove candidates in stop-loss cooldown."""
    return [c for c in candidates if c.ticker not in cooldown_tickers]


def exclude_recently_debated(
    candidates: list[ScreenerCandidate],
    debated_tickers: set[str],
) -> list[ScreenerCandidate]:
    """Remove candidates that were already debated within lookback window."""
    before = len(candidates)
    result = [c for c in candidates if c.ticker not in debated_tickers]
    excluded = before - len(result)
    if excluded:
        logger.info("Excluded %d recently-debated tickers", excluded)
    return result


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_market_cap(val) -> float:
    """Parse finviz market cap strings like '1.5B', '800M'."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().upper()
    multiplier = 1
    if s.endswith("T"):
        multiplier = 1_000_000_000_000
        s = s[:-1]
    elif s.endswith("B"):
        multiplier = 1_000_000_000
        s = s[:-1]
    elif s.endswith("M"):
        multiplier = 1_000_000
        s = s[:-1]
    elif s.endswith("K"):
        multiplier = 1_000
        s = s[:-1]
    try:
        return float(s.replace(",", "")) * multiplier
    except (ValueError, TypeError):
        return 0.0


def _parse_float(val) -> float:
    """Parse a string or numeric value to float."""
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_pct(val) -> float:
    """Parse a percentage string like '2.5%' to float."""
    s = str(val).strip().replace("%", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


# Fallback tickers if S&P 500 Wikipedia fetch fails
_FALLBACK_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "UNH", "JNJ", "JPM", "V", "PG", "XOM", "MA", "HD", "CVX", "MRK",
    "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "TMO", "MCD", "WMT",
    "CSCO", "ACN", "ABT", "DHR", "NEE", "LIN", "TXN", "PM", "RTX",
    "UNP", "LOW", "HON", "AMGN", "UPS", "BMY", "COP", "SBUX", "BA",
    "AMD", "GS", "CAT", "ISRG",
]
