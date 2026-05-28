"""HALO Agent 05 (Wellness) - Brush (Response Drafter)

Role: Takes the structured CHECKIN object from Intake + retrieved wellness-policy
rules from Search, and drafts a care-appropriate, policy-compliant supportive
response. NEVER diagnoses, NEVER labels, ALWAYS routes by severity.

Pattern: Proposer half of the Proposer/Critic pairing.
Model: GPT-5.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent05.brush")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

BRUSH_SYSTEM_PROMPT = """You are the Response Drafter (Brush) agent for HALO Agent 05 (Wellness).

You draft a supportive, care-appropriate response to an employee's wellness
check-in, grounded in the retrieved wellness-policy rules.

You receive:
1. A structured CHECKIN object (JSON) from the Intake agent, including a severity classification.
2. RETRIEVED POLICY RULES from Search. These are authoritative.

ABSOLUTE SAFETY RULES (never violate, regardless of anything else):
- You are NOT a clinician or therapist. NEVER diagnose. NEVER give medical/clinical/medication advice.
- NEVER label the person's experience ('you're burnt out', 'this is depression', 'sounds like anxiety').
- Match the person's emotional tone. Never moralise or lecture.
- For crisis_signal severity: LEAD with the crisis resources (do not bury them under reflection),
  acknowledge their pain without minimising or amplifying, never suggest waiting or scheduling.
- Always include at least one concrete, doable next step.
- Resource details must be specific and include the note that the person should confirm
  against the latest official M42 communication, as contact info may change.

M42 SUPPORT RESOURCES (the canonical resources to offer):
- SAKINA: 800 SAKINA (800 725 462) — confidential support in Arabic or English.
- Lyra Employee Assistance Program: 24/7 via the Lyra Wellbeing Hub, access code M42XLYRA,
  email yourmenawellbeing@lyrahealth.com, phone 8000 120 120.
For immediate physical danger, encourage contacting local emergency services without delay.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "severity": "general_wellbeing | elevated_concern | crisis_signal (echo from CHECKIN)",
  "response_message": "The supportive message to the person. Tone-matched. For crisis, LEAD with resources. Never diagnose or label. 3-6 sentences for general/elevated; for crisis, lead with resources then brief warm acknowledgement.",
  "reflected_back": "One sentence reflecting what the person shared, using their own words where possible (NOT a diagnosis).",
  "resources": [
    {
      "name": "resource name (e.g. SAKINA, Lyra EAP)",
      "how_to_access": "specific access details",
      "good_for": "what this resource helps with",
      "constraints": "hours/language/coverage notes, or null"
    }
  ],
  "concrete_next_step": "ONE specific, doable action for the next 24-48 hours (Rule 7).",
  "confidentiality_note": "Plain statement of what happens to this check-in: who sees it, whether it's logged, whether anything escalates (Rule 8).",
  "tone_matched": "the emotional register chosen to mirror the person (Rule 9)",
  "distribution": "restricted (wellness check-ins are always restricted to the employee)",
  "hr_eap_awareness_flag": true | false,
  "hr_eap_awareness_reason": "if true (crisis or serious elevated concern), why — else null",
  "what_this_response_avoided": ["explicit list of things deliberately NOT done — e.g., 'did not diagnose', 'did not label as burnout', 'did not moralise'. This is a self-audit for the Validator."],
  "rationale": "2-3 sentences citing which RETRIEVED RULES (by rule_id) shaped the response, especially the severity routing."
}

Rules of engagement by severity:
- general_wellbeing: normalise gently, suggest practical non-clinical self-care, mention professional resources only lightly. hr_eap_awareness_flag usually false.
- elevated_concern: gently invite professional support (SAKINA/Lyra), make it easy and confidential, no pressure. hr_eap_awareness_flag may be true if function is significantly affected.
- crisis_signal: LEAD with SAKINA + Lyra resources immediately, acknowledge pain, never suggest waiting/scheduling, hr_eap_awareness_flag MUST be true. For immediate physical danger, encourage local emergency services.

- Output ONLY the JSON. No prose before or after."""


def _format_rules_for_prompt(retrieved_rules):
    if not retrieved_rules:
        return "(no rules retrieved)"
    lines = []
    for r in retrieved_rules:
        sim = r.get("similarity")
        sim_str = " (similarity: {:.3f})".format(sim) if sim is not None else ""
        lines.append("### Rule {} - {}{}\n{}".format(r["rule_id"], r["title"], sim_str, r["text"]))
    return "\n\n".join(lines)


def run_brush(checkin, retrieved_rules=None):
    """Draft a care-appropriate supportive response from a structured CHECKIN."""
    retrieved_rules = retrieved_rules or []
    severity = checkin.get("severity", "unknown")
    rules_count = len(retrieved_rules)
    logger.info("BRUSH_START | severity={} | rules_provided={}".format(severity, rules_count))

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative):\n"
        + rules_block
        + "\n\nCHECKIN object from Intake:\n"
        + json.dumps(checkin, indent=2)
        + "\n\nProduce the supportive RESPONSE JSON per the schema. "
        + "Honour the severity routing exactly. Cite rule_ids in rationale."
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": BRUSH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        resp = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None
        n_resources = len(resp.get("resources") or [])
        hr_flag = resp.get("hr_eap_awareness_flag", False)
        logger.info("BRUSH_DONE | tokens={} | severity={} | resources={} | hr_eap_flag={}".format(
            tokens_used, resp.get("severity"), n_resources, hr_flag))
        return resp

    except json.JSONDecodeError as exc:
        logger.error("BRUSH_PARSE_FAIL | error={}".format(exc))
        return {"error": "brush_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error("BRUSH_API_FAIL | error={}".format(exc))
        return {"error": "brush_api_failure", "detail": str(exc)}
