"""
portfolio_review.py
===================
Staggered weekly process that checks if existing holdings' investment theses
still hold. Reviews 2-4 holdings per day so the entire portfolio is covered
over a 2-4 week window.

Much cheaper than re-debating every ticker daily — only escalates to full
12-agent debate when a thesis is actually broken.

TICKET-110
"""

# ---------------------------------------------------------------------------
# Path setup — MUST be first
# ---------------------------------------------------------------------------
import _path_setup  # noqa: F401
from _path_setup import PROJECT_ROOT, TRADING_LOGS_DIR, MEMORY_DIR

# ---------------------------------------------------------------------------

import argparse
import json
import logging
import os
import time
import urllib3
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

ET = ZoneInfo("America/New_York")

DATA_DIR = PROJECT_ROOT / "data"
REVIEWS_DIR = DATA_DIR / "reviews"


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def _get_review_config() -> dict:
    from tradingagents.default_config import DEFAULT_CONFIG
    return DEFAULT_CONFIG.get("review", {})


def seconds_until_next_run() -> int:
    """Seconds until next 8:00 AM ET weekday."""
    config = _get_review_config()
    run_hour = config.get("run_hour", 8)
    run_minute = config.get("run_minute", 0)

    now = datetime.now(ET)
    target = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)

    if now >= target:
        target += timedelta(days=1)

    while target.weekday() >= 5:
        target += timedelta(days=1)

    return max(0, int((target - now).total_seconds()))


# ---------------------------------------------------------------------------
# Exit rule checks
# ---------------------------------------------------------------------------


def _check_exit_rules(
    ticker: str,
    thesis_record,
    current_price: float,
    trailing_high: float,
) -> dict | None:
    """Check exit rules before thesis review.

    Returns a dict with exit info if triggered, or None.
    """
    entry_price = thesis_record.entry_price
    targets = thesis_record.targets
    category = thesis_record.category.value if hasattr(thesis_record.category, "value") else thesis_record.category

    if entry_price <= 0 or current_price <= 0:
        return None

    pnl_pct = (current_price - entry_price) / entry_price

    # Catastrophic loss: -15%
    if pnl_pct <= -0.15:
        return {
            "rule": "catastrophic_loss",
            "ticker": ticker,
            "pnl_pct": pnl_pct * 100,
            "action": "SELL",
            "reason": f"Down {pnl_pct*100:.1f}% — catastrophic loss threshold hit",
        }

    # Trailing stop: activated at +20%, trail 15%
    activation = targets.trailing_stop_activation
    trail = targets.trailing_stop_trail

    if trailing_high > 0 and entry_price > 0:
        gain_from_entry = (trailing_high - entry_price) / entry_price
        if gain_from_entry >= activation:
            pullback = (trailing_high - current_price) / trailing_high
            if pullback >= trail:
                return {
                    "rule": "trailing_stop",
                    "ticker": ticker,
                    "gain_from_entry": gain_from_entry * 100,
                    "pullback_pct": pullback * 100,
                    "action": "SELL",
                    "reason": f"Trailing stop: gained {gain_from_entry*100:.1f}%, pulled back {pullback*100:.1f}%",
                }

    # Profit target hit
    if targets.price_target > 0 and current_price >= targets.price_target:
        return {
            "rule": "profit_target",
            "ticker": ticker,
            "target": targets.price_target,
            "current": current_price,
            "action": "REVIEW",  # review rather than auto-sell
            "reason": f"Price target ${targets.price_target:.2f} reached",
        }

    # Hold period exceeded
    expected_months = thesis_record.expected_hold_months
    try:
        entry_dt = datetime.strptime(thesis_record.entry_date, "%Y-%m-%d")
        days_held = (datetime.now() - entry_dt).days
        max_days = expected_months * 30

        if days_held > max_days:
            return {
                "rule": "hold_period_exceeded",
                "ticker": ticker,
                "days_held": days_held,
                "max_days": max_days,
                "action": "REVIEW",
                "reason": f"Held {days_held} days (expected max {max_days})",
            }
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Get current price
# ---------------------------------------------------------------------------


def _get_current_price(ticker: str) -> tuple[float, float]:
    """Fetch current price and approximate trailing high.

    Returns (current_price, trailing_high).
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        if hist.empty:
            return 0.0, 0.0
        current = float(hist["Close"].iloc[-1])
        high = float(hist["High"].max())
        return current, high
    except Exception as exc:
        logger.warning("Failed to get price for %s: %s", ticker, exc)
        return 0.0, 0.0


# ---------------------------------------------------------------------------
# Review a single ticker
# ---------------------------------------------------------------------------


def _review_ticker(
    ticker: str,
    thesis_record,
    dry_run: bool = False,
) -> dict:
    """Run thesis review on a single holding.

    Returns a dict with the review outcome and any action taken.
    """
    from tradingagents.review_agents import (
        run_thesis_review,
        run_market_update,
        run_fundamentals_update,
    )

    result = {
        "ticker": ticker,
        "category": thesis_record.category.value if hasattr(thesis_record.category, "value") else thesis_record.category,
        "verdict": None,
        "confidence": 0,
        "action_taken": "none",
        "exit_rule": None,
        "error": None,
    }

    # Get current price
    current_price, trailing_high = _get_current_price(ticker)
    result["current_price"] = current_price
    result["entry_price"] = thesis_record.entry_price
    if thesis_record.entry_price > 0:
        result["pnl_pct"] = (current_price - thesis_record.entry_price) / thesis_record.entry_price * 100
    else:
        result["pnl_pct"] = 0.0

    # Check exit rules first
    exit_trigger = _check_exit_rules(ticker, thesis_record, current_price, trailing_high)
    if exit_trigger and exit_trigger["action"] == "SELL":
        result["exit_rule"] = exit_trigger
        result["verdict"] = "broken"
        result["action_taken"] = "exit_rule_sell"
        logger.info("  %s: EXIT RULE triggered — %s", ticker, exit_trigger["reason"])

        if not dry_run:
            try:
                from alpaca_bridge import execute_decision
                execute_decision(ticker, "SELL", 0, tier=result["category"])
            except Exception as exc:
                logger.error("  Failed to execute exit rule SELL for %s: %s", ticker, exc)
                result["error"] = str(exc)

        return result

    if exit_trigger and exit_trigger["action"] == "REVIEW":
        logger.info("  %s: %s — triggering review", ticker, exit_trigger["reason"])
        result["exit_rule"] = exit_trigger

    # Run lightweight analyst updates
    logger.info("  %s: Running market update...", ticker)
    market_update = run_market_update(ticker)

    logger.info("  %s: Running fundamentals update...", ticker)
    fundamentals_update = run_fundamentals_update(ticker)

    # Build news summary from thesis history
    news_summary = ""
    if thesis_record.history and thesis_record.history.news_events:
        recent = thesis_record.history.news_events[-5:]
        news_lines = [f"- [{e.date}] {e.headline}" for e in recent]
        news_summary = "\n".join(news_lines)

    # Run thesis assessor
    logger.info("  %s: Running thesis assessment...", ticker)
    try:
        review_result = run_thesis_review(
            ticker=ticker,
            thesis_record=thesis_record.model_dump(),
            current_price=current_price,
            trailing_high=trailing_high,
            market_update=market_update,
            fundamentals_update=fundamentals_update,
            news_summary=news_summary,
        )

        result["verdict"] = review_result.verdict
        result["confidence"] = review_result.confidence
        result["reasoning"] = review_result.reasoning
        result["thesis_update"] = review_result.thesis_update
        result["recommended_action"] = review_result.action
        result["stop_loss_update"] = review_result.stop_loss_update

    except Exception as exc:
        logger.error("  Thesis assessment failed for %s: %s", ticker, exc)
        result["verdict"] = "intact"
        result["confidence"] = 3
        result["error"] = str(exc)
        result["action_taken"] = "assessment_failed"
        return result

    # Act on verdict
    if review_result.verdict == "broken" and review_result.action == "SELL":
        if review_result.confidence >= 8:
            result["action_taken"] = "sell"
            logger.info("  %s: THESIS BROKEN (confidence %d) — SELL", ticker, review_result.confidence)
            if not dry_run:
                try:
                    from alpaca_bridge import execute_decision
                    execute_decision(ticker, "SELL", 0, tier=result["category"])
                except Exception as exc:
                    logger.error("  Failed to execute SELL for %s: %s", ticker, exc)
                    result["error"] = str(exc)
        else:
            result["action_taken"] = "flagged_for_debate"
            logger.info("  %s: THESIS BROKEN but low confidence (%d) — flagging for debate",
                       ticker, review_result.confidence)

    elif review_result.verdict == "weakening":
        result["action_taken"] = "weakening_flagged"
        logger.info("  %s: THESIS WEAKENING — accelerating review", ticker)
        if review_result.action == "TIGHTEN_STOP" and review_result.stop_loss_update:
            result["action_taken"] = "tighten_stop"

    else:
        result["action_taken"] = "hold"
        logger.info("  %s: THESIS INTACT (confidence %d)", ticker, review_result.confidence)

    return result


# ---------------------------------------------------------------------------
# Main review cycle
# ---------------------------------------------------------------------------


def run_portfolio_review(
    dry_run: bool = False,
    ticker: str | None = None,
    all_holdings: bool = False,
    max_reviews: int | None = None,
) -> list[dict]:
    """Run the portfolio review cycle.

    Args:
        dry_run: If True, assess only, no trades.
        ticker: Review a specific ticker only.
        all_holdings: Review all holdings today (override schedule).
        max_reviews: Override max reviews per day.

    Returns:
        List of review outcome dicts.
    """
    from tradingagents.redis_state import RedisState
    from tradingagents.thesis import ThesisStore

    config = _get_review_config()
    state = RedisState()
    thesis_store = ThesisStore(redis_state=state)

    logger.info("=" * 60)
    logger.info("PORTFOLIO REVIEW — %s", datetime.now(ET).strftime("%Y-%m-%d"))
    logger.info("=" * 60)

    # Determine which tickers to review
    if ticker:
        # Single ticker review
        record = thesis_store.get_thesis(ticker)
        if record is None:
            logger.error("No thesis found for %s", ticker)
            return []
        to_review = [record]
        logger.info("Reviewing specific ticker: %s", ticker)

    elif all_holdings:
        # Review everything
        to_review = list(thesis_store.get_all_theses().values())
        logger.info("Reviewing all %d holdings", len(to_review))

    else:
        # Staggered schedule
        today = datetime.now().strftime("%Y-%m-%d")
        to_review = thesis_store.get_due_for_review(today)

        # Also include accelerated review flags from news monitor
        review_flags = state.pop_review_flags()
        flagged_tickers = {f["ticker"] for f in review_flags}
        for ft in flagged_tickers:
            record = thesis_store.get_thesis(ft)
            if record and record not in to_review:
                to_review.append(record)
                logger.info("  Added %s from review queue (news flagged)", ft)

        # Cap daily reviews
        daily_max = max_reviews or config.get("max_reviews_per_day", 4)
        if len(to_review) > daily_max:
            logger.info("  Capping from %d to %d reviews", len(to_review), daily_max)
            to_review = to_review[:daily_max]

        logger.info("Scheduled %d reviews for today", len(to_review))

    if not to_review:
        logger.info("No reviews due today")
        return []

    # Run reviews
    outcomes = []
    for i, record in enumerate(to_review, 1):
        t = record.ticker
        cat = record.category.value if hasattr(record.category, "value") else record.category
        logger.info("[%d/%d] Reviewing %s (%s)...", i, len(to_review), t, cat)

        outcome = _review_ticker(t, record, dry_run=dry_run)
        outcomes.append(outcome)

        # Update thesis store based on outcome
        if outcome["verdict"] and not dry_run:
            thesis_store.add_review(
                t,
                verdict=outcome["verdict"],
                confidence=outcome.get("confidence", 5),
                reasoning=outcome.get("reasoning", ""),
                action_taken=outcome.get("action_taken", ""),
            )

            # Accelerate review if weakening
            if outcome["verdict"] == "weakening":
                recheck_days = config.get("weakening_recheck_days", 3)
                thesis_store.accelerate_review(t, days=recheck_days)

            # Check for escalation (2+ consecutive weakening)
            escalation_threshold = config.get("escalation_threshold", 2)
            updated = thesis_store.get_thesis(t)
            if updated and updated.review.consecutive_weakening >= escalation_threshold:
                logger.warning("  %s: %d consecutive weakening reviews — needs full debate",
                             t, updated.review.consecutive_weakening)
                state.push_review_flag(t, reason="consecutive_weakening_escalation")

            # Tighten stop if recommended
            if outcome.get("stop_loss_update") and outcome["action_taken"] == "tighten_stop":
                thesis_store.update_thesis(t, targets__stop_loss=outcome["stop_loss_update"])
                logger.info("  %s: Stop tightened to $%.2f", t, outcome["stop_loss_update"])

            # Remove thesis on sell
            if outcome["action_taken"] in ("sell", "exit_rule_sell"):
                thesis_store.remove_thesis(t)
                state.set_cooldown(t, days=7)

        # Save individual review report
        _save_review_report(t, outcome)

    # Save summary
    _save_review_summary(outcomes)

    # Print summary
    logger.info("=" * 60)
    logger.info("REVIEW COMPLETE — %d holdings reviewed", len(outcomes))
    verdicts = {}
    for o in outcomes:
        v = o.get("verdict", "unknown")
        verdicts[v] = verdicts.get(v, 0) + 1
    for v, count in sorted(verdicts.items()):
        logger.info("  %s: %d", v.upper(), count)
    logger.info("=" * 60)

    return outcomes


# ---------------------------------------------------------------------------
# Report saving
# ---------------------------------------------------------------------------


def _save_review_report(ticker: str, outcome: dict) -> None:
    """Save a per-ticker review report."""
    today = datetime.now().strftime("%Y-%m-%d")
    review_dir = REVIEWS_DIR / ticker
    review_dir.mkdir(parents=True, exist_ok=True)
    path = review_dir / f"{today}.json"
    try:
        path.write_text(json.dumps(outcome, indent=2, default=str))
    except Exception as exc:
        logger.warning("Failed to save review report for %s: %s", ticker, exc)


def _save_review_summary(outcomes: list[dict]) -> None:
    """Save the daily review summary."""
    today = datetime.now().strftime("%Y-%m-%d")
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    path = REVIEWS_DIR / f"{today}-summary.json"
    try:
        path.write_text(json.dumps(outcomes, indent=2, default=str))
    except Exception as exc:
        logger.warning("Failed to save review summary: %s", exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Portfolio Review — staggered thesis checks")
    parser.add_argument("--all", action="store_true", help="Review all holdings today")
    parser.add_argument("--ticker", type=str, help="Review a specific ticker")
    parser.add_argument("--dry-run", action="store_true", help="Assess only, no trades")
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    parser.add_argument("--no-wait", action="store_true", help="Skip 8 AM ET wait")
    parser.add_argument("--max-reviews", type=int, help="Override max reviews per day")
    args = parser.parse_args()

    if args.no_wait or args.once or args.ticker or args.all:
        run_portfolio_review(
            dry_run=args.dry_run,
            ticker=args.ticker,
            all_holdings=args.all,
            max_reviews=args.max_reviews,
        )
        if args.once or args.ticker:
            return

    # Loop forever, running daily
    while True:
        wait_seconds = seconds_until_next_run()
        if wait_seconds > 0 and not args.no_wait:
            hours = wait_seconds // 3600
            mins = (wait_seconds % 3600) // 60
            logger.info("Next review run in %dh %dm", hours, mins)
            time.sleep(wait_seconds)

        run_portfolio_review(
            dry_run=args.dry_run,
            all_holdings=args.all,
            max_reviews=args.max_reviews,
        )

        if args.once:
            break


if __name__ == "__main__":
    main()
