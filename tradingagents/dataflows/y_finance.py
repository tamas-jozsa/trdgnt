from typing import Annotated
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import glob as _glob
import logging
import time
import yfinance as yf
import os
from .stockstats_utils import StockstatsUtils, _clean_dataframe

logger = logging.getLogger(__name__)

# Guard: run cache cleanup at most once per calendar day
# Tracks the date so long-running processes (launchctl) clean up daily
_cache_cleaned_date: str = ""
_CACHE_MAX_AGE_DAYS = 2

# Maximum size for a cached CSV file.
# 2-year OHLCV data is ~40-50 KB. 500 KB is a generous ceiling that catches
# accidental 15-year files (2-5 MB) without false positives.
_MAX_CACHE_FILE_BYTES = 500 * 1024   # 500 KB


def _is_oversized_lookback(filename: str) -> bool:
    """
    Return True if the cache filename encodes a lookback start year before 2023.

    Pattern: {TICKER}-YFin-data-{START}-{END}.csv
    Example: NVDA-YFin-data-2011-03-25-2026-03-25.csv  → start year 2011 → True
             NVDA-YFin-data-2024-03-25-2026-03-25.csv  → start year 2024 → False
    """
    import re as _re
    m = _re.search(r"-YFin-data-(\d{4})-", os.path.basename(filename))
    if m:
        start_year = int(m.group(1))
        return start_year < 2023   # anything older than 3-year lookback is stale
    return False


def _cleanup_old_cache_files(cache_dir: str) -> None:
    """Delete CSV cache files that are either too old (by mtime) or have an
    oversized lookback range (identified by filename start year < 2023).

    Two-pronged approach:
    1. Filename-based: catches 15-year files even if they were just created today
    2. Mtime-based: catches any file older than _CACHE_MAX_AGE_DAYS regardless of name

    Runs at most once per calendar day.
    """
    global _cache_cleaned_date
    today = datetime.now().strftime("%Y-%m-%d")
    if _cache_cleaned_date == today:
        return
    _cache_cleaned_date = today

    cutoff = time.time() - _CACHE_MAX_AGE_DAYS * 86400
    pattern = os.path.join(cache_dir, "*-YFin-data-*.csv")
    deleted = 0
    for path in _glob.glob(pattern):
        try:
            if _is_oversized_lookback(path) or os.path.getmtime(path) < cutoff:
                os.remove(path)
                deleted += 1
        except Exception:
            pass
    if deleted:
        logger.debug(
            "Cache cleanup: deleted %d file(s) from %s (oversized lookback or stale)",
            deleted, cache_dir,
        )


def _safe_read_csv(path: str, symbol: str) -> "pd.DataFrame":
    """
    Read a cached CSV file with size and integrity safeguards.

    1. Check file size BEFORE opening — if it exceeds _MAX_CACHE_FILE_BYTES,
       delete the file and raise so the caller re-downloads fresh data.
    2. Read in a single chunked pass using pd.read_csv with chunksize to
       avoid holding the file descriptor open while pandas processes data.
    3. File handle is guaranteed closed via context manager before any
       downstream code runs.

    Returns a pandas DataFrame or raises Exception if file is bad.
    """
    import pandas as pd

    file_size = os.path.getsize(path)
    if file_size > _MAX_CACHE_FILE_BYTES:
        logger.warning(
            "Cache file %s is %s bytes (limit %s) — deleting and re-downloading",
            path, f"{file_size:,}", f"{_MAX_CACHE_FILE_BYTES:,}",
        )
        try:
            os.remove(path)
        except Exception:
            pass
        raise Exception(
            f"Oversized cache file for {symbol} ({file_size:,} bytes) was deleted. "
            f"Re-downloading on next call."
        )

    # Read in chunks to avoid keeping the fd open during processing
    chunks = []
    try:
        with open(path, "r") as fh:
            for chunk in pd.read_csv(fh, on_bad_lines="skip", chunksize=500):
                chunks.append(chunk)
    except Exception as e:
        # Corrupted file — delete it so next call re-downloads
        logger.warning("Corrupted cache file %s: %s — deleting", path, e)
        try:
            os.remove(path)
        except Exception:
            pass
        raise Exception(f"Corrupted cache file for {symbol} deleted. Re-downloading on next call.")

    if not chunks:
        try:
            os.remove(path)
        except Exception:
            pass
        raise Exception(f"Empty cache file for {symbol} deleted.")

    df = pd.concat(chunks, ignore_index=True)

    if df.empty:
        try:
            os.remove(path)
        except Exception:
            pass
        raise Exception(f"Cache file for {symbol} contained no data rows — deleted.")

    return df


def get_YFin_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Create ticker object
    ticker = yf.Ticker(symbol.upper())

    # Fetch historical data for the specified date range
    data = ticker.history(start=start_date, end=end_date)

    # Check if data is empty
    if data.empty:
        return (
            f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
        )

    # Remove timezone info from index for cleaner output
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Round numerical values to 2 decimal places for cleaner display
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    # Convert DataFrame to CSV string
    csv_string = data.to_csv()

    # Add header information
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string

def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:

    best_ind_params = {
        # Moving Averages
        "close_50_sma": (
            "50 SMA: A medium-term trend indicator. "
            "Usage: Identify trend direction and serve as dynamic support/resistance. "
            "Tips: It lags price; combine with faster indicators for timely signals."
        ),
        "close_200_sma": (
            "200 SMA: A long-term trend benchmark. "
            "Usage: Confirm overall market trend and identify golden/death cross setups. "
            "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
        ),
        "close_10_ema": (
            "10 EMA: A responsive short-term average. "
            "Usage: Capture quick shifts in momentum and potential entry points. "
            "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
        ),
        # MACD Related
        "macd": (
            "MACD: Computes momentum via differences of EMAs. "
            "Usage: Look for crossovers and divergence as signals of trend changes. "
            "Tips: Confirm with other indicators in low-volatility or sideways markets."
        ),
        "macds": (
            "MACD Signal: An EMA smoothing of the MACD line. "
            "Usage: Use crossovers with the MACD line to trigger trades. "
            "Tips: Should be part of a broader strategy to avoid false positives."
        ),
        "macdh": (
            "MACD Histogram: Shows the gap between the MACD line and its signal. "
            "Usage: Visualize momentum strength and spot divergence early. "
            "Tips: Can be volatile; complement with additional filters in fast-moving markets."
        ),
        # Momentum Indicators
        "rsi": (
            "RSI: Measures momentum to flag overbought/oversold conditions. "
            "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
            "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
        ),
        # Volatility Indicators
        "boll": (
            "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
            "Usage: Acts as a dynamic benchmark for price movement. "
            "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
        ),
        "boll_ub": (
            "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
            "Usage: Signals potential overbought conditions and breakout zones. "
            "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
        ),
        "boll_lb": (
            "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
            "Usage: Indicates potential oversold conditions. "
            "Tips: Use additional analysis to avoid false reversal signals."
        ),
        "atr": (
            "ATR: Averages true range to measure volatility. "
            "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
            "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
        ),
        # Volume-Based Indicators
        "vwma": (
            "VWMA: A moving average weighted by volume. "
            "Usage: Confirm trends by integrating price action with volume data. "
            "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
        ),
        "mfi": (
            "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
            "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
            "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
        ),
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )

    end_date = curr_date
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    # Optimized: Get stock data once and calculate indicators for all dates
    try:
        indicator_data = _get_stock_stats_bulk(symbol, indicator, curr_date)
        
        # Generate the date range we need
        current_dt = curr_date_dt
        date_values = []
        
        while current_dt >= before:
            date_str = current_dt.strftime('%Y-%m-%d')
            
            # Look up the indicator value for this date
            if date_str in indicator_data:
                indicator_value = indicator_data[date_str]
            else:
                indicator_value = "N/A: Not a trading day (weekend or holiday)"
            
            date_values.append((date_str, indicator_value))
            current_dt = current_dt - relativedelta(days=1)
        
        # Build the result string
        ind_string = ""
        for date_str, value in date_values:
            ind_string += f"{date_str}: {value}\n"
        
    except Exception as e:
        err_str = str(e)
        # Don't retry day-by-day if the error is file-system related —
        # it will just generate hundreds of identical errors for nothing
        if "Too many open files" in err_str or "unable to open database" in err_str or "NoneType" in err_str:
            logger.warning("Skipping fallback for %s/%s due to: %s", symbol, indicator, err_str[:80])
            ind_string = f"N/A: data unavailable ({err_str[:60]})\n" * 1
        else:
            print(f"Error getting bulk stockstats data: {e}")
            # Fallback to original implementation only for recoverable errors
            ind_string = ""
            curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
            while curr_date_dt >= before:
                indicator_value = get_stockstats_indicator(
                    symbol, indicator, curr_date_dt.strftime("%Y-%m-%d")
                )
                ind_string += f"{curr_date_dt.strftime('%Y-%m-%d')}: {indicator_value}\n"
                curr_date_dt = curr_date_dt - relativedelta(days=1)

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "No description available.")
    )

    return result_str


def _get_stock_stats_bulk(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to calculate"],
    curr_date: Annotated[str, "current date for reference"]
) -> dict:
    """
    Optimized bulk calculation of stock stats indicators.
    Fetches data once and calculates indicator for all available dates.
    Returns dict mapping date strings to indicator values.
    """
    from .config import get_config
    import pandas as pd
    from stockstats import wrap
    import os
    
    config = get_config()
    online = config["data_vendors"]["technical_indicators"] != "local"
    
    if not online:
        # Local data path
        try:
            data = pd.read_csv(
                os.path.join(
                    config.get("data_cache_dir", "data"),
                    f"{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
                ),
                on_bad_lines="skip",
            )
        except FileNotFoundError:
            raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
    else:
        # Online data fetching with caching
        today_date = pd.Timestamp.today()
        curr_date_dt = pd.to_datetime(curr_date)

        end_date = today_date
        # 2-year lookback is sufficient for all indicators (200 SMA needs ~200 days)
        # Previously 15 years — created huge files and exhausted file descriptors
        start_date = today_date - pd.DateOffset(years=2)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        os.makedirs(config["data_cache_dir"], exist_ok=True)
        _cleanup_old_cache_files(config["data_cache_dir"])

        data_file = os.path.join(
            config["data_cache_dir"],
            f"{symbol}-YFin-data-{start_date_str}-{end_date_str}.csv",
        )

        if os.path.exists(data_file):
            data = _safe_read_csv(data_file, symbol)
        else:
            data = yf.download(
                symbol,
                start=start_date_str,
                end=end_date_str,
                multi_level_index=False,
                progress=False,
                auto_adjust=True,
            )
            if data is None or data.empty:
                raise Exception(f"yfinance returned no data for {symbol}")
            data = data.reset_index()
            # Guard: refuse to cache files larger than MAX_CACHE_FILE_BYTES
            import io as _io
            buf = _io.StringIO()
            data.to_csv(buf, index=False)
            csv_str = buf.getvalue()
            if len(csv_str) > _MAX_CACHE_FILE_BYTES:
                raise Exception(
                    f"Downloaded data for {symbol} is {len(csv_str):,} bytes "
                    f"(limit {_MAX_CACHE_FILE_BYTES:,}) — refusing to cache oversized file"
                )
            with open(data_file, "w") as fh:
                fh.write(csv_str)

    if data is None or (hasattr(data, "empty") and data.empty):
        raise Exception(f"No data available for {symbol}")

    data = _clean_dataframe(data)
    df = wrap(data)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    
    # Calculate the indicator for all rows at once
    df[indicator]  # This triggers stockstats to calculate the indicator
    
    # Create a dictionary mapping date strings to indicator values
    result_dict = {}
    for _, row in df.iterrows():
        date_str = row["Date"]
        indicator_value = row[indicator]
        
        # Handle NaN/None values
        if pd.isna(indicator_value):
            result_dict[date_str] = "N/A"
        else:
            result_dict[date_str] = str(indicator_value)
    
    return result_dict


def get_stockstats_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
) -> str:

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_date = curr_date_dt.strftime("%Y-%m-%d")

    try:
        indicator_value = StockstatsUtils.get_stock_stats(
            symbol,
            indicator,
            curr_date,
        )
    except Exception as e:
        print(
            f"Error getting stockstats indicator data for indicator {indicator} on {curr_date}: {e}"
        )
        return ""

    return str(indicator_value)


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get company fundamentals overview from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        info = ticker_obj.info

        if not info:
            return f"No fundamentals data found for symbol '{ticker}'"

        fields = [
            ("Name", info.get("longName")),
            ("Sector", info.get("sector")),
            ("Industry", info.get("industry")),
            ("Market Cap", info.get("marketCap")),
            # Valuation — the key metrics for comparing to peers
            ("Enterprise Value", info.get("enterpriseValue")),
            ("EV/EBITDA", info.get("enterpriseToEbitda")),
            ("EV/Revenue", info.get("enterpriseToRevenue")),
            ("PE Ratio (TTM)", info.get("trailingPE")),
            ("Forward PE", info.get("forwardPE")),
            ("PEG Ratio", info.get("pegRatio")),
            ("Price to Book", info.get("priceToBook")),
            ("EPS (TTM)", info.get("trailingEps")),
            ("Forward EPS", info.get("forwardEps")),
            ("Dividend Yield", info.get("dividendYield")),
            ("Beta", info.get("beta")),
            ("52 Week High", info.get("fiftyTwoWeekHigh")),
            ("52 Week Low", info.get("fiftyTwoWeekLow")),
            ("50 Day Average", info.get("fiftyDayAverage")),
            ("200 Day Average", info.get("twoHundredDayAverage")),
            ("Revenue (TTM)", info.get("totalRevenue")),
            ("Revenue Growth (YoY)", info.get("revenueGrowth")),
            ("Gross Profit", info.get("grossProfits")),
            ("EBITDA", info.get("ebitda")),
            ("Net Income", info.get("netIncomeToCommon")),
            ("Earnings Growth (YoY)", info.get("earningsGrowth")),
            ("Profit Margin", info.get("profitMargins")),
            ("Operating Margin", info.get("operatingMargins")),
            ("Return on Equity", info.get("returnOnEquity")),
            ("Return on Assets", info.get("returnOnAssets")),
            ("Debt to Equity", info.get("debtToEquity")),
            ("Current Ratio", info.get("currentRatio")),
            ("Book Value", info.get("bookValue")),
            ("Free Cash Flow", info.get("freeCashflow")),
        ]

        lines = []
        for label, value in fields:
            if value is not None:
                lines.append(f"{label}: {value}")

        header = f"# Company Fundamentals for {ticker.upper()}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + "\n".join(lines)

    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get balance sheet data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_balance_sheet
        else:
            data = ticker_obj.balance_sheet
            
        if data.empty:
            return f"No balance sheet data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Balance Sheet data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get cash flow data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_cashflow
        else:
            data = ticker_obj.cashflow
            
        if data.empty:
            return f"No cash flow data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Cash Flow data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get income statement data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_income_stmt
        else:
            data = ticker_obj.income_stmt
            
        if data.empty:
            return f"No income statement data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Income Statement data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"]
):
    """Get insider transactions data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        data = ticker_obj.insider_transactions
        
        if data is None or data.empty:
            return f"No insider transactions data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Insider Transactions data for {ticker.upper()}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving insider transactions for {ticker}: {str(e)}"