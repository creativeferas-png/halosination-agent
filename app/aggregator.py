"""HALO Aggregator - the 6th capability.

Reads saved agent outputs (output_examples/agent02..05) and extracts ONLY signals
- counts and flags, never names, never content, never who said what. This is the
substrate for the aggregate wellbeing dashboard.

DESIGN COMMITMENT: this module is incapable of producing individual identification.
It does not store names, full text, or any field that could be traced back to a
single person. The threshold-gating happens downstream in the dashboard endpoint.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("halo.aggregator")

OUTPUTS_BASE = Path(__file__).resolve().parent.parent / "output_examples"


def _safe_load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("AGG_LOAD_FAIL | path={} | error={}".format(path.name, exc))
        return None


def extract_signals_agent02(record):
    """Agent 02 (Productivity) - meeting-load + stress + restricted-distribution signals."""
    output = record.get("output") or {}
    final = output.get("final_notes") or {}
    actions = final.get("action_items") or []
    risks = final.get("risks_or_blockers") or []
    distribution = (final.get("distribution") or "wide").lower()
    return {
        "action_items_count": len(actions),
        "risks_or_blockers_count": len(risks),
        "restricted_distribution": distribution == "restricted",
    }


def extract_signals_agent03(record):
    """Agent 03 (Task) - active-task load + risks + restricted-distribution signals."""
    output = record.get("output") or {}
    final = output.get("final_notes") or {}
    tasks = final.get("tasks") or []
    active_tasks = [t for t in tasks if (t.get("status") or "").lower() != "done"]
    risks = final.get("risks") or []
    distribution = (final.get("distribution") or "wide").lower()
    return {
        "active_tasks_count": len(active_tasks),
        "risks_count": len(risks),
        "restricted_distribution": distribution == "restricted",
    }


def extract_signals_agent04(record):
    """Agent 04 (Social) - connection-health proxy (isolation signal only)."""
    output = record.get("output") or {}
    profile = output.get("profile") or {}
    social_signals = profile.get("social_context_signals") or {}
    isolation = bool(social_signals.get("isolation_or_loneliness_signal"))
    return {"isolation_signal": isolation}


def extract_signals_agent05(record):
    """Agent 05 (Wellness) - severity classification only."""
    output = record.get("output") or {}
    checkin = output.get("checkin") or {}
    severity = checkin.get("severity") or "unknown"
    return {"severity": severity}


EXTRACTORS = {
    "agent02": extract_signals_agent02,
    "agent03": extract_signals_agent03,
    "agent04": extract_signals_agent04,
    "agent05": extract_signals_agent05,
}


def collect_signals():
    """Walk the saved outputs and return a flat list of signal dicts.

    Each signal dict has only:
      - agent: which agent produced it
      - source_filename: for diagnostics ONLY (a sample id, not an individual)
      - signal fields per the extractors above

    Names, full content, and identifying fields are not included.
    """
    signals = []
    for agent_key, extractor in EXTRACTORS.items():
        agent_dir = OUTPUTS_BASE / agent_key
        if not agent_dir.exists():
            logger.info("AGG_SKIP | no dir for {}".format(agent_key))
            continue
        files = sorted(agent_dir.glob("*.json"))
        for f in files:
            record = _safe_load(f)
            if record is None:
                continue
            sig = {"agent": agent_key, "source_filename": f.name}
            sig.update(extractor(record))
            signals.append(sig)
    logger.info("AGG_COLLECTED | total_signals={}".format(len(signals)))
    return signals


def summarise_real_signals():
    """Aggregate the collected signals into headline counts (no thresholding yet).

    Returns a dict with per-agent and overall aggregate counts. The threshold
    gate is applied in the dashboard endpoint, not here.
    """
    sigs = collect_signals()
    summary = {
        "total_records": len(sigs),
        "by_agent": {},
        "wellness_severity_distribution": {"general_wellbeing": 0, "elevated_concern": 0, "crisis_signal": 0, "unknown": 0},
        "isolation_signals": 0,
        "active_tasks_total": 0,
        "risks_total": 0,
        "restricted_distribution_count": 0,
        "action_items_total": 0,
        "risks_or_blockers_total": 0,
    }
    for s in sigs:
        a = s["agent"]
        summary["by_agent"][a] = summary["by_agent"].get(a, 0) + 1
        if a == "agent02":
            summary["action_items_total"] += s.get("action_items_count", 0)
            summary["risks_or_blockers_total"] += s.get("risks_or_blockers_count", 0)
            if s.get("restricted_distribution"):
                summary["restricted_distribution_count"] += 1
        elif a == "agent03":
            summary["active_tasks_total"] += s.get("active_tasks_count", 0)
            summary["risks_total"] += s.get("risks_count", 0)
            if s.get("restricted_distribution"):
                summary["restricted_distribution_count"] += 1
        elif a == "agent04":
            if s.get("isolation_signal"):
                summary["isolation_signals"] += 1
        elif a == "agent05":
            sev = s.get("severity", "unknown")
            if sev in summary["wellness_severity_distribution"]:
                summary["wellness_severity_distribution"][sev] += 1
            else:
                summary["wellness_severity_distribution"]["unknown"] += 1
    logger.info("AGG_SUMMARY | records={} | wellness_sev={} | isolation={}".format(
        summary["total_records"], summary["wellness_severity_distribution"], summary["isolation_signals"]))
    return summary
