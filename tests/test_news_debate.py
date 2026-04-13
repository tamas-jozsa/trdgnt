"""Tests for news_debate.py — news-specific graduated response pipeline.

TICKET-113
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tradingagents.news_debate import (
    NewsSeverity,
    TriageResult,
    NewsTradeDecision,
    _parse_triage_results,
    _extract_conviction,
    _build_triage_result,
)


class TestNewsSeverity:
    def test_values(self):
        assert NewsSeverity.LOW.value == "low"
        assert NewsSeverity.CRITICAL.value == "critical"


class TestParseTriage:
    def test_parse_single_result(self):
        text = """---
HEADLINE: NVDA Q2 guidance cut
AFFECTED: NVDA, AMD
SEVERITY: HIGH
SENTIMENT: negative
REASONING: Direct impact on AI thesis
---"""
        results = _parse_triage_results(text, [])
        assert len(results) == 1
        assert results[0].severity == NewsSeverity.HIGH
        assert "NVDA" in results[0].affected_tickers
        assert "AMD" in results[0].affected_tickers

    def test_parse_multiple_results(self):
        text = """---
HEADLINE: Routine analyst note
AFFECTED: NONE
SEVERITY: LOW
SENTIMENT: neutral
REASONING: No impact
---
---
HEADLINE: Major earnings miss
AFFECTED: AAPL
SEVERITY: HIGH
SENTIMENT: negative
REASONING: Revenue below expectations
---"""
        results = _parse_triage_results(text, [])
        assert len(results) == 2
        assert results[0].severity == NewsSeverity.LOW
        assert results[0].affected_tickers == []
        assert results[1].severity == NewsSeverity.HIGH
        assert results[1].affected_tickers == ["AAPL"]

    def test_parse_critical_severity(self):
        text = """---
HEADLINE: Fraud allegation
AFFECTED: XYZ
SEVERITY: CRITICAL
SENTIMENT: negative
REASONING: Immediate thesis threat
---"""
        results = _parse_triage_results(text, [])
        assert results[0].severity == NewsSeverity.CRITICAL

    def test_parse_empty_text(self):
        results = _parse_triage_results("", [])
        assert results == []


class TestBuildTriageResult:
    def test_builds_correctly(self):
        data = {
            "headline": "Test headline",
            "affected": ["NVDA", "AMD"],
            "severity": "high",
            "sentiment": "negative",
            "reasoning": "Test reasoning",
        }
        result = _build_triage_result(data)
        assert result.headline == "Test headline"
        assert result.severity == NewsSeverity.HIGH
        assert len(result.affected_tickers) == 2

    def test_unknown_severity_defaults_to_low(self):
        data = {"headline": "Test", "severity": "unknown"}
        result = _build_triage_result(data)
        assert result.severity == NewsSeverity.LOW


class TestExtractConviction:
    def test_explicit_conviction(self):
        assert _extract_conviction("CONVICTION: 8") == 8
        assert _extract_conviction("Conviction: 9/10") == 9

    def test_no_conviction_defaults(self):
        assert _extract_conviction("no conviction here") == 5

    def test_clamped_values(self):
        assert _extract_conviction("CONVICTION: 15") == 10
        assert _extract_conviction("CONVICTION: 0") == 1


class TestNewsTradeDecision:
    def test_should_execute_high_conviction(self):
        d = NewsTradeDecision(
            ticker="NVDA", action="SELL", conviction=9,
            reasoning="Thesis broken", severity=NewsSeverity.CRITICAL,
            should_execute=True,
        )
        assert d.should_execute

    def test_should_not_execute_low_conviction(self):
        d = NewsTradeDecision(
            ticker="NVDA", action="SELL", conviction=5,
            reasoning="Uncertain", severity=NewsSeverity.HIGH,
            should_execute=False,
        )
        assert not d.should_execute
