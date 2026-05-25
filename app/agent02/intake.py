"""
HALO Agent 02 (Productivity) — Meeting Intake

Role: Parse a raw meeting transcript or notes into a structured Meeting object
that downstream agents (Search, Brush, Validator) can reason over.

Pattern: Same agentic spine as Agent 01's intake — structured-extraction from
messy human text, low temperature for consistency, JSON response format.

Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent02.intake")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

INTAKE_SYSTEM_PROMPT = """You are the Meeting Intake agent for HALO, an internal employee platform.

You receive a raw meeting transcript, notes, or dictated summary. Your job is to
extract a STRUCTURED MEETING OBJECT — never to summarise, polish, or invent.
Preserve what was said as faithfully as possible. Downstream agents (Search, Brush,
Validator) will do the polishing — but only if you give them clean structured data.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "title": "concise meeting title inferred from content, or null",
  "date": "ISO date YYYY-MM-DD if explicitly mentioned, else null",
  "attendees": ["array of named attendees if mentioned, else empty array"],
  "purpose": "one-sentence statement of why the meeting was held, or null",
  "raw_discussion": "2-4 sentences summarising what was discussed (faithful, not opinionated)",
  "raw_decisions": [
    {
      "decision": "the decision made",
      "rationale": "the stated reason, or null if not given"
    }
  ],
  "raw_action_items": [
    {
      "description": "the action",
      "owner_mentioned": "who was named as owner, or null",
      "deadline_mentioned": "any deadline phrasing as it was said, or null"
    }
  ],
  "raw_open_questions": ["questions raised but not answered in the meeting"],
  "raw_risks_or_blockers": ["risks, blockers, or concerns flagged"],
  "follow_ups_mentioned": ["any 'we will follow up on...' phrases"],
  "sensitive_topics_flagged": false,
  "sensitive_reason": "if flagged, why (HR, legal, regulatory, confidential...), else null",
  "open_questions": [
    "anything Intake itself is unsure about - e.g., 'attendee names not clear', 'no date given'"
  ]
}

Rules of engagement:
- DO NOT invent attendees, dates, decisions, owners, or deadlines. If unclear, use null or empty array, and surface in open_questions.
- DO NOT rephrase decisions or action items into "better" language — preserve original phrasing. Downstream Brush will polish.
- DO flag sensitive_topics_flagged=true if the transcript touches on HR, legal, regulatory, confidential, or otherwise restricted matters.
- DO surface ambiguity. If "John will handle it" but no John was introduced, that goes in open_questions.
- DO preserve vague language exactly as said — "the team will look into it soon" stays as-is, with owner_mentioned=null and deadline_mentioned="soon". The Validator will flag this against Rule 2.
- Output ONLY the JSON. No prose before or after."""


def run_intake(transcript: str) -> dict:
    """
    Parse a raw meeting transcript into a structured Meeting object.

    Args:
        transcript: Raw text of the meeting (transcript, notes, dictation).

    Returns:
        A structured Meeting dict matching the schema above.
        On parse failure, returns {"error": ..., "raw": ...}.
    """
    transcript_preview = transcript[:120].replace("\n", " ")
    logger.info(f"INTAKE_START | transcript_preview={transcript_preview!r}")

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Meeting transcript:\n\n{transcript}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        meeting = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None

        title = meeting.get("title") or "<no title>"
        attendees_count = len(meeting.get("attendees") or [])
        decisions_count = len(meeting.get("raw_decisions") or [])
        actions_count = len(meeting.get("raw_action_items") or [])
        open_qs_count = len(meeting.get("open_questions") or [])
        sensitive = meeting.get("sensitive_topics_flagged", False)

        logger.info(
            f"INTAKE_DONE | tokens={tokens_used} | "
            f"title={title!r} | attendees={attendees_count} | "
            f"decisions={decisions_count} | actions={actions_count} | "
            f"open_qs={open_qs_count} | sensitive={sensitive}"
        )
        return meeting

    except json.JSONDecodeError as exc:
        logger.error(f"INTAKE_PARSE_FAIL | error={exc} | raw={raw_output[:200]!r}")
        return {"error": "intake_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error(f"INTAKE_API_FAIL | error={exc!s}")
        return {"error": "intake_api_failure", "detail": str(exc)}
