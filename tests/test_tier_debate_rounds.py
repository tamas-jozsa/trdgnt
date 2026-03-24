"""Tests for TICKET-027: tier-based debate rounds."""

import pytest
from trading_loop import (
    TIER_DEBATE_ROUNDS,
    TIER_RISK_ROUNDS,
    TIER_MULTIPLIER,
    get_tier,
    WATCHLIST,
)


class TestTierDebateRounds:

    def test_core_gets_2_debate_rounds(self):
        assert TIER_DEBATE_ROUNDS["CORE"] == 2

    def test_tactical_gets_1_debate_round(self):
        assert TIER_DEBATE_ROUNDS["TACTICAL"] == 1

    def test_speculative_gets_1_debate_round(self):
        assert TIER_DEBATE_ROUNDS["SPECULATIVE"] == 1

    def test_hedge_gets_1_debate_round(self):
        assert TIER_DEBATE_ROUNDS["HEDGE"] == 1

    def test_core_gets_2_risk_rounds(self):
        assert TIER_RISK_ROUNDS["CORE"] == 2

    def test_tactical_gets_1_risk_round(self):
        assert TIER_RISK_ROUNDS["TACTICAL"] == 1

    def test_speculative_gets_1_risk_round(self):
        assert TIER_RISK_ROUNDS["SPECULATIVE"] == 1

    def test_hedge_gets_1_risk_round(self):
        assert TIER_RISK_ROUNDS["HEDGE"] == 1

    def test_all_tiers_covered_in_debate(self):
        for tier in TIER_MULTIPLIER:
            assert tier in TIER_DEBATE_ROUNDS, f"Tier {tier} missing from TIER_DEBATE_ROUNDS"

    def test_all_tiers_covered_in_risk(self):
        for tier in TIER_MULTIPLIER:
            assert tier in TIER_RISK_ROUNDS, f"Tier {tier} missing from TIER_RISK_ROUNDS"

    def test_nvda_is_core_gets_2_rounds(self):
        assert get_tier("NVDA") == "CORE"
        assert TIER_DEBATE_ROUNDS[get_tier("NVDA")] == 2

    def test_rcat_is_speculative_gets_1_round(self):
        assert get_tier("RCAT") == "SPECULATIVE"
        assert TIER_DEBATE_ROUNDS[get_tier("RCAT")] == 1

    def test_gld_is_hedge_gets_1_round(self):
        assert get_tier("GLD") == "HEDGE"
        assert TIER_DEBATE_ROUNDS[get_tier("GLD")] == 1

    def test_cmc_is_tactical_gets_1_round(self):
        assert get_tier("CMC") == "TACTICAL"
        assert TIER_DEBATE_ROUNDS[get_tier("CMC")] == 1

    def test_debate_rounds_are_positive_ints(self):
        for tier, rounds in TIER_DEBATE_ROUNDS.items():
            assert isinstance(rounds, int), f"{tier} debate rounds not int"
            assert rounds >= 1, f"{tier} debate rounds must be >= 1"

    def test_risk_rounds_are_positive_ints(self):
        for tier, rounds in TIER_RISK_ROUNDS.items():
            assert isinstance(rounds, int), f"{tier} risk rounds not int"
            assert rounds >= 1, f"{tier} risk rounds must be >= 1"

    def test_core_has_most_rounds(self):
        """CORE must have the most (or equal most) debate rounds of any tier."""
        max_rounds = max(TIER_DEBATE_ROUNDS.values())
        assert TIER_DEBATE_ROUNDS["CORE"] == max_rounds

    def test_config_override_applied_correctly(self):
        """Simulate what analyse_and_trade does — config reflects tier rounds."""
        from tradingagents.default_config import DEFAULT_CONFIG

        for ticker in ["NVDA", "RCAT", "GLD", "CMC"]:
            tier = get_tier(ticker)
            config = DEFAULT_CONFIG.copy()
            config["max_debate_rounds"]       = TIER_DEBATE_ROUNDS.get(tier, 1)
            config["max_risk_discuss_rounds"] = TIER_RISK_ROUNDS.get(tier, 1)

            expected_debate = TIER_DEBATE_ROUNDS[tier]
            expected_risk   = TIER_RISK_ROUNDS[tier]
            assert config["max_debate_rounds"]       == expected_debate,       f"{ticker}"
            assert config["max_risk_discuss_rounds"] == expected_risk,         f"{ticker}"
