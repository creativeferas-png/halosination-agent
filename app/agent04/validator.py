"""HALO Agent 04 (Social) - Validator (the Critic)

Role: Scores the SUGGESTIONS drafted by Agent 04 Brush against the
social-policy rubric.

Rubric (each 0-3, max 9):
  - relevance              (suggestions specific, rationale present, why_now where applicable)
  - diversity              (>=3 suggestion_types, mix of senior/peer/horizon, group + people balance)
  - privacy_and_care       (Rule 4 respected, Rule 9 firing correctly with wellbeing_note, Rule 8 conflicts excluded)

Pass: 7+. Below: returns one fix for Brush to revise once.
Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent04.validator")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

PASS_THRESHOLD = 7

VALIDATOR_SYSTEM_PROMPT = """You are the Validator (Critic) agent for HALO Agent 04 (Social).
You score a SUGGESTIONS draft against three social-quality dimensions, WITH ACCESS
to the same retrieved policy rules that Brush used.

You receive:
- The original PROFILE object from Intake
- RETRIEVED POLICY RULES (authoritative)
- The SUGGESTIONS draft produced by Brush

Return STRICT JSON ONLY. Schema:

{
  "scores": {
    "relevance": <integer 0-3>,
    "diversity": <integer 0-3>,
    "privacy_and_care": <integer 0-3>
  },
  "total": <integer 0-9>,
  "verdict": "pass" | "revise" | "escalate",
  "reasoning": {
    "relevance": "one sentence; CITE rule_ids",
    "diversity": "one sentence; CITE rule_ids",
    "privacy_and_care": "one sentence; CITE rule_ids"
  },
  "rules_cited": [array of rule_ids referenced],
  "fix": "if total < 7, ONE concrete fix targeting lowest dimension, citing rule_id. Empty string if total >= 7."
}

Scoring guide (0-3):
  0 = fails entirely; suggestions would be unusable or harmful
  1 = significant issues; multiple fixes needed
  2 = minor issues; close to acceptable
  3 = on-target; no changes needed

Rubric dimensions:

relevance (0-3) - Suggestions specific, rationale present, why_now grounded.
  - Are people_suggestions specific (named, with role)? (Rule 1)
  - Does EVERY suggestion have a relevance_rationale that names a concrete overlap? (Rule 2)
  - Is why_now populated where genuinely applicable? (Rule 5)
  - Are group_suggestions specific with what_it_does + why_this_employee_fits? (Rule 6)
  - Is summary_60s readable in 60 seconds and front-loads the best suggestions? (Rule 10)

diversity (0-3) - Suggestion set spans connection types; no filter bubble.
  - Are at least 3 different suggestion_types represented? (Rule 3)
  - Is there a mix of peer / mentor / cross-OpCo / horizon-broadener? (Rule 3)
  - Are mentor/mentee suggestions paired with power_dynamics_note? (Rule 7)
  - Is there a balance of people_suggestions and group_suggestions?

privacy_and_care (0-3) - Sensitive attributes avoided, vulnerable signals handled.
  - Are all suggestions based on professional or mixed attributes, NEVER on sensitive personal attributes? (Rule 4)
  - If conflict_signals were present, are conflicted suggestions excluded with explanation? (Rule 8)
  - If isolation_or_loneliness_signal is true: is distribution=restricted AND wellbeing_note populated with care-appropriate (non-clinical, non-prescriptive) language? (Rule 9)
  - Is the tone supportive rather than transactional?

Rules:
- The "total" field MUST equal the sum of the three scores.
- The "verdict" field: "pass" if total >= 7, otherwise "revise".
- The "fix" field MUST be empty if total >= 7. Otherwise ONE specific actionable fix.
- Output ONLY the JSON."""


def _format_rules_for_prompt(retrieved_rules):
    if not retrieved_rules:
        return "(no rules retrieved)"
    lines = []
    for r in retrieved_rules:
        lines.append("### Rule {} - {}\n{}".format(r["rule_id"], r["title"], r["text"]))
    return "\n\n".join(lines)


def run_validator(profile, suggestions, is_revision=False, retrieved_rules=None):
    """Score a SUGGESTIONS draft against the social-policy rubric."""
    retrieved_rules = retrieved_rules or []
    logger.info("VALIDATOR_START | is_revision={} | threshold={}/9 | rules_provided={}".format(
        is_revision, PASS_THRESHOLD, len(retrieved_rules)))

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative):\n" + rules_block + "\n\n"
        + "Original PROFILE object:\n" + json.dumps(profile, indent=2) + "\n\n"
        + "SUGGESTIONS draft to evaluate:\n" + json.dumps(suggestions, indent=2) + "\n\n"
        + "Is this a re-score after revision? " + str(is_revision) + "\n\n"
        + "Score this SUGGESTIONS draft against the rubric. Cite rule_ids in reasoning."
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

        # Enforce verdict logic locally
        scores = verdict.get("scores", {})
        computed_total = (
            scores.get("relevance", 0)
            + scores.get("diversity", 0)
            + scores.get("privacy_and_care", 0)
        )
        verdict["total"] = computed_total

        if computed_total >= PASS_THRESHOLD:
            verdict["verdict"] = "pass"
            verdict["fix"] = ""
        elif is_revision:
            verdict["verdict"] = "escalate"
        else:
            verdict["verdict"] = "revise"

        logger.info("VALIDATOR_DONE | tokens={} | total={}/9 | verdict={} | scores=rel:{},div:{},care:{} | rules_cited={}".format(
            tokens_used, computed_total, verdict["verdict"],
            scores.get("relevance"), scores.get("diversity"), scores.get("privacy_and_care"),
            verdict.get("rules_cited", [])))
        return verdict

    except json.JSONDecodeError as exc:
        logger.error("VALIDATOR_PARSE_FAIL | error={}".format(exc))
        return {"error": "validator_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error("VALIDATOR_API_FAIL | error={}".format(exc))
        return {"error": "validator_api_failure", "detail": str(exc)}


def run_brush_revision(profile, original_suggestions, fix_instruction, retrieved_rules=None):
    """Ask Brush to revise suggestions based on the Validator's specific fix."""
    from app.agent04.brush import BRUSH_SYSTEM_PROMPT, _client as brush_client, _format_rules_for_prompt

    retrieved_rules = retrieved_rules or []
    logger.info("REVISION_START | fix_preview={!r} | rules_provided={}".format(
        fix_instruction[:100], len(retrieved_rules)))

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative):\n" + rules_block + "\n\n"
        + "Previous SUGGESTIONS draft, original PROFILE, and Validator's fix follow. "
        + "Produce a REVISED SUGGESTIONS draft (same JSON schema) addressing the fix "
        + "while preserving what was working.\n\n"
        + "PROFILE object:\n" + json.dumps(profile, indent=2) + "\n\n"
        + "PREVIOUS SUGGESTIONS draft:\n" + json.dumps(original_suggestions, indent=2) + "\n\n"
        + "VALIDATOR FIX (apply this):\n" + fix_instruction
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
        logger.info("REVISION_DONE | tokens={}".format(tokens_used))
        return revised

    except json.JSONDecodeError as exc:
        logger.error("REVISION_PARSE_FAIL | error={}".format(exc))
        return {"error": "revision_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error("REVISION_API_FAIL | error={}".format(exc))
        return {"error": "revision_api_failure", "detail": str(exc)}
