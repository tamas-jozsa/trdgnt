"""
Tests for TICKET-038: update_positions.py

Covers:
  - fetch_positions()            successful API response → correct dict structure
  - fetch_positions()            API error dict → raises RuntimeError (not TypeError)
  - build_positions_markdown()   non-empty positions → table present
  - build_positions_markdown()   zero positions → "100% cash" message
  - inject_into_prompt()         placeholder tags replaced in MARKET_RESEARCH_PROMPT.md
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

ACCOUNT_RESPONSE = {
    "equity":        "125000.00",
    "cash":          "75000.00",
    "buying_power":  "75000.00",
}

POSITIONS_RESPONSE = [
    {
        "symbol":          "NVDA",
        "qty":             "5.0",
        "avg_entry_price": "900.00",
        "market_value":    "4750.00",
        "unrealized_pl":   "-250.00",
        "unrealized_plpc": "-0.05",
        "side":            "long",
    },
    {
        "symbol":          "MSFT",
        "qty":             "10.0",
        "avg_entry_price": "420.00",
        "market_value":    "4600.00",
        "unrealized_pl":   "400.00",
        "unrealized_plpc": "0.095",
        "side":            "long",
    },
]

ALPACA_ERROR_RESPONSE = {
    "code":    40110000,
    "message": "request is not authorized",
}


def _make_session(account_json, positions_json):
    """Create a mock requests.Session whose .get() returns appropriate responses."""
    def _get_response(data):
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        return mock_resp

    mock_session = MagicMock()

    def side_effect(url, **kwargs):
        if "/account" in url:
            return _get_response(account_json)
        if "/positions" in url:
            return _get_response(positions_json)
        return _get_response({})

    mock_session.get.side_effect = side_effect
    return mock_session


# ---------------------------------------------------------------------------
# fetch_positions
# ---------------------------------------------------------------------------

class TestFetchPositions:

    def test_successful_response_returns_correct_structure(self, monkeypatch):
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")

        mock_session = _make_session(ACCOUNT_RESPONSE, POSITIONS_RESPONSE)
        with patch.object(up, "get_session", return_value=mock_session):
            result = up.fetch_positions()

        assert "updated_at" in result
        assert result["account"]["equity"]       == 125000.0
        assert result["account"]["cash"]         == 75000.0
        assert result["account"]["buying_power"] == 75000.0
        assert len(result["positions"]) == 2

    def test_positions_have_expected_fields(self, monkeypatch):
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")

        mock_session = _make_session(ACCOUNT_RESPONSE, POSITIONS_RESPONSE)
        with patch.object(up, "get_session", return_value=mock_session):
            result = up.fetch_positions()

        nvda = next(p for p in result["positions"] if p["ticker"] == "NVDA")
        assert nvda["qty"]              == 5.0
        assert nvda["avg_entry_price"]  == 900.0
        assert nvda["market_value"]     == 4750.0
        assert nvda["unrealized_pl"]    == -250.0
        assert nvda["unrealized_pl_pct"] == pytest.approx(-5.0, abs=0.01)
        assert nvda["side"]             == "long"

    def test_empty_positions_list(self, monkeypatch):
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")

        mock_session = _make_session(ACCOUNT_RESPONSE, [])
        with patch.object(up, "get_session", return_value=mock_session):
            result = up.fetch_positions()

        assert result["positions"] == []

    def test_account_api_error_raises_runtime_error(self, monkeypatch):
        """Alpaca auth error dict → RuntimeError, not a silent TypeError."""
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")

        mock_session = _make_session(ALPACA_ERROR_RESPONSE, POSITIONS_RESPONSE)
        with patch.object(up, "get_session", return_value=mock_session):
            with pytest.raises(RuntimeError, match="error"):
                up.fetch_positions()

    def test_positions_api_error_raises_runtime_error(self, monkeypatch):
        """Error on /positions endpoint → RuntimeError."""
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")

        mock_session = _make_session(ACCOUNT_RESPONSE, ALPACA_ERROR_RESPONSE)
        with patch.object(up, "get_session", return_value=mock_session):
            with pytest.raises(RuntimeError, match="error"):
                up.fetch_positions()

    def test_missing_api_key_raises_environment_error(self, monkeypatch):
        import update_positions as up
        monkeypatch.delenv("ALPACA_API_KEY",    raising=False)
        monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
        with pytest.raises(EnvironmentError):
            up.fetch_positions()

    def test_respects_alpaca_base_url_env_var(self, monkeypatch):
        """fetch_positions should use ALPACA_BASE_URL, not a hardcoded paper URL."""
        import update_positions as up
        monkeypatch.setenv("ALPACA_API_KEY",    "test-key")
        monkeypatch.setenv("ALPACA_API_SECRET", "test-secret")
        monkeypatch.setenv("ALPACA_BASE_URL",   "https://api.custom.alpaca.markets")

        mock_session = _make_session(ACCOUNT_RESPONSE, POSITIONS_RESPONSE)
        with patch.object(up, "get_session", return_value=mock_session):
            up.fetch_positions()

        called_urls = [call.args[0] for call in mock_session.get.call_args_list]
        assert any("api.custom.alpaca.markets" in url for url in called_urls), (
            f"Expected custom base URL to be used. Actual calls: {called_urls}"
        )


# ---------------------------------------------------------------------------
# build_positions_markdown
# ---------------------------------------------------------------------------

class TestBuildPositionsMarkdown:

    def _make_data(self, positions=None):
        return {
            "updated_at": "2026-03-27T10:00:00Z",
            "account": {
                "equity":       125000.0,
                "cash":         75000.0,
                "buying_power": 75000.0,
            },
            "positions": positions or [],
        }

    def test_non_empty_positions_renders_table(self):
        import update_positions as up
        data = self._make_data([
            {
                "ticker": "NVDA", "qty": 5.0, "avg_entry_price": 900.0,
                "market_value": 4750.0, "unrealized_pl": -250.0,
                "unrealized_pl_pct": -5.0, "side": "long",
            }
        ])
        result = up.build_positions_markdown(data)
        assert "NVDA" in result
        assert "900.00" in result or "900" in result
        assert "-" in result   # P/L sign

    def test_empty_positions_shows_cash_message(self):
        import update_positions as up
        data = self._make_data([])
        result = up.build_positions_markdown(data)
        assert "100% cash" in result.lower() or "no open positions" in result.lower()

    def test_equity_and_cash_shown(self):
        import update_positions as up
        data = self._make_data()
        result = up.build_positions_markdown(data)
        assert "125,000" in result or "125000" in result

    def test_positive_pl_has_plus_sign(self):
        import update_positions as up
        data = self._make_data([
            {
                "ticker": "MSFT", "qty": 10.0, "avg_entry_price": 420.0,
                "market_value": 4600.0, "unrealized_pl": 400.0,
                "unrealized_pl_pct": 9.5, "side": "long",
            }
        ])
        result = up.build_positions_markdown(data)
        assert "+$400" in result or "+400" in result


# ---------------------------------------------------------------------------
# inject_into_prompt
# ---------------------------------------------------------------------------

class TestInjectIntoPrompt:

    def _make_prompt_file(self, tmp_path: Path) -> Path:
        prompt_file = tmp_path / "MARKET_RESEARCH_PROMPT.md"
        prompt_file.write_text(
            "# Research Prompt\n\n"
            "<!-- POSITIONS_PLACEHOLDER -->\n"
            "OLD CONTENT\n"
            "<!-- /POSITIONS_PLACEHOLDER -->\n\n"
            "## Strategy\n"
        )
        return prompt_file

    def test_inject_replaces_between_tags(self, tmp_path):
        """inject_into_prompt replaces content between placeholder tags."""
        import update_positions as up

        prompt_file = self._make_prompt_file(tmp_path)

        # Patch __file__ so Path(__file__).parent resolves to tmp_path
        with patch.object(up, "__file__", str(tmp_path / "update_positions.py")):
            up.inject_into_prompt("NEW CONTENT HERE")

        result = prompt_file.read_text()
        assert "NEW CONTENT HERE" in result
        assert "OLD CONTENT" not in result

    def test_inject_preserves_content_outside_tags(self, tmp_path):
        """Content before and after the placeholder tags is preserved."""
        import update_positions as up

        prompt_file = self._make_prompt_file(tmp_path)

        with patch.object(up, "__file__", str(tmp_path / "update_positions.py")):
            up.inject_into_prompt("NEW")

        result = prompt_file.read_text()
        assert "# Research Prompt" in result
        assert "## Strategy" in result

    def test_inject_with_empty_markdown(self, tmp_path):
        """inject_into_prompt handles empty markdown without crashing."""
        import update_positions as up

        prompt_file = self._make_prompt_file(tmp_path)

        with patch.object(up, "__file__", str(tmp_path / "update_positions.py")):
            up.inject_into_prompt("")

        result = prompt_file.read_text()
        assert "<!-- POSITIONS_PLACEHOLDER -->" in result  # tags still present
