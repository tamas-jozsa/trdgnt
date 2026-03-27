"""
Tests for TICKET-053, TICKET-054, TICKET-055, TICKET-056.

TICKET-053: WAIT vs HOLD distinction in execute_decision + cycle summary
TICKET-054: 30-day target constraint in all three decision-agent prompts
TICKET-055: check_agent_stops() reads log and fires on price ≤ agent_stop
TICKET-056: _warn_multi_run_sessions detects ghost log sessions
"""

import json
import pytest
from pathlib import Path
from datetime import date, timedelta
from unittest.mock import MagicMock, patch


# ===========================================================================
# TICKET-053 — WAIT vs HOLD
# ===========================================================================

class TestWaitVsHold:

    def test_hold_with_open_position_returns_hold(self):
        """HOLD + has position → action='HOLD'."""
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.get_open_position.return_value.qty = "5.0"
        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = ab.execute_decision("NVDA", "HOLD", 1000.0)
        assert result["action"] == "HOLD"

    def test_hold_without_position_returns_wait(self):
        """HOLD + no position → action='WAIT'."""
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.get_open_position.side_effect = Exception("no position")
        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = ab.execute_decision("NVDA", "HOLD", 1000.0)
        assert result["action"] == "WAIT"

    def test_wait_result_includes_conviction_and_size_mult(self):
        """WAIT result carries the same structured fields as HOLD."""
        import alpaca_bridge as ab
        decision_text = "FINAL DECISION: HOLD\nCONVICTION: 7\nPOSITION SIZE: 0.5x\n"
        mock_tc = MagicMock()
        mock_tc.get_open_position.side_effect = Exception("no position")
        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = ab.execute_decision("NVDA", "HOLD", 1000.0,
                                          agent_decision_text=decision_text)
        assert result["action"] == "WAIT"
        assert result["conviction"] == 7
        assert result["size_mult"] == 0.5

    def test_wait_does_not_place_order(self):
        """WAIT must never call submit_order."""
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.get_open_position.side_effect = Exception("no position")
        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            ab.execute_decision("NVDA", "HOLD", 1000.0)
        mock_tc.submit_order.assert_not_called()

    def test_cycle_summary_separates_wait_from_hold(self):
        """Cycle summary counts WAIT separately from HOLD."""
        import trading_loop as tl
        results = [
            {"ticker": "NVDA", "decision": "HOLD",
             "order": {"action": "HOLD"}, "error": None,
             "llm_cost": 0.01, "llm_tokens_in": 100, "llm_tokens_out": 50},
            {"ticker": "GOOGL", "decision": "HOLD",
             "order": {"action": "WAIT"}, "error": None,
             "llm_cost": 0.01, "llm_tokens_in": 100, "llm_tokens_out": 50},
            {"ticker": "MSFT", "decision": "BUY",
             "order": {"action": "BUY", "qty": 1.0}, "error": None,
             "llm_cost": 0.01, "llm_tokens_in": 100, "llm_tokens_out": 50},
        ]
        holds = [r["ticker"] for r in results
                 if r["decision"] == "HOLD"
                 and (r.get("order") or {}).get("action") == "HOLD"]
        waits = [r["ticker"] for r in results
                 if r["decision"] == "HOLD"
                 and (r.get("order") or {}).get("action") == "WAIT"]
        assert holds == ["NVDA"]
        assert waits == ["GOOGL"]


# ===========================================================================
# TICKET-054 — 30-day target constraint in prompts
# ===========================================================================

class TestThirtyDayTargetConstraint:

    def test_research_manager_prompt_has_target_constraint(self):
        import inspect
        from tradingagents.agents.managers import research_manager
        src = inspect.getsource(research_manager)
        assert "Do NOT" in src and "analyst" in src.lower() and "TARGET" in src, \
            "Research Manager prompt missing 30-day target constraint (TICKET-054)"

    def test_trader_prompt_has_target_constraint(self):
        import inspect
        from tradingagents.agents.trader import trader
        src = inspect.getsource(trader)
        assert "Do NOT" in src and "analyst" in src.lower(), \
            "Trader prompt missing 30-day target constraint (TICKET-054)"

    def test_risk_judge_prompt_has_target_constraint(self):
        import inspect
        from tradingagents.agents.managers import risk_manager
        src = inspect.getsource(risk_manager)
        assert "Do NOT" in src and "analyst" in src.lower() and "TARGET" in src, \
            "Risk Judge prompt missing 30-day target constraint (TICKET-054)"

    def test_all_prompts_mention_30_day_range(self):
        import inspect
        from tradingagents.agents.managers import research_manager, risk_manager
        from tradingagents.agents.trader import trader
        for mod in [research_manager, risk_manager, trader]:
            src = inspect.getsource(mod)
            assert "30" in src, f"{mod.__name__} prompt missing 30-day reference"


# ===========================================================================
# TICKET-055 — check_agent_stops
# ===========================================================================

class TestCheckAgentStops:

    def _make_log(self, tmp_path: Path, ticker: str, agent_stop: float,
                  date_str: str | None = None) -> Path:
        """Write a minimal trade log with a BUY entry containing agent_stop."""
        d = date_str or str(date.today())
        log = tmp_path / f"{d}.json"
        log.write_text(json.dumps({
            "date": d,
            "trades": [{
                "ticker": ticker,
                "decision": "BUY",
                "order": {
                    "action": "BUY",
                    "ticker": ticker,
                    "agent_stop": agent_stop,
                    "agent_target": agent_stop * 1.15,
                    "conviction": 7,
                    "qty": 5.0,
                },
                "time": f"{d}T10:30:00-04:00",
            }]
        }))
        return log

    def test_price_above_stop_no_trigger(self, tmp_path):
        """Price > agent_stop → no sell."""
        import alpaca_bridge as ab
        self._make_log(tmp_path, "NVDA", agent_stop=100.0)

        mock_tc = MagicMock()
        mock_pos = MagicMock()
        mock_pos.symbol = "NVDA"
        mock_pos.qty = "5.0"
        mock_tc.get_all_positions.return_value = [mock_pos]

        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "get_latest_price", return_value=120.0):
            results = ab.check_agent_stops(log_dir=str(tmp_path))

        assert results == []
        mock_tc.submit_order.assert_not_called()

    def test_price_at_stop_triggers_sell(self, tmp_path):
        """Price == agent_stop → sell triggered."""
        import alpaca_bridge as ab
        self._make_log(tmp_path, "NVDA", agent_stop=100.0)

        mock_tc = MagicMock()
        mock_pos = MagicMock()
        mock_pos.symbol = "NVDA"
        mock_pos.qty = "5.0"
        mock_tc.get_all_positions.return_value = [mock_pos]
        mock_tc.submit_order.return_value.id = "order-123"
        mock_tc.submit_order.return_value.status = "accepted"

        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "get_latest_price", return_value=100.0):
            results = ab.check_agent_stops(log_dir=str(tmp_path))

        assert len(results) == 1
        assert results[0]["action"] == "AGENT_STOP_TRIGGERED"
        assert results[0]["ticker"] == "NVDA"
        mock_tc.submit_order.assert_called_once()

    def test_price_below_stop_triggers_sell(self, tmp_path):
        """Price < agent_stop → sell triggered."""
        import alpaca_bridge as ab
        self._make_log(tmp_path, "NVDA", agent_stop=100.0)

        mock_tc = MagicMock()
        mock_pos = MagicMock()
        mock_pos.symbol = "NVDA"
        mock_pos.qty = "5.0"
        mock_tc.get_all_positions.return_value = [mock_pos]
        mock_tc.submit_order.return_value.id = "order-456"
        mock_tc.submit_order.return_value.status = "accepted"

        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "get_latest_price", return_value=90.0):
            results = ab.check_agent_stops(log_dir=str(tmp_path))

        assert len(results) == 1
        assert results[0]["agent_stop"] == 100.0
        assert results[0]["price"] == 90.0

    def test_dry_run_no_order_placed(self, tmp_path):
        """dry_run=True → logs but does not submit order."""
        import alpaca_bridge as ab
        self._make_log(tmp_path, "NVDA", agent_stop=100.0)

        mock_tc = MagicMock()
        mock_pos = MagicMock()
        mock_pos.symbol = "NVDA"
        mock_pos.qty = "5.0"
        mock_tc.get_all_positions.return_value = [mock_pos]

        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "get_latest_price", return_value=90.0):
            results = ab.check_agent_stops(log_dir=str(tmp_path), dry_run=True)

        assert results[0]["dry_run"] is True
        mock_tc.submit_order.assert_not_called()

    def test_no_position_for_logged_stop_skipped(self, tmp_path):
        """agent_stop found in log but no open position — no trigger."""
        import alpaca_bridge as ab
        self._make_log(tmp_path, "NVDA", agent_stop=100.0)

        mock_tc = MagicMock()
        mock_tc.get_all_positions.return_value = []  # no positions

        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            results = ab.check_agent_stops(log_dir=str(tmp_path))

        assert results == []

    def test_no_logs_returns_empty(self, tmp_path):
        """Empty log directory → no triggers."""
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.get_all_positions.return_value = []
        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            results = ab.check_agent_stops(log_dir=str(tmp_path))
        assert results == []


# ===========================================================================
# TICKET-056 — Multi-run ghost session detection
# ===========================================================================

class TestWarnMultiRunSessions:

    def test_clean_log_no_warning(self, tmp_path, capsys):
        """A log with normal entry count produces no warning."""
        import trading_loop as tl
        today = str(date.today())
        log = tmp_path / f"{today}.json"
        log.write_text(json.dumps({
            "date": today,
            "trades": [{"ticker": f"T{i}", "decision": "HOLD"} for i in range(5)]
        }))
        with patch.object(tl, "LOG_DIR", tmp_path):
            tl._warn_multi_run_sessions(watchlist_size=10)
        out = capsys.readouterr().out
        assert "WARNING" not in out

    def test_bloated_log_triggers_warning(self, tmp_path, capsys):
        """A log with > 2× watchlist entries triggers a warning."""
        import trading_loop as tl
        today = str(date.today())
        log = tmp_path / f"{today}.json"
        # 25 entries for watchlist_size=10 → exceeds 2×10=20 threshold
        log.write_text(json.dumps({
            "date": today,
            "trades": [{"ticker": f"T{i}", "decision": "HOLD"} for i in range(25)]
        }))
        with patch.object(tl, "LOG_DIR", tmp_path):
            tl._warn_multi_run_sessions(watchlist_size=10)
        out = capsys.readouterr().out
        assert "WARNING" in out

    def test_annotated_log_no_warning(self, tmp_path, capsys):
        """A log already marked multi_run_session=True suppresses the warning."""
        import trading_loop as tl
        today = str(date.today())
        log = tmp_path / f"{today}.json"
        log.write_text(json.dumps({
            "date": today,
            "multi_run_session": True,
            "trades": [{"ticker": f"T{i}", "decision": "HOLD"} for i in range(25)]
        }))
        with patch.object(tl, "LOG_DIR", tmp_path):
            tl._warn_multi_run_sessions(watchlist_size=10)
        out = capsys.readouterr().out
        assert "WARNING" not in out
