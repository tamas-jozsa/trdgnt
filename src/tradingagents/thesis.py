"""Thesis data model and storage for thesis-driven investing.

Every position has a thesis — why we bought it, what catalysts to watch, and
what would invalidate the investment. Reviews and news reactions are always
assessed against this thesis.

TICKET-106
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from .redis_state import RedisState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PositionCategory(str, Enum):
    CORE = "CORE"  # 6-12 month hold, 2.0x base
    TACTICAL = "TACTICAL"  # 1-3 month hold, 1.0x base


CATEGORY_DEFAULTS = {
    PositionCategory.CORE: {
        "hold_months_min": 6,
        "hold_months_max": 12,
        "base_multiplier": 2.0,
        "review_interval_days": 14,
        "debate_rounds": 2,
        "size_limits": {"min": 0.5, "max": 2.0},
    },
    PositionCategory.TACTICAL: {
        "hold_months_min": 1,
        "hold_months_max": 3,
        "base_multiplier": 1.0,
        "review_interval_days": 7,
        "debate_rounds": 1,
        "size_limits": {"min": 0.25, "max": 1.5},
    },
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ThesisCore(BaseModel):
    """The investment thesis itself."""

    rationale: str = Field(description="Why we bought this stock")
    key_catalysts: list[str] = Field(
        default_factory=list,
        description="Specific events/trends we expect to drive the price",
    )
    invalidation_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that would break the thesis and trigger a sell",
    )
    sector: str = ""
    macro_theme: str = ""


class ThesisTargets(BaseModel):
    """Price targets and stop-loss levels."""

    price_target: float = 0.0
    stop_loss: float = 0.0
    trailing_stop_activation: float = 0.20  # activate at 20% gain
    trailing_stop_trail: float = 0.15  # sell on 15% pullback from high


class ReviewEntry(BaseModel):
    """A single review verdict."""

    date: str
    verdict: Literal["intact", "weakening", "broken"]
    confidence: int = 5
    reasoning: str = ""
    action_taken: str = ""


class NewsEventEntry(BaseModel):
    """A material news event assessed against the thesis."""

    date: str
    headline: str
    severity: str = ""  # low / medium / high / critical
    assessment: str = ""
    action_taken: str = ""


class ThesisHistory(BaseModel):
    """Accumulated history of reviews and news events."""

    review_history: list[ReviewEntry] = Field(default_factory=list)
    news_events: list[NewsEventEntry] = Field(default_factory=list)
    thesis_updates: list[dict] = Field(default_factory=list)


class ThesisReviewState(BaseModel):
    """Scheduling state for periodic reviews."""

    next_review_date: str = ""
    review_interval_days: int = 14
    review_count: int = 0
    last_verdict: str | None = None  # intact | weakening | broken
    consecutive_weakening: int = 0


class ThesisRecord(BaseModel):
    """Complete position record with thesis, targets, and review state.

    This is the central data structure. Every held position has one.
    """

    ticker: str
    entry_date: str
    entry_price: float
    shares: float = 0.0
    position_size_usd: float = 0.0
    category: PositionCategory
    expected_hold_months: int = 6
    thesis: ThesisCore
    targets: ThesisTargets = Field(default_factory=ThesisTargets)
    review: ThesisReviewState = Field(default_factory=ThesisReviewState)
    history: ThesisHistory = Field(default_factory=ThesisHistory)


# ---------------------------------------------------------------------------
# ThesisStore — CRUD over RedisState
# ---------------------------------------------------------------------------


class ThesisStore:
    """High-level CRUD for thesis records, backed by RedisState.

    Usage::

        store = ThesisStore()
        record = store.create_thesis("NVDA", entry_price=142.5, ...)
        print(store.get_thesis("NVDA"))
        store.add_review("NVDA", "intact", 8, "Thesis on track")
    """

    def __init__(self, redis_state: RedisState | None = None):
        self._state = redis_state or RedisState()

    # ----- Create / Read / Update / Delete -----

    def create_thesis(
        self,
        ticker: str,
        entry_price: float,
        category: PositionCategory | str,
        rationale: str,
        catalysts: list[str] | None = None,
        invalidation: list[str] | None = None,
        sector: str = "",
        macro_theme: str = "",
        target: float = 0.0,
        stop_loss: float = 0.0,
        shares: float = 0.0,
        position_size_usd: float = 0.0,
        expected_hold_months: int | None = None,
    ) -> ThesisRecord:
        """Create a new thesis for a position opened by the discovery pipeline."""
        if isinstance(category, str):
            category = PositionCategory(category.upper())

        defaults = CATEGORY_DEFAULTS[category]
        if expected_hold_months is None:
            expected_hold_months = defaults["hold_months_min"]

        today = datetime.now().strftime("%Y-%m-%d")
        review_interval = defaults["review_interval_days"]
        next_review = (datetime.now() + timedelta(days=review_interval)).strftime(
            "%Y-%m-%d"
        )

        record = ThesisRecord(
            ticker=ticker,
            entry_date=today,
            entry_price=entry_price,
            shares=shares,
            position_size_usd=position_size_usd,
            category=category,
            expected_hold_months=expected_hold_months,
            thesis=ThesisCore(
                rationale=rationale,
                key_catalysts=catalysts or [],
                invalidation_conditions=invalidation or [],
                sector=sector,
                macro_theme=macro_theme,
            ),
            targets=ThesisTargets(
                price_target=target,
                stop_loss=stop_loss,
            ),
            review=ThesisReviewState(
                next_review_date=next_review,
                review_interval_days=review_interval,
            ),
        )

        self._state.set_position(ticker, record.model_dump())
        logger.info(
            "Created %s thesis for %s (entry $%.2f, target $%.2f, stop $%.2f)",
            category.value,
            ticker,
            entry_price,
            target,
            stop_loss,
        )
        return record

    def get_thesis(self, ticker: str) -> ThesisRecord | None:
        """Retrieve a thesis by ticker, or None if not held."""
        data = self._state.get_position(ticker)
        if data is None:
            return None
        try:
            return ThesisRecord.model_validate(data)
        except Exception as exc:
            logger.error("Failed to parse thesis for %s: %s", ticker, exc)
            return None

    def get_all_theses(self) -> dict[str, ThesisRecord]:
        """Return all held positions as {ticker: ThesisRecord}."""
        positions = self._state.get_positions()
        result = {}
        for ticker, data in positions.items():
            try:
                result[ticker] = ThesisRecord.model_validate(data)
            except Exception as exc:
                logger.error("Failed to parse thesis for %s: %s", ticker, exc)
        return result

    def get_portfolio_tickers(self) -> set[str]:
        """Return the set of all held tickers."""
        return self._state.get_portfolio_tickers()

    def update_thesis(self, ticker: str, **updates) -> ThesisRecord | None:
        """Partial update of a thesis record.

        Supports nested updates via dotted keys:
            store.update_thesis("NVDA", targets__stop_loss=130.0)
        """
        record = self.get_thesis(ticker)
        if record is None:
            logger.warning("Cannot update thesis for %s — not found", ticker)
            return None

        data = record.model_dump()
        for key, value in updates.items():
            parts = key.split("__")
            d = data
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value

        try:
            updated = ThesisRecord.model_validate(data)
            self._state.set_position(ticker, updated.model_dump())
            return updated
        except Exception as exc:
            logger.error("Failed to update thesis for %s: %s", ticker, exc)
            return None

    def remove_thesis(self, ticker: str) -> None:
        """Remove a thesis when a position is sold."""
        self._state.remove_position(ticker)
        logger.info("Removed thesis for %s", ticker)

    # ----- Review operations -----

    def add_review(
        self,
        ticker: str,
        verdict: str,
        confidence: int = 5,
        reasoning: str = "",
        action_taken: str = "",
    ) -> ThesisRecord | None:
        """Append a review verdict and update scheduling."""
        record = self.get_thesis(ticker)
        if record is None:
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        entry = ReviewEntry(
            date=today,
            verdict=verdict,
            confidence=confidence,
            reasoning=reasoning,
            action_taken=action_taken,
        )
        record.history.review_history.append(entry)
        record.review.review_count += 1
        record.review.last_verdict = verdict

        # Update consecutive weakening counter
        if verdict == "weakening":
            record.review.consecutive_weakening += 1
        else:
            record.review.consecutive_weakening = 0

        # Schedule next review based on verdict
        if verdict == "weakening":
            interval = 3  # Accelerated review
        elif verdict == "broken":
            interval = 0  # No future review needed (position will be sold)
        else:
            interval = record.review.review_interval_days

        if interval > 0:
            next_date = (datetime.now() + timedelta(days=interval)).strftime("%Y-%m-%d")
            record.review.next_review_date = next_date

        self._state.set_position(ticker, record.model_dump())
        logger.info(
            "Review %s: %s (confidence %d) — next review %s",
            ticker,
            verdict,
            confidence,
            record.review.next_review_date,
        )
        return record

    def add_news_event(
        self,
        ticker: str,
        headline: str,
        severity: str = "",
        assessment: str = "",
        action_taken: str = "",
    ) -> ThesisRecord | None:
        """Record a material news event against a position's thesis."""
        record = self.get_thesis(ticker)
        if record is None:
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        event = NewsEventEntry(
            date=today,
            headline=headline,
            severity=severity,
            assessment=assessment,
            action_taken=action_taken,
        )
        record.history.news_events.append(event)

        # Keep news history bounded
        if len(record.history.news_events) > 100:
            record.history.news_events = record.history.news_events[-100:]

        self._state.set_position(ticker, record.model_dump())
        return record

    def accelerate_review(self, ticker: str, days: int = 3) -> ThesisRecord | None:
        """Bring forward the next review date (e.g., after concerning news)."""
        record = self.get_thesis(ticker)
        if record is None:
            return None

        next_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        record.review.next_review_date = next_date
        self._state.set_position(ticker, record.model_dump())
        logger.info("Accelerated review for %s to %s", ticker, next_date)
        return record

    # ----- Query helpers -----

    def get_due_for_review(self, date: str | None = None) -> list[ThesisRecord]:
        """Return theses whose next_review_date <= the given date."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        all_theses = self.get_all_theses()
        due = []
        for record in all_theses.values():
            if record.review.next_review_date and record.review.next_review_date <= date:
                due.append(record)
        # Sort: TACTICAL first (more time-sensitive), then by next_review_date
        due.sort(
            key=lambda r: (
                0 if r.category == PositionCategory.TACTICAL else 1,
                r.review.next_review_date,
            )
        )
        return due

    def get_by_category(self, category: PositionCategory | str) -> list[ThesisRecord]:
        """Return all theses of a given category."""
        if isinstance(category, str):
            category = PositionCategory(category.upper())
        return [
            r for r in self.get_all_theses().values() if r.category == category
        ]

    def get_weakening(self) -> list[ThesisRecord]:
        """Return theses with last_verdict == 'weakening'."""
        return [
            r
            for r in self.get_all_theses().values()
            if r.review.last_verdict == "weakening"
        ]

    def get_needs_escalation(self) -> list[ThesisRecord]:
        """Return theses weakening for 2+ consecutive reviews (need full debate)."""
        return [
            r
            for r in self.get_all_theses().values()
            if r.review.consecutive_weakening >= 2
        ]

    # ----- Thesis generation from debate output -----

    @staticmethod
    def build_thesis_from_debate(
        ticker: str,
        entry_price: float,
        shares: float,
        position_size_usd: float,
        research_manager_output: str,
        risk_judge_output: str,
        category: PositionCategory | str = PositionCategory.TACTICAL,
        sector: str = "",
        macro_theme: str = "",
    ) -> dict:
        """Extract thesis fields from debate pipeline output.

        Returns a kwargs dict suitable for ``create_thesis()``.
        Does not call create_thesis — the caller decides when to persist.
        """
        if isinstance(category, str):
            category = PositionCategory(category.upper())

        # Extract rationale (first substantial paragraph from Research Manager)
        rationale = _extract_rationale(research_manager_output)

        # Extract catalysts (look for bullet points or numbered lists)
        catalysts = _extract_list_items(
            research_manager_output, patterns=["catalyst", "driver", "upside"]
        )

        # Extract invalidation conditions
        invalidation = _extract_list_items(
            research_manager_output, patterns=["risk", "invalidat", "downside", "threat"]
        )
        invalidation += _extract_list_items(
            risk_judge_output, patterns=["risk", "concern", "warning"]
        )
        # Deduplicate
        invalidation = list(dict.fromkeys(invalidation))[:5]

        # Extract price target from Risk Judge
        target = _extract_price(risk_judge_output, "TARGET")

        # Extract stop-loss from Risk Judge
        stop_loss = _extract_price(risk_judge_output, "STOP")

        # Determine hold period from category defaults
        defaults = CATEGORY_DEFAULTS[category]
        expected_hold = defaults["hold_months_min"]

        return {
            "ticker": ticker,
            "entry_price": entry_price,
            "category": category,
            "rationale": rationale or f"Investment in {ticker} based on multi-agent analysis",
            "catalysts": catalysts[:5],
            "invalidation": invalidation[:5],
            "sector": sector,
            "macro_theme": macro_theme,
            "target": target,
            "stop_loss": stop_loss,
            "shares": shares,
            "position_size_usd": position_size_usd,
            "expected_hold_months": expected_hold,
        }


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_rationale(text: str) -> str:
    """Extract the main investment rationale from Research Manager output."""
    if not text:
        return ""

    # Look for explicit recommendation/rationale section
    for marker in [
        "RECOMMENDATION:",
        "INVESTMENT PLAN:",
        "RATIONALE:",
        "THESIS:",
        "**Recommendation",
        "**Investment Plan",
    ]:
        idx = text.upper().find(marker.upper())
        if idx >= 0:
            block = text[idx + len(marker) :].strip()
            # Take up to 500 chars or first double-newline
            end = block.find("\n\n")
            if end > 0:
                block = block[:end]
            return block[:500].strip()

    # Fallback: first paragraph with 50+ chars
    for para in text.split("\n\n"):
        cleaned = para.strip()
        if len(cleaned) >= 50:
            return cleaned[:500]

    return text[:500].strip()


def _extract_list_items(text: str, patterns: list[str]) -> list[str]:
    """Extract bullet-point items near pattern-matching headings."""
    if not text:
        return []

    items = []
    lines = text.split("\n")

    # Find sections matching any pattern
    in_section = False
    for line in lines:
        lower = line.lower().strip()

        # Check if this line is a heading matching our patterns
        if any(p in lower for p in patterns) and (
            lower.startswith("#")
            or lower.startswith("**")
            or lower.endswith(":")
        ):
            in_section = True
            continue

        # If we're in a matching section, collect bullet items
        if in_section:
            # Stop at next heading
            if lower.startswith("#") or (lower.startswith("**") and lower.endswith("**")):
                in_section = False
                continue

            # Collect bullet points
            stripped = line.strip()
            if stripped.startswith(("-", "*", "•")) or re.match(r"^\d+[\.\)]\s", stripped):
                clean = re.sub(r"^[-*•\d.\)]+\s*", "", stripped).strip()
                if len(clean) > 10:
                    items.append(clean[:200])

    return items


def _extract_price(text: str, label: str) -> float:
    """Extract a price value after a label like 'TARGET:' or 'STOP-LOSS:'."""
    if not text:
        return 0.0

    # Try patterns like "TARGET: $185.00" or "STOP-LOSS: $120.00"
    for pattern in [
        rf"{label}[:\s]*\$?([\d,.]+)",
        rf"{label}[-\s]*LOSS[:\s]*\$?([\d,.]+)",
        rf"{label}[-\s]*PRICE[:\s]*\$?([\d,.]+)",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except (ValueError, IndexError):
                pass
    return 0.0
