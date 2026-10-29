"""Optional OpenAI text embeddings, deliberately opt-in to avoid surprise API costs.

Search still works through Thai lexical matching when embedding is disabled or fails.
"""
import math

from openai import OpenAI

from config import EMBEDDING_MODEL, EMBEDDINGS_ENABLED, LLM_API_KEY

EMBEDDING_DIMENSIONS = 768


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts or not EMBEDDINGS_ENABLED or not LLM_API_KEY:
        return []
    with OpenAI(api_key=LLM_API_KEY, timeout=15.0, max_retries=0) as client:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )
    output = []
    items = sorted(response.data, key=lambda item: item.index)
    if [item.index for item in items] != list(range(len(texts))):
        raise ValueError("EMBEDDING_COUNT_MISMATCH")
    for item in items:
        values = item.embedding
        if len(values) != EMBEDDING_DIMENSIONS:
            raise ValueError("EMBEDDING_DIMENSION_MISMATCH")
        # Unit normalization makes the 768-dimensional representation comparable.
        norm = math.sqrt(sum(float(x) * float(x) for x in values))
        if not math.isfinite(norm) or norm <= 0:
            raise ValueError("INVALID_EMBEDDING")
        output.append([float(x) / norm for x in values])
    if len(output) != len(texts):
        raise ValueError("EMBEDDING_COUNT_MISMATCH")
    return output


def embed_query(query: str) -> list[float] | None:
    vectors = embed_texts([query[:4000]])
    return vectors[0] if vectors else None


def embed_document_batch(texts: list[str]) -> list[list[float]]:
    return embed_texts(texts)
