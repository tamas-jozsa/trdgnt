"""Financial situation memory with BM25 and optional embedding-based retrieval.

Default: BM25 (keyword overlap) — no API calls, works offline.
Optional: OpenAI text-embedding-3-small — semantic similarity, much better
          at matching situations with different words but same meaning.

Enable embeddings by setting use_embeddings=True when constructing.
Requires OPENAI_API_KEY in environment. Falls back to BM25 on any error.

Memory is persisted to disk between runs so agents accumulate lessons
across trading sessions.
"""

import json
import logging
import os
from pathlib import Path
from rank_bm25 import BM25Okapi
from typing import List, Optional, Tuple
import re

logger = logging.getLogger(__name__)

# Maximum stored entries per memory instance to prevent unbounded growth
MAX_MEMORY_ENTRIES = 500


def _embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """
    Embed a list of texts using OpenAI text-embedding-3-small.

    Returns list of embedding vectors, or None if embedding fails.
    Cost: ~$0.02 / 1M tokens = effectively free for our usage.
    """
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [d.embedding for d in response.data]
    except Exception as e:
        logger.debug("Embedding failed, falling back to BM25: %s", e)
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    import math
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class FinancialSituationMemory:
    """Memory system for storing and retrieving financial situations.

    Supports two retrieval modes:
    - BM25 (default): keyword-based, no API calls, works offline
    - Embeddings (opt-in): semantic similarity via OpenAI text-embedding-3-small
    """

    def __init__(self, name: str, config: dict = None, use_embeddings: bool = False):
        """Initialize the memory system.

        Args:
            name:           Name identifier for this memory instance
            config:         Configuration dict (kept for API compatibility)
            use_embeddings: If True, use OpenAI embeddings for retrieval when
                            OPENAI_API_KEY is available. Falls back to BM25.
        """
        self.name = name
        self.use_embeddings = use_embeddings
        self.documents: List[str] = []
        self.recommendations: List[str] = []
        self.embeddings: List[List[float]] = []   # parallel to documents
        self.bm25 = None

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing.

        Simple whitespace + punctuation tokenization with lowercasing.
        """
        # Lowercase and split on non-alphanumeric characters
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _rebuild_index(self):
        """Rebuild the BM25 index after adding documents."""
        if self.documents:
            tokenized_docs = [self._tokenize(doc) for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_docs)
        else:
            self.bm25 = None

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]):
        """Add financial situations and their corresponding advice.

        Args:
            situations_and_advice: List of tuples (situation, recommendation)
        """
        new_situations = [s for s, _ in situations_and_advice]

        # Embed new situations if embeddings are enabled
        if self.use_embeddings and new_situations:
            new_embeddings = _embed_texts(new_situations)
            if new_embeddings:
                self.embeddings.extend(new_embeddings)
            else:
                # Embed failed — pad with empty lists so index stays aligned
                self.embeddings.extend([[] for _ in new_situations])
        elif self.use_embeddings:
            self.embeddings.extend([[] for _ in new_situations])

        for situation, recommendation in situations_and_advice:
            self.documents.append(situation)
            self.recommendations.append(recommendation)

        # Evict oldest entries if over the cap
        if len(self.documents) > MAX_MEMORY_ENTRIES:
            excess = len(self.documents) - MAX_MEMORY_ENTRIES
            self.documents       = self.documents[excess:]
            self.recommendations = self.recommendations[excess:]
            if self.embeddings:
                self.embeddings  = self.embeddings[excess:]

        # Rebuild BM25 index (always maintained as fallback)
        self._rebuild_index()

    def get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Find matching recommendations using semantic or BM25 similarity.

        If use_embeddings=True and embeddings are available for stored situations,
        uses cosine similarity on OpenAI text-embedding-3-small vectors.
        Falls back to BM25 if embeddings are unavailable.

        Args:
            current_situation: The current financial situation to match against
            n_matches: Number of top matches to return

        Returns:
            List of dicts with matched_situation, recommendation, and similarity_score
        """
        if not self.documents:
            return []

        # Try embedding-based retrieval first
        if self.use_embeddings and any(e for e in self.embeddings):
            query_embedding = _embed_texts([current_situation])
            if query_embedding:
                q_vec = query_embedding[0]
                scores = []
                for i, doc_vec in enumerate(self.embeddings):
                    if doc_vec:
                        scores.append((i, _cosine_similarity(q_vec, doc_vec)))
                    else:
                        scores.append((i, 0.0))
                scores.sort(key=lambda x: x[1], reverse=True)
                results = []
                for idx, score in scores[:n_matches]:
                    results.append({
                        "matched_situation": self.documents[idx],
                        "recommendation":    self.recommendations[idx],
                        "similarity_score":  score,
                        "retrieval_method":  "embedding",
                    })
                return results

        # BM25 fallback
        if self.bm25 is None:
            return []

        query_tokens = self._tokenize(current_situation)
        scores = self.bm25.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_matches]
        max_score = max(scores) if max(scores) > 0 else 1

        results = []
        for idx in top_indices:
            normalized_score = scores[idx] / max_score if max_score > 0 else 0
            results.append({
                "matched_situation": self.documents[idx],
                "recommendation":    self.recommendations[idx],
                "similarity_score":  normalized_score,
                "retrieval_method":  "bm25",
            })
        return results

    def save(self, path: str) -> None:
        """Persist memory to a JSON file (and embeddings .npy if available).

        Args:
            path: File path to save to (created/overwritten).
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = [
            {"situation": s, "recommendation": r}
            for s, r in zip(self.documents, self.recommendations)
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("Saved %d memory entries to %s", len(data), path)

        # Save embeddings alongside if they exist
        if self.use_embeddings and any(e for e in self.embeddings):
            emb_path = path.replace(".json", ".embeddings.json")
            with open(emb_path, "w") as f:
                json.dump(self.embeddings, f)
            logger.debug("Saved embeddings to %s", emb_path)

    def load(self, path: str) -> None:
        """Load memory from a JSON file (merges into existing memory).

        Also loads pre-computed embeddings from .embeddings.json if present
        (avoids re-embedding on every restart).

        Args:
            path: File path to load from. Silently skips if file does not exist.
        """
        p = Path(path)
        if not p.exists():
            return
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            situations     = [d["situation"]     for d in data]
            recommendations = [d["recommendation"] for d in data]

            # Load pre-computed embeddings if available
            emb_path = path.replace(".json", ".embeddings.json")
            pre_embeddings = None
            if self.use_embeddings and Path(emb_path).exists():
                try:
                    with open(emb_path) as ef:
                        pre_embeddings = json.load(ef)
                    logger.debug("Loaded pre-computed embeddings from %s", emb_path)
                except Exception as ee:
                    logger.debug("Could not load embeddings from %s: %s", emb_path, ee)

            if pre_embeddings and len(pre_embeddings) == len(situations):
                # Bypass re-embedding — use stored vectors directly
                for s, r, e in zip(situations, recommendations, pre_embeddings):
                    self.documents.append(s)
                    self.recommendations.append(r)
                    self.embeddings.append(e)
                if len(self.documents) > MAX_MEMORY_ENTRIES:
                    excess = len(self.documents) - MAX_MEMORY_ENTRIES
                    self.documents       = self.documents[excess:]
                    self.recommendations = self.recommendations[excess:]
                    self.embeddings      = self.embeddings[excess:]
                self._rebuild_index()
            else:
                # No pre-computed embeddings — fall back to add_situations (will embed)
                pairs = list(zip(situations, recommendations))
                self.add_situations(pairs)

            logger.debug("Loaded %d memory entries from %s", len(situations), path)
        except Exception as e:
            logger.warning("Failed to load memory from %s: %s", path, e)

    def clear(self):
        """Clear all stored memories."""
        self.documents = []
        self.recommendations = []
        self.bm25 = None


if __name__ == "__main__":
    # Example usage
    matcher = FinancialSituationMemory("test_memory")

    # Example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
        (
            "Market showing signs of sector rotation with rising yields",
            "Rebalance portfolio to maintain target allocations. Consider increasing exposure to sectors benefiting from higher rates.",
        ),
    ]

    # Add the example situations and recommendations
    matcher.add_situations(example_data)

    # Example query
    current_situation = """
    Market showing increased volatility in tech sector, with institutional investors
    reducing positions and rising interest rates affecting growth stock valuations
    """

    try:
        recommendations = matcher.get_memories(current_situation, n_matches=2)

        for i, rec in enumerate(recommendations, 1):
            print(f"\nMatch {i}:")
            print(f"Similarity Score: {rec['similarity_score']:.2f}")
            print(f"Matched Situation: {rec['matched_situation']}")
            print(f"Recommendation: {rec['recommendation']}")

    except Exception as e:
        print(f"Error during recommendation: {str(e)}")
