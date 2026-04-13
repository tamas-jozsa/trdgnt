"""Tests for thesis.py — thesis data model and storage.

TICKET-113
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tradingagents.thesis import (
    ThesisRecord,
    ThesisCore,
    ThesisTargets,
    ThesisReviewState,
    ThesisHistory,
    ThesisStore,
    PositionCategory,
    CATEGORY_DEFAULTS,
    _extract_rationale,
    _extract_price,
    _extract_list_items,
)


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestThesisModels:
    def test_thesis_record_minimal(self):
        record = ThesisRecord(
            ticker="NVDA",
            entry_date="2026-04-10",
            entry_price=142.5,
            category=PositionCategory.CORE,
            thesis=ThesisCore(rationale="AI infrastructure play"),
        )
        assert record.ticker == "NVDA"
        assert record.category == PositionCategory.CORE
        assert record.expected_hold_months == 6
        assert record.targets.price_target == 0.0

    def test_thesis_record_full(self):
        record = ThesisRecord(
            ticker="NVDA",
            entry_date="2026-04-10",
            entry_price=142.5,
            shares=14.035,
            position_size_usd=2000,
            category=PositionCategory.TACTICAL,
            expected_hold_months=3,
            thesis=ThesisCore(
                rationale="Earnings catalyst",
                key_catalysts=["Q2 earnings"],
                invalidation_conditions=["Revenue miss"],
                sector="Technology",
            ),
            targets=ThesisTargets(price_target=185.0, stop_loss=120.0),
        )
        assert record.shares == 14.035
        assert record.targets.price_target == 185.0
        assert len(record.thesis.key_catalysts) == 1

    def test_serialization_roundtrip(self):
        record = ThesisRecord(
            ticker="AAPL",
            entry_date="2026-04-10",
            entry_price=200.0,
            category=PositionCategory.CORE,
            thesis=ThesisCore(rationale="Ecosystem moat"),
        )
        data = record.model_dump()
        restored = ThesisRecord.model_validate(data)
        assert restored.ticker == "AAPL"
        assert restored.thesis.rationale == "Ecosystem moat"

    def test_category_defaults(self):
        core = CATEGORY_DEFAULTS[PositionCategory.CORE]
        assert core["base_multiplier"] == 2.0
        assert core["review_interval_days"] == 14

        tactical = CATEGORY_DEFAULTS[PositionCategory.TACTICAL]
        assert tactical["base_multiplier"] == 1.0
        assert tactical["review_interval_days"] == 7


# ---------------------------------------------------------------------------
# ThesisStore tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_state():
    """Mock RedisState for ThesisStore tests."""
    state = MagicMock()
    state.get_positions.return_value = {}
    state.get_position.return_value = None
    state.get_portfolio_tickers.return_value = set()
    return state


@pytest.fixture
def store(mock_redis_state):
    return ThesisStore(redis_state=mock_redis_state)


class TestThesisStore:
    def test_create_thesis(self, store, mock_redis_state):
        record = store.create_thesis(
            ticker="NVDA",
            entry_price=142.5,
            category="CORE",
            rationale="AI play",
            catalysts=["Q2 earnings"],
            invalidation=["Revenue miss"],
            target=185.0,
            stop_loss=120.0,
        )
        assert record.ticker == "NVDA"
        assert record.category == PositionCategory.CORE
        assert record.targets.price_target == 185.0
        assert record.review.review_interval_days == 14

        # Should have called set_position
        mock_redis_state.set_position.assert_called_once()
        call_args = mock_redis_state.set_position.call_args
        assert call_args[0][0] == "NVDA"

    def test_get_thesis(self, store, mock_redis_state):
        thesis_data = ThesisRecord(
            ticker="AAPL",
            entry_date="2026-04-10",
            entry_price=200.0,
            category=PositionCategory.TACTICAL,
            thesis=ThesisCore(rationale="test"),
        ).model_dump()

        mock_redis_state.get_position.return_value = thesis_data
        result = store.get_thesis("AAPL")
        assert result is not None
        assert result.ticker == "AAPL"

    def test_get_thesis_not_found(self, store, mock_redis_state):
        mock_redis_state.get_position.return_value = None
        assert store.get_thesis("NOPE") is None

    def test_add_review_intact(self, store, mock_redis_state):
        thesis_data = ThesisRecord(
            ticker="NVDA",
            entry_date="2026-04-10",
            entry_price=142.5,
            category=PositionCategory.CORE,
            thesis=ThesisCore(rationale="test"),
            review=ThesisReviewState(next_review_date="2026-04-20", review_interval_days=14),
        ).model_dump()

        mock_redis_state.get_position.return_value = thesis_data
        result = store.add_review("NVDA", "intact", confidence=8, reasoning="On track")

        assert result is not None
        assert result.review.review_count == 1
        assert result.review.last_verdict == "intact"
        assert result.review.consecutive_weakening == 0

    def test_add_review_weakening(self, store, mock_redis_state):
        thesis_data = ThesisRecord(
            ticker="NVDA",
            entry_date="2026-04-10",
            entry_price=142.5,
            category=PositionCategory.CORE,
            thesis=ThesisCore(rationale="test"),
        ).model_dump()

        mock_redis_state.get_position.return_value = thesis_data
        result = store.add_review("NVDA", "weakening", confidence=6, reasoning="Slowing")

        assert result.review.consecutive_weakening == 1
        # Next review should be accelerated (3 days, not 14)
        expected_min = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        expected_max = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
        assert expected_min <= result.review.next_review_date <= expected_max

    def test_get_due_for_review(self, store, mock_redis_state):
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        positions = {
            "NVDA": ThesisRecord(
                ticker="NVDA", entry_date="2026-03-01", entry_price=140,
                category=PositionCategory.CORE,
                thesis=ThesisCore(rationale="test"),
                review=ThesisReviewState(next_review_date=yesterday),
            ).model_dump(),
            "AAPL": ThesisRecord(
                ticker="AAPL", entry_date="2026-03-01", entry_price=200,
                category=PositionCategory.TACTICAL,
                thesis=ThesisCore(rationale="test"),
                review=ThesisReviewState(next_review_date=tomorrow),
            ).model_dump(),
        }
        mock_redis_state.get_positions.return_value = positions

        due = store.get_due_for_review(today)
        assert len(due) == 1
        assert due[0].ticker == "NVDA"


# ---------------------------------------------------------------------------
# Text extraction tests
# ---------------------------------------------------------------------------


class TestTextExtraction:
    def test_extract_rationale_with_marker(self):
        text = "Some preamble\nRECOMMENDATION: Buy NVDA for AI infrastructure growth.\n\nMore text"
        result = _extract_rationale(text)
        assert "NVDA" in result
        assert "AI" in result

    def test_extract_rationale_fallback(self):
        text = "This is a long enough paragraph that should be extracted as the rationale for the investment decision."
        result = _extract_rationale(text)
        assert len(result) > 0

    def test_extract_price_target(self):
        text = "TARGET: $185.00\nSTOP-LOSS: $120.50"
        assert _extract_price(text, "TARGET") == 185.0
        assert _extract_price(text, "STOP") == 120.5

    def test_extract_price_no_match(self):
        assert _extract_price("no prices here", "TARGET") == 0.0
        assert _extract_price("", "TARGET") == 0.0

    def test_extract_list_items(self):
        text = """## Key Catalysts
- Q2 earnings expected to beat
- Blackwell GPU ramp in Q3
- Hyperscaler capex growth

## Risks
- Competition from AMD
- Regulatory concerns
"""
        catalysts = _extract_list_items(text, ["catalyst"])
        assert len(catalysts) >= 2

        risks = _extract_list_items(text, ["risk"])
        assert len(risks) >= 1
