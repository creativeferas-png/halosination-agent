"""
HALOsination — Intake Agent

Role: Takes a raw, plain-language employee request and turns it into
a structured BRIEF that downstream agents (Brush, Validator) can use.

Pattern: This is the "Context-Packer" half of the Pack ↔ Act pairing.
It condenses messy input into BRIEF | CITES | RISKS | OPEN_QS.

Model: GPT-4.1 via Compass (good reasoning, cheap, fast).
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.intake")

# Compass client — uses OPENAI_API_KEY and OPENAI_BASE_URL from .env
_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

INTAKE_SYSTEM_PROMPT = """You are the Intake agent for HALOsination, an internal G42 brand
& creative agent. Your only job is to turn a messy employee request into a structured BRIEF.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "asset_type": "banner | social_post | announcement | memo | slide | other",
  "project": "name of the project or initiative, or null",
  "audience": "who the asset is for",
  "deadline": "when the asset is needed, or null",
  "tone_hints": ["array of tone descriptors inferred from the request"],
  "format": "image | text | mixed | unknown",
  "opco_context": "G42 / Core42 / Inception / M42 / Mubadala Health / unknown",
  "key_message": "the single most important thing the asset must communicate",
  "open_questions": ["array of questions needed to produce a high-quality asset"],
  "risks": ["array of brand or audience risks to flag"]
}

Rules:
- If a field is genuinely unknown, set it to null (or empty array for list fields).
- Do NOT invent specifics. Better to flag in open_questions than to hallucinate.
- The key_message must be one short sentence the requester would agree with.
- Output ONLY the JSON. No prose before or after."""


def run_intake(employee_request: str) -> dict:
    """
    Run the Intake agent on a raw employee request.

    Args:
        employee_request: The plain-language request from a G42 employee.

    Returns:
        A structured BRIEF dict matching the schema in INTAKE_SYSTEM_PROMPT.
        On parse failure, returns a dict with "error" populated.
    """
    logger.info(f"INTAKE_START | request_preview={employee_request[:80]!r}")

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                {"role": "user", "content": employee_request},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        brief = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None
        logger.info(
            f"INTAKE_DONE | tokens={tokens_used} | "
            f"asset_type={brief.get('asset_type')} | "
            f"audience={brief.get('audience')} | "
            f"open_qs={len(brief.get('open_questions', []))}"
        )
        return brief

    except json.JSONDecodeError as exc:
        logger.error(f"INTAKE_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "intake_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"INTAKE_API_FAIL | error={exc!s}")
        return {"error": "intake_api_failure", "detail": str(exc)}
