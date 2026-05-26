"""
HALO Agent 04 (Social) — Search wrapper.

Thin wrapper that calls the generalised search agent with:
  - the social policy index
  - a profile-specific query builder
"""
import logging
from pathlib import Path

from app.search_agent import run_search as _run_search

logger = logging.getLogger("halo.agent04.search")

INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "social_policy_index.json"


def _profile_to_query(profile: dict) -> str:
    """Build a retrieval query from the structured PROFILE object."""
    expertise = profile.get("expertise_areas") or []
    interests_prof = profile.get("interests_professional") or []
    goals = profile.get("goals_stated") or []
    social = profile.get("social_context_signals") or {}
    sensitive = profile.get("sensitive_attributes_detected") or []
    conflicts = profile.get("conflict_signals") or []

    any_social_signal = any(social.values()) if social else False
    has_isolation = social.get("isolation_or_loneliness_signal", False)
    is_new = social.get("new_to_company", False) or social.get("recently_relocated", False)

    parts = [
        f"Role: {profile.get('role', 'unknown')}",
        f"Career stage: {profile.get('career_stage', 'unknown')}",
        f"Expertise areas: {len(expertise)}",
        f"Professional interests: {len(interests_prof)}",
        f"Stated goals: {len(goals)}",
        f"Sensitive attributes detected: {'yes' if sensitive else 'no'}",
        f"Conflict signals: {'yes' if conflicts else 'no'}",
        f"Social signals present: {'yes' if any_social_signal else 'no'}",
        f"Isolation/loneliness signal: {'yes' if has_isolation else 'no'}",
        f"New / relocated: {'yes' if is_new else 'no'}",
    ]
    return " | ".join(parts)


def run_search(profile: dict, top_k: int = 3) -> dict:
    """Run the Search agent against the social policy index."""
    return _run_search(
        brief=profile,
        top_k=top_k,
        index_path=INDEX_PATH,
        query_builder=_profile_to_query,
    )
