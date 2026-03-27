"""
Tests for TICKET-036: trading_loop.py core functions.

Covers:
  - get_analysis_date()            date arithmetic for all weekdays + weekend guards
  - seconds_until_next_run()       scheduling arithmetic
  - parse_watchlist_changes()      regex parsing of LLM markdown output
  - load_watchlist_overrides()     file I/O + merge with static WATCHLIST
  - save_watchlist_overrides()     write + merge existing overrides
  - Portfolio limit guard          BUY downgraded to HOLD when at cap
"""

import json
import pytest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# get_analysis_date
# ---------------------------------------------------------------------------

class TestGetAnalysisDate:

    def _mock_now(self, weekday_name: str, hour: int = 10) -> datetime:
        """Return a fake ET datetime on a given weekday at the given hour."""
        # Find the next occurrence of the target weekday from a known Monday
        base = datetime(2026, 3, 23, hour, 0, 0, tzinfo=ET)  # Monday
        days = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                "Friday": 4, "Saturday": 5, "Sunday": 6}
        return base + timedelta(days=days[weekday_name])

    def test_monday_returns_friday(self):
        from trading_loop import get_analysis_date
        monday = self._mock_now("Monday")
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = monday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = get_analysis_date()
        # Monday 2026-03-23 → Friday 2026-03-20
        assert result == "2026-03-20"

    def test_tuesday_returns_monday(self):
        from trading_loop import get_analysis_date
        tuesday = self._mock_now("Tuesday")
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = get_analysis_date()
        assert result == "2026-03-23"  # Monday

    def test_wednesday_returns_tuesday(self):
        from trading_loop import get_analysis_date
        wednesday = self._mock_now("Wednesday")
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = wednesday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = get_analysis_date()
        assert result == "2026-03-24"  # Tuesday

    def test_friday_returns_thursday(self):
        from trading_loop import get_analysis_date
        friday = self._mock_now("Friday")
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = friday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = get_analysis_date()
        assert result == "2026-03-26"  # Thursday

    def test_saturday_returns_friday(self):
        from trading_loop import get_analysis_date
        saturday = self._mock_now("Saturday")
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = saturday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = get_analysis_date()
        assert result == "2026-03-27"  # Friday

    def test_sunday_returns_friday(self):
        from trading_loop import get_analysis_date
        sunday = self._mock_now("Sunday")
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = sunday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = get_analysis_date()
        assert result == "2026-03-27"  # Friday

    def test_returns_string_in_iso_format(self):
        from trading_loop import get_analysis_date
        result = get_analysis_date()
        # Must be parseable as a date
        parsed = date.fromisoformat(result)
        assert isinstance(parsed, date)


# ---------------------------------------------------------------------------
# seconds_until_next_run
# ---------------------------------------------------------------------------

class TestSecondsUntilNextRun:

    def test_before_10am_same_day(self):
        from trading_loop import seconds_until_next_run, _RUN_HOUR, _RUN_MIN
        # 08:00 ET Monday — next run is 10:00 ET same day (~7200s)
        now = datetime(2026, 3, 23, 8, 0, 0, tzinfo=ET)
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            secs = seconds_until_next_run()
        assert 7000 < secs <= 7200

    def test_after_10am_targets_next_day(self):
        from trading_loop import seconds_until_next_run
        # 11:00 ET Tuesday — next run is 10:00 ET Wednesday (~82800s)
        now = datetime(2026, 3, 24, 11, 0, 0, tzinfo=ET)
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            secs = seconds_until_next_run()
        # Should be ~23h = 82800s
        assert 80000 < secs <= 86400

    def test_friday_after_10am_skips_to_monday(self):
        from trading_loop import seconds_until_next_run
        # 11:00 ET Friday — next run is 10:00 ET Monday (~3 days minus 1h)
        now = datetime(2026, 3, 27, 11, 0, 0, tzinfo=ET)
        with patch("trading_loop.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            secs = seconds_until_next_run()
        # Friday 11am → Monday 10am = ~2d23h = ~255600s
        assert 250000 < secs <= 260000

    def test_result_is_non_negative(self):
        from trading_loop import seconds_until_next_run
        secs = seconds_until_next_run()
        assert secs >= 0


# ---------------------------------------------------------------------------
# parse_watchlist_changes
# ---------------------------------------------------------------------------

class TestParseWatchlistChanges:

    def test_sell_row_triggers_remove_for_known_ticker(self):
        from trading_loop import parse_watchlist_changes
        findings = """\
### WATCHLIST DECISIONS
| Ticker | Sector | Verdict  | Confidence | Reason              |
|--------|--------|----------|------------|---------------------|
| NVDA   | AI     | SELL     | HIGH       | overbought RSI=82   |
| MSFT   | Cloud  | HOLD     | MEDIUM     | fair value          |
"""
        result = parse_watchlist_changes(findings)
        assert "NVDA" in result["remove"]
        assert "MSFT" not in result["remove"]

    def test_remove_verdict_also_triggers_remove(self):
        from trading_loop import parse_watchlist_changes
        findings = "| AMD | AI | REMOVE | HIGH | cutting losses |\n"
        result = parse_watchlist_changes(findings)
        assert "AMD" in result["remove"]

    def test_new_picks_section_triggers_add(self):
        from trading_loop import parse_watchlist_changes
        findings = """\
### TOP 3 NEW PICKS

1. IONQ — quantum computing — IBM partnership — high risk
2. SMCI — server OEM — Nvidia rack wins — binary risk
3. WDAY — SaaS — AI HR workflow — medium risk
"""
        result = parse_watchlist_changes(findings)
        assert "IONQ" in result["add"]
        assert "SMCI" in result["add"]
        assert "WDAY" in result["add"]
        for ticker, info in result["add"].items():
            assert info["tier"] == "TACTICAL"

    def test_existing_watchlist_ticker_not_added_again(self):
        from trading_loop import parse_watchlist_changes
        # NVDA is already in WATCHLIST — should not be in adds even if in picks
        findings = "### TOP 3 NEW PICKS\n\n1. NVDA — AI — GPU — low risk\n"
        result = parse_watchlist_changes(findings)
        assert "NVDA" not in result["add"]

    def test_empty_findings_returns_empty(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes("")
        assert result["add"] == {}
        assert result["remove"] == []

    def test_malformed_table_does_not_crash(self):
        from trading_loop import parse_watchlist_changes
        result = parse_watchlist_changes("garbage | | | SELL | \n")
        # Should not raise, result may or may not have entries
        assert isinstance(result["add"], dict)
        assert isinstance(result["remove"], list)

    def test_both_add_and_remove_in_same_findings(self):
        from trading_loop import parse_watchlist_changes
        findings = """\
### WATCHLIST DECISIONS
| AMD | AI | SELL | HIGH | reason |

### TOP 3 NEW PICKS

1. IONQ — quantum — IBM — risk
"""
        result = parse_watchlist_changes(findings)
        assert "AMD" in result["remove"]
        assert "IONQ" in result["add"]


# ---------------------------------------------------------------------------
# load_watchlist_overrides / save_watchlist_overrides
# ---------------------------------------------------------------------------

class TestWatchlistOverrides:

    def test_no_overrides_file_returns_static_watchlist(self, tmp_path):
        import trading_loop as tl
        with patch.object(tl, "_OVERRIDES_FILE", tmp_path / "nonexistent.json"):
            result = tl.load_watchlist_overrides()
        # Must contain all static tickers
        from trading_loop import WATCHLIST
        for ticker in WATCHLIST:
            assert ticker in result

    def test_add_override_inserts_new_ticker(self, tmp_path):
        import trading_loop as tl
        overrides = {
            "add": {"IONQ": {"sector": "Quantum", "tier": "TACTICAL", "note": "test"}},
            "remove": [],
        }
        override_file = tmp_path / "watchlist_overrides.json"
        override_file.write_text(json.dumps(overrides))
        with patch.object(tl, "_OVERRIDES_FILE", override_file):
            result = tl.load_watchlist_overrides()
        assert "IONQ" in result

    def test_remove_override_drops_ticker(self, tmp_path):
        import trading_loop as tl
        overrides = {"add": {}, "remove": ["NVDA"]}
        override_file = tmp_path / "watchlist_overrides.json"
        override_file.write_text(json.dumps(overrides))
        with patch.object(tl, "_OVERRIDES_FILE", override_file):
            result = tl.load_watchlist_overrides()
        assert "NVDA" not in result

    def test_static_watchlist_not_mutated(self, tmp_path):
        import trading_loop as tl
        from trading_loop import WATCHLIST
        original_keys = set(WATCHLIST.keys())
        overrides = {"add": {"IONQ": {"sector": "X", "tier": "TACTICAL", "note": ""}}, "remove": ["NVDA"]}
        override_file = tmp_path / "watchlist_overrides.json"
        override_file.write_text(json.dumps(overrides))
        with patch.object(tl, "_OVERRIDES_FILE", override_file):
            tl.load_watchlist_overrides()
        assert set(WATCHLIST.keys()) == original_keys

    def test_save_creates_file(self, tmp_path):
        """RCAT is SPECULATIVE — removed on first SELL (no prior-day protection)."""
        import trading_loop as tl
        override_file = tmp_path / "overrides.json"
        with patch.object(tl, "_OVERRIDES_FILE", override_file):
            tl.save_watchlist_overrides(
                adds={"IONQ": {"sector": "X", "tier": "TACTICAL", "note": ""}},
                removes=["RCAT"],
            )
        assert override_file.exists()
        data = json.loads(override_file.read_text())
        assert "IONQ" in data["add"]
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e for e in data["remove"]]
        assert "RCAT" in remove_tickers

    def test_save_merges_with_existing(self, tmp_path):
        """Use RCAT (SPECULATIVE) for the remove — CORE/TACTICAL tickers need prior-day entry."""
        import trading_loop as tl
        override_file = tmp_path / "overrides.json"
        # Pre-existing: SMCI added
        override_file.write_text(json.dumps({
            "add": {"SMCI": {"sector": "X", "tier": "TACTICAL", "note": ""}},
            "remove": [],
        }))
        with patch.object(tl, "_OVERRIDES_FILE", override_file):
            tl.save_watchlist_overrides(
                adds={"IONQ": {"sector": "Y", "tier": "TACTICAL", "note": ""}},
                removes=["RCAT"],
            )
        data = json.loads(override_file.read_text())
        # Both adds must be present
        assert "SMCI" in data["add"]
        assert "IONQ" in data["add"]
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e for e in data["remove"]]
        assert "RCAT" in remove_tickers

    def test_save_resolves_ticker_in_both_add_and_remove(self, tmp_path):
        """A ticker in both add and remove: add wins (remove is cleaned up).
        This matches the save_watchlist_overrides implementation which removes
        the ticker from merged_removes when it also appears in merged_adds."""
        import trading_loop as tl
        override_file = tmp_path / "overrides.json"
        with patch.object(tl, "_OVERRIDES_FILE", override_file):
            tl.save_watchlist_overrides(
                adds={"IONQ": {"sector": "X", "tier": "TACTICAL", "note": ""}},
                removes=["IONQ"],
            )
        data = json.loads(override_file.read_text())
        # Add wins: IONQ is kept in add, removed from remove list
        assert "IONQ" in data["add"]
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e for e in data["remove"]]
        assert "IONQ" not in remove_tickers

    def test_corrupt_overrides_file_handled_gracefully(self, tmp_path):
        import trading_loop as tl
        override_file = tmp_path / "overrides.json"
        override_file.write_text("NOT VALID JSON{{{{")
        with patch.object(tl, "_OVERRIDES_FILE", override_file):
            result = tl.load_watchlist_overrides()
        # Should not raise — returns static watchlist
        from trading_loop import WATCHLIST
        assert set(result.keys()) == set(WATCHLIST.keys())


# ---------------------------------------------------------------------------
# Portfolio limit guard (BUY → HOLD downgrade)
# ---------------------------------------------------------------------------

class TestPortfolioLimitGuard:
    """Verify that analyse_and_trade downgrades BUY to HOLD when at position cap."""

    def _make_portfolio(self, n_positions: int) -> dict:
        return {
            "equity": 100000.0,
            "cash": 50000.0,
            "buying_power": 50000.0,
            "positions": [{"ticker": f"T{i}"} for i in range(n_positions)],
        }

    def test_buy_downgraded_at_cap(self):
        import trading_loop as tl
        import alpaca_bridge as ab

        mock_state = {"final_trade_decision": "FINAL DECISION: BUY\nCONVICTION: 8"}

        mock_ta = MagicMock()
        mock_ta.propagate.return_value = (mock_state, "BUY")

        mock_cb_inner = MagicMock()
        mock_cb_inner.total_cost = 0.001
        mock_cb_inner.prompt_tokens = 100
        mock_cb_inner.completion_tokens = 50

        mock_cb_ctx = MagicMock()
        mock_cb_ctx.__enter__ = MagicMock(return_value=mock_cb_inner)
        mock_cb_ctx.__exit__ = MagicMock(return_value=False)

        # Both TradingAgentsGraph and load_latest_research_context are imported
        # inside analyse_and_trade, so we patch at their real source locations.
        with patch("tradingagents.graph.trading_graph.TradingAgentsGraph",
                   return_value=mock_ta), \
             patch("tradingagents.research_context.load_latest_research_context",
                   return_value=""), \
             patch.object(tl, "_build_position_context", return_value=""), \
             patch.object(tl, "_build_returns_losses_summary", return_value=""), \
             patch("langchain_community.callbacks.get_openai_callback",
                   return_value=mock_cb_ctx), \
             patch.object(ab, "get_portfolio_summary",
                          return_value=self._make_portfolio(20)), \
             patch.object(ab, "execute_decision",
                          return_value={"action": "HOLD", "ticker": "NVDA"}):

            result = tl.analyse_and_trade("NVDA", "2026-03-26", 1000.0, dry_run=False,
                                           max_open_positions=20, current_open_positions=20)

        assert result["decision"] == "HOLD", (
            f"Expected HOLD (position cap), got {result['decision']}"
        )

    def test_buy_not_downgraded_below_cap(self):
        import trading_loop as tl
        import alpaca_bridge as ab

        mock_state = {"final_trade_decision": "FINAL DECISION: BUY\nCONVICTION: 8"}

        mock_ta = MagicMock()
        mock_ta.propagate.return_value = (mock_state, "BUY")

        mock_cb_inner = MagicMock()
        mock_cb_inner.total_cost = 0.001
        mock_cb_inner.prompt_tokens = 100
        mock_cb_inner.completion_tokens = 50

        mock_cb_ctx = MagicMock()
        mock_cb_ctx.__enter__ = MagicMock(return_value=mock_cb_inner)
        mock_cb_ctx.__exit__ = MagicMock(return_value=False)

        with patch("tradingagents.graph.trading_graph.TradingAgentsGraph",
                   return_value=mock_ta), \
             patch("tradingagents.research_context.load_latest_research_context",
                   return_value=""), \
             patch.object(tl, "_build_position_context", return_value=""), \
             patch.object(tl, "_build_returns_losses_summary", return_value=""), \
             patch("langchain_community.callbacks.get_openai_callback",
                   return_value=mock_cb_ctx), \
             patch.object(ab, "get_portfolio_summary",
                          return_value=self._make_portfolio(5)), \
             patch.object(ab, "execute_decision",
                          return_value={"action": "BUY", "ticker": "NVDA",
                                        "order_id": "abc", "qty": 0.5, "status": "new",
                                        "size_mult": 1.0, "conviction": 8}):

            result = tl.analyse_and_trade("NVDA", "2026-03-26", 1000.0, dry_run=False,
                                           max_open_positions=20, current_open_positions=5)

        assert result["decision"] == "BUY"
