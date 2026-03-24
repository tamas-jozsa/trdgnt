"""Tests for TICKET-001: robust signal extraction."""

import pytest
from tradingagents.graph.signal_processing import SignalProcessor


class TestParseSignal:
    """Unit tests for SignalProcessor._parse_signal (no LLM needed)."""

    def test_exact_buy(self):
        assert SignalProcessor._parse_signal("BUY") == "BUY"

    def test_exact_sell(self):
        assert SignalProcessor._parse_signal("SELL") == "SELL"

    def test_exact_hold(self):
        assert SignalProcessor._parse_signal("HOLD") == "HOLD"

    def test_lowercase(self):
        assert SignalProcessor._parse_signal("buy") == "BUY"

    def test_mixed_case(self):
        assert SignalProcessor._parse_signal("Sell") == "SELL"

    def test_leading_trailing_whitespace(self):
        assert SignalProcessor._parse_signal("  HOLD  ") == "HOLD"

    def test_embedded_in_sentence(self):
        assert SignalProcessor._parse_signal("I recommend BUY for this stock.") == "BUY"

    def test_embedded_lowercase(self):
        assert SignalProcessor._parse_signal("The decision is to sell immediately.") == "SELL"

    def test_strong_buy_extracts_buy(self):
        # "STRONG BUY" contains BUY — regex should catch it
        assert SignalProcessor._parse_signal("STRONG BUY") == "BUY"

    def test_no_match_defaults_to_hold(self):
        assert SignalProcessor._parse_signal("I cannot determine a direction.") == "HOLD"

    def test_empty_string_defaults_to_hold(self):
        assert SignalProcessor._parse_signal("") == "HOLD"

    def test_context_fallback(self):
        """If LLM response is unparseable but original prose has signal, use prose."""
        result = SignalProcessor._parse_signal(
            raw="I am unable to provide a recommendation.",
            context="Based on all evidence the final decision is SELL.",
        )
        assert result == "SELL"

    def test_no_match_anywhere_defaults_to_hold(self):
        result = SignalProcessor._parse_signal(
            raw="Unclear.",
            context="Market conditions are mixed.",
        )
        assert result == "HOLD"

    def test_final_transaction_proposal_pattern(self):
        """Match the FINAL TRANSACTION PROPOSAL: **BUY** pattern used in agent prompts."""
        prose = "FINAL TRANSACTION PROPOSAL: **BUY**"
        assert SignalProcessor._parse_signal(prose) == "BUY"

    def test_final_transaction_proposal_sell(self):
        prose = "After careful analysis: FINAL TRANSACTION PROPOSAL: **SELL**"
        assert SignalProcessor._parse_signal(prose) == "SELL"
