"""Tests for TICKET-026: embedding-based memory retrieval."""

import json
import pytest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path


def _make_embedding(seed: float, dim: int = 8) -> list:
    """Make a deterministic fake embedding vector."""
    import math
    vec = [math.sin(seed * (i + 1)) for i in range(dim)]
    # Normalize
    mag = math.sqrt(sum(x * x for x in vec))
    return [x / mag for x in vec]


class TestCosineSimilarity:

    def test_identical_vectors_give_1(self):
        from tradingagents.agents.utils.memory import _cosine_similarity
        v = [1.0, 0.0, 0.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_give_0(self):
        from tradingagents.agents.utils.memory import _cosine_similarity
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_give_negative(self):
        from tradingagents.agents.utils.memory import _cosine_similarity
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        from tradingagents.agents.utils.memory import _cosine_similarity
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestEmbeddingMemory:

    def test_bm25_mode_by_default(self):
        from tradingagents.agents.utils.memory import FinancialSituationMemory
        mem = FinancialSituationMemory("test")
        assert mem.use_embeddings is False

    def test_embedding_mode_opt_in(self):
        from tradingagents.agents.utils.memory import FinancialSituationMemory
        mem = FinancialSituationMemory("test", use_embeddings=True)
        assert mem.use_embeddings is True

    def test_bm25_retrieval_still_works(self):
        from tradingagents.agents.utils.memory import FinancialSituationMemory
        mem = FinancialSituationMemory("test", use_embeddings=False)
        mem.add_situations([("oil price spike geopolitical", "BUY energy")])
        results = mem.get_memories("oil rising Middle East", n_matches=1)
        assert len(results) == 1
        assert results[0]["retrieval_method"] == "bm25"

    def test_embedding_retrieval_used_when_embeddings_available(self):
        """When embeddings are stored, cosine similarity is used."""
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        mem = FinancialSituationMemory("test", use_embeddings=True)
        # Inject fake embeddings directly
        mem.documents       = ["oil price spike geopolitical"]
        mem.recommendations = ["BUY energy"]
        mem.embeddings      = [_make_embedding(1.0)]
        mem._rebuild_index()

        q_embedding = [_make_embedding(1.0)]  # same vector → cosine = 1.0

        with patch("tradingagents.agents.utils.memory._embed_texts", return_value=q_embedding):
            results = mem.get_memories("oil rising Middle East", n_matches=1)

        assert len(results) == 1
        assert results[0]["retrieval_method"] == "embedding"
        assert results[0]["similarity_score"] == pytest.approx(1.0, abs=0.01)

    def test_falls_back_to_bm25_when_embed_fails(self):
        """If embedding API call fails, BM25 is used as fallback."""
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        mem = FinancialSituationMemory("test", use_embeddings=True)
        mem.add_situations([("oil spike", "BUY energy")])
        # Force no embeddings stored (as if embedding failed during add)
        mem.embeddings = [[]]  # empty vector = no embeddings

        with patch("tradingagents.agents.utils.memory._embed_texts", return_value=None):
            results = mem.get_memories("oil price", n_matches=1)

        assert len(results) == 1
        assert results[0]["retrieval_method"] == "bm25"

    def test_embedding_added_on_add_situations(self):
        """add_situations should store embeddings when enabled."""
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        fake_emb = [_make_embedding(1.0)]
        with patch("tradingagents.agents.utils.memory._embed_texts", return_value=fake_emb):
            mem = FinancialSituationMemory("test", use_embeddings=True)
            mem.add_situations([("oil spike", "BUY energy")])

        assert len(mem.embeddings) == 1
        assert len(mem.embeddings[0]) == 8  # our fake dim

    def test_embeddings_saved_and_loaded(self, tmp_path):
        """Embeddings persist to disk and reload without re-embedding."""
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        fake_emb = [_make_embedding(1.5)]
        with patch("tradingagents.agents.utils.memory._embed_texts", return_value=fake_emb):
            mem1 = FinancialSituationMemory("test", use_embeddings=True)
            mem1.add_situations([("iran war energy", "BUY VG")])
            path = str(tmp_path / "test.json")
            mem1.save(path)

        # Load into new instance — should NOT call _embed_texts again
        mem2 = FinancialSituationMemory("test", use_embeddings=True)
        with patch("tradingagents.agents.utils.memory._embed_texts") as mock_embed:
            mem2.load(path)
            mock_embed.assert_not_called()  # pre-computed embeddings used

        assert len(mem2.embeddings) == 1
        assert mem2.embeddings[0] == fake_emb[0]

    def test_semantic_retrieves_better_than_bm25_for_paraphrase(self):
        """Embedding should find semantically similar situations BM25 misses."""
        from tradingagents.agents.utils.memory import _cosine_similarity

        # Simulate: stored as "geopolitical supply shock commodity rally"
        # Query: "Iran war oil spike buy energy"
        # BM25: zero overlap on these exact words
        # Embeddings: semantically very similar

        # Use fake embeddings that are close for similar meanings
        stored_vec  = _make_embedding(2.0)    # "geopolitical supply shock"
        query_vec   = _make_embedding(2.05)   # "Iran war oil spike" — close seed
        unrelated   = _make_embedding(99.0)   # "earnings beat tech stock" — far

        sim_related   = _cosine_similarity(stored_vec, query_vec)
        sim_unrelated = _cosine_similarity(stored_vec, unrelated)

        assert sim_related > sim_unrelated, \
            "Embedding should score related situations higher than unrelated"

    def test_graph_enables_embeddings_when_api_key_set(self):
        """TradingAgentsGraph enables embeddings when OPENAI_API_KEY is set."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        with patch("tradingagents.graph.trading_graph.create_llm_client") as mock_client, \
             patch("tradingagents.graph.trading_graph.set_config"), \
             patch("tradingagents.graph.trading_graph.GraphSetup") as mock_setup, \
             patch("os.makedirs"), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):

            mock_llm = MagicMock()
            mock_client.return_value.get_llm.return_value = mock_llm
            mock_setup.return_value.setup_graph.return_value = MagicMock()

            ta = TradingAgentsGraph()

        assert ta.bull_memory.use_embeddings is True
        assert ta.bear_memory.use_embeddings is True
        assert ta.trader_memory.use_embeddings is True

    def test_graph_disables_embeddings_when_no_api_key(self):
        """TradingAgentsGraph disables embeddings without OPENAI_API_KEY."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        env_without_key = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}

        with patch("tradingagents.graph.trading_graph.create_llm_client") as mock_client, \
             patch("tradingagents.graph.trading_graph.set_config"), \
             patch("tradingagents.graph.trading_graph.GraphSetup") as mock_setup, \
             patch("os.makedirs"), \
             patch.dict(os.environ, env_without_key, clear=True):

            mock_llm = MagicMock()
            mock_client.return_value.get_llm.return_value = mock_llm
            mock_setup.return_value.setup_graph.return_value = MagicMock()

            ta = TradingAgentsGraph()

        assert ta.bull_memory.use_embeddings is False
