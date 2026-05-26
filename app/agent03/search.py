"""
HALO Agent 03 (Task & KPI) — Search wrapper.

Thin wrapper that calls the generalised search agent with:
  - the task policy index
  - a status-specific query builder
"""
import logging
from pathlib import Path

from app.search_agent import run_search as _run_search

logger = logging.getLogger("halo.agent03.search")

INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "task_policy_index.json"


def _status_to_query(status: dict) -> str:
    """
    Build a retrieval query from the structured STATUS object produced by
    Agent 03 Intake. We emphasise the fields most relevant to task/KPI policy
    rules (task gaps, KPI completeness, risks, performance signals).
    """
    tasks = status.get("raw_tasks") or []
    kpis = status.get("raw_kpis") or []
    risks = status.get("raw_risks") or []

    has_owner_gaps = any(t.get("owner_mentioned") is None for t in tasks)
    has_deadline_gaps = any(t.get("deadline_mentioned") is None for t in tasks)
    has_blocked = any(t.get("status_mentioned") == "blocked" for t in tasks)
    has_dependencies = any(t.get("blocked_by_mentioned") for t in tasks)

    has_kpi_gaps = any(
        (k.get("magnitude_mentioned") in (None, "unspecified", "a few points")) or
        (k.get("timeframe_mentioned") is None)
        for k in kpis
    )
    has_risk_without_impact = any(r.get("impact_mentioned") is None for r in risks)
    perf_flagged = status.get("performance_signals_flagged", False)

    parts = [
        f"Project: {status.get('project_or_team', 'unknown')}",
        f"Tasks: {len(tasks)} captured",
        f"KPIs: {len(kpis)} captured",
        f"Risks: {len(risks)} captured",
        f"Owner gaps: {'yes' if has_owner_gaps else 'no'}",
        f"Deadline gaps: {'yes' if has_deadline_gaps else 'no'}",
        f"Blocked tasks: {'yes' if has_blocked else 'no'}",
        f"Dependencies: {'yes' if has_dependencies else 'no'}",
        f"KPI gaps: {'yes' if has_kpi_gaps else 'no'}",
        f"Risk without impact: {'yes' if has_risk_without_impact else 'no'}",
        f"Performance signals: {'yes' if perf_flagged else 'no'}",
    ]
    return " | ".join(parts)


def run_search(status: dict, top_k: int = 3) -> dict:
    """
    Run the Search agent against the task policy index.

    Args:
        status: structured STATUS object from Agent 03 Intake
        top_k: number of rules to return (default 3)

    Returns:
        {"retrieved_rules": [...], "query_text": str}
        or {"error": ..., "detail": ...} on failure.
    """
    return _run_search(
        brief=status,
        top_k=top_k,
        index_path=INDEX_PATH,
        query_builder=_status_to_query,
    )
