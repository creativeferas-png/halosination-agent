"""
HALOsination — Brush Agent

Role: Takes a structured BRIEF from Intake plus retrieved brand rules from
Search, and drafts the actual asset content — copy (headline, body, CTA)
and a visual spec.

Pattern: This is the "Proposer" half of the Propose <-> Critic pairing.
Phase 5: Now accepts retrieved_rules from Search so drafts are grounded
in actual brand rules, not just GPT priors.

Model: GPT-5.1 via Compass.
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

You receive:
1. A structured BRIEF (JSON) from the Intake agent.
2. RETRIEVED BRAND RULES — the top-K most relevant brand rules pulled by the
   Search agent from the G42 brand guidelines. These are authoritative.
   Treat them as hard constraints, not suggestions.

Your output is a structured DRAFT (JSON) for downstream agents.

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
  "rationale": "2-3 sentences explaining why these creative choices serve the brief AND cite which RETRIEVED RULES (by rule_id) most informed each major decision."
}

Rules of engagement:
- The RETRIEVED RULES are authoritative. If the BRIEF asks for something the
  retrieved rules forbid, you MUST follow the rules — and note the conflict
  in the rationale. Do NOT comply with off-brand requests.
- Stay strictly inside the BRIEF. Do not invent products, claims, or facts.
- If the BRIEF has open_questions, work around them with safe defaults and
  flag forced assumptions in the rationale.
- For healthcare audiences: extra care. See retrieved rules.
- Output ONLY the JSON. No prose before or after."""


def _format_rules_for_prompt(retrieved_rules: list[dict]) -> str:
    """Format retrieved rules into a readable block for the LLM."""
    if not retrieved_rules:
        return "(no rules retrieved — proceed using your priors but flag in rationale)"
    lines = []
    for r in retrieved_rules:
        sim = r.get("similarity")
        sim_str = f" (similarity: {sim:.3f})" if sim is not None else ""
        lines.append(f"### Rule {r['rule_id']} — {r['title']}{sim_str}\n{r['text']}")
    return "\n\n".join(lines)


def run_brush(brief: dict, retrieved_rules: list[dict] | None = None) -> dict:
    """
    Run the Brush agent on a structured BRIEF, grounded in retrieved brand rules.

    Args:
        brief: The structured BRIEF dict from run_intake().
        retrieved_rules: The top-K rules from run_search(). Optional but recommended.

    Returns:
        A structured DRAFT dict matching the schema. On parse failure,
        returns a dict with "error" populated.
    """
    retrieved_rules = retrieved_rules or []
    asset_type = brief.get("asset_type", "unknown")
    audience = brief.get("audience", "unknown")
    logger.info(
        f"BRUSH_START | asset_type={asset_type} | audience={audience!r} | "
        f"rules_provided={len(retrieved_rules)}"
    )

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED BRAND RULES (authoritative — treat as hard constraints):\n"
        f"{rules_block}\n\n"
        "BRIEF from Intake agent:\n"
        f"{json.dumps(brief, indent=2)}\n\n"
        "Produce the DRAFT JSON per the schema. In your rationale, cite the "
        "rule_id of every retrieved rule that materially shaped a decision."
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
