"""HALO Agent 05 (Wellness) - Search wrapper.

Thin wrapper calling the generalised search agent with the wellness policy index
and a check-in-specific query builder.
"""
import logging
from pathlib import Path

from app.search_agent import run_search as _run_search

logger = logging.getLogger("halo.agent05.search")

INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wellness_policy_index.json"


def _checkin_to_query(checkin):
    """Build a retrieval query from the structured CHECKIN object."""
    severity = checkin.get("severity", "unknown")
    crisis = checkin.get("crisis_indicators") or []
    themes = checkin.get("themes_mentioned") or []
    requests = checkin.get("request_signals") or []
    sensitive = checkin.get("sensitive_topics_detected") or []

    has_crisis = len(crisis) > 0

    parts = [
        "Severity: " + severity,
        "Crisis indicators present: " + ("yes" if has_crisis else "no"),
        "Themes count: " + str(len(themes)),
        "Person requested support: " + ("yes" if requests else "no"),
        "Sensitive topics present: " + ("yes" if sensitive else "no"),
        "Needs resource pointers: yes",
        "Needs care-appropriate tone: yes",
    ]
    return " | ".join(parts)


def run_search(checkin, top_k=3):
    """Run the Search agent against the wellness policy index."""
    return _run_search(
        brief=checkin,
        top_k=top_k,
        index_path=INDEX_PATH,
        query_builder=_checkin_to_query,
    )
