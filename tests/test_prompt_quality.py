"""Tests for TICKET-025: full agent prompt rewrite quality checks."""

import pytest
import inspect


class TestNoWrongBoilerplate:
    """No analyst prompt should contain the FINAL TRANSACTION PROPOSAL boilerplate."""

    def _get_system_message(self, create_fn, mock_llm=None):
        """Extract the system message string from an analyst create function."""
        from unittest.mock import MagicMock
        from langchain_core.messages import HumanMessage

        llm = mock_llm or MagicMock()
        llm.bind_tools.return_value = MagicMock()
        node = create_fn(llm)
        # Get the source to inspect the system_message string
        src = inspect.getsource(create_fn)
        return src

    def test_market_analyst_no_final_proposal_boilerplate(self):
        from tradingagents.agents.analysts.market_analyst import create_market_analyst
        src = inspect.getsource(create_market_analyst)
        assert "FINAL TRANSACTION PROPOSAL" not in src, \
            "Market analyst must not contain FINAL TRANSACTION PROPOSAL boilerplate"

    def test_social_analyst_no_final_proposal_boilerplate(self):
        from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst
        src = inspect.getsource(create_social_media_analyst)
        assert "FINAL TRANSACTION PROPOSAL" not in src, \
            "Social analyst must not contain FINAL TRANSACTION PROPOSAL boilerplate"

    def test_news_analyst_no_final_proposal_boilerplate(self):
        from tradingagents.agents.analysts.news_analyst import create_news_analyst
        src = inspect.getsource(create_news_analyst)
        assert "FINAL TRANSACTION PROPOSAL" not in src, \
            "News analyst must not contain FINAL TRANSACTION PROPOSAL boilerplate"

    def test_fundamentals_analyst_no_final_proposal_boilerplate(self):
        from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
        src = inspect.getsource(create_fundamentals_analyst)
        assert "FINAL TRANSACTION PROPOSAL" not in src, \
            "Fundamentals analyst must not contain FINAL TRANSACTION PROPOSAL boilerplate"

    def test_trader_has_final_proposal(self):
        """Trader SHOULD have FINAL TRANSACTION PROPOSAL — it's the decision maker."""
        from tradingagents.agents.trader.trader import create_trader
        src = inspect.getsource(create_trader)
        assert "FINAL TRANSACTION PROPOSAL" in src, \
            "Trader must end with FINAL TRANSACTION PROPOSAL"


class TestTyposFix:

    def test_trader_typo_fixed(self):
        from tradingagents.agents.trader.trader import create_trader
        src = inspect.getsource(create_trader)
        assert "situatiosn" not in src, "Typo 'situatiosn' still present in trader.py"

    def test_trader_grammar_fixed(self):
        from tradingagents.agents.trader.trader import create_trader
        src = inspect.getsource(create_trader)
        assert "Here is some reflections" not in src, \
            "Grammar error 'Here is some reflections' still present"


class TestPromptContent:

    def test_market_analyst_requires_90_day_or_lookback(self):
        from tradingagents.agents.analysts.market_analyst import create_market_analyst
        src = inspect.getsource(create_market_analyst)
        assert "90" in src or "90-day" in src or "90 day" in src, \
            "Market analyst should specify 90-day lookback"

    def test_market_analyst_requires_rsi(self):
        from tradingagents.agents.analysts.market_analyst import create_market_analyst
        src = inspect.getsource(create_market_analyst)
        assert "rsi" in src.lower(), "Market analyst must explicitly require RSI"

    def test_market_analyst_requires_swing_horizon(self):
        from tradingagents.agents.analysts.market_analyst import create_market_analyst
        src = inspect.getsource(create_market_analyst)
        assert "3-30" in src or "swing" in src.lower(), \
            "Market analyst should specify swing trading horizon"

    def test_news_analyst_requires_both_tools(self):
        from tradingagents.agents.analysts.news_analyst import create_news_analyst
        src = inspect.getsource(create_news_analyst)
        assert "get_news" in src and "get_global_news" in src, \
            "News analyst must call both get_news and get_global_news"

    def test_news_analyst_mentions_earnings_risk(self):
        from tradingagents.agents.analysts.news_analyst import create_news_analyst
        src = inspect.getsource(create_news_analyst)
        assert "earnings" in src.lower() or "binary" in src.lower(), \
            "News analyst should flag earnings as binary risk event"

    def test_fundamentals_analyst_no_past_week(self):
        from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
        src = inspect.getsource(create_fundamentals_analyst)
        assert "over the past week" not in src, \
            "'over the past week' still in fundamentals analyst — balance sheets are quarterly"

    def test_fundamentals_analyst_has_valuation_framework(self):
        from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
        src = inspect.getsource(create_fundamentals_analyst)
        assert "P/E" in src or "p/e" in src.lower(), \
            "Fundamentals analyst must include P/E valuation framework"

    def test_fundamentals_analyst_mentions_insider(self):
        from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
        src = inspect.getsource(create_fundamentals_analyst)
        assert "insider" in src.lower(), \
            "Fundamentals analyst must mention insider transactions"

    def test_bull_researcher_can_concede(self):
        from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
        src = inspect.getsource(create_bull_researcher)
        assert "concede" in src.lower() or "acknowledge" in src.lower() or "credible" in src.lower(), \
            "Bull researcher should be able to concede weak points"

    def test_bear_researcher_can_concede(self):
        from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
        src = inspect.getsource(create_bear_researcher)
        assert "concede" in src.lower() or "acknowledge" in src.lower() or "credible" in src.lower(), \
            "Bear researcher should be able to concede weak points"

    def test_research_manager_injects_raw_reports(self):
        from tradingagents.agents.managers.research_manager import create_research_manager
        src = inspect.getsource(create_research_manager)
        assert "market_research_report" in src and "sentiment_report" in src and \
               "news_report" in src and "fundamentals_report" in src, \
            "Research Manager must inject all 4 raw analyst reports"

    def test_research_manager_structured_output(self):
        from tradingagents.agents.managers.research_manager import create_research_manager
        src = inspect.getsource(create_research_manager)
        assert "RECOMMENDATION:" in src and "CONVICTION:" in src and "TARGET:" in src, \
            "Research Manager must require structured output format"

    def test_trader_includes_stop_loss_instruction(self):
        from tradingagents.agents.trader.trader import create_trader
        src = inspect.getsource(create_trader)
        assert "stop" in src.lower() or "stop-loss" in src.lower(), \
            "Trader must include stop-loss instruction"

    def test_trader_includes_target_instruction(self):
        from tradingagents.agents.trader.trader import create_trader
        src = inspect.getsource(create_trader)
        assert "target" in src.lower(), "Trader must include price target instruction"

    def test_risk_debaters_independent_evaluation(self):
        """Risk debaters should evaluate independently, not just defend the trader."""
        from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
        from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
        src_agg  = inspect.getsource(create_aggressive_debator)
        src_cons = inspect.getsource(create_conservative_debator)
        # Should NOT contain the old "create a compelling case for the trader's decision"
        assert "create a compelling case for the trader" not in src_agg.lower(), \
            "Aggressive debater should evaluate independently, not blindly defend"
        assert "create a compelling case for the trader" not in src_cons.lower(), \
            "Conservative debater should evaluate independently"

    def test_risk_manager_hold_is_valid(self):
        """Risk manager must not have an anti-HOLD bias."""
        from tradingagents.agents.managers.risk_manager import create_risk_manager
        src = inspect.getsource(create_risk_manager)
        assert "hold is" in src.lower() or "hold is correct" in src.lower() or \
               "hold is valid" in src.lower(), \
            "Risk manager should explicitly acknowledge HOLD as a valid answer"

    def test_risk_manager_structured_output(self):
        from tradingagents.agents.managers.risk_manager import create_risk_manager
        src = inspect.getsource(create_risk_manager)
        assert "FINAL DECISION:" in src and "STOP-LOSS:" in src and "TARGET:" in src, \
            "Risk manager must require structured output with decision + stop + target"


class TestMemoryRetrievalCount:
    """All 5 agent memories should retrieve n_matches=5."""

    def test_bull_uses_5_memories(self):
        from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
        src = inspect.getsource(create_bull_researcher)
        assert "n_matches=5" in src, "Bull researcher should retrieve 5 memories"

    def test_bear_uses_5_memories(self):
        from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
        src = inspect.getsource(create_bear_researcher)
        assert "n_matches=5" in src, "Bear researcher should retrieve 5 memories"

    def test_research_manager_uses_5_memories(self):
        from tradingagents.agents.managers.research_manager import create_research_manager
        src = inspect.getsource(create_research_manager)
        assert "n_matches=5" in src, "Research manager should retrieve 5 memories"

    def test_trader_uses_5_memories(self):
        from tradingagents.agents.trader.trader import create_trader
        src = inspect.getsource(create_trader)
        assert "n_matches=5" in src, "Trader should retrieve 5 memories"

    def test_risk_manager_uses_5_memories(self):
        from tradingagents.agents.managers.risk_manager import create_risk_manager
        src = inspect.getsource(create_risk_manager)
        assert "n_matches=5" in src, "Risk manager should retrieve 5 memories"


class TestDeadCodeRemoved:

    def test_bull_no_dead_imports(self):
        from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
        src = inspect.getsource(create_bull_researcher)
        assert "import time" not in src
        assert "import json" not in src

    def test_bear_no_dead_imports(self):
        from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
        src = inspect.getsource(create_bear_researcher)
        assert "import time" not in src
        assert "import json" not in src

    def test_risk_agents_no_dead_imports(self):
        from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
        from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
        from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
        for fn in [create_aggressive_debator, create_conservative_debator, create_neutral_debator]:
            src = inspect.getsource(fn)
            assert "import time" not in src
            assert "import json" not in src
