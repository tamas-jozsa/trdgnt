"""Tests for review_agents.py — thesis assessor and quick assessment.

TICKET-113
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tradingagents.review_agents import (
    ReviewResult,
    AssessmentResult,
    _parse_review_result,
    _parse_assessment_result,
)


class TestParseReviewResult:
    def test_intact_verdict(self):
        text = """VERDICT: INTACT
CONFIDENCE: 8
REASONING: Thesis remains strong, all catalysts on track
THESIS_UPDATE: none
ACTION: HOLD
STOP_LOSS_UPDATE: none"""

        result = _parse_review_result("NVDA", text)
        assert result.verdict == "intact"
        assert result.confidence == 8
        assert result.action == "HOLD"
        assert result.stop_loss_update is None

    def test_weakening_verdict(self):
        text = """VERDICT: WEAKENING
CONFIDENCE: 6
REASONING: Revenue growth decelerating, competitor gaining share
THESIS_UPDATE: Adjusted growth expectations downward
ACTION: TIGHTEN_STOP
STOP_LOSS_UPDATE: $130.00"""

        result = _parse_review_result("NVDA", text)
        assert result.verdict == "weakening"
        assert result.confidence == 6
        assert result.action == "TIGHTEN_STOP"
        assert result.stop_loss_update == 130.0
        assert result.thesis_update is not None

    def test_broken_verdict(self):
        text = """VERDICT: BROKEN
CONFIDENCE: 9
REASONING: Key customer cut capex guidance by 30%, directly invalidating our thesis
THESIS_UPDATE: Thesis invalidated
ACTION: SELL
STOP_LOSS_UPDATE: none"""

        result = _parse_review_result("NVDA", text)
        assert result.verdict == "broken"
        assert result.confidence == 9
        assert result.action == "SELL"

    def test_malformed_output_defaults(self):
        text = "Some random text without proper format"
        result = _parse_review_result("NVDA", text)
        assert result.verdict == "intact"  # default
        assert result.confidence == 5  # default
        assert result.action == "HOLD"  # default

    def test_confidence_clamped(self):
        text = "VERDICT: INTACT\nCONFIDENCE: 15\nACTION: HOLD"
        result = _parse_review_result("NVDA", text)
        assert result.confidence == 10  # clamped to max

        text2 = "VERDICT: INTACT\nCONFIDENCE: 0\nACTION: HOLD"
        result2 = _parse_review_result("NVDA", text2)
        assert result2.confidence == 1  # clamped to min


class TestParseAssessmentResult:
    def test_negative_impact(self):
        text = """BULL VIEW: The company's diversified revenue base limits exposure
BEAR VIEW: This directly threatens the main growth driver identified in our thesis
NET IMPACT: negative
SEVERITY: upgrade_to_high
REASONING: News directly affects key catalyst"""

        result = _parse_assessment_result("NVDA", text)
        assert result.net_impact == "negative"
        assert result.severity_reassessment == "upgrade_to_high"
        assert "diversified" in result.bull_view

    def test_neutral_impact(self):
        text = """BULL VIEW: Sector rotation could benefit our position
BEAR VIEW: Minor headwinds but nothing thesis-breaking
NET IMPACT: neutral
SEVERITY: keep_medium
REASONING: Not material to our thesis"""

        result = _parse_assessment_result("NVDA", text)
        assert result.net_impact == "neutral"
        assert result.severity_reassessment == "keep_medium"

    def test_positive_impact(self):
        text = """BULL VIEW: This validates our core thesis
BEAR VIEW: Some execution risk remains
NET IMPACT: positive
SEVERITY: keep_medium
REASONING: Positive for our position"""

        result = _parse_assessment_result("NVDA", text)
        assert result.net_impact == "positive"
