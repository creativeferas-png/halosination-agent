"""
HALOsination — Validator Agent (the Critic)

Role: Scores a DRAFT from the Brush agent against the brand rubric.
Returns a verdict + specific fix recommendation if the draft fails.

Rubric (each dimension 0-3, max 9 total):
  - brand_voice: tone, vocabulary, no forbidden words
  - visual_spec: colors, typography, layout per brand guidelines
  - audience_fit: right register for stated stakeholder

Pass threshold: 7/9. Below that, returns one concrete fix for Brush to revise.

Pattern: This is the "Critic" half of the Proposer <-> Critic pairing
from Sam's May 21 check-in. After one revision attempt, the system
escalates to a human (per "human-in-the-loop + light autonomy" principle).

Model: GPT-4.1 via Compass (good structured-judgment reasoning, cheap).
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

PASS_THRESHOLD = 7  # out of 9

VALIDATOR_SYSTEM_PROMPT = """You are the Validator agent for HALOsination, an internal G42
brand and creative agent. You score a DRAFT asset against three brand-quality dimensions.

You receive:
- The original BRIEF (what the asset is supposed to do)
- The DRAFT produced by the Brush agent (copy + visual_spec + rationale)

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
    "brand_voice": "one sentence explaining the brand_voice score",
    "visual_spec": "one sentence explaining the visual_spec score",
    "audience_fit": "one sentence explaining the audience_fit score"
  },
  "fix": "if total < 7, ONE concrete, specific fix for Brush to apply. Empty string if total >= 7."
}

Scoring guide for each dimension (0-3):
  0 = fails entirely; would harm the brand or audience if shipped
  1 = significant issues; multiple fixes needed
  2 = minor issues; close to acceptable
  3 = on-target; no changes needed

Rubric dimensions in detail:

brand_voice (0-3):
  - Does the copy tone match the BRIEF's tone_hints?
  - Is vocabulary appropriate for the opco_context (G42 / M42 / Core42 / Inception)?
  - Any forbidden words (sensationalism, jargon misuse, over-promising)?
  - Is the headline concise and memorable?

visual_spec (0-3):
  - Is the visual concept aligned with G42's modern, technology-forward visual language?
  - Is the palette appropriate (no gimmicky or off-brand colors)?
  - Is the composition clean and readable?
  - For healthcare audiences: zero tolerance for distress imagery, needles, blood, etc.

audience_fit (0-3):
  - Does the register match the stated audience?
  - For healthcare professionals: trustworthy, evidence-aware, non-sensational?
  - For executives: confident, concise, outcome-oriented?
  - For the public: clear, accessible, non-jargony?

Rules:
- The "total" field MUST equal the sum of the three scores.
- The "verdict" field MUST be:
    "pass" if total >= 7,
    "revise" if total < 7 (first attempt allowed),
    "escalate" only if explicitly told this is a re-scoring after a prior revision (in which case still mark "revise" technically wrong — see below)
- The "fix" field MUST be empty if total >= 7. If total < 7, provide ONE specific, actionable fix targeting the lowest-scoring dimension.
- Output ONLY the JSON."""


def run_validator(brief: dict, draft: dict, is_revision: bool = False) -> dict:
    """
    Run the Validator (Critic) on a draft from the Brush agent.

    Args:
        brief: The structured BRIEF from the Intake agent.
        draft: The DRAFT from the Brush agent.
        is_revision: True if this is the re-score after one revision attempt.

    Returns:
        A verdict dict matching the schema in VALIDATOR_SYSTEM_PROMPT.
        On parse failure, returns a dict with "error" populated.
    """
    logger.info(f"VALIDATOR_START | is_revision={is_revision} | threshold={PASS_THRESHOLD}/9")

    user_message = (
        f"Original BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"DRAFT to evaluate:\n{json.dumps(draft, indent=2)}\n\n"
        f"Is this a re-score after revision? {is_revision}\n\n"
        "Score this DRAFT against the rubric and return the JSON verdict."
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,  # low temp for consistent scoring
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        verdict = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None

        # Enforce verdict logic locally (don't trust the model to do its own arithmetic)
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
            # Already revised once and still failing -> escalate to human
            verdict["verdict"] = "escalate"
        else:
            verdict["verdict"] = "revise"

        logger.info(
            f"VALIDATOR_DONE | tokens={tokens_used} | "
            f"total={computed_total}/9 | verdict={verdict['verdict']} | "
            f"scores=voice:{scores.get('brand_voice')},visual:{scores.get('visual_spec')},audience:{scores.get('audience_fit')}"
        )
        return verdict

    except json.JSONDecodeError as exc:
        logger.error(f"VALIDATOR_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "validator_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"VALIDATOR_API_FAIL | error={exc!s}")
        return {"error": "validator_api_failure", "detail": str(exc)}


def run_brush_revision(brief: dict, original_draft: dict, fix_instruction: str) -> dict:
    """
    Ask the Brush agent to revise its draft based on the Validator's specific fix.

    This is a thin wrapper around Brush that injects the fix instruction into the
    user message. We keep it here (rather than in brush_agent.py) because the
    revision behaviour is a Validator-driven pattern, not a Brush primitive.
    """
    from app.brush_agent import run_brush, BRUSH_SYSTEM_PROMPT, _client as brush_client

    logger.info(f"REVISION_START | fix_preview={fix_instruction[:100]!r}")

    user_message = (
        "Here is a previous DRAFT you produced, the original BRIEF, and the Validator's "
        "specific fix instruction. Produce a REVISED DRAFT JSON (same schema as before) "
        "that addresses the fix while preserving everything else that was working.\n\n"
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
            temperature=0.5,  # slightly lower than initial draft, for more targeted change
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
