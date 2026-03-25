# TICKET-026 — Embedding-Based Memory Retrieval

**Priority:** MEDIUM
**Effort:** 2h
**Status:** DONE

## Problem

`FinancialSituationMemory` uses BM25 (keyword overlap) to retrieve relevant past
lessons. BM25 matches on word co-occurrence, which is weak for financial situations:

- "Iran war oil spike buy energy" matches "Iran oil price" correctly
- BUT misses "geopolitical supply shock commodity rally" — same situation, different words
- "RSI oversold MACD divergence" misses "momentum reversal technical setup"

Real trading situations are semantically similar but lexically different. BM25 gives
poor retrieval quality, meaning agents don't benefit much from accumulated lessons.

## Solution

Replace BM25 with OpenAI's `text-embedding-3-small` model (cheapest, excellent quality):
- Embed situations at storage time
- Embed query at retrieval time
- Use cosine similarity instead of BM25 scores

### Cost
`text-embedding-3-small`: $0.02 per 1M tokens
- Average situation: ~500 tokens → $0.00001 per situation stored
- 5 agents × 34 tickers × 500 tokens = ~85k tokens/cycle = **$0.0017/cycle**
- 500-entry cap per agent = max 2500 embeddings stored = **$0.05 one-time**

Effectively free.

## Acceptance Criteria

- [ ] `FinancialSituationMemory` gains optional `use_embeddings: bool = False` flag
- [ ] When `use_embeddings=True`: embed situations using `text-embedding-3-small`
  on `add_situations()`, embed query on `get_memories()`, rank by cosine similarity
- [ ] When `use_embeddings=False`: fall back to BM25 (default, no breaking change)
- [ ] Embeddings persisted to disk alongside JSON: `{agent}.embeddings.npy`
- [ ] `trading_loop.py` enables embeddings when `OPENAI_API_KEY` is set
- [ ] Embedding failures fall back to BM25 silently (API could be unavailable)
- [ ] Unit tests: embedding retrieval returns semantically relevant result
  that BM25 would miss (different words, same meaning)
- [ ] All 115 tests still pass (BM25 path unchanged)

## Implementation

```python
# memory.py
import numpy as np
from openai import OpenAI

def _embed(texts: list[str]) -> np.ndarray:
    client = OpenAI()
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return np.array([d.embedding for d in resp.data])

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a @ b.T) / (np.linalg.norm(a) * np.linalg.norm(b, axis=1))
```
