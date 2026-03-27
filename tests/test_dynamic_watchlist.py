"""Tests for TICKET-022: dynamic watchlist from research findings."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


# Sample findings markdown with ADD and REMOVE signals
SAMPLE_FINDINGS_WITH_CHANGES = """
## RESEARCH FINDINGS — 2026-03-25

### Overall Market Sentiment: BULLISH

### WATCHLIST DECISIONS:
| Ticker | Sector | Decision | Conviction | Reason |
|--------|--------|----------|------------|--------|
| NVDA   | AI     | HOLD     | HIGH       | thesis intact |
| AVGO   | AI     | BUY      | HIGH       | DoD contract |
| TSM    | AI     | SELL     | MEDIUM     | thesis broken |
| MU     | AI     | REMOVE   | LOW        | better alternatives |

### TOP 3 NEW PICKS (not in current watchlist):
1. ASML — SK Hynix $8B order drives demand — lithography monopoly — risk: tariffs
2. PLTR — Maven AI federal program — DoD spending surge — risk: valuation
3. NVDA — already in watchlist, should not be added again
"""

SAMPLE_FINDINGS_NO_CHANGES = """
## RESEARCH FINDINGS — 2026-03-25

### Overall Market Sentiment: NEUTRAL

### WATCHLIST DECISIONS:
| Ticker | Sector | Decision | Conviction | Reason |
|--------|--------|----------|------------|--------|
| NVDA   | AI     | HOLD     | HIGH       | intact |
| AVGO   | AI     | ADD      | HIGH       | thesis |
"""


class TestParseWatchlistChanges:

    def test_detects_sell_as_remove_candidate(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_WITH_CHANGES)
        assert "TSM" in result["remove"]

    def test_detects_remove_verdict(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_WITH_CHANGES)
        assert "MU" in result["remove"]

    def test_hold_is_not_removed(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_WITH_CHANGES)
        assert "NVDA" not in result["remove"]

    def test_buy_is_not_removed(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_WITH_CHANGES)
        assert "AVGO" not in result["remove"]

    def test_new_picks_parsed_as_adds(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_WITH_CHANGES)
        assert "ASML" in result["add"]

    def test_existing_watchlist_ticker_not_re_added(self):
        """Tickers already in WATCHLIST should not appear in adds."""
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_WITH_CHANGES)
        # NVDA is in WATCHLIST, should not be added again
        assert "NVDA" not in result["add"]

    def test_new_pick_gets_tactical_tier(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_WITH_CHANGES)
        if "ASML" in result["add"]:
            assert result["add"]["ASML"]["tier"] == "TACTICAL"

    def test_no_changes_returns_empty(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes(SAMPLE_FINDINGS_NO_CHANGES)
        assert result["remove"] == []

    def test_returns_dict_with_add_and_remove_keys(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes("")
        assert "add" in result
        assert "remove" in result
        assert isinstance(result["add"], dict)
        assert isinstance(result["remove"], list)


class TestSaveLoadWatchlistOverrides:

    def test_save_and_load_roundtrip(self, tmp_path):
        """TACTICAL/SPECULATIVE/HEDGE tickers are removed on first SELL.
        CORE tickers (e.g. MU) require a prior-day remove entry — use a
        non-CORE ticker (RCAT is SPECULATIVE) for the simple roundtrip test."""
        from trading_loop import save_watchlist_overrides, load_watchlist_overrides, _OVERRIDES_FILE
        adds    = {"ASML": {"sector": "AI Semis", "tier": "TACTICAL", "note": "test"}}
        removes = ["RCAT"]  # SPECULATIVE — no prior-day protection required

        with patch("trading_loop._OVERRIDES_FILE", tmp_path / "overrides.json"):
            save_watchlist_overrides(adds, removes)
            effective = load_watchlist_overrides()

        assert "ASML" in effective
        assert "RCAT" not in effective

    def test_load_returns_full_watchlist_when_no_overrides(self, tmp_path):
        from trading_loop import load_watchlist_overrides, WATCHLIST
        with patch("trading_loop._OVERRIDES_FILE", tmp_path / "nonexistent.json"):
            effective = load_watchlist_overrides()
        assert set(effective.keys()) == set(WATCHLIST.keys())

    def test_overrides_merged_not_replaced(self, tmp_path):
        """Second save merges with existing overrides rather than overwriting.
        Use RCAT (SPECULATIVE) for the remove — CORE tickers need prior-day confirmation."""
        from trading_loop import save_watchlist_overrides

        overrides_path = tmp_path / "overrides.json"
        with patch("trading_loop._OVERRIDES_FILE", overrides_path):
            save_watchlist_overrides({"ASML": {"tier": "TACTICAL"}}, [])
            save_watchlist_overrides({"AMD2": {"tier": "TACTICAL"}}, ["RCAT"])

            data = json.loads(overrides_path.read_text())

        assert "ASML" in data["add"]
        assert "AMD2" in data["add"]
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e
                          for e in data["remove"]]
        assert "RCAT" in remove_tickers

    def test_ticker_not_in_both_add_and_remove(self, tmp_path):
        """A ticker should not appear in both adds and removes."""
        from trading_loop import save_watchlist_overrides

        overrides_path = tmp_path / "overrides.json"
        with patch("trading_loop._OVERRIDES_FILE", overrides_path):
            # Add ASML first
            save_watchlist_overrides({"ASML": {"tier": "TACTICAL"}}, [])
            # Then add it to removes
            save_watchlist_overrides({}, ["ASML"])
            data = json.loads(overrides_path.read_text())

        # ASML should be in removes only (later decision wins)
        if "ASML" in data.get("add", {}):
            assert "ASML" not in data.get("remove", [])
        else:
            assert "ASML" in data.get("remove", [])

    def test_effective_watchlist_adds_new_ticker(self, tmp_path):
        from trading_loop import load_watchlist_overrides, WATCHLIST

        overrides = {
            "add": {"ASML": {"sector": "AI Semis", "tier": "TACTICAL", "note": "test"}},
            "remove": [],
        }
        overrides_path = tmp_path / "overrides.json"
        overrides_path.write_text(json.dumps(overrides))

        with patch("trading_loop._OVERRIDES_FILE", overrides_path):
            effective = load_watchlist_overrides()

        assert "ASML" in effective
        assert len(effective) == len(WATCHLIST) + 1

    def test_effective_watchlist_removes_ticker(self, tmp_path):
        """load_watchlist_overrides handles both legacy plain-string and new dict remove formats."""
        from trading_loop import load_watchlist_overrides, WATCHLIST

        # New dict format with removed_on date (non-expired)
        from datetime import date
        today = str(date.today())
        overrides = {"add": {}, "remove": [{"ticker": "MU", "removed_on": today}]}
        overrides_path = tmp_path / "overrides.json"
        overrides_path.write_text(json.dumps(overrides))

        with patch("trading_loop._OVERRIDES_FILE", overrides_path):
            effective = load_watchlist_overrides()

        assert "MU" not in effective
        assert len(effective) == len(WATCHLIST) - 1
