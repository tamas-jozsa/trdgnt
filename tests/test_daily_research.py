"""
Tests for TICKET-037: daily_research.py scrapers and core functions.

Covers:
  - fetch_yahoo_gainers()      JSON parsing + graceful empty/error handling
  - fetch_vix()                VIX JSON parsing + graceful error handling
  - fetch_reddit_hot()         Reddit JSON parsing + graceful error handling
  - fetch_reuters_headlines()  delegates to reuters_utils — test delegation
  - call_llm()                 OpenAI API call + missing key raises EnvironmentError
  - _estimate_cost()           known models return expected cost; unknown → 0.0
  - run_daily_research()       idempotent (skips if file exists); force overwrites;
                                creates findings file on successful LLM call
"""

import json
import os
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

YAHOO_GAINERS_JSON = json.dumps({
    "finance": {
        "result": [{
            "quotes": [
                {
                    "symbol": "NVDA",
                    "regularMarketChangePercent": 5.42,
                    "regularMarketPrice": 950.0,
                    "shortName": "NVIDIA Corp",
                    "regularMarketVolume": 42000000,
                },
                {
                    "symbol": "AMD",
                    "regularMarketChangePercent": 3.10,
                    "regularMarketPrice": 180.0,
                    "shortName": "Advanced Micro Devices",
                    "regularMarketVolume": 25000000,
                },
            ]
        }]
    }
})

VIX_JSON = json.dumps({
    "chart": {
        "result": [{
            "meta": {
                "regularMarketPrice": 18.5,
                "chartPreviousClose": 17.0,
            }
        }]
    }
})

REDDIT_HOT_JSON = json.dumps({
    "data": {
        "children": [
            {"data": {"score": 12000, "title": "NVDA just went parabolic — DD inside", "link_flair_text": "DD"}},
            {"data": {"score": 8000, "title": "Why I'm short AMD into earnings", "link_flair_text": ""}},
        ]
    }
})


# ---------------------------------------------------------------------------
# fetch_yahoo_gainers
# ---------------------------------------------------------------------------

class TestFetchYahooGainers:

    def test_parses_realistic_response(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value=YAHOO_GAINERS_JSON):
            result = dr.fetch_yahoo_gainers()
        assert "NVDA" in result
        assert "+5.42%" in result
        assert "AMD" in result

    def test_empty_url_response_returns_empty_string(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value=""):
            result = dr.fetch_yahoo_gainers()
        assert result == ""

    def test_malformed_json_returns_empty_string(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value="NOT JSON {{{"):
            result = dr.fetch_yahoo_gainers()
        assert result == ""

    def test_missing_quotes_key_returns_empty_string(self):
        import daily_research as dr
        bad_json = json.dumps({"finance": {"result": [{"notquotes": []}]}})
        with patch.object(dr, "_fetch_url", return_value=bad_json):
            result = dr.fetch_yahoo_gainers()
        assert result == ""


# ---------------------------------------------------------------------------
# fetch_vix
# ---------------------------------------------------------------------------

class TestFetchVix:

    def test_parses_realistic_response(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value=VIX_JSON):
            result = dr.fetch_vix()
        assert "VIX" in result
        assert "18.5" in result or "18.50" in result

    def test_empty_response_returns_empty_string(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value=""):
            result = dr.fetch_vix()
        assert result == ""

    def test_malformed_json_returns_empty_string(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value="bad"):
            result = dr.fetch_vix()
        assert result == ""


# ---------------------------------------------------------------------------
# fetch_reddit_hot
# ---------------------------------------------------------------------------

class TestFetchRedditHot:

    def test_parses_posts_correctly(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value=REDDIT_HOT_JSON):
            result = dr.fetch_reddit_hot("wallstreetbets")
        assert "wallstreetbets" in result
        assert "NVDA" in result
        assert "12,000" in result or "12000" in result

    def test_empty_response_returns_empty_string(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value=""):
            result = dr.fetch_reddit_hot("stocks")
        assert result == ""

    def test_network_error_returns_empty_string(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value=""):
            result = dr.fetch_reddit_hot("investing")
        assert result == ""

    def test_malformed_json_returns_empty_string(self):
        import daily_research as dr
        with patch.object(dr, "_fetch_url", return_value="NOT JSON"):
            result = dr.fetch_reddit_hot("wallstreetbets")
        assert result == ""


# ---------------------------------------------------------------------------
# fetch_reuters_headlines — delegates to reuters_utils
# ---------------------------------------------------------------------------

class TestFetchReutersHeadlines:

    def test_returns_string(self):
        """fetch_reuters_headlines() should always return a str (never raise)."""
        import daily_research as dr
        # Patch the inner import inside the function body
        with patch("tradingagents.dataflows.reuters_utils.get_reuters_global_news",
                   return_value="### Reuters\n- Markets rally on AI optimism"):
            result = dr.fetch_reuters_headlines()
        assert isinstance(result, str)

    def test_exception_returns_empty_string(self):
        """If reuters_utils raises, fetch_reuters_headlines returns '' gracefully."""
        import daily_research as dr
        with patch("tradingagents.dataflows.reuters_utils.get_reuters_global_news",
                   side_effect=Exception("network timeout")):
            result = dr.fetch_reuters_headlines()
        assert result == ""


# ---------------------------------------------------------------------------
# call_llm
# ---------------------------------------------------------------------------

class TestCallLlm:

    def _make_mock_response(self, content: str, input_tokens: int = 500, output_tokens: int = 200):
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = input_tokens
        mock_usage.completion_tokens = output_tokens
        mock_usage.total_tokens = input_tokens + output_tokens

        mock_choice = MagicMock()
        mock_choice.message.content = content

        mock_response = MagicMock()
        mock_response.usage = mock_usage
        mock_response.choices = [mock_choice]
        return mock_response

    def test_returns_llm_content(self, monkeypatch):
        import daily_research as dr
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        expected = "## RESEARCH FINDINGS\n### Sentiment: BULLISH"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_mock_response(expected)

        with patch("openai.OpenAI", return_value=mock_client):
            result = dr.call_llm("some live data")

        assert result == expected
        mock_client.chat.completions.create.assert_called_once()

    def test_passes_live_data_in_user_message(self, monkeypatch):
        import daily_research as dr
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_mock_response("result")

        with patch("openai.OpenAI", return_value=mock_client):
            dr.call_llm("MY_LIVE_DATA_SENTINEL")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "MY_LIVE_DATA_SENTINEL" in user_content

    def test_missing_api_key_raises_environment_error(self, monkeypatch):
        import daily_research as dr
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            dr.call_llm("some data")

    def test_uses_research_llm_model_env_var(self, monkeypatch):
        import daily_research as dr
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("RESEARCH_LLM_MODEL", "gpt-4o")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._make_mock_response("ok")

        with patch("openai.OpenAI", return_value=mock_client):
            dr.call_llm("data")

        call_kwargs = mock_client.chat.completions.create.call_args
        model_used = call_kwargs[1].get("model") or call_kwargs[0][0]
        assert model_used == "gpt-4o"


# ---------------------------------------------------------------------------
# _estimate_cost
# ---------------------------------------------------------------------------

class TestEstimateCost:

    def test_gpt4o_mini_known_price(self):
        import daily_research as dr
        # 1000 input + 1000 output tokens with gpt-4o-mini
        # = (1000 * 0.00015 + 1000 * 0.00060) / 1000 = 0.00075
        cost = dr._estimate_cost("gpt-4o-mini", 1000, 1000)
        assert abs(cost - 0.00075) < 1e-8

    def test_gpt4o_known_price(self):
        import daily_research as dr
        # 1000 in + 1000 out = (1000*0.00250 + 1000*0.01000)/1000 = 0.01250
        cost = dr._estimate_cost("gpt-4o", 1000, 1000)
        assert abs(cost - 0.01250) < 1e-8

    def test_unknown_model_returns_zero(self):
        import daily_research as dr
        cost = dr._estimate_cost("totally-fake-model-xyz", 1000, 1000)
        assert cost == 0.0

    def test_zero_tokens_returns_zero(self):
        import daily_research as dr
        cost = dr._estimate_cost("gpt-4o-mini", 0, 0)
        assert cost == 0.0

    def test_model_with_date_suffix_matches(self):
        """gpt-4o-mini-2024-07-18 should match gpt-4o-mini key."""
        import daily_research as dr
        cost = dr._estimate_cost("gpt-4o-mini-2024-07-18", 1000, 1000)
        assert cost > 0.0


# ---------------------------------------------------------------------------
# run_daily_research
# ---------------------------------------------------------------------------

class TestRunDailyResearch:

    def _mock_research_env(self, monkeypatch, results_dir: Path):
        """Patch RESULTS_DIR and all expensive operations."""
        import daily_research as dr
        monkeypatch.setattr(dr, "RESULTS_DIR", results_dir)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def test_creates_findings_file(self, tmp_path, monkeypatch):
        import daily_research as dr
        self._mock_research_env(monkeypatch, tmp_path)

        with patch.object(dr, "fetch_live_market_data", return_value="live data"), \
             patch.object(dr, "call_llm", return_value="## RESEARCH FINDINGS"), \
             patch("update_positions.fetch_positions", side_effect=Exception("no alpaca")):
            result = dr.run_daily_research()

        today = date.today().isoformat()
        expected = tmp_path / f"RESEARCH_FINDINGS_{today}.md"
        assert expected.exists(), f"Expected {expected} to be created"
        assert result == expected

    def test_idempotent_when_file_exists(self, tmp_path, monkeypatch):
        """Second call on same day should not call LLM again."""
        import daily_research as dr
        self._mock_research_env(monkeypatch, tmp_path)

        today = date.today().isoformat()
        existing = tmp_path / f"RESEARCH_FINDINGS_{today}.md"
        existing.write_text("existing findings")

        with patch.object(dr, "call_llm") as mock_llm:
            result = dr.run_daily_research()

        mock_llm.assert_not_called()
        assert result == existing

    def test_force_flag_overwrites_existing(self, tmp_path, monkeypatch):
        """--force should overwrite existing findings and call LLM again."""
        import daily_research as dr
        self._mock_research_env(monkeypatch, tmp_path)

        today = date.today().isoformat()
        existing = tmp_path / f"RESEARCH_FINDINGS_{today}.md"
        existing.write_text("old findings")

        new_content = "## NEW RESEARCH FINDINGS\n### Sentiment: BULLISH"
        with patch.object(dr, "fetch_live_market_data", return_value="data"), \
             patch.object(dr, "call_llm", return_value=new_content), \
             patch("update_positions.fetch_positions", side_effect=Exception("no alpaca")):
            result = dr.run_daily_research(force=True)

        assert result is not None
        assert result.exists()
        assert "NEW RESEARCH" in result.read_text()

    def test_dry_run_returns_none_and_no_file_created(self, tmp_path, monkeypatch):
        """dry_run=True should print but not save or call LLM."""
        import daily_research as dr
        self._mock_research_env(monkeypatch, tmp_path)

        with patch.object(dr, "fetch_live_market_data", return_value="data"), \
             patch.object(dr, "call_llm") as mock_llm, \
             patch("update_positions.fetch_positions", side_effect=Exception("no alpaca")):
            result = dr.run_daily_research(dry_run=True)

        mock_llm.assert_not_called()
        assert result is None
        # No file should have been created
        assert not list(tmp_path.glob("RESEARCH_FINDINGS_*.md"))
