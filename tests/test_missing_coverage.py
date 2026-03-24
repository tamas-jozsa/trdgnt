"""Tests for TICKET-016: previously missing test coverage."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# TICKET-003: tier_amount correctness
# ---------------------------------------------------------------------------

class TestTierAmount:

    def test_core_is_2x(self):
        from trading_loop import tier_amount
        assert tier_amount(1000.0, "NVDA") == 2000.0

    def test_tactical_is_1x(self):
        from trading_loop import tier_amount
        assert tier_amount(1000.0, "CMC") == 1000.0

    def test_speculative_is_0_4x(self):
        from trading_loop import tier_amount
        assert tier_amount(1000.0, "RCAT") == 400.0

    def test_hedge_is_0_5x(self):
        from trading_loop import tier_amount
        assert tier_amount(1000.0, "GLD") == 500.0

    def test_unknown_ticker_defaults_to_tactical(self):
        from trading_loop import tier_amount
        # unknown ticker → TACTICAL tier → 1x
        assert tier_amount(1000.0, "UNKNOWN_XYZ") == 1000.0

    def test_custom_base_amount(self):
        from trading_loop import tier_amount
        assert tier_amount(500.0, "NVDA") == 1000.0   # CORE 2x
        assert tier_amount(500.0, "RCAT") == 200.0    # SPECULATIVE 0.4x


# ---------------------------------------------------------------------------
# TICKET-004: TradingAgentsGraph.load_memories reads all 5 agent files
# ---------------------------------------------------------------------------

class TestLoadMemoriesFromDir:

    def test_load_memories_populates_all_5_agents(self, tmp_path):
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        # Write memory JSON files for all 5 agents
        agents = [
            "bull_memory", "bear_memory", "trader_memory",
            "invest_judge_memory", "risk_manager_memory",
        ]
        for agent in agents:
            data = [
                {"situation": f"{agent} situation 1", "recommendation": "rec 1"},
                {"situation": f"{agent} situation 2", "recommendation": "rec 2"},
            ]
            (tmp_path / f"{agent}.json").write_text(json.dumps(data))

        # Create a graph with mocked LLMs
        with patch("tradingagents.graph.trading_graph.create_llm_client") as mock_client, \
             patch("tradingagents.graph.trading_graph.set_config"), \
             patch("tradingagents.graph.trading_graph.GraphSetup") as mock_setup, \
             patch("os.makedirs"):
            mock_llm = MagicMock()
            mock_client.return_value.get_llm.return_value = mock_llm
            mock_setup.return_value.setup_graph.return_value = MagicMock()
            ta = TradingAgentsGraph()

        ta.load_memories(str(tmp_path))

        # All 5 agent memories should now have 2 documents each
        mem_map = ta._memory_map()
        for agent_name, mem in mem_map.items():
            assert len(mem.documents) == 2, \
                f"{agent_name} should have 2 docs after load, got {len(mem.documents)}"

    def test_load_memories_graceful_when_files_missing(self, tmp_path):
        """load_memories should not raise if files don't exist."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        with patch("tradingagents.graph.trading_graph.create_llm_client") as mock_client, \
             patch("tradingagents.graph.trading_graph.set_config"), \
             patch("tradingagents.graph.trading_graph.GraphSetup") as mock_setup, \
             patch("os.makedirs"):
            mock_llm = MagicMock()
            mock_client.return_value.get_llm.return_value = mock_llm
            mock_setup.return_value.setup_graph.return_value = MagicMock()
            ta = TradingAgentsGraph()

        # Should not raise even though no files exist
        ta.load_memories(str(tmp_path / "nonexistent"))

        for mem in ta._memory_map().values():
            assert len(mem.documents) == 0


# ---------------------------------------------------------------------------
# TICKET-011: reflect_and_remember is called after a trade
# ---------------------------------------------------------------------------

class TestReflectCalledAfterTrade:

    def test_reflect_called_when_position_exists(self):
        """When a prior position exists, reflect_and_remember should be called."""
        import trading_loop as tl
        import alpaca_bridge as ab

        mock_pos = MagicMock()
        mock_pos.qty = "10.0"
        mock_pos.avg_entry_price = "142.30"
        mock_pos.unrealized_plpc = "-0.082"
        mock_pos.unrealized_pl   = "-116.69"

        mock_tc = MagicMock()
        mock_tc.get_open_position.return_value = mock_pos

        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = tl._build_returns_losses_summary("NVDA")

        assert "gained" in result or "lost" in result
        assert "NVDA" in result
        assert "-8.2%" in result

    def test_returns_losses_empty_when_no_position_no_logs(self, tmp_path, monkeypatch):
        """No position + no logs → empty string."""
        import trading_loop as tl
        import alpaca_bridge as ab

        mock_tc = MagicMock()
        mock_tc.get_open_position.side_effect = Exception("no position")

        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            monkeypatch.chdir(tmp_path)  # empty dir — no trade log files
            result = tl._build_returns_losses_summary("NVDA")

        assert result == ""

    def test_returns_losses_from_trade_log(self, tmp_path, monkeypatch):
        """Falls back to trade log when no open position."""
        import trading_loop as tl
        import alpaca_bridge as ab
        from pathlib import Path

        # Write a fake trade log in tmp_path
        log = {
            "date": "2026-03-23",
            "trades": [
                {"ticker": "NVDA", "decision": "BUY", "order": {}, "error": None}
            ]
        }
        log_dir = tmp_path / "trading_loop_logs"
        log_dir.mkdir()
        (log_dir / "2026-03-23.json").write_text(json.dumps(log))

        mock_tc = MagicMock()
        mock_tc.get_open_position.side_effect = Exception("no position")

        # Patch PROJECT_ROOT so the absolute log path points to tmp_path
        with patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(tl, "PROJECT_ROOT", tmp_path):
            result = tl._build_returns_losses_summary("NVDA")

        assert "BUY" in result
        assert "NVDA" in result


# ---------------------------------------------------------------------------
# Fix dead conditional in test_position_context.py (regression check)
# ---------------------------------------------------------------------------

class TestPositionContextPatchIsSane:
    """Verify the position context mock correctly patches alpaca_bridge."""

    def test_no_position_returns_empty(self):
        import trading_loop as tl
        import alpaca_bridge as ab

        mock_tc = MagicMock()
        mock_tc.get_open_position.side_effect = Exception("no pos")

        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = tl._build_position_context("NVDA")

        assert result == ""


# ---------------------------------------------------------------------------
# TICKET-012: CSV cache cleanup unit test
# ---------------------------------------------------------------------------

class TestCsvCacheCleanup:

    def test_deletes_old_files_keeps_fresh(self, tmp_path):
        import time
        from tradingagents.dataflows import y_finance as yf_mod

        # Reset the guard so cleanup runs fresh for this test
        yf_mod._cache_cleaned = False

        # Create 2 old CSV files and 1 fresh one
        old1  = tmp_path / "NVDA-YFin-data-2026-01-01-2026-01-02.csv"
        old2  = tmp_path / "AAPL-YFin-data-2026-01-01-2026-01-02.csv"
        fresh = tmp_path / "MSFT-YFin-data-2026-03-22-2026-03-24.csv"
        for p in [old1, old2, fresh]:
            p.write_text("dummy")

        cutoff = time.time() - 3 * 86400
        import os
        os.utime(str(old1), (cutoff, cutoff))
        os.utime(str(old2), (cutoff, cutoff))

        yf_mod._cleanup_old_cache_files(str(tmp_path))

        remaining = list(tmp_path.iterdir())
        assert len(remaining) == 1
        assert remaining[0].name == "MSFT-YFin-data-2026-03-22-2026-03-24.csv"

    def test_runs_once_per_process(self, tmp_path):
        """Second call should be a no-op (guard flag)."""
        import time
        from tradingagents.dataflows import y_finance as yf_mod

        yf_mod._cache_cleaned = False

        old = tmp_path / "OLD-YFin-data-2025-01-01-2025-01-02.csv"
        old.write_text("dummy")
        cutoff = time.time() - 3 * 86400
        import os
        os.utime(str(old), (cutoff, cutoff))

        # First call — should delete
        yf_mod._cleanup_old_cache_files(str(tmp_path))
        assert not old.exists()

        # Recreate and call again — should NOT delete (guard prevents it)
        old.write_text("dummy")
        os.utime(str(old), (cutoff, cutoff))
        yf_mod._cleanup_old_cache_files(str(tmp_path))
        assert old.exists(), "Second call should be no-op due to _cache_cleaned guard"

        # Reset for other tests
        yf_mod._cache_cleaned = False
