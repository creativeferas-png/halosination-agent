"""HALO structured agent trace logger.

Writes one JSON line per agent step to logs/agent_trace.jsonl in the format the
G42 Agentathon rubric expects. Runs ALONGSIDE the existing Python logger - both
fire on every event, neither replaces the other.

Fields per line (matching the rubric's "Strong Trace Example"):
  timestamp:        ISO-8601 with Z (UTC)
  agent_name:       which agent emitted the event
  action:           what it did (parse_request, retrieve_rules, draft, validate, revise, route_decision, etc.)
  input_summary:    short description of what the agent received (NOT raw content, NOT PII)
  output_summary:   short description of what it produced
  target_agent:     which agent the work moves to next (None if final step)
  confidence:       agent-self-reported, 0.0-1.0 (None if not applicable)
  retry_count:      0 for first pass, 1 on revision, etc.
  status:           "success" | "needs_revision" | "escalated" | "failed"

Privacy/security:
  Summaries are deliberately SHORT (under ~120 chars). Full content is never
  written here. No keys, no transcripts, no individual names from check-ins.
  Safe to commit a reference trace to the repo.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("halo.trace")

# logs/agent_trace.jsonl, created if missing
_TRACE_PATH = Path(__file__).resolve().parent.parent / "logs" / "agent_trace.jsonl"
_TRACE_PATH.parent.mkdir(exist_ok=True)

_lock = threading.Lock()


def _truncate(s, limit=120):
    if s is None:
        return None
    s = str(s).replace("\n", " ").strip()
    if len(s) <= limit:
        return s
    return s[:limit - 1] + "\u2026"


def trace_event(agent_name, action, input_summary, output_summary,
                target_agent=None, status="success", confidence=None,
                retry_count=0, run_id=None):
    """Append one structured event to logs/agent_trace.jsonl.

    Truncates summaries to ~120 chars. Thread-safe via a module-level lock.
    Failures here NEVER raise - tracing must not break the pipeline.
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "agent_name": agent_name,
        "action": action,
        "input_summary": _truncate(input_summary),
        "output_summary": _truncate(output_summary),
        "target_agent": target_agent,
        "confidence": confidence,
        "retry_count": retry_count,
        "status": status,
    }
    if run_id:
        event["run_id"] = run_id

    line = json.dumps(event, ensure_ascii=False)
    try:
        with _lock:
            with open(_TRACE_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        logger.info("TRACE | %s | %s -> %s | status=%s", agent_name, action, target_agent or "-", status)
    except Exception as exc:
        # NEVER raise from a tracer - log and swallow
        logger.warning("TRACE_WRITE_FAIL | error=%s", str(exc)[:120])
