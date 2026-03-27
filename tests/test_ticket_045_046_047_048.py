"""
Tests for TICKET-045, TICKET-046, TICKET-047, TICKET-048.

TICKET-045: Watchlist override decay, expiry, cap, CORE protection
TICKET-046: HOLD trade log includes agent_stop / agent_target / conviction
TICKET-047: Research findings coverage validation helper
TICKET-048: Stop/target directional swap in execute_decision + Risk Judge output
"""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch


# ===========================================================================
# TICKET-045 — Watchlist override decay, cap, CORE protection
# ===========================================================================

class TestRemoveExpiry:

    def test_expired_remove_dropped_on_load(self, tmp_path):
        """A remove entry older than _REMOVE_EXPIRY_DAYS is ignored during load."""
        import trading_loop as tl
        old_date = str(date.today() - timedelta(days=tl._REMOVE_EXPIRY_DAYS + 1))
        overrides = {
            "add": {},
            "remove": [{"ticker": "RCAT", "removed_on": old_date}],
        }
        f = tmp_path / "overrides.json"
        f.write_text(json.dumps(overrides))
        with patch.object(tl, "_OVERRIDES_FILE", f):
            effective = tl.load_watchlist_overrides()
        # Expired — RCAT should be present again
        assert "RCAT" in effective

    def test_fresh_remove_applied_on_load(self, tmp_path):
        """A remove entry dated today is applied normally."""
        import trading_loop as tl
        today = str(date.today())
        overrides = {
            "add": {},
            "remove": [{"ticker": "RCAT", "removed_on": today}],
        }
        f = tmp_path / "overrides.json"
        f.write_text(json.dumps(overrides))
        with patch.object(tl, "_OVERRIDES_FILE", f):
            effective = tl.load_watchlist_overrides()
        assert "RCAT" not in effective

    def test_expired_removes_cleaned_up_on_save(self, tmp_path):
        """save_watchlist_overrides drops expired removes from the file."""
        import trading_loop as tl
        old_date = str(date.today() - timedelta(days=tl._REMOVE_EXPIRY_DAYS + 1))
        f = tmp_path / "overrides.json"
        f.write_text(json.dumps({
            "add": {},
            "remove": [{"ticker": "MOS", "removed_on": old_date}],
        }))
        with patch.object(tl, "_OVERRIDES_FILE", f):
            tl.save_watchlist_overrides(adds={}, removes=[])
        data = json.loads(f.read_text())
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e for e in data["remove"]]
        assert "MOS" not in remove_tickers

    def test_legacy_string_remove_never_expires(self, tmp_path):
        """Plain-string entries (old format) have no date — treated as non-expiring."""
        import trading_loop as tl
        overrides = {"add": {}, "remove": ["RCAT"]}
        f = tmp_path / "overrides.json"
        f.write_text(json.dumps(overrides))
        with patch.object(tl, "_OVERRIDES_FILE", f):
            effective = tl.load_watchlist_overrides()
        # No date → non-expiring → still removed
        assert "RCAT" not in effective

    def test_new_remove_entries_stamped_with_today(self, tmp_path):
        """save_watchlist_overrides stamps new removes with today's date."""
        import trading_loop as tl
        f = tmp_path / "overrides.json"
        with patch.object(tl, "_OVERRIDES_FILE", f):
            tl.save_watchlist_overrides(adds={}, removes=["RCAT"])
        data = json.loads(f.read_text())
        remove_entries = data["remove"]
        assert len(remove_entries) == 1
        assert isinstance(remove_entries[0], dict)
        assert remove_entries[0]["ticker"] == "RCAT"
        assert remove_entries[0]["removed_on"] == str(date.today())


class TestRemoveCap:

    def test_removes_capped_at_max(self, tmp_path):
        """Total removes from static WATCHLIST are capped at _MAX_REMOVES."""
        import trading_loop as tl
        f = tmp_path / "overrides.json"
        # Build a list of _MAX_REMOVES + 2 non-CORE tickers to remove
        speculative_tactical = ["RCAT", "MOS", "RCKT", "CMC", "NUE", "APA", "SOC", "SCCO", "GLD", "GLD2"]
        candidates = speculative_tactical[:tl._MAX_REMOVES + 2]
        with patch.object(tl, "_OVERRIDES_FILE", f):
            tl.save_watchlist_overrides(adds={}, removes=candidates)
        data = json.loads(f.read_text())
        assert len(data["remove"]) <= tl._MAX_REMOVES


class TestCoreProtection:

    def test_single_day_sell_on_core_ticker_ignored(self, tmp_path):
        """A brand-new SELL on a CORE ticker with no prior remove entry is blocked."""
        import trading_loop as tl
        f = tmp_path / "overrides.json"
        with patch.object(tl, "_OVERRIDES_FILE", f):
            tl.save_watchlist_overrides(adds={}, removes=["NVDA"])  # NVDA is CORE
        data = json.loads(f.read_text())
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e for e in data["remove"]]
        assert "NVDA" not in remove_tickers

    def test_core_ticker_removed_after_prior_day_confirmation(self, tmp_path):
        """A CORE ticker with an existing remove entry is confirmed (kept in removes)."""
        import trading_loop as tl
        f = tmp_path / "overrides.json"
        yesterday = str(date.today() - timedelta(days=1))
        # Pre-seed: NVDA was already in removes yesterday
        f.write_text(json.dumps({
            "add": {},
            "remove": [{"ticker": "NVDA", "removed_on": yesterday}],
        }))
        with patch.object(tl, "_OVERRIDES_FILE", f):
            tl.save_watchlist_overrides(adds={}, removes=["NVDA"])
        data = json.loads(f.read_text())
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e for e in data["remove"]]
        assert "NVDA" in remove_tickers

    def test_non_core_ticker_removed_immediately(self, tmp_path):
        """TACTICAL/SPECULATIVE/HEDGE tickers have no prior-day protection."""
        import trading_loop as tl
        f = tmp_path / "overrides.json"
        with patch.object(tl, "_OVERRIDES_FILE", f):
            tl.save_watchlist_overrides(adds={}, removes=["RCAT"])  # SPECULATIVE
        data = json.loads(f.read_text())
        remove_tickers = [e["ticker"] if isinstance(e, dict) else e for e in data["remove"]]
        assert "RCAT" in remove_tickers


class TestAddCap:

    def test_adds_capped_at_max(self, tmp_path):
        """Accumulated adds are capped at _MAX_ADDS; oldest dropped first."""
        import trading_loop as tl
        f = tmp_path / "overrides.json"
        # Pre-seed with _MAX_ADDS existing adds (with old dates)
        old_date = str(date.today() - timedelta(days=10))
        existing_adds = {f"OLD{i}": {"sector": "X", "tier": "TACTICAL",
                                      "note": "", "added_on": old_date}
                         for i in range(tl._MAX_ADDS)}
        f.write_text(json.dumps({"add": existing_adds, "remove": []}))
        # Now save one more new add
        with patch.object(tl, "_OVERRIDES_FILE", f):
            tl.save_watchlist_overrides(
                adds={"NEWT": {"sector": "Y", "tier": "TACTICAL", "note": ""}},
                removes=[]
            )
        data = json.loads(f.read_text())
        assert len(data["add"]) <= tl._MAX_ADDS
        # Newest add should be kept
        assert "NEWT" in data["add"]


# ===========================================================================
# TICKET-046 — HOLD includes agent_stop, agent_target, conviction in log
# ===========================================================================

class TestHoldIncludesStopTarget:

    def _make_hold_decision_text(self, stop=394.42, target=420.00, conviction=6):
        return (
            f"FINAL DECISION: HOLD\n"
            f"CONVICTION: {conviction}\n"
            f"STOP-LOSS: ${stop}\n"
            f"TARGET: ${target}\n"
            f"POSITION SIZE: 0.5x\n"
        )

    def test_hold_includes_conviction_and_size_mult(self):
        import alpaca_bridge as ab
        decision_text = self._make_hold_decision_text()
        with patch.object(ab, "_get_trading_client", return_value=MagicMock()):
            result = ab.execute_decision("MU", "HOLD", 2000.0,
                                          agent_decision_text=decision_text)
        assert result["action"] == "HOLD"
        assert result["conviction"] == 6
        assert result["size_mult"] == 0.5

    def test_hold_includes_agent_stop_when_provided(self):
        """agent_stop is present; value may be corrected if stop was above price."""
        import alpaca_bridge as ab
        decision_text = self._make_hold_decision_text(stop=394.42, target=420.00)
        with patch.object(ab, "_get_trading_client", return_value=MagicMock()), \
             patch.object(ab, "get_latest_price", return_value=400.0):
            result = ab.execute_decision("MU", "HOLD", 2000.0,
                                          agent_decision_text=decision_text)
        assert "agent_stop" in result
        # Stop must be below the mock price of 400 (correct direction enforced)
        assert result["agent_stop"] < 400.0

    def test_hold_includes_agent_target_when_provided(self):
        import alpaca_bridge as ab
        decision_text = self._make_hold_decision_text(stop=350.00, target=420.00)
        with patch.object(ab, "_get_trading_client", return_value=MagicMock()), \
             patch.object(ab, "get_latest_price", return_value=380.0):
            result = ab.execute_decision("MU", "HOLD", 2000.0,
                                          agent_decision_text=decision_text)
        assert "agent_target" in result
        assert abs(result["agent_target"] - 420.00) < 0.01

    def test_hold_without_stop_target_still_works(self):
        import alpaca_bridge as ab
        with patch.object(ab, "_get_trading_client", return_value=MagicMock()):
            result = ab.execute_decision("MU", "HOLD", 2000.0, agent_decision_text="")
        assert result["action"] == "HOLD"
        assert "agent_stop" not in result
        assert "agent_target" not in result


# ===========================================================================
# TICKET-047 — Research findings coverage validation
# ===========================================================================

class TestFindingsCoverageValidation:

    def _make_findings(self, tickers: list[str]) -> str:
        rows = "\n".join(f"| {t} | C | HOLD | Medium | stable |" for t in tickers)
        return f"""## RESEARCH FINDINGS
### WATCHLIST DECISIONS:
| Ticker | Tier | Decision | Conviction | Reason |
|--------|------|----------|------------|--------|
{rows}
"""

    def test_all_present_returns_empty_list(self):
        from daily_research import _validate_findings_coverage
        watchlist = ["NVDA", "AAPL", "MSFT"]
        findings = self._make_findings(watchlist)
        missing = _validate_findings_coverage(findings, watchlist)
        assert missing == []

    def test_missing_ticker_returned(self):
        from daily_research import _validate_findings_coverage
        watchlist = ["NVDA", "AAPL", "SOC"]
        findings = self._make_findings(["NVDA", "AAPL"])  # SOC missing
        missing = _validate_findings_coverage(findings, watchlist)
        assert "SOC" in missing
        assert "NVDA" not in missing

    def test_empty_findings_returns_all_tickers(self):
        from daily_research import _validate_findings_coverage
        watchlist = ["NVDA", "AAPL"]
        missing = _validate_findings_coverage("no table here", watchlist)
        assert set(missing) == set(watchlist)

    def test_empty_watchlist_always_passes(self):
        from daily_research import _validate_findings_coverage
        findings = self._make_findings(["NVDA"])
        missing = _validate_findings_coverage(findings, [])
        assert missing == []

    def test_max_tokens_is_3000(self):
        """Verify max_tokens was raised to 3000 in call_llm."""
        import inspect
        import daily_research as dr
        src = inspect.getsource(dr.call_llm)
        assert "max_tokens=3000" in src, \
            "max_tokens should be 3000 (was 2000 before TICKET-047)"


# ===========================================================================
# TICKET-048 — Stop/target directional swap in execute_decision
# ===========================================================================

class TestStopTargetDirectionalSwap:

    def _mock_buy_order(self, ticker="TEST"):
        mock_order = MagicMock()
        mock_order.id = "abc-123"
        mock_order.qty = 5.0
        mock_order.status = "accepted"
        return mock_order

    def _make_decision_text(self, signal, stop, target, conviction=7, size="1x"):
        return (
            f"FINAL DECISION: {signal}\n"
            f"CONVICTION: {conviction}\n"
            f"STOP-LOSS: ${stop}\n"
            f"TARGET: ${target}\n"
            f"POSITION SIZE: {size}\n"
        )

    def test_buy_stop_above_price_corrected(self):
        """BUY where stop > price → stop corrected to 5% below entry (TICKET-049)."""
        import alpaca_bridge as ab
        # Price=100, stop=120 (above entry) — partial inversion caught by new logic
        decision_text = self._make_decision_text("BUY", stop=120, target=150)
        mock_tc = MagicMock()
        mock_tc.get_account.return_value.cash = "10000"
        mock_tc.submit_order.return_value = self._mock_buy_order()

        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "get_latest_price", return_value=100.0):
            result = ab.execute_decision("TEST", "BUY", 1000.0,
                                          agent_decision_text=decision_text)

        # Stop corrected to 95% of price = 95.0
        assert result.get("agent_stop", 0) < 100.0, \
            f"stop should be below price after correction, got {result.get('agent_stop')}"
        assert abs(result.get("agent_stop", 0) - 95.0) < 0.01
        # Target unchanged — already above price
        assert abs(result.get("agent_target", 0) - 150.0) < 0.01

    def test_buy_correct_stop_unchanged(self):
        """BUY where stop < price → stop unchanged."""
        import alpaca_bridge as ab
        decision_text = self._make_decision_text("BUY", stop=80, target=130)
        mock_tc = MagicMock()
        mock_tc.get_account.return_value.cash = "10000"
        mock_tc.submit_order.return_value = self._mock_buy_order()

        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "get_latest_price", return_value=100.0):
            result = ab.execute_decision("TEST", "BUY", 1000.0,
                                          agent_decision_text=decision_text)

        assert abs(result.get("agent_stop", 0) - 80) < 0.01
        assert abs(result.get("agent_target", 0) - 130) < 0.01

    def test_sell_stop_below_price_corrected(self):
        """SELL where stop < price → stop corrected to 5% above entry."""
        import alpaca_bridge as ab
        decision_text = self._make_decision_text("SELL", stop=80, target=60)
        mock_tc = MagicMock()
        mock_tc.get_open_position.return_value.qty = "10"
        mock_tc.submit_order.return_value = self._mock_buy_order()

        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "get_latest_price", return_value=100.0):
            result = ab.execute_decision("TEST", "SELL", 1000.0,
                                          agent_decision_text=decision_text)

        # Stop corrected to 105% of price = 105.0
        assert result.get("agent_stop", 0) > 100.0
        assert abs(result.get("agent_stop", 0) - 105.0) < 0.01

    def test_hold_inverted_stop_above_price_corrected(self):
        """HOLD where stop > price → stop corrected to 5% below price."""
        import alpaca_bridge as ab
        # Mirrors the MU real-world bug: stop=394 > price=382
        decision_text = self._make_decision_text("HOLD", stop=394, target=420)
        with patch.object(ab, "_get_trading_client", return_value=MagicMock()), \
             patch.object(ab, "get_latest_price", return_value=382.0):
            result = ab.execute_decision("MU", "HOLD", 2000.0,
                                          agent_decision_text=decision_text)

        # Stop must be below price=382 after correction
        assert result["agent_stop"] < 382.0
        # Target is already above price — unchanged
        assert abs(result["agent_target"] - 420.0) < 0.01

    def test_risk_judge_prompt_contains_directional_constraint(self):
        """Verify the Risk Judge prompt was updated with the directional stop/target rule."""
        import inspect
        from tradingagents.agents.managers import risk_manager
        src = inspect.getsource(risk_manager)
        assert "STOP-LOSS must be BELOW current price" in src, \
            "Risk Judge prompt missing directional stop/target constraint (TICKET-048)"
        assert "TARGET must be ABOVE current price" in src
