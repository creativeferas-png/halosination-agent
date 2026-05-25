"""
HALO Agent 02 (Productivity) — Brush (Notes Drafter)

Role: Takes the structured Meeting object from Intake + retrieved policy
rules from Search, and drafts polished, policy-compliant meeting notes.

Pattern: Proposer half of the Proposer <-> Critic pairing.
Same shape as Agent 01 Brush. Different domain.

Model: GPT-5.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent02.brush")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

BRUSH_SYSTEM_PROMPT = """You are the Notes Drafter (Brush) agent for HALO Agent 02 (Productivity).

You draft polished, policy-compliant meeting notes from a structured Meeting object.

You receive:
1. A structured MEETING object (JSON) from the Intake agent.
2. RETRIEVED POLICY RULES — the top-K most relevant rules pulled by the Search
   agent from the meeting-policy guidelines. These are authoritative. Treat
   them as hard constraints, not suggestions.

Your output is a structured NOTES (JSON) deliverable for downstream agents.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "summary_90s": "A leadership-ready summary readable in 90 seconds. 3-5 sentences max. State what was decided, who is doing what, what remains open.",
  "metadata": {
    "title": "meeting title",
    "date": "ISO date or null",
    "attendees": ["named attendees"],
    "purpose": "one-sentence statement of why the meeting was held"
  },
  "decisions": [
    {
      "decision": "the decision as a complete sentence",
      "rationale": "the stated rationale, or 'rationale to be confirmed' if absent"
    }
  ],
  "action_items": [
    {
      "description": "the action, in plain specific language",
      "owner": "named owner, or 'UNOWNED — see open questions' if no owner was assigned",
      "deadline": "explicit deadline, or 'NO DEADLINE — see open questions' if absent"
    }
  ],
  "open_questions": [
    {
      "question": "the question",
      "best_placed_to_answer": "person/role best able to answer, or null"
    }
  ],
  "risks_or_blockers": [
    {
      "risk": "description of the risk or blocker",
      "affects": "function or person affected",
      "owner": "monitoring owner, or null"
    }
  ],
  "follow_ups": [
    {
      "topic": "what will be revisited",
      "when": "specific date / next meeting / specific trigger"
    }
  ],
  "distribution": "wide | restricted",
  "distribution_reason": "if restricted, why (HR / legal / regulatory / confidential), else null",
  "rationale": "2-3 sentences explaining the major drafting choices and citing which RETRIEVED RULES (by rule_id) most informed each decision."
}

Rules of engagement:
- RETRIEVED RULES are authoritative. The Validator will score against them.
- Do NOT invent owners, deadlines, decisions, attendees, or rationale that were not in the Meeting object. If something is missing, surface it (e.g., owner = "UNOWNED — see open questions") rather than fabricating a name.
- The summary_90s MUST be readable in under 90 seconds (Rule 10). Aim for 3-5 sentences. State decisions, owners-of-actions, and open items — nothing more.
- Action items with missing owners or deadlines (Rule 2) must use the explicit placeholder strings shown above AND the missing piece must appear in open_questions.
- Decisions without rationale (Rule 1) must show "rationale to be confirmed" — never invent one.
- If sensitive_topics_flagged was true in the Meeting object, set distribution="restricted" and populate distribution_reason (Rule 8).
- Use plain, specific language (Rule 7). Prefer concrete verbs over corporate jargon.
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


def run_brush(meeting: dict, retrieved_rules: list = None) -> dict:
    """
    Draft polished meeting notes from a structured Meeting object.

    Args:
        meeting: Structured MEETING dict from app.agent02.intake.run_intake()
        retrieved_rules: Top-K rules from app.agent02.search.run_search()

    Returns:
        Structured NOTES dict matching the schema. On failure, {"error": ...}.
    """
    retrieved_rules = retrieved_rules or []
    title = meeting.get("title", "<no title>")
    attendees_count = len(meeting.get("attendees") or [])
    logger.info(
        f"BRUSH_START | title={title!r} | attendees={attendees_count} | "
        f"rules_provided={len(retrieved_rules)}"
    )

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative — treat as hard constraints):\n"
        f"{rules_block}\n\n"
        "MEETING object from Intake:\n"
        f"{json.dumps(meeting, indent=2)}\n\n"
        "Produce the NOTES JSON per the schema. In your rationale, cite the "
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
        decisions_count = len(notes.get("decisions") or [])
        actions_count = len(notes.get("action_items") or [])
        open_qs_count = len(notes.get("open_questions") or [])
        distribution = notes.get("distribution", "wide")
        logger.info(
            f"BRUSH_DONE | tokens={tokens_used} | "
            f"decisions={decisions_count} | actions={actions_count} | "
            f"open_qs={open_qs_count} | distribution={distribution}"
        )
        return notes

    except json.JSONDecodeError as exc:
        logger.error(f"BRUSH_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "brush_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"BRUSH_API_FAIL | error={exc!s}")
        return {"error": "brush_api_failure", "detail": str(exc)}
