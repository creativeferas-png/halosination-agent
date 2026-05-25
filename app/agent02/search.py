"""
HALO Agent 02 (Productivity) — Search wrapper.

Thin wrapper that calls the generalized search agent with:
  - the meeting policy index
  - a meeting-specific query builder
"""
import logging
from pathlib import Path

from app.search_agent import run_search as _run_search

logger = logging.getLogger("halo.agent02.search")

INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "meeting_policy_index.json"


def _meeting_to_query(meeting: dict) -> str:
    """
    Build a retrieval query from the structured MEETING object produced by
    Agent 02 Intake. We emphasize the fields most relevant to meeting-policy
    rules (decisions/actions/sensitivity/follow-ups).
    """
    decisions = meeting.get("raw_decisions") or []
    actions = meeting.get("raw_action_items") or []
    has_owner_gaps = any(a.get("owner_mentioned") is None for a in actions)
    has_deadline_gaps = any(a.get("deadline_mentioned") is None for a in actions)
    open_q = meeting.get("open_questions") or []
    sensitive = meeting.get("sensitive_topics_flagged", False)

    parts = [
        f"Meeting purpose: {meeting.get('purpose', 'unknown')}",
        f"Attendees: {len(meeting.get('attendees') or [])} named",
        f"Decisions: {len(decisions)} captured",
        f"Action items: {len(actions)} captured",
        f"Owner gaps: {'yes' if has_owner_gaps else 'no'}",
        f"Deadline gaps: {'yes' if has_deadline_gaps else 'no'}",
        f"Open questions: {len(open_q)}",
        f"Sensitive topics: {'yes' if sensitive else 'no'}",
    ]
    return " | ".join(parts)


def run_search(meeting: dict, top_k: int = 3) -> dict:
    """
    Run the Search agent against the meeting policy index.

    Args:
        meeting: structured MEETING object from Agent 02 Intake
        top_k: number of rules to return (default 3)

    Returns:
        {"retrieved_rules": [...], "query_text": str}
        or {"error": ..., "detail": ...} on failure.
    """
    return _run_search(
        brief=meeting,
        top_k=top_k,
        index_path=INDEX_PATH,
        query_builder=_meeting_to_query,
    )
