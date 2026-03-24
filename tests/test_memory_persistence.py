"""Tests for TICKET-004: persistent agent memory across restarts."""

import json
import pytest
from pathlib import Path


class TestMemoryPersistence:

    def test_save_creates_file(self, tmp_path):
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        mem = FinancialSituationMemory("test")
        mem.add_situations([("market up 10%", "BUY momentum"), ("bear trend", "SELL")])

        path = str(tmp_path / "test_memory.json")
        mem.save(path)

        assert Path(path).exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        mem1 = FinancialSituationMemory("test")
        mem1.add_situations([
            ("RSI oversold, MACD turning up", "BUY — momentum reversal"),
            ("Price below 200 SMA, volume declining", "SELL — downtrend confirmed"),
        ])
        path = str(tmp_path / "memory.json")
        mem1.save(path)

        mem2 = FinancialSituationMemory("test")
        mem2.load(path)

        assert len(mem2.documents) == 2
        assert "RSI oversold" in mem2.documents[0]
        assert "BUY" in mem2.recommendations[0]

    def test_load_nonexistent_file_is_silent(self, tmp_path):
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        mem = FinancialSituationMemory("test")
        mem.load(str(tmp_path / "nonexistent.json"))   # should not raise

        assert len(mem.documents) == 0

    def test_load_merges_into_existing(self, tmp_path):
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        # Save one entry
        mem1 = FinancialSituationMemory("test")
        mem1.add_situations([("entry 1", "rec 1")])
        path = str(tmp_path / "memory.json")
        mem1.save(path)

        # Load into a mem that already has data
        mem2 = FinancialSituationMemory("test")
        mem2.add_situations([("entry 2", "rec 2")])
        mem2.load(path)

        assert len(mem2.documents) == 2

    def test_max_entries_cap(self):
        from tradingagents.agents.utils.memory import FinancialSituationMemory, MAX_MEMORY_ENTRIES

        mem = FinancialSituationMemory("test")
        # Add more than the cap
        pairs = [(f"situation {i}", f"rec {i}") for i in range(MAX_MEMORY_ENTRIES + 50)]
        mem.add_situations(pairs)

        assert len(mem.documents) <= MAX_MEMORY_ENTRIES
        # Oldest entries should be evicted; newest should remain
        assert "situation 549" in mem.documents[-1]  # last added

    def test_saved_json_is_valid_structure(self, tmp_path):
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        mem = FinancialSituationMemory("test")
        mem.add_situations([("Iran war, oil up 20%", "BUY energy stocks")])
        path = str(tmp_path / "memory.json")
        mem.save(path)

        with open(path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert "situation" in data[0]
        assert "recommendation" in data[0]

    def test_bm25_retrieval_works_after_load(self, tmp_path):
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        mem1 = FinancialSituationMemory("test")
        mem1.add_situations([
            ("oil prices rising on geopolitical risk", "BUY energy ETFs"),
            ("tech selloff, RSI 25 oversold", "BUY tech on dip"),
        ])
        path = str(tmp_path / "memory.json")
        mem1.save(path)

        mem2 = FinancialSituationMemory("test")
        mem2.load(path)

        results = mem2.get_memories("oil prices spike Middle East tension", n_matches=1)
        assert len(results) == 1
        assert "energy" in results[0]["recommendation"].lower()


class TestTradingGraphMemoryMethods:

    def test_memory_map_has_5_agents(self):
        """_memory_map returns all 5 agent memories."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from unittest.mock import patch, MagicMock

        # Patch LLM creation so we don't need API keys
        with patch("tradingagents.graph.trading_graph.create_llm_client") as mock_client, \
             patch("tradingagents.graph.trading_graph.set_config"), \
             patch("tradingagents.graph.trading_graph.GraphSetup") as mock_setup, \
             patch("os.makedirs"):

            mock_llm = MagicMock()
            mock_client.return_value.get_llm.return_value = mock_llm
            mock_setup.return_value.setup_graph.return_value = MagicMock()

            ta = TradingAgentsGraph()
            mem_map = ta._memory_map()

        assert set(mem_map.keys()) == {
            "bull_memory", "bear_memory", "trader_memory",
            "invest_judge_memory", "risk_manager_memory",
        }
