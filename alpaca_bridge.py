"""
alpaca_bridge.py
================
Connects TradingAgents analysis to an Alpaca paper trading account.

Flow:
  1. Run TradingAgents analysis on a ticker → BUY / SELL / HOLD
  2. Query current Alpaca paper portfolio
  3. Execute the appropriate paper order
  4. Print portfolio summary

Usage:
  python alpaca_bridge.py --ticker NVDA --date 2024-05-10 --amount 1000

Requirements:
  pip install alpaca-py
"""

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Disable SSL verification for requests/urllib3 (corporate proxy workaround)
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NoVerifyAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        kwargs["ssl_context"].check_hostname = False
        kwargs["ssl_context"].verify_mode = ssl.CERT_NONE
        return super().init_poolmanager(*args, **kwargs)

_original_session_init = requests.Session.__init__
def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.verify = False
    self.mount("https://", NoVerifyAdapter())
requests.Session.__init__ = _patched_session_init

import argparse
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Alpaca client setup
# ---------------------------------------------------------------------------

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            "Add it to your .env file. See .env.example for the full list."
        )
    return val

ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# Clients are initialised lazily on first use so tests can mock them without real keys.
_trading_client: TradingClient | None              = None
_data_client:    StockHistoricalDataClient | None  = None


def _get_trading_client() -> TradingClient:
    global _trading_client
    if _trading_client is None:
        _trading_client = TradingClient(
            api_key=_require_env("ALPACA_API_KEY"),
            secret_key=_require_env("ALPACA_API_SECRET"),
            paper=True,
        )
    return _trading_client


def _get_data_client() -> StockHistoricalDataClient:
    global _data_client
    if _data_client is None:
        _data_client = StockHistoricalDataClient(
            api_key=_require_env("ALPACA_API_KEY"),
            secret_key=_require_env("ALPACA_API_SECRET"),
        )
    return _data_client


# ---------------------------------------------------------------------------
# Portfolio helpers
# ---------------------------------------------------------------------------

def check_stop_losses(
    threshold: float = 0.15,
    dry_run: bool = False,
) -> list[dict]:
    """
    Check all open positions and close any that have fallen below the
    stop-loss threshold.

    Args:
        threshold: Fraction loss that triggers a stop (0.15 = -15%).
        dry_run:   If True, log what would be sold but place no orders.

    Returns:
        List of dicts describing each triggered stop.
    """
    import subprocess

    triggered = []
    tc = _get_trading_client()
    positions = tc.get_all_positions()

    for p in positions:
        pnl_pct = float(p.unrealized_plpc)          # e.g. -0.18 = -18%
        if pnl_pct <= -abs(threshold):
            ticker = p.symbol
            qty    = float(p.qty)
            msg = (
                f"[STOP-LOSS] {ticker}: P&L {pnl_pct*100:.1f}% ≤ -{threshold*100:.0f}% "
                f"— closing {qty:.4f} shares"
            )
            print(msg)

            result = {
                "action":   "STOP_LOSS_TRIGGERED",
                "ticker":   ticker,
                "qty":      qty,
                "pnl_pct":  round(pnl_pct * 100, 2),
                "threshold": round(-threshold * 100, 0),
                "dry_run":  dry_run,
            }

            if not dry_run:
                order_req = MarketOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
                order = tc.submit_order(order_req)
                result["order_id"] = str(order.id)
                result["status"]   = str(order.status)
                print(f"  [ORDER] Stop-loss order submitted: {order.id}")
            else:
                print(f"  [DRY-RUN] Would sell {qty:.4f} {ticker}")

            # macOS notification
            try:
                note = f"{ticker}: {pnl_pct*100:.1f}% — {'DRY-RUN' if dry_run else 'SOLD'}"
                subprocess.run(
                    ["osascript", "-e",
                     f'display notification "{note}" with title "TradingAgents — STOP-LOSS"'],
                    check=False, capture_output=True,
                )
            except Exception:
                pass

            triggered.append(result)

    if not triggered:
        print(f"[STOP-LOSS] No positions triggered at -{threshold*100:.0f}% threshold.")

    return triggered

def get_portfolio_summary() -> dict:
    """Return account equity, cash, and current positions."""
    tc = _get_trading_client()
    account = tc.get_account()
    positions = tc.get_all_positions()

    pos_summary = []
    for p in positions:
        pos_summary.append({
            "ticker":    p.symbol,
            "qty":       float(p.qty),
            "avg_cost":  float(p.avg_entry_price),
            "mkt_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_pl_pct": float(p.unrealized_plpc) * 100,
        })

    return {
        "equity":       float(account.equity),
        "cash":         float(account.cash),
        "buying_power": float(account.buying_power),
        "positions":    pos_summary,
    }


def get_latest_price(ticker: str) -> float:
    """
    Get the latest price for a ticker.

    After market close, ask_price is 0. Falls back through:
      ask_price → bid_price → last trade price → yfinance close price
    """
    try:
        req = StockLatestQuoteRequest(symbol_or_symbols=ticker)
        quote = _get_data_client().get_stock_latest_quote(req)
        q = quote[ticker]

        # Try ask first, then bid
        for price_attr in ("ask_price", "bid_price"):
            price = float(getattr(q, price_attr, 0) or 0)
            if price > 0:
                return price
    except Exception:
        pass

    # Fall back to latest trade price via Alpaca
    try:
        from alpaca.data.requests import StockLatestTradeRequest
        req = StockLatestTradeRequest(symbol_or_symbols=ticker)
        trade = _get_data_client().get_stock_latest_trade(req)
        price = float(trade[ticker].price or 0)
        if price > 0:
            return price
    except Exception:
        pass

    # Final fallback: yfinance previous close
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        price = float(getattr(info, "last_price", None) or getattr(info, "previous_close", 0) or 0)
        if price > 0:
            print(f"[ALPACA] Using yfinance price for {ticker}: ${price:.2f}")
            return price
    except Exception:
        pass

    return 0.0


def shares_held(ticker: str) -> float:
    """Return number of shares currently held for ticker (0 if none)."""
    try:
        pos = _get_trading_client().get_open_position(ticker)
        return float(pos.qty)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Order execution
# ---------------------------------------------------------------------------

def execute_decision(ticker: str, decision: str, trade_amount_usd: float) -> dict:
    """
    Execute a paper trade based on the TradingAgents decision.

    Args:
        ticker:           Stock symbol, e.g. "NVDA"
        decision:         "BUY", "SELL", or "HOLD"
        trade_amount_usd: Dollar amount to buy/sell

    Returns:
        Dict with order result or hold message.
    """
    decision = decision.strip().upper()

    if decision == "HOLD":
        print(f"[ALPACA] Decision is HOLD for {ticker} — no order placed.")
        return {"action": "HOLD", "ticker": ticker}

    price = get_latest_price(ticker)
    if price <= 0:
        raise ValueError(f"Could not get a valid price for {ticker} (got {price})")

    if decision == "BUY":
        account = _get_trading_client().get_account()
        available_cash = float(account.cash)
        buy_amount = min(trade_amount_usd, available_cash)

        if buy_amount < 1:
            print(f"[ALPACA] Insufficient cash (${available_cash:.2f}) to BUY {ticker}.")
            return {"action": "SKIPPED", "reason": "insufficient_cash"}

        qty = round(buy_amount / price, 6)
        print(f"[ALPACA] BUY {qty:.4f} shares of {ticker} @ ~${price:.2f} (≈${buy_amount:.2f})")

        order_request = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )

    elif decision == "SELL":
        held = shares_held(ticker)
        if held <= 0:
            print(f"[ALPACA] No position in {ticker} to SELL.")
            return {"action": "SKIPPED", "reason": "no_position"}

        # Sell the lesser of what we hold or what the trade amount covers
        sell_qty = min(held, round(trade_amount_usd / price, 6))
        print(f"[ALPACA] SELL {sell_qty:.4f} shares of {ticker} @ ~${price:.2f} (holding {held:.4f})")

        order_request = MarketOrderRequest(
            symbol=ticker,
            qty=sell_qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )

    else:
        raise ValueError(f"Unknown decision: '{decision}'. Expected BUY, SELL, or HOLD.")

    order = _get_trading_client().submit_order(order_request)
    return {
        "action":   decision,
        "ticker":   ticker,
        "order_id": str(order.id),
        "qty":      float(order.qty),
        "status":   str(order.status),
    }


# ---------------------------------------------------------------------------
# TradingAgents runner
# ---------------------------------------------------------------------------

def run_analysis(
    ticker: str,
    trade_date: str,
    debug: bool = False,
    position_context: str = "",
    macro_context: str = "",
    memory_dir: str = "",
) -> str:
    """
    Standalone entry point: run TradingAgents for one ticker and return decision.

    This is used when running alpaca_bridge.py directly from the CLI.
    For production use, prefer trading_loop.py which handles the full
    daily cycle including stop-loss checks and tier-based position sizing.

    Args:
        ticker:           Stock symbol.
        trade_date:       Date to analyse (YYYY-MM-DD).
        debug:            Enable LangGraph debug tracing.
        position_context: Pre-formatted position context string.
        macro_context:    Daily research findings context string.
        memory_dir:       Directory for agent memory files. If empty, uses
                          trading_loop_logs/memory/{ticker}.
    """
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["deep_think_llm"]  = "gpt-4o-mini"
    config["quick_think_llm"] = "gpt-4o-mini"
    config["data_vendors"] = {
        "core_stock_apis":      "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data":     "yfinance",
        "news_data":            "yfinance",
    }

    mem_dir = memory_dir or f"trading_loop_logs/memory/{ticker}"

    print(f"\n[TRADINGAGENTS] Analysing {ticker} for {trade_date} ...")
    if position_context:
        print(f"[TRADINGAGENTS] Position context: {position_context}")
    if macro_context:
        print(f"[TRADINGAGENTS] Macro context loaded ({len(macro_context)} chars)")

    ta = TradingAgentsGraph(debug=debug, config=config)
    ta.load_memories(mem_dir)

    _, decision = ta.propagate(
        ticker, trade_date,
        position_context=position_context,
        macro_context=macro_context,
    )
    decision = (decision or "HOLD").strip().upper()
    print(f"[TRADINGAGENTS] Decision → {decision}")

    ta.save_memories(mem_dir)
    return decision


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def print_portfolio(portfolio: dict):
    print("\n" + "=" * 55)
    print("  ALPACA PAPER PORTFOLIO")
    print("=" * 55)
    print(f"  Equity      : ${portfolio['equity']:>12,.2f}")
    print(f"  Cash        : ${portfolio['cash']:>12,.2f}")
    print(f"  Buying power: ${portfolio['buying_power']:>12,.2f}")

    if portfolio["positions"]:
        print("\n  Positions:")
        print(f"  {'Ticker':<8} {'Qty':>8} {'Avg Cost':>10} {'Mkt Value':>11} {'P/L':>10} {'P/L %':>8}")
        print("  " + "-" * 57)
        for p in portfolio["positions"]:
            pl_sign = "+" if p["unrealized_pl"] >= 0 else ""
            print(
                f"  {p['ticker']:<8} {p['qty']:>8.4f} "
                f"${p['avg_cost']:>9.2f} "
                f"${p['mkt_value']:>10.2f} "
                f"{pl_sign}${p['unrealized_pl']:>8.2f} "
                f"{pl_sign}{p['unrealized_pl_pct']:>6.2f}%"
            )
    else:
        print("\n  No open positions.")
    print("=" * 55 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run TradingAgents analysis and execute on Alpaca paper account."
    )
    parser.add_argument("--ticker", default="NVDA",       help="Stock ticker symbol (default: NVDA)")
    parser.add_argument("--date",   default=str(date.today()), help="Trade date YYYY-MM-DD (default: today)")
    parser.add_argument("--amount", type=float, default=1000.0, help="USD amount per trade (default: 1000)")
    parser.add_argument("--debug",  action="store_true",  help="Enable TradingAgents debug output")
    parser.add_argument("--dry-run", action="store_true", help="Analyse only, do not place order")
    args = parser.parse_args()

    # 1. Show portfolio before
    print("\n[PORTFOLIO] Before trade:")
    portfolio_before = get_portfolio_summary()
    print_portfolio(portfolio_before)

    # 2. Run TradingAgents
    decision = run_analysis(args.ticker, args.date, debug=args.debug)

    # 3. Execute (unless dry-run)
    if args.dry_run:
        print(f"[DRY-RUN] Would execute: {decision} {args.ticker} up to ${args.amount:.2f}")
    else:
        result = execute_decision(args.ticker, decision, args.amount)
        print(f"\n[ORDER RESULT] {result}")

    # 4. Show portfolio after
    print("\n[PORTFOLIO] After trade:")
    portfolio_after = get_portfolio_summary()
    print_portfolio(portfolio_after)


if __name__ == "__main__":
    main()
