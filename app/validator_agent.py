"""
HALOsination — Validator Agent (the Critic)

Role: Scores a DRAFT from Brush against the brand rubric, with access to
the same retrieved brand rules that Brush saw. This means the Critic can
cite specific rules when it flags a problem.

Rubric (each 0-3, max 9):
  - brand_voice
  - visual_spec
  - audience_fit

Pass: 7+. Below: returns one fix for Brush to revise once.

Pattern: Critic half of Proposer <-> Critic pairing.
After 1 revision, escalates to human review.

Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.validator")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

PASS_THRESHOLD = 7

VALIDATOR_SYSTEM_PROMPT = """You are the Validator agent for HALOsination, an internal G42
brand and creative agent. You score a DRAFT asset against three brand-quality dimensions,
WITH ACCESS to the same retrieved brand rules that Brush used.

You receive:
- The original BRIEF (what the asset is supposed to do)
- RETRIEVED BRAND RULES (authoritative — Brush saw these too)
- The DRAFT produced by Brush

You return STRICT JSON ONLY (no markdown, no code fences, no commentary). Schema:

{
  "scores": {
    "brand_voice": <integer 0-3>,
    "visual_spec": <integer 0-3>,
    "audience_fit": <integer 0-3>
  },
  "total": <integer 0-9>,
  "verdict": "pass" | "revise" | "escalate",
  "reasoning": {
    "brand_voice": "one sentence explaining the brand_voice score; CITE rule_ids when applicable",
    "visual_spec": "one sentence explaining the visual_spec score; CITE rule_ids when applicable",
    "audience_fit": "one sentence explaining the audience_fit score; CITE rule_ids when applicable"
  },
  "rules_cited": [array of rule_ids you actually referenced in your reasoning],
  "fix": "if total < 7, ONE concrete, specific fix for Brush to apply (cite a rule_id if relevant). Empty string if total >= 7."
}

Scoring guide (0-3):
  0 = fails entirely; would harm the brand or audience if shipped
  1 = significant issues; multiple fixes needed
  2 = minor issues; close to acceptable
  3 = on-target; no changes needed

Rubric dimensions:

brand_voice (0-3):
  - Does the copy tone match the BRIEF's tone_hints?
  - Does the copy comply with the retrieved voice rules?
  - Any forbidden words from the retrieved forbidden-words rule?
  - Concise, memorable headline?

visual_spec (0-3):
  - Does the visual concept comply with retrieved visual identity rules (palette, composition, imagery)?
  - For healthcare audiences: zero tolerance for distress imagery; check retrieved healthcare-imagery rule.
  - Clean and readable composition?

audience_fit (0-3):
  - Does the register match the retrieved audience-register rule?
  - For healthcare professionals: trustworthy, evidence-aware, non-sensational?
  - Right CTA style per retrieved CTA rule?

Rules:
- The "total" field MUST equal the sum of the three scores.
- The "verdict" field: "pass" if total >= 7, otherwise "revise".
- The "fix" field MUST be empty if total >= 7. If total < 7, provide ONE specific, actionable fix
  targeting the lowest-scoring dimension, citing the rule_id when applicable.
- Output ONLY the JSON."""


def _format_rules_for_prompt(retrieved_rules: list[dict]) -> str:
    if not retrieved_rules:
        return "(no rules retrieved)"
    lines = []
    for r in retrieved_rules:
        lines.append(f"### Rule {r['rule_id']} — {r['title']}\n{r['text']}")
    return "\n\n".join(lines)


def run_validator(
    brief: dict,
    draft: dict,
    is_revision: bool = False,
    retrieved_rules: list[dict] | None = None,
) -> dict:
    """
    Score a draft against the brand rubric, citing retrieved rules.
    """
    retrieved_rules = retrieved_rules or []
    logger.info(
        f"VALIDATOR_START | is_revision={is_revision} | "
        f"threshold={PASS_THRESHOLD}/9 | rules_provided={len(retrieved_rules)}"
    )

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        f"RETRIEVED BRAND RULES (authoritative):\n{rules_block}\n\n"
        f"Original BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"DRAFT to evaluate:\n{json.dumps(draft, indent=2)}\n\n"
        f"Is this a re-score after revision? {is_revision}\n\n"
        "Score this DRAFT against the rubric. Cite rule_ids in your reasoning when relevant."
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
            scores.get("brand_voice", 0)
            + scores.get("visual_spec", 0)
            + scores.get("audience_fit", 0)
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
            f"scores=voice:{scores.get('brand_voice')},visual:{scores.get('visual_spec')},audience:{scores.get('audience_fit')} | "
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
    brief: dict,
    original_draft: dict,
    fix_instruction: str,
    retrieved_rules: list[dict] | None = None,
) -> dict:
    """
    Ask Brush to revise its draft based on the Validator's specific fix.
    The retrieved rules go with the revision so Brush stays grounded.
    """
    from app.brush_agent import BRUSH_SYSTEM_PROMPT, _client as brush_client, _format_rules_for_prompt

    retrieved_rules = retrieved_rules or []
    logger.info(f"REVISION_START | fix_preview={fix_instruction[:100]!r} | rules_provided={len(retrieved_rules)}")

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        f"RETRIEVED BRAND RULES (authoritative — same rules from the original draft):\n{rules_block}\n\n"
        "Here is the previous DRAFT, the original BRIEF, and the Validator's specific fix. "
        "Produce a REVISED DRAFT (same JSON schema) that addresses the fix while preserving "
        "everything that was working.\n\n"
        f"BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"PREVIOUS DRAFT:\n{json.dumps(original_draft, indent=2)}\n\n"
        f"VALIDATOR FIX (apply this):\n{fix_instruction}"
    )

    try:
        response = brush_client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": BRUSH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        revised = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None
        logger.info(
            f"REVISION_DONE | tokens={tokens_used} | "
            f"new_headline={revised.get('copy', {}).get('headline', '')[:60]!r}"
        )
        return revised

    except json.JSONDecodeError as exc:
        logger.error(f"REVISION_PARSE_FAIL | error={exc}")
        return {"error": "revision_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"REVISION_API_FAIL | error={exc!s}")
        return {"error": "revision_api_failure", "detail": str(exc)}
