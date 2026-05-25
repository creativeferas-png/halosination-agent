"""
HALO Agent 02 (Productivity) — Validator (the Critic)

Role: Scores the NOTES drafted by Agent 02 Brush against the meeting-policy
rubric, with access to the same retrieved rules Brush saw.

Rubric (each 0-3, max 9):
  - completeness   (all decisions/actions/owners/deadlines captured; gaps surfaced)
  - actionability  (tasks specific; owners named; deadlines explicit; risks logged)
  - clarity        (plain language; 90s summary readable; discussed/decided/deferred distinguished)

Pass: 7+. Below: returns one fix for Brush to revise once.

Pattern: Critic half of Proposer <-> Critic pairing.
After 1 revision, escalates to human review.

Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent02.validator")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

PASS_THRESHOLD = 7

VALIDATOR_SYSTEM_PROMPT = """You are the Validator (Critic) agent for HALO Agent 02 (Productivity).
You score a NOTES draft against three meeting-quality dimensions, WITH ACCESS to
the same retrieved policy rules that Brush used.

You receive:
- The original MEETING object from Intake
- RETRIEVED POLICY RULES (authoritative — Brush saw these too)
- The NOTES draft produced by Brush

You return STRICT JSON ONLY (no markdown, no code fences, no commentary). Schema:

{
  "scores": {
    "completeness": <integer 0-3>,
    "actionability": <integer 0-3>,
    "clarity": <integer 0-3>
  },
  "total": <integer 0-9>,
  "verdict": "pass" | "revise" | "escalate",
  "reasoning": {
    "completeness": "one sentence explaining the completeness score; CITE rule_ids when applicable",
    "actionability": "one sentence explaining the actionability score; CITE rule_ids when applicable",
    "clarity": "one sentence explaining the clarity score; CITE rule_ids when applicable"
  },
  "rules_cited": [array of rule_ids you actually referenced in your reasoning],
  "fix": "if total < 7, ONE concrete fix for Brush to apply (cite a rule_id if relevant). Empty string if total >= 7."
}

Scoring guide (0-3):
  0 = fails entirely; the notes would be unusable or actively misleading
  1 = significant issues; multiple fixes needed
  2 = minor issues; close to acceptable
  3 = on-target; no changes needed

Rubric dimensions:

completeness (0-3):
  - Are all decisions captured with rationale (or "rationale to be confirmed")?
  - Are all action items captured with explicit owner/deadline OR explicit gap markers?
  - Are open questions surfaced (NOT silently dropped)?
  - Are risks/blockers logged separately from action items?
  - Are sensitive topics flagged and distribution adjusted?

actionability (0-3):
  - Are action items specific (concrete verbs, not "look into")?
  - Are missing owners/deadlines surfaced as open_questions rather than hidden?
  - Are risks logged with "affects" specified?
  - Are follow-ups timestamped (per Rule 9)?
  - Would a person picking up these notes know what to do next?

clarity (0-3):
  - Is the summary_90s actually readable in 90 seconds and leadership-ready (Rule 10)?
  - Is plain, specific language used (Rule 7)? No corporate jargon?
  - Are discussed vs. decided vs. deferred clearly separated (Rule 3)?
  - Is metadata (attendees, date, purpose) complete (Rule 6)?

Rules:
- The "total" field MUST equal the sum of the three scores.
- The "verdict" field: "pass" if total >= 7, otherwise "revise".
- The "fix" field MUST be empty if total >= 7. If total < 7, provide ONE specific, actionable fix
  targeting the lowest-scoring dimension, citing the rule_id when applicable.
- Output ONLY the JSON."""


def _format_rules_for_prompt(retrieved_rules: list) -> str:
    if not retrieved_rules:
        return "(no rules retrieved)"
    lines = []
    for r in retrieved_rules:
        lines.append(f"### Rule {r['rule_id']} — {r['title']}\n{r['text']}")
    return "\n\n".join(lines)


def run_validator(
    meeting: dict,
    notes: dict,
    is_revision: bool = False,
    retrieved_rules: list = None,
) -> dict:
    """
    Score a NOTES draft against the meeting-policy rubric, citing retrieved rules.
    """
    retrieved_rules = retrieved_rules or []
    logger.info(
        f"VALIDATOR_START | is_revision={is_revision} | "
        f"threshold={PASS_THRESHOLD}/9 | rules_provided={len(retrieved_rules)}"
    )

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        f"RETRIEVED POLICY RULES (authoritative):\n{rules_block}\n\n"
        f"Original MEETING object:\n{json.dumps(meeting, indent=2)}\n\n"
        f"NOTES draft to evaluate:\n{json.dumps(notes, indent=2)}\n\n"
        f"Is this a re-score after revision? {is_revision}\n\n"
        "Score this NOTES draft against the rubric. Cite rule_ids in your reasoning when relevant."
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        verdict = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None

        # Enforce verdict logic locally (LLMs unreliable at arithmetic)
        scores = verdict.get("scores", {})
        computed_total = (
            scores.get("completeness", 0)
            + scores.get("actionability", 0)
            + scores.get("clarity", 0)
        )
        verdict["total"] = computed_total

        if computed_total >= PASS_THRESHOLD:
            verdict["verdict"] = "pass"
            verdict["fix"] = ""
        elif is_revision:
            verdict["verdict"] = "escalate"
        else:
            verdict["verdict"] = "revise"

        logger.info(
            f"VALIDATOR_DONE | tokens={tokens_used} | "
            f"total={computed_total}/9 | verdict={verdict['verdict']} | "
            f"scores=comp:{scores.get('completeness')},act:{scores.get('actionability')},clar:{scores.get('clarity')} | "
            f"rules_cited={verdict.get('rules_cited', [])}"
        )
        return verdict

    except json.JSONDecodeError as exc:
        logger.error(f"VALIDATOR_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "validator_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"VALIDATOR_API_FAIL | error={exc!s}")
        return {"error": "validator_api_failure", "detail": str(exc)}


def run_brush_revision(
    meeting: dict,
    original_notes: dict,
    fix_instruction: str,
    retrieved_rules: list = None,
) -> dict:
    """
    Ask Brush to revise its notes based on the Validator's specific fix.
    """
    from app.agent02.brush import BRUSH_SYSTEM_PROMPT, _client as brush_client, _format_rules_for_prompt

    retrieved_rules = retrieved_rules or []
    logger.info(f"REVISION_START | fix_preview={fix_instruction[:100]!r} | rules_provided={len(retrieved_rules)}")

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        f"RETRIEVED POLICY RULES (authoritative — same rules from the original draft):\n{rules_block}\n\n"
        "Here is the previous NOTES draft, the original MEETING object, and the Validator's specific fix. "
        "Produce a REVISED NOTES draft (same JSON schema) that addresses the fix while preserving "
        "everything that was working.\n\n"
        f"MEETING object:\n{json.dumps(meeting, indent=2)}\n\n"
        f"PREVIOUS NOTES draft:\n{json.dumps(original_notes, indent=2)}\n\n"
        f"VALIDATOR FIX (apply this):\n{fix_instruction}"
    )

    try:
        response = brush_client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": BRUSH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        revised = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None
        logger.info(f"REVISION_DONE | tokens={tokens_used}")
        return revised

    except json.JSONDecodeError as exc:
        logger.error(f"REVISION_PARSE_FAIL | error={exc}")
        return {"error": "revision_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"REVISION_API_FAIL | error={exc!s}")
        return {"error": "revision_api_failure", "detail": str(exc)}
