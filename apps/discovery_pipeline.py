"""
discovery_pipeline.py
=====================
Daily process that screens all US equities for new investment candidates,
filters them through an LLM, runs the full 12-agent debate on top picks,
and executes BUY orders with recorded theses.

Replaces the static WATCHLIST + daily re-debate pattern from v1.

TICKET-108
"""

# ---------------------------------------------------------------------------
# Path setup — MUST be first
# ---------------------------------------------------------------------------
import _path_setup  # noqa: F401
from _path_setup import PROJECT_ROOT, TRADING_LOGS_DIR, MEMORY_DIR, RESULTS_DIR

# ---------------------------------------------------------------------------

import argparse
import json
import logging
import os
import sys
import time
import urllib3
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

ET = ZoneInfo("America/New_York")

# Directories
DATA_DIR = PROJECT_ROOT / "data"
DISCOVERY_DIR = DATA_DIR / "discovery"
CHECKPOINT_DIR = TRADING_LOGS_DIR / "discovery_checkpoints"


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def _get_run_config() -> dict:
    """Load discovery config from DEFAULT_CONFIG."""
    from tradingagents.default_config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.get("discovery", {})


def seconds_until_next_run() -> int:
    """Seconds until next 9:00 AM ET weekday."""
    config = _get_run_config()
    run_hour = config.get("run_hour", 9)
    run_minute = config.get("run_minute", 0)

    now = datetime.now(ET)
    target = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)

    if now >= target:
        target += timedelta(days=1)

    while target.weekday() >= 5:  # skip weekends
        target += timedelta(days=1)

    return max(0, int((target - now).total_seconds()))


def get_analysis_date() -> str:
    """Return the most recent completed trading session date."""
    now = datetime.now(ET)
    # If before market open, use yesterday's data
    if now.hour < 10:
        d = now.date() - timedelta(days=1)
    else:
        d = now.date()
    # Skip weekends
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Checkpoint (crash recovery)
# ---------------------------------------------------------------------------


def _save_checkpoint(trade_date: str, ticker: str, result: dict) -> None:
    """Save a completed ticker analysis for crash recovery."""
    checkpoint_dir = CHECKPOINT_DIR / trade_date
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / f"{ticker}.json"
    try:
        data = {
            "ticker": ticker,
            "decision": result.get("decision", "HOLD"),
            "completed_at": datetime.now(ET).isoformat(),
        }
        path.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        logger.warning("Failed to save checkpoint for %s: %s", ticker, exc)


def _load_completed_tickers(trade_date: str) -> set[str]:
    """Load tickers already completed today."""
    checkpoint_dir = CHECKPOINT_DIR / trade_date
    if not checkpoint_dir.exists():
        return set()
    completed = set()
    for f in checkpoint_dir.glob("*.json"):
        completed.add(f.stem)
    return completed


# ---------------------------------------------------------------------------
# LLM Filter
# ---------------------------------------------------------------------------


def _build_filter_prompt(
    candidates: list,
    macro_context: str,
    portfolio_summary: str,
    max_candidates: int,
) -> str:
    """Build the LLM filter prompt for ranking screener candidates."""
    candidate_lines = []
    for c in candidates[:60]:  # cap input to avoid token overflow
        line = f"- {c.ticker}: {c.sector} | ${c.price:.2f} | vol_ratio={c.volume_ratio:.1f}x | 1d={c.price_change_1d:+.1f}% | signal={c.signal_source}"
        if c.company_name:
            line = f"- {c.ticker} ({c.company_name}): {c.sector} | ${c.price:.2f} | vol_ratio={c.volume_ratio:.1f}x | 1d={c.price_change_1d:+.1f}% | signal={c.signal_source}"
        candidate_lines.append(line)

    return f"""You are a portfolio manager screening for new medium-term investment candidates.

CURRENT MACRO CONTEXT:
{macro_context[:3000]}

CURRENT PORTFOLIO:
{portfolio_summary}

SCREENER CANDIDATES ({len(candidates)} stocks with unusual activity today):
{chr(10).join(candidate_lines)}

TASK:
Select the top {max_candidates} candidates most suitable for a medium-term investment (1-12 months).

SELECTION CRITERIA:
1. Alignment with current macro themes (strongest weight)
2. Fills gaps in current portfolio (sector diversity, theme coverage)
3. Strong signal quality (multiple signals > single signal)
4. Reasonable valuation for the sector
5. Avoid stocks in sectors flagged for avoidance in macro context

OUTPUT FORMAT (one ticker per line, ranked by priority):
TICKER | CATEGORY | REASONING
where CATEGORY is CORE (6-12mo hold, strong fundamentals) or TACTICAL (1-3mo, catalyst-driven)

Example:
SMCI | TACTICAL | AI server demand surge, catalyst: next earnings in 3 weeks
ANET | CORE | Networking infrastructure play, secular AI growth theme

Return exactly {max_candidates} lines. No other text.
"""


def _run_llm_filter(
    candidates: list,
    macro_context: str,
    portfolio_summary: str,
    max_candidates: int,
) -> list[dict]:
    """Call LLM to filter and rank screener candidates.

    Returns list of {ticker, category, reasoning} dicts.
    """
    from tradingagents.llm_clients.factory import create_llm_client

    prompt = _build_filter_prompt(
        candidates, macro_context, portfolio_summary, max_candidates
    )

    model = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
    provider = os.getenv("LLM_PROVIDER", "openai")

    try:
        client = create_llm_client(provider=provider, model=model)
        response = client.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("LLM filter call failed: %s", exc)
        # Fallback: return top N by score
        return [
            {"ticker": c.ticker, "category": "TACTICAL", "reasoning": "Fallback: top by score"}
            for c in candidates[:max_candidates]
        ]

    # Parse response
    selected = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            ticker = parts[0].strip().upper()
            category = parts[1].strip().upper() if len(parts) > 1 else "TACTICAL"
            reasoning = parts[2].strip() if len(parts) > 2 else ""
            if category not in ("CORE", "TACTICAL"):
                category = "TACTICAL"
            selected.append({
                "ticker": ticker,
                "category": category,
                "reasoning": reasoning,
            })

    logger.info("LLM filter selected %d candidates", len(selected))
    return selected[:max_candidates]


# ---------------------------------------------------------------------------
# Portfolio summary helper
# ---------------------------------------------------------------------------


def _build_portfolio_summary(thesis_store) -> str:
    """Build a concise portfolio summary for the LLM filter."""
    theses = thesis_store.get_all_theses()
    if not theses:
        return "Portfolio is EMPTY — no current holdings. All sectors are open."

    lines = [f"Currently holding {len(theses)} positions:"]
    sectors = {}
    for ticker, record in theses.items():
        cat = record.category.value if hasattr(record.category, "value") else record.category
        sector = record.thesis.sector or "Unknown"
        lines.append(f"  {ticker} ({cat}): {sector} — {record.thesis.rationale[:80]}")
        sectors[sector] = sectors.get(sector, 0) + 1

    lines.append("\nSector exposure:")
    for sector, count in sorted(sectors.items(), key=lambda x: -x[1]):
        lines.append(f"  {sector}: {count} positions")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Debate a single candidate
# ---------------------------------------------------------------------------


def _debate_candidate(
    ticker: str,
    trade_date: str,
    category: str,
    macro_context: str,
    dry_run: bool = False,
) -> dict:
    """Run the full 12-agent debate on a single discovery candidate.

    Returns a result dict with decision, agent text, cost info, etc.
    """
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["deep_think_llm"] = os.getenv("DEEP_LLM_MODEL", "gpt-4o")
    config["quick_think_llm"] = os.getenv("QUICK_LLM_MODEL", "gpt-4o-mini")
    config["data_vendors"] = {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    }

    # Category-based debate rounds
    cat_config = DEFAULT_CONFIG.get("categories", {}).get(category, {})
    debate_rounds = cat_config.get("debate_rounds", 1)
    config["max_debate_rounds"] = debate_rounds
    config["max_risk_discuss_rounds"] = debate_rounds

    result = {
        "ticker": ticker,
        "category": category,
        "decision": "HOLD",
        "agent_decision_text": "",
        "llm_cost": 0.0,
        "llm_tokens_in": 0,
        "llm_tokens_out": 0,
        "error": None,
    }

    # Memory directory
    memory_dir = MEMORY_DIR / ticker
    memory_dir.mkdir(parents=True, exist_ok=True)

    try:
        ta = TradingAgentsGraph(config=config)
        ta.load_memories(str(memory_dir))

        # Discovery candidates have no existing position
        position_context = (
            f"NO CURRENT POSITION in {ticker}. "
            "This is a NEW DISCOVERY CANDIDATE — only BUY or HOLD are actionable. "
            "SELL is not meaningful without an existing position."
        )

        # Run the full pipeline
        logger.info("  Debating %s (%s)...", ticker, category)
        from langchain_community.callbacks import get_openai_callback

        with get_openai_callback() as cb:
            final_state, decision = ta.propagate(
                ticker,
                trade_date,
                position_context=position_context,
                macro_context=macro_context,
            )

        result["decision"] = (decision or "HOLD").upper().strip()
        result["llm_cost"] = cb.total_cost
        result["llm_tokens_in"] = cb.prompt_tokens
        result["llm_tokens_out"] = cb.completion_tokens

        # Extract full agent text
        agent_text = final_state.get("final_trade_decision", "")
        if isinstance(agent_text, list):
            agent_text = "\n".join(str(m) for m in agent_text)
        result["agent_decision_text"] = str(agent_text)

        # Normalize decision
        if result["decision"] not in ("BUY", "SELL", "HOLD"):
            result["decision"] = "HOLD"

        # For discovery, SELL is meaningless — treat as HOLD
        if result["decision"] == "SELL":
            result["decision"] = "HOLD"
            logger.info("  %s: SELL on new candidate → treating as HOLD", ticker)

        # Reflect and save memories
        ta.reflect_and_remember("New discovery candidate — no prior P&L")
        ta.save_memories(str(memory_dir))

    except Exception as exc:
        result["error"] = str(exc)
        result["decision"] = "HOLD"
        logger.error("  %s debate failed: %s", ticker, exc)

    return result


# ---------------------------------------------------------------------------
# Execute BUY
# ---------------------------------------------------------------------------


def _execute_discovery_buy(
    ticker: str,
    category: str,
    agent_text: str,
    amount: float,
    thesis_store,
    dry_run: bool = False,
) -> dict:
    """Execute a BUY order and create a thesis record."""
    from alpaca_bridge import execute_decision
    from tradingagents.thesis import ThesisStore

    cat_config = _get_run_config()
    categories = {
        "CORE": {"base_multiplier": 2.0},
        "TACTICAL": {"base_multiplier": 1.0},
    }
    multiplier = categories.get(category, {}).get("base_multiplier", 1.0)
    effective_amount = amount * multiplier

    result = {
        "ticker": ticker,
        "action": "BUY",
        "amount_usd": effective_amount,
        "order": None,
        "thesis_created": False,
    }

    if dry_run:
        logger.info(
            "  [DRY-RUN] Would BUY %s for $%.2f (%s)",
            ticker, effective_amount, category,
        )
        result["order"] = {"status": "dry_run"}
        return result

    try:
        order = execute_decision(
            ticker, "BUY", effective_amount,
            agent_decision_text=agent_text, tier=category,
        )
        result["order"] = order

        if order and order.get("status") != "error":
            # Create thesis from debate output
            thesis_kwargs = ThesisStore.build_thesis_from_debate(
                ticker=ticker,
                entry_price=order.get("price", 0.0),
                shares=order.get("qty", 0.0),
                position_size_usd=effective_amount,
                research_manager_output=agent_text,
                risk_judge_output=agent_text,
                category=category,
            )
            thesis_store.create_thesis(**thesis_kwargs)
            result["thesis_created"] = True
            logger.info("  Created %s thesis for %s", category, ticker)

    except Exception as exc:
        logger.error("  Failed to execute BUY for %s: %s", ticker, exc)
        result["order"] = {"status": "error", "error": str(exc)}

    return result


# ---------------------------------------------------------------------------
# Main discovery cycle
# ---------------------------------------------------------------------------


def run_discovery(
    amount: float = 1000.0,
    dry_run: bool = False,
    max_candidates: int = 15,
    once: bool = False,
    no_wait: bool = False,
) -> dict:
    """Run one discovery cycle.

    Returns a summary dict with screener stats, debate results, and trades.
    """
    from tradingagents.redis_state import RedisState
    from tradingagents.thesis import ThesisStore
    from tradingagents.research_context import load_latest_research_context
    from screener import (
        ScreenerFilters,
        create_screener,
        exclude_portfolio,
        exclude_cooldown,
        exclude_recently_debated,
    )

    trade_date = get_analysis_date()
    logger.info("=" * 60)
    logger.info("DISCOVERY PIPELINE — %s", trade_date)
    logger.info("=" * 60)

    # Initialize state
    state = RedisState()
    thesis_store = ThesisStore(redis_state=state)

    # --- Stage 1: Daily research ---
    logger.info("[1/6] Running daily research...")
    try:
        from daily_research import run_daily_research
        run_daily_research()
    except Exception as exc:
        logger.warning("Daily research failed (continuing): %s", exc)

    # Load macro context
    macro_context = ""
    try:
        macro_context = load_latest_research_context() or ""
    except Exception:
        pass

    # --- Stage 2: Screen ---
    logger.info("[2/6] Screening all US equities...")
    config = _get_run_config()
    screener = create_screener(config.get("screener_source", "finviz"))

    filters = ScreenerFilters(
        min_market_cap=config.get("min_market_cap", 500_000_000),
        min_price=config.get("min_price", 5.0),
        min_volume_ratio=config.get("min_volume_ratio", 2.0),
        max_raw_candidates=config.get("max_raw_candidates", 100),
        exclude_tickers=thesis_store.get_portfolio_tickers(),
    )

    candidates = screener.scan(filters)
    logger.info("  Screener returned %d raw candidates", len(candidates))

    # --- Stage 3: Exclusions ---
    logger.info("[3/6] Applying exclusions...")
    portfolio_tickers = thesis_store.get_portfolio_tickers()
    candidates = exclude_portfolio(candidates, portfolio_tickers)

    # Cooldown exclusion
    cooldown_tickers = set()
    for ticker in [c.ticker for c in candidates]:
        if state.is_in_cooldown(ticker):
            cooldown_tickers.add(ticker)
    candidates = exclude_cooldown(candidates, cooldown_tickers)

    # Recently debated exclusion
    completed_today = _load_completed_tickers(trade_date)
    lookback_days = config.get("lookback_days", 7)
    recently_debated = set(completed_today)
    for i in range(1, lookback_days):
        past_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        recently_debated |= _load_completed_tickers(past_date)
    candidates = exclude_recently_debated(candidates, recently_debated)

    logger.info("  After exclusions: %d candidates", len(candidates))

    if not candidates:
        logger.info("No candidates after exclusions — nothing to debate")
        return {"date": trade_date, "candidates": 0, "debates": [], "trades": []}

    # --- Stage 4: LLM Filter ---
    logger.info("[4/6] LLM filtering to top %d...", max_candidates)
    portfolio_summary = _build_portfolio_summary(thesis_store)
    selected = _run_llm_filter(candidates, macro_context, portfolio_summary, max_candidates)

    if not selected:
        logger.info("LLM filter returned no candidates")
        return {"date": trade_date, "candidates": len(candidates), "debates": [], "trades": []}

    logger.info("  Selected for debate: %s", ", ".join(s["ticker"] for s in selected))

    # --- Stage 5: Full 12-agent debate ---
    logger.info("[5/6] Running full debate on %d candidates...", len(selected))
    debate_results = []
    buy_decisions = []

    for i, sel in enumerate(selected, 1):
        ticker = sel["ticker"]
        category = sel["category"]

        # Skip if already completed today (crash recovery)
        if ticker in completed_today:
            logger.info("  [%d/%d] %s — already completed (checkpoint), skipping",
                       i, len(selected), ticker)
            continue

        logger.info("[%d/%d] %s (%s)", i, len(selected), ticker, category)
        result = _debate_candidate(
            ticker=ticker,
            trade_date=trade_date,
            category=category,
            macro_context=macro_context,
            dry_run=dry_run,
        )

        debate_results.append(result)
        _save_checkpoint(trade_date, ticker, result)
        state.mark_analyzed_today(ticker)

        if result["decision"] == "BUY":
            buy_decisions.append((ticker, category, result))
            logger.info("  %s → BUY (%s)", ticker, category)
        else:
            logger.info("  %s → %s", ticker, result["decision"])

    # --- Stage 6: Execute BUY orders ---
    logger.info("[6/6] Executing %d BUY orders...", len(buy_decisions))
    trades = []

    for ticker, category, debate_result in buy_decisions:
        trade = _execute_discovery_buy(
            ticker=ticker,
            category=category,
            agent_text=debate_result.get("agent_decision_text", ""),
            amount=amount,
            thesis_store=thesis_store,
            dry_run=dry_run,
        )
        trades.append(trade)
        time.sleep(1)  # pace orders

    # --- Save discovery log ---
    summary = {
        "date": trade_date,
        "screener_source": screener.get_source_name() if hasattr(screener, 'get_source_name') else "unknown",
        "raw_candidates": len(candidates),
        "after_exclusions": len(candidates),
        "llm_filtered": len(selected),
        "debated": len(debate_results),
        "buy_decisions": len(buy_decisions),
        "trades_executed": len([t for t in trades if t.get("thesis_created")]),
        "total_cost": sum(r.get("llm_cost", 0) for r in debate_results),
        "debates": [
            {
                "ticker": r["ticker"],
                "category": r["category"],
                "decision": r["decision"],
                "cost": r.get("llm_cost", 0),
            }
            for r in debate_results
        ],
        "trades": trades,
    }

    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DISCOVERY_DIR / f"{trade_date}.json"
    try:
        log_path.write_text(json.dumps(summary, indent=2, default=str))
        logger.info("Discovery log saved to %s", log_path)
    except Exception as exc:
        logger.error("Failed to save discovery log: %s", exc)

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("DISCOVERY COMPLETE — %s", trade_date)
    logger.info("  Screened: %d → Filtered: %d → Debated: %d → Bought: %d",
               summary["raw_candidates"], summary["llm_filtered"],
               summary["debated"], summary["buy_decisions"])
    logger.info("  Cost: $%.4f", summary["total_cost"])
    logger.info("=" * 60)

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Discovery Pipeline — find new investment candidates")
    parser.add_argument("--once", action="store_true", help="Run one cycle then exit")
    parser.add_argument("--no-wait", action="store_true", help="Skip 9 AM ET wait, run immediately")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, no orders")
    parser.add_argument("--amount", type=float, default=1000.0, help="Base trade size USD")
    parser.add_argument("--max-candidates", type=int, default=15, help="Max candidates for debate")
    args = parser.parse_args()

    if args.no_wait or args.once:
        run_discovery(
            amount=args.amount,
            dry_run=args.dry_run,
            max_candidates=args.max_candidates,
        )
        if args.once:
            return

    # Loop forever, running daily
    while True:
        wait_seconds = seconds_until_next_run()
        if wait_seconds > 0 and not args.no_wait:
            hours = wait_seconds // 3600
            mins = (wait_seconds % 3600) // 60
            logger.info("Next discovery run in %dh %dm", hours, mins)
            time.sleep(wait_seconds)

        run_discovery(
            amount=args.amount,
            dry_run=args.dry_run,
            max_candidates=args.max_candidates,
        )

        if args.once:
            break


if __name__ == "__main__":
    main()
