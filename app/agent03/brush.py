"""
HALO Agent 03 (Task & KPI) — Brush (Status Drafter)

Role: Takes the structured STATUS object from Intake + retrieved task-policy
rules from Search, and drafts polished, policy-compliant status notes.

Pattern: Proposer half of the Proposer <-> Critic pairing.
Same shape as Agent 01/02 Brush. Different domain.

Model: GPT-5.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent03.brush")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

BRUSH_SYSTEM_PROMPT = """You are the Status Drafter (Brush) agent for HALO Agent 03 (Task & KPI).

You draft polished, policy-compliant status notes from a structured STATUS object.

You receive:
1. A structured STATUS object (JSON) from the Intake agent.
2. RETRIEVED POLICY RULES — the top-K most relevant rules pulled by the Search
   agent from the task-policy guidelines. These are authoritative. Treat them
   as hard constraints, not suggestions.

Your output is a structured STATUS_NOTES (JSON) deliverable for downstream agents.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "digest_90s": "A leadership-ready digest readable in 90 seconds. 3-5 sentences. State what shipped, what slipped, what's at risk, and the single most important next decision.",
  "metadata": {
    "project_or_team": "name",
    "reporter": "named reporter or null",
    "period": "reporting period as stated"
  },
  "tasks": [
    {
      "description": "the task, in plain specific language",
      "owner": "named owner, or 'UNOWNED — see open questions' if no owner was assigned",
      "deadline": "explicit calendar date or stated deadline, or 'NO DEADLINE — see open questions' if absent",
      "status": "blocked | at-risk | on-track | done | unclear",
      "progress": "quantified progress with 'self-reported, unverified' suffix if unsupported, or null",
      "blocked_by": "named blocker / dependency, or null",
      "smart_flag": "ok | needs SMART-ing — <which SMART dimensions are weak>"
    }
  ],
  "kpis": [
    {
      "name": "KPI name",
      "direction": "up | down | flat | unclear",
      "magnitude": "explicit value, or 'magnitude unspecified — see open questions' if vague",
      "timeframe": "explicit comparison window, or 'timeframe unspecified — see open questions' if absent",
      "completeness_flag": "ok | needs direction/magnitude/timeframe"
    }
  ],
  "risks": [
    {
      "risk": "the risk in the source's own words",
      "what_is_at_risk": "what specifically is at risk",
      "business_impact": "stated impact, or 'IMPACT NOT STATED — see open questions' if absent",
      "trigger_or_cause": "stated trigger/root cause, or null"
    }
  ],
  "open_questions": [
    {
      "question": "the open question",
      "best_placed_to_answer": "named person or role, or null"
    }
  ],
  "recommendations": [
    {
      "recommendation": "escalate | reassign | re-scope | hold review | other",
      "target": "what or who the recommendation applies to",
      "rationale": "one sentence tying the recommendation to a specific risk or rule_id"
    }
  ],
  "distribution": "wide | restricted",
  "distribution_reason": "if restricted, why (performance signals, HR-sensitive, confidential), else null",
  "rationale": "2-3 sentences explaining the major drafting choices and citing which RETRIEVED RULES (by rule_id) most informed each decision."
}

Rules of engagement:
- RETRIEVED RULES are authoritative. The Validator will score against them.
- Do NOT invent owners, deadlines, KPI numbers, or risk impacts that were not in the STATUS object. If something is missing, surface it using the explicit placeholders above AND in open_questions.
- Tasks failing SMART criteria (Rule 1) must have smart_flag='needs SMART-ing — <reason>' rather than being silently passed through as complete.
- KPIs missing direction/magnitude/timeframe (Rule 2) must use the explicit placeholders above AND have completeness_flag='needs ...'.
- Risks without business_impact (Rule 3) must use the 'IMPACT NOT STATED' placeholder.
- Progress claims (Rule 6) that are self-reported and unverified must include 'self-reported, unverified' in the progress field.
- If performance_signals_flagged was true in the STATUS object, set distribution='restricted' and populate distribution_reason (Rule 9). Do NOT name individuals in widely-distributed notes; if Rule 9 fires, keep names only in restricted-distribution sections.
- Recommendations must cite rationale tied to a specific risk or rule_id (Rule 8). Recommendations without rationale are forbidden.
- The digest_90s MUST be readable in under 90 seconds (Rule 10). Aim for 3-5 sentences. Leadership-ready.
- Use plain, specific language. Prefer concrete verbs over corporate jargon.
- In the rationale field, cite rule_ids of the retrieved rules that materially shaped your decisions.
- Output ONLY the JSON. No prose before or after."""


def _format_rules_for_prompt(retrieved_rules: list) -> str:
    """Format retrieved rules into a readable block for the LLM."""
    if not retrieved_rules:
        return "(no rules retrieved — proceed using priors but flag in rationale)"
    lines = []
    for r in retrieved_rules:
        sim = r.get("similarity")
        sim_str = f" (similarity: {sim:.3f})" if sim is not None else ""
        lines.append(f"### Rule {r['rule_id']} — {r['title']}{sim_str}\n{r['text']}")
    return "\n\n".join(lines)


def run_brush(status: dict, retrieved_rules: list = None) -> dict:
    """
    Draft polished status notes from a structured STATUS object.

    Args:
        status: Structured STATUS dict from app.agent03.intake.run_intake()
        retrieved_rules: Top-K rules from app.agent03.search.run_search()

    Returns:
        Structured STATUS_NOTES dict matching the schema. On failure, {"error": ...}.
    """
    retrieved_rules = retrieved_rules or []
    project = status.get("project_or_team", "<no project>")
    tasks_count = len(status.get("raw_tasks") or [])
    logger.info(
        f"BRUSH_START | project={project!r} | tasks={tasks_count} | "
        f"rules_provided={len(retrieved_rules)}"
    )

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative — treat as hard constraints):\n"
        f"{rules_block}\n\n"
        "STATUS object from Intake:\n"
        f"{json.dumps(status, indent=2)}\n\n"
        "Produce the STATUS_NOTES JSON per the schema. In your rationale, cite the "
        "rule_id of every retrieved rule that materially shaped a decision."
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": BRUSH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        notes = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None
        tasks_count = len(notes.get("tasks") or [])
        kpis_count = len(notes.get("kpis") or [])
        risks_count = len(notes.get("risks") or [])
        recs_count = len(notes.get("recommendations") or [])
        distribution = notes.get("distribution", "wide")
        logger.info(
            f"BRUSH_DONE | tokens={tokens_used} | "
            f"tasks={tasks_count} | kpis={kpis_count} | risks={risks_count} | "
            f"recs={recs_count} | distribution={distribution}"
        )
        return notes

    except json.JSONDecodeError as exc:
        logger.error(f"BRUSH_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "brush_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"BRUSH_API_FAIL | error={exc!s}")
        return {"error": "brush_api_failure", "detail": str(exc)}
