"""
HALO Agent 03 (Task & KPI) — Validator (the Critic)

Role: Scores the STATUS_NOTES drafted by Agent 03 Brush against the
task-policy rubric, with access to the same retrieved rules Brush saw.

Rubric (each 0-3, max 9):
  - specificity      (tasks SMART, owners/deadlines explicit or surfaced, dependencies named)
  - measurability    (KPIs complete in direction/magnitude/timeframe, progress quantified, risks have impact)
  - risk_awareness   (blocked/at-risk classification, performance flag respected, recommendations have rationale)

Pass: 7+. Below: returns one fix for Brush to revise once.

Pattern: Critic half of Proposer <-> Critic pairing.
After 1 revision, escalates to human review.

Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent03.validator")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

PASS_THRESHOLD = 7

VALIDATOR_SYSTEM_PROMPT = """You are the Validator (Critic) agent for HALO Agent 03 (Task & KPI).
You score a STATUS_NOTES draft against three task-and-KPI-quality dimensions,
WITH ACCESS to the same retrieved policy rules that Brush used.

You receive:
- The original STATUS object from Intake
- RETRIEVED POLICY RULES (authoritative — Brush saw these too)
- The STATUS_NOTES draft produced by Brush

You return STRICT JSON ONLY (no markdown, no code fences, no commentary). Schema:

{
  "scores": {
    "specificity": <integer 0-3>,
    "measurability": <integer 0-3>,
    "risk_awareness": <integer 0-3>
  },
  "total": <integer 0-9>,
  "verdict": "pass" | "revise" | "escalate",
  "reasoning": {
    "specificity": "one sentence; CITE rule_ids when applicable",
    "measurability": "one sentence; CITE rule_ids when applicable",
    "risk_awareness": "one sentence; CITE rule_ids when applicable"
  },
  "rules_cited": [array of rule_ids you actually referenced in your reasoning],
  "fix": "if total < 7, ONE concrete fix for Brush to apply (cite a rule_id if relevant). Empty string if total >= 7."
}

Scoring guide (0-3):
  0 = fails entirely; status would be misleading or unusable
  1 = significant issues; multiple fixes needed
  2 = minor issues; close to acceptable
  3 = on-target; no changes needed

Rubric dimensions:

specificity (0-3) — Are tasks SMART? Owners/deadlines explicit or surfaced as gaps?
  - Are tasks rewritten as Specific deliverables (Rule 1)?
  - Are owners and deadlines explicit OR surfaced as 'UNOWNED / NO DEADLINE — see open questions' (Rule 4)?
  - Are tasks failing SMART criteria flagged with smart_flag='needs SMART-ing' (Rule 1)?
  - Are dependencies surfaced via blocked_by (Rule 7)?
  - Is the digest_90s specific enough to act on (Rule 10)?

measurability (0-3) — KPIs complete; progress quantified; risks have impact.
  - Do KPIs have direction + magnitude + timeframe, OR are gaps surfaced with 'unspecified' placeholders (Rule 2)?
  - Is progress quantified, with 'self-reported, unverified' flagged where needed (Rule 6)?
  - Do risks have business_impact, OR use 'IMPACT NOT STATED' placeholder (Rule 3)?
  - Are KPIs flagged for completeness via completeness_flag?

risk_awareness (0-3) — Correct status classification, sensitive handling, accountable recommendations.
  - Are tasks classified into blocked / at-risk / on-track / done / unclear correctly (Rule 5)?
  - If performance_signals_flagged was true in STATUS, is distribution='restricted' (Rule 9)?
  - Do all recommendations have rationale tied to specific risks or rule_ids (Rule 8)?
  - Are risks with named individuals handled appropriately (Rule 9)?

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
    status: dict,
    notes: dict,
    is_revision: bool = False,
    retrieved_rules: list = None,
) -> dict:
    """
    Score a STATUS_NOTES draft against the task-policy rubric, citing retrieved rules.
    """
    retrieved_rules = retrieved_rules or []
    logger.info(
        f"VALIDATOR_START | is_revision={is_revision} | "
        f"threshold={PASS_THRESHOLD}/9 | rules_provided={len(retrieved_rules)}"
    )

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        f"RETRIEVED POLICY RULES (authoritative):\n{rules_block}\n\n"
        f"Original STATUS object:\n{json.dumps(status, indent=2)}\n\n"
        f"STATUS_NOTES draft to evaluate:\n{json.dumps(notes, indent=2)}\n\n"
        f"Is this a re-score after revision? {is_revision}\n\n"
        "Score this STATUS_NOTES draft against the rubric. Cite rule_ids in your reasoning when relevant."
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
            scores.get("specificity", 0)
            + scores.get("measurability", 0)
            + scores.get("risk_awareness", 0)
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
            f"scores=spec:{scores.get('specificity')},meas:{scores.get('measurability')},risk:{scores.get('risk_awareness')} | "
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
    status: dict,
    original_notes: dict,
    fix_instruction: str,
    retrieved_rules: list = None,
) -> dict:
    """
    Ask Brush to revise its notes based on the Validator's specific fix.
    """
    from app.agent03.brush import BRUSH_SYSTEM_PROMPT, _client as brush_client, _format_rules_for_prompt

    retrieved_rules = retrieved_rules or []
    logger.info(f"REVISION_START | fix_preview={fix_instruction[:100]!r} | rules_provided={len(retrieved_rules)}")

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        f"RETRIEVED POLICY RULES (authoritative — same rules from the original draft):\n{rules_block}\n\n"
        "Here is the previous STATUS_NOTES draft, the original STATUS object, and the Validator's specific fix. "
        "Produce a REVISED STATUS_NOTES draft (same JSON schema) that addresses the fix while preserving "
        "everything that was working.\n\n"
        f"STATUS object:\n{json.dumps(status, indent=2)}\n\n"
        f"PREVIOUS STATUS_NOTES draft:\n{json.dumps(original_notes, indent=2)}\n\n"
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
