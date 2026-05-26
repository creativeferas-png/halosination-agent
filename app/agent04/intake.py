"""
HALO Agent 04 (Social) — Profile Intake

Role: Parse an employee profile, self-introduction blurb, or about-me update
into a structured PROFILE object that downstream agents can reason over.

Pattern: Same agentic spine as Agents 01/02/03 — structured-extraction from
messy human text, low temperature for consistency, JSON response format.

Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent04.intake")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

INTAKE_SYSTEM_PROMPT = """You are the Profile Intake agent for HALO, an internal employee platform.

You receive an employee's profile blurb, self-introduction, or about-me text.
Your job is to extract a STRUCTURED PROFILE OBJECT — never to summarise or invent.
Preserve what was said as faithfully as possible. Downstream agents (Search,
Brush, Validator) will produce the suggestions — but only with clean structured data.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "name": "the person's name if stated, else null",
  "role": "their stated role / title, or null",
  "opco_or_team": "the OpCo, business unit, or team they belong to, or null",
  "location": "city / country if stated, else null",
  "tenure": "how long they've been at the company, if stated, else null",
  "expertise_areas": ["array of professional expertise areas mentioned"],
  "current_projects": ["array of current projects or workstreams mentioned"],
  "interests_professional": ["array of professional interests / topics they want to learn or discuss"],
  "interests_personal": ["array of stated personal interests (hobbies, sports, etc.) — only if explicitly mentioned"],
  "goals_stated": ["array of explicit goals (e.g., 'looking to learn ML', 'want to find a mentor in regulatory affairs')"],
  "languages": ["array of spoken languages mentioned, e.g. 'English', 'Arabic'"],
  "career_stage": "early-career / mid-career / senior / executive / unclear",
  "social_context_signals": {
    "new_to_company": false,
    "recently_relocated": false,
    "isolation_or_loneliness_signal": false,
    "post_team_change": false,
    "active_conflict_mentioned": false
  },
  "sensitive_attributes_detected": [
    "any sensitive attributes the profile reveals (e.g., 'medical condition', 'religion', 'family situation') — listed but NOT used downstream for suggestions"
  ],
  "conflict_signals": [
    "any signals of role conflicts to be aware of (e.g., 'is a manager of X', 'is reviewing Y')"
  ],
  "open_questions": [
    "things Intake is unsure about - e.g., 'role unclear', 'no team named', 'tenure not given'"
  ]
}

Rules of engagement:
- DO NOT invent expertise, interests, projects, or goals not stated in the source.
- DO distinguish professional interests (career-relevant) from personal interests (hobbies) — they have different suggestion implications.
- DO populate social_context_signals based on what the source actually says (e.g., 'just moved to Abu Dhabi' -> recently_relocated=true; 'I miss my old team' -> post_team_change=true).
- DO flag isolation_or_loneliness_signal=true ONLY if the source contains explicit signals (e.g., 'feeling disconnected', 'no one to talk to', 'lonely'). Do not infer it from neutral statements.
- DO list sensitive_attributes_detected if any are present (medical, religious, family, etc.) so downstream agents know to AVOID using them for suggestions.
- DO list conflict_signals if the profile mentions reporting relationships, reviews, or HR processes.
- Output ONLY the JSON. No prose before or after."""


def run_intake(profile_text: str) -> dict:
    """
    Parse a raw employee profile blurb into a structured PROFILE object.

    Args:
        profile_text: Raw text of the profile / self-introduction.

    Returns:
        Structured PROFILE dict matching the schema above.
        On parse failure, returns {"error": ..., "raw": ...}.
    """
    preview = profile_text[:120].replace("\n", " ")
    logger.info(f"INTAKE_START | preview={preview!r}")

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Employee profile:\n\n{profile_text}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        profile = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None

        name = profile.get("name") or "<unnamed>"
        expertise_count = len(profile.get("expertise_areas") or [])
        interests_count = len(profile.get("interests_professional") or [])
        social_signals = profile.get("social_context_signals", {})
        any_social_signal = any(social_signals.values()) if social_signals else False
        sensitive = profile.get("sensitive_attributes_detected") or []
        conflicts = profile.get("conflict_signals") or []

        logger.info(
            f"INTAKE_DONE | tokens={tokens_used} | name={name!r} | "
            f"expertise={expertise_count} | interests={interests_count} | "
            f"social_signal={any_social_signal} | sensitive={len(sensitive)} | conflicts={len(conflicts)}"
        )
        return profile

    except json.JSONDecodeError as exc:
        logger.error(f"INTAKE_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "intake_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"INTAKE_API_FAIL | error={exc!s}")
        return {"error": "intake_api_failure", "detail": str(exc)}
