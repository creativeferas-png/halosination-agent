"""
HALO — Search Agent (generalized)

Role: Retrieves the top-K most relevant policy rules for a given structured
brief, against a per-agent policy index.

Pattern: Retrieval-augmented generation. OpenAI-protocol via Compass.
The index is pre-built (scripts/build_policy_index.py); at runtime this agent
makes ONE embedding call per brief and does in-memory cosine similarity
against the pre-indexed rules.

Used by:
  - Agent 01 (Brand & Brief)   -> default index: data/brand_index.json
  - Agent 02 (Productivity)    -> index: data/meeting_policy_index.json
  - Agents 03-05               -> their own policy indexes

Model: text-embedding-3-large via Compass.
"""
import json
import logging
import math
import os
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger("halo.search")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

EMBED_MODEL = "text-embedding-3-large"
TOP_K = 3

# Default index for Agent 01 (backwards compatibility)
DEFAULT_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "brand_index.json"

# Lazy-loaded index cache, keyed by path so each agent's index is loaded once
_index_cache: dict = {}


def _load_index(index_path: Path) -> list:
    """Load a policy index from disk on first use, cache by path."""
    path_str = str(index_path)
    if path_str not in _index_cache:
        if not index_path.exists():
            raise FileNotFoundError(
                f"Policy index not found at {index_path}. "
                "Run `python scripts/build_policy_index.py <md_file> <json_path>` first."
            )
        _index_cache[path_str] = json.loads(index_path.read_text(encoding="utf-8"))
        logger.info(
            f"SEARCH_INDEX_LOADED | rules={len(_index_cache[path_str])} | "
            f"path={index_path.name}"
        )
    return _index_cache[path_str]


def _cosine_similarity(a: list, b: list) -> float:
    """Cosine similarity between two vectors. Returns a value in [-1, 1]."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed(text: str) -> list:
    """Single embedding call via Compass."""
    response = _client.embeddings.create(model=EMBED_MODEL, input=text)
    return response.data[0].embedding


def _default_brief_to_query(brief: dict) -> str:
    """
    Default query-builder for Agent 01 (Brand & Brief).

    Concatenates the high-signal BRIEF fields so the embedding captures
    asset type, audience, OpCo context, tone, and the key message.
    """
    parts = [
        f"Asset type: {brief.get('asset_type', 'unknown')}",
        f"Audience: {brief.get('audience', 'unknown')}",
        f"OpCo: {brief.get('opco_context', 'unknown')}",
        f"Tone hints: {', '.join(brief.get('tone_hints') or []) or 'none'}",
        f"Key message: {brief.get('key_message', '')}",
    ]
    return " | ".join(parts)


def run_search(
    brief: dict,
    top_k: int = TOP_K,
    index_path: Path = None,
    query_builder = None,
) -> dict:
    """
    Retrieve the top-K most relevant policy rules for the given structured brief.

    Args:
        brief: The structured brief from an Intake agent (Agent 01 BRIEF,
               Agent 02 MEETING, etc.)
        top_k: How many rules to return (default 3).
        index_path: Path to the policy index JSON. Defaults to brand_index.json
                    (Agent 01). Pass a different path for other agents.
        query_builder: Optional callable taking a brief dict and returning a
                       query string. Defaults to the Agent 01 brand query.

    Returns:
        {
          "retrieved_rules": [{"rule_id", "title", "text", "similarity"}, ...],
          "query_text": str,
        }
        On failure, returns a dict with "error" populated.
    """
    if index_path is None:
        index_path = DEFAULT_INDEX_PATH
    if query_builder is None:
        query_builder = _default_brief_to_query

    query_text = query_builder(brief)
    logger.info(
        f"SEARCH_START | query_preview={query_text[:100]!r} | "
        f"top_k={top_k} | index={Path(index_path).name}"
    )

    try:
        index = _load_index(Path(index_path))
        query_embedding = _embed(query_text)

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

        top_summary = ", ".join(f"#{r['rule_id']}({r['similarity']:.3f})" for r in top)
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
