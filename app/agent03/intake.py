"""
HALO Agent 03 (Task & KPI) — Status Intake

Role: Parse a raw status update, weekly report, or stand-up dictation into a
structured STATUS object that downstream agents (Search, Brush, Validator)
can reason over.

Pattern: Same agentic spine as Agent 01/02 — structured-extraction from
messy human text, low temperature for consistency, JSON response format.

Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent03.intake")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

INTAKE_SYSTEM_PROMPT = """You are the Status Intake agent for HALO, an internal employee platform.

You receive a raw status update, weekly report, project digest, or stand-up
dictation. Your job is to extract a STRUCTURED STATUS OBJECT — never to
summarise, polish, or invent. Preserve what was said as faithfully as possible.
Downstream agents (Search, Brush, Validator) will do the structuring and
scoring — but only if you give them clean structured data.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "project_or_team": "name of the project, team, or scope being reported on, or null",
  "reporter": "the named reporter if identifiable, else null",
  "period": "the reporting period as stated (e.g. 'last week', 'May 19-25', 'sprint 14'), or null",
  "raw_tasks": [
    {
      "description": "the task as stated, faithful to source",
      "owner_mentioned": "who was named as owner, or null",
      "deadline_mentioned": "any deadline phrasing as it was said, or null",
      "status_mentioned": "blocked / at-risk / on-track / done / unclear",
      "progress_mentioned": "any percent / fraction / qualitative phrasing as said, or null",
      "blocked_by_mentioned": "any dependency or blocker named, or null"
    }
  ],
  "raw_kpis": [
    {
      "name": "the KPI name as said (e.g. 'NPS', 'velocity', 'revenue')",
      "direction_mentioned": "up / down / flat / unclear",
      "magnitude_mentioned": "any number/percent/qualifier as said (e.g. '12%', 'a few points', 'unspecified')",
      "timeframe_mentioned": "any comparison window as said (e.g. 'vs last week', 'YTD', null)"
    }
  ],
  "raw_risks": [
    {
      "risk_as_stated": "the risk as worded in the source",
      "impact_mentioned": "any business impact named, or null",
      "trigger_mentioned": "any root cause or trigger named, or null"
    }
  ],
  "performance_signals_flagged": false,
  "performance_reason": "if flagged, why (individual missed deadlines, team conflict, capability gap), else null",
  "open_questions": [
    "anything Intake is unsure about - e.g., 'progress claim unverified', 'no owner named for X', 'KPI magnitude vague'"
  ]
}

Rules of engagement:
- DO NOT invent owners, deadlines, progress percentages, or KPI numbers. If unclear, use null and surface in open_questions.
- DO NOT classify a task as on-track if the source is ambiguous. When in doubt use 'unclear'.
- DO preserve vague language exactly as said — 'about 60% done', 'a few points', 'soon' stay as-is. Validator will flag against the rules.
- DO flag performance_signals_flagged=true if the update implies individual performance concerns (chronic missed deadlines by named individuals, team conflicts, capability gaps).
- DO surface KPIs even if they are vague. 'NPS up a few points' becomes a raw_kpi with magnitude_mentioned='a few points' and timeframe_mentioned=null.
- Output ONLY the JSON. No prose before or after."""


def run_intake(status_text: str) -> dict:
    """
    Parse a raw status update into a structured STATUS object.

    Args:
        status_text: Raw text of the status update (report, dictation, email).

    Returns:
        Structured STATUS dict matching the schema above.
        On parse failure, returns {"error": ..., "raw": ...}.
    """
    preview = status_text[:120].replace("\n", " ")
    logger.info(f"INTAKE_START | preview={preview!r}")

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Status update:\n\n{status_text}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        status = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None

        project = status.get("project_or_team") or "<no project>"
        tasks_count = len(status.get("raw_tasks") or [])
        kpis_count = len(status.get("raw_kpis") or [])
        risks_count = len(status.get("raw_risks") or [])
        open_qs_count = len(status.get("open_questions") or [])
        perf_flagged = status.get("performance_signals_flagged", False)

        logger.info(
            f"INTAKE_DONE | tokens={tokens_used} | "
            f"project={project!r} | tasks={tasks_count} | kpis={kpis_count} | "
            f"risks={risks_count} | open_qs={open_qs_count} | perf_flagged={perf_flagged}"
        )
        return status

    except json.JSONDecodeError as exc:
        logger.error(f"INTAKE_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "intake_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"INTAKE_API_FAIL | error={exc!s}")
        return {"error": "intake_api_failure", "detail": str(exc)}
