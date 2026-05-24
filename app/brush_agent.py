"""
HALOsination — Brush Agent

Role: Takes a structured BRIEF from the Intake agent and drafts the actual
asset content — copy (headline, body, CTA) and a visual spec (description,
mood, palette). Output is structured JSON so the Validator agent can score
each dimension.

Pattern: This is the "Proposer" half of the Propose <-> Critic pairing
that Sam introduced on the May 21 check-in. The Validator (Phase 4) is
the Critic that scores this output and may trigger one revision.

Model: GPT-5.1 via Compass (stronger creative reasoning).
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.brush")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

BRUSH_SYSTEM_PROMPT = """You are the Brush agent for HALOsination, an internal G42 brand
and creative agent. You draft on-brand assets for G42 employees.

You receive a structured BRIEF (JSON) from the Intake agent. Your output is a structured
DRAFT (JSON) that downstream agents (Validator, Route) can work with.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "copy": {
    "headline": "the main attention-grabbing line, 10 words or fewer",
    "subhead": "supporting line, 20 words or fewer, or null",
    "body": "the main message body, 50 words or fewer",
    "cta": "call-to-action phrase, 6 words or fewer, or null"
  },
  "visual_spec": {
    "concept": "one-sentence description of what the image depicts",
    "mood": ["array of 2-4 mood descriptors aligned with the brief's tone_hints"],
    "palette": ["array of 3-5 color names or hex codes appropriate for the brand and audience"],
    "composition": "brief layout guidance (e.g., 'hero image left, copy right, ample whitespace')",
    "must_include": ["array of mandatory visual elements (logos, icons, etc.) inferred from the brief, or empty array"],
    "must_avoid": ["array of visual choices to avoid given the audience or brand, or empty array"]
  },
  "rationale": "2-3 sentences explaining why these creative choices serve the brief's audience, opco_context, and key_message"
}

Rules:
- Stay strictly inside the BRIEF. Do not invent products, claims, or facts not present.
- If the BRIEF has open_questions, work around them with safe defaults and flag any forced assumptions in the rationale.
- Tone must match the BRIEF's tone_hints exactly.
- For healthcare audiences: avoid sensationalism, avoid imagery of patients in distress, use professional and trustworthy language.
- For G42 / M42 / Core42 / Inception: respect the parent G42 visual language (modern, technology-forward, restrained).
- Output ONLY the JSON. No prose before or after."""


def run_brush(brief: dict) -> dict:
    """
    Run the Brush agent on a structured BRIEF from the Intake agent.

    Args:
        brief: The structured BRIEF dict from run_intake().

    Returns:
        A structured DRAFT dict matching the schema in BRUSH_SYSTEM_PROMPT.
        On parse failure, returns a dict with "error" populated.
    """
    asset_type = brief.get("asset_type", "unknown")
    audience = brief.get("audience", "unknown")
    logger.info(f"BRUSH_START | asset_type={asset_type} | audience={audience!r}")

    user_message = (
        "Here is the structured BRIEF from the Intake agent. "
        "Produce the DRAFT JSON per the schema you were given.\n\n"
        f"BRIEF:\n{json.dumps(brief, indent=2)}"
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": BRUSH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        draft = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None
        headline = draft.get("copy", {}).get("headline", "")
        logger.info(
            f"BRUSH_DONE | tokens={tokens_used} | "
            f"headline={headline[:60]!r} | "
            f"mood={draft.get('visual_spec', {}).get('mood')}"
        )
        return draft

    except json.JSONDecodeError as exc:
        logger.error(f"BRUSH_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "brush_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"BRUSH_API_FAIL | error={exc!s}")
        return {"error": "brush_api_failure", "detail": str(exc)}
