"""
main.py — quick single-ticker demo / manual test harness.

For the production daily loop use trading_loop.py instead.

Usage:
  python main.py                          # analyse NVDA for yesterday
  python main.py --ticker AAPL            # different ticker
  python main.py --date 2025-03-26        # specific date
  python main.py --debug                  # verbose LangGraph tracing
"""

# Path setup
import _path_setup  # noqa: F401


import argparse
import os
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Single-ticker TradingAgents demo.")
    parser.add_argument("--ticker", default="NVDA",          help="Ticker to analyse (default: NVDA)")
    parser.add_argument("--date",   default=None,            help="Analysis date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--debug",  action="store_true",     help="Enable LangGraph debug output")
    args = parser.parse_args()

    trade_date = args.date or str(date.today() - timedelta(days=1))

    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["deep_think_llm"]  = os.getenv("DEEP_LLM_MODEL",  "gpt-4o")
    config["quick_think_llm"] = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
    config["max_debate_rounds"] = 1
    config["data_vendors"] = {
        "core_stock_apis":      "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data":     "yfinance",
        "news_data":            "yfinance",
    }

    print(f"Analysing {args.ticker} for {trade_date} ...")
    ta = TradingAgentsGraph(debug=args.debug, config=config)
    _, decision = ta.propagate(args.ticker, trade_date)
    print(f"Decision: {decision}")

    # To run reflection after a trade:
    # ta.reflect_and_remember("Position gained +5%")


if __name__ == "__main__":
    main()
