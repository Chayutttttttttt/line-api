"""Optional Gemini text embeddings, deliberately opt-in to avoid surprise API costs.

Search still works through Thai lexical matching when embedding is disabled or fails.
"""
import logging
import math

from google import genai
from google.genai import types

from config import EMBEDDING_MODEL, EMBEDDINGS_ENABLED, LLM_API_KEY

log = logging.getLogger(__name__)
EMBEDDING_DIMENSIONS = 768


def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts or not EMBEDDINGS_ENABLED or not LLM_API_KEY:
        return []
    with genai.Client(api_key=LLM_API_KEY,
        http_options=types.HttpOptions(timeout=15000)) as client:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )
    output = []
    for item in response.embeddings or []:
        values = list(item.values or [])
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
    vectors = embed_texts([query[:4000]], "RETRIEVAL_QUERY")
    return vectors[0] if vectors else None


def embed_document_batch(texts: list[str]) -> list[list[float]]:
    return embed_texts(texts, "RETRIEVAL_DOCUMENT")
