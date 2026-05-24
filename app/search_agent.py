"""
HALOsination — Search Agent

Role: Retrieves the top-K most relevant brand rules for a given BRIEF.
The retrieved rules ground Brush's drafting and give Validator concrete
evidence to score against (rather than relying on GPT's priors alone).

Pattern: Retrieval-augmented generation, OpenAI-protocol via Compass.
The brand index is pre-built (scripts/build_brand_index.py); at runtime
this agent makes ONE embedding call per BRIEF and does in-memory cosine
similarity against the indexed rules.

Model: text-embedding-3-large via Compass.
"""
import json
import logging
import math
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

logger = logging.getLogger("halo.search")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

EMBED_MODEL = "text-embedding-3-large"
TOP_K = 3
DEFAULT_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "brand_index.json"

# Lazy-loaded index (loaded once per process, cached in memory)
_brand_index: list[dict] | None = None


def _load_index() -> list[dict]:
    """Load the brand index from disk on first use, cache for subsequent calls."""
    global _brand_index
    if _brand_index is None:
        if not DEFAULT_INDEX_PATH.exists():
            raise FileNotFoundError(
                f"Brand index not found at {DEFAULT_INDEX_PATH}. "
                "Run `python scripts/build_brand_index.py` first."
            )
        _brand_index = json.loads(DEFAULT_INDEX_PATH.read_text(encoding="utf-8"))
        logger.info(f"SEARCH_INDEX_LOADED | rules={len(_brand_index)} | path={DEFAULT_INDEX_PATH.name}")
    return _brand_index


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns a value in [-1, 1]."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed(text: str) -> list[float]:
    """Single embedding call to Compass."""
    response = _client.embeddings.create(
        model=EMBED_MODEL,
        input=text,
    )
    return response.data[0].embedding


def _brief_to_query_text(brief: dict) -> str:
    """
    Construct the query string from the most retrieval-relevant BRIEF fields.
    We deliberately concatenate the high-signal fields so the embedding
    captures asset type, audience, OpCo context, tone, and the key message.
    """
    parts = [
        f"Asset type: {brief.get('asset_type', 'unknown')}",
        f"Audience: {brief.get('audience', 'unknown')}",
        f"OpCo: {brief.get('opco_context', 'unknown')}",
        f"Tone hints: {', '.join(brief.get('tone_hints') or []) or 'none'}",
        f"Key message: {brief.get('key_message', '')}",
    ]
    return " | ".join(parts)


def run_search(brief: dict, top_k: int = TOP_K) -> dict:
    """
    Retrieve the top-K most relevant brand rules for the given BRIEF.

    Args:
        brief: The structured BRIEF from the Intake agent.
        top_k: How many rules to return (default 3).

    Returns:
        {
          "retrieved_rules": [
            {"rule_id": int, "title": str, "text": str, "similarity": float},
            ...
          ],
          "query_text": str,            # what was actually embedded
          "tokens_used": int | None,    # embedding tokens
        }
        On failure, returns a dict with "error" populated.
    """
    query_text = _brief_to_query_text(brief)
    logger.info(f"SEARCH_START | query_preview={query_text[:100]!r} | top_k={top_k}")

    try:
        index = _load_index()
        # ONE embedding call for the BRIEF
        query_embedding = _embed(query_text)

        # Score every rule by cosine similarity
        scored = []
        for rule in index:
            sim = _cosine_similarity(query_embedding, rule["embedding"])
            scored.append({
                "rule_id": rule["rule_id"],
                "title": rule["title"],
                "text": rule["text"],
                "similarity": round(sim, 4),
            })

        scored.sort(key=lambda r: r["similarity"], reverse=True)
        top = scored[:top_k]

        top_summary = ", ".join(
            f"#{r['rule_id']}({r['similarity']:.3f})" for r in top
        )
        logger.info(f"SEARCH_DONE | top_k_rules=[{top_summary}]")

        return {
            "retrieved_rules": top,
            "query_text": query_text,
        }

    except FileNotFoundError as exc:
        logger.error(f"SEARCH_INDEX_MISSING | {exc}")
        return {"error": "search_index_missing", "detail": str(exc)}
    except Exception as exc:
        logger.error(f"SEARCH_API_FAIL | error={exc!s}")
        return {"error": "search_api_failure", "detail": str(exc)}
