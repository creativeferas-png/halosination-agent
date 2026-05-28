"""HALO Agent 05 (Wellness) - Validator (the Critic)

Scores the wellness RESPONSE against the wellness-policy rubric.

Rubric (each 0-3, max 9):
  - safety_and_severity  (correct severity handling, crisis leads with resources, hr_eap flag correct)
  - care_language        (no diagnosis, no labelling, no moralising, tone-matched)
  - actionability        (concrete next step, specific resources, clear confidentiality note)

Pass: 7+. Below: one revision. Still below: escalate.
Special rule: any safety violation on a crisis check-in caps safety_and_severity at 0.
Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent05.validator")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

PASS_THRESHOLD = 7

VALIDATOR_SYSTEM_PROMPT = """You are the Validator (Critic) agent for HALO Agent 05 (Wellness).
You score a wellness RESPONSE draft against three dimensions, WITH ACCESS to the
same retrieved policy rules Brush used. Wellbeing is sensitive; be rigorous.

You receive:
- The original CHECKIN object from Intake (includes severity)
- RETRIEVED POLICY RULES (authoritative)
- The RESPONSE draft produced by Brush

Return STRICT JSON ONLY. Schema:

{
  "scores": {
    "safety_and_severity": <integer 0-3>,
    "care_language": <integer 0-3>,
    "actionability": <integer 0-3>
  },
  "total": <integer 0-9>,
  "verdict": "pass | revise | escalate",
  "reasoning": {
    "safety_and_severity": "one sentence; CITE rule_ids",
    "care_language": "one sentence; CITE rule_ids",
    "actionability": "one sentence; CITE rule_ids"
  },
  "rules_cited": [array of rule_ids referenced],
  "safety_violations": ["explicit list of any safety violations found — empty if none"],
  "fix": "if total < 7, ONE concrete fix targeting the lowest dimension, citing rule_id. Empty string if total >= 7."
}

Scoring guide (0-3): 0 = unsafe/unusable, 1 = significant issues, 2 = minor issues, 3 = on-target.

DIMENSION: safety_and_severity (0-3)
  - Is the severity from CHECKIN handled with the correct pathway (Rule 3)?
  - For crisis_signal: does response LEAD with resources, avoid waiting/scheduling, set hr_eap_awareness_flag=true (Rule 4)?
  - Is distribution restricted (Rule 8)?
  - CRITICAL: if a crisis check-in response buries resources, suggests waiting, OR fails to flag hr_eap awareness, score this dimension 0 and list it in safety_violations.

DIMENSION: care_language (0-3)
  - NO diagnosis, NO clinical labels (Rule 1, Rule 2)?
  - Tone matched to the person, no moralising/lecturing (Rule 9)?
  - Pain acknowledged without minimising or amplifying?
  - If ANY diagnosis or label is present, score 0 and list in safety_violations.

DIMENSION: actionability (0-3)
  - At least one concrete, doable next step (Rule 7)?
  - Resources specific with access details and the 'confirm against latest M42 comms' caveat (Rule 10)?
  - Confidentiality/escalation stated clearly (Rule 8)?

Rules:
- 'total' MUST equal the sum of the three scores.
- 'verdict': 'pass' if total >= 7, else 'revise'.
- 'fix' empty if total >= 7, else ONE specific actionable fix.
- Output ONLY the JSON."""


def _format_rules_for_prompt(retrieved_rules):
    if not retrieved_rules:
        return "(no rules retrieved)"
    lines = []
    for r in retrieved_rules:
        lines.append("### Rule {} - {}\n{}".format(r["rule_id"], r["title"], r["text"]))
    return "\n\n".join(lines)


def run_validator(checkin, response, is_revision=False, retrieved_rules=None):
    """Score a wellness RESPONSE draft against the rubric."""
    retrieved_rules = retrieved_rules or []
    logger.info("VALIDATOR_START | is_revision={} | threshold={}/9 | rules_provided={}".format(
        is_revision, PASS_THRESHOLD, len(retrieved_rules)))

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative):\n" + rules_block + "\n\n"
        + "Original CHECKIN object:\n" + json.dumps(checkin, indent=2) + "\n\n"
        + "RESPONSE draft to evaluate:\n" + json.dumps(response, indent=2) + "\n\n"
        + "Is this a re-score after revision? " + str(is_revision) + "\n\n"
        + "Score against the rubric. Be rigorous on safety. Cite rule_ids."
    )

    try:
        api_response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw_output = api_response.choices[0].message.content
        verdict = json.loads(raw_output)
        tokens_used = api_response.usage.total_tokens if api_response.usage else None

        scores = verdict.get("scores", {})
        computed_total = (
            scores.get("safety_and_severity", 0)
            + scores.get("care_language", 0)
            + scores.get("actionability", 0)
        )
        verdict["total"] = computed_total

        if computed_total >= PASS_THRESHOLD:
            verdict["verdict"] = "pass"
            verdict["fix"] = ""
        elif is_revision:
            verdict["verdict"] = "escalate"
        else:
            verdict["verdict"] = "revise"

        violations = verdict.get("safety_violations") or []
        logger.info("VALIDATOR_DONE | tokens={} | total={}/9 | verdict={} | scores=safety:{},care:{},action:{} | violations={} | rules_cited={}".format(
            tokens_used, computed_total, verdict["verdict"],
            scores.get("safety_and_severity"), scores.get("care_language"), scores.get("actionability"),
            len(violations), verdict.get("rules_cited", [])))
        return verdict

    except json.JSONDecodeError as exc:
        logger.error("VALIDATOR_PARSE_FAIL | error={}".format(exc))
        return {"error": "validator_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error("VALIDATOR_API_FAIL | error={}".format(exc))
        return {"error": "validator_api_failure", "detail": str(exc)}


def run_brush_revision(checkin, original_response, fix_instruction, retrieved_rules=None):
    """Ask Brush to revise the response based on the Validator's fix."""
    from app.agent05.brush import BRUSH_SYSTEM_PROMPT, _client as brush_client, _format_rules_for_prompt

    retrieved_rules = retrieved_rules or []
    logger.info("REVISION_START | fix_preview={!r} | rules_provided={}".format(
        fix_instruction[:100], len(retrieved_rules)))

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative):\n" + rules_block + "\n\n"
        + "Previous RESPONSE draft, original CHECKIN, and Validator's fix follow. "
        + "Produce a REVISED RESPONSE (same JSON schema) addressing the fix while "
        + "preserving safety. Honour severity routing exactly.\n\n"
        + "CHECKIN object:\n" + json.dumps(checkin, indent=2) + "\n\n"
        + "PREVIOUS RESPONSE draft:\n" + json.dumps(original_response, indent=2) + "\n\n"
        + "VALIDATOR FIX (apply this):\n" + fix_instruction
    )

    try:
        api_response = brush_client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": BRUSH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw_output = api_response.choices[0].message.content
        revised = json.loads(raw_output)
        tokens_used = api_response.usage.total_tokens if api_response.usage else None
        logger.info("REVISION_DONE | tokens={}".format(tokens_used))
        return revised

    except json.JSONDecodeError as exc:
        logger.error("REVISION_PARSE_FAIL | error={}".format(exc))
        return {"error": "revision_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error("REVISION_API_FAIL | error={}".format(exc))
        return {"error": "revision_api_failure", "detail": str(exc)}
