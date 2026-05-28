"""HALO Agent 05 (Wellness) - Check-in Intake

Role: Parse a self check-in / wellness-share into a structured CHECKIN object.
Critically: classify severity (general_wellbeing / elevated_concern / crisis_signal)
without diagnosing the person or labelling their experience.

Pattern: Same agentic spine as Agents 01/02/03/04.
Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent05.intake")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

INTAKE_SYSTEM_PROMPT = """You are the Check-in Intake agent for HALO Agent 05 (Wellness).

You receive a self check-in from an employee about how they are doing. Your job is
to extract a STRUCTURED CHECKIN OBJECT — faithfully, without diagnosing or labelling.

CRITICAL DISCIPLINE:
- You are NOT a clinician. Do not diagnose. Do not label.
- Reflect what the person said using their own words where possible.
- Classify severity correctly. Under-classifying a crisis is the most dangerous failure.

Output STRICT JSON ONLY (no markdown, no commentary, no code fences). Schema:

{
  "name": "the person's name if stated, else null",
  "tone_signals": ["array of emotional registers detected in the check-in — e.g., 'matter-of-fact', 'vulnerable', 'tired', 'overwhelmed', 'hopeful'"],
  "themes_mentioned": ["array of life domains the person mentioned — e.g., 'work stress', 'sleep', 'relationships', 'physical health', 'isolation'"],
  "person_own_phrases": ["array of distinctive phrases from the person's own words that capture their experience"],
  "severity": "general_wellbeing | elevated_concern | crisis_signal",
  "severity_rationale": "one sentence explaining the classification — citing specific phrases from the check-in",
  "crisis_indicators": ["array of any specific crisis signals detected: 'self-harm mention', 'suicidal ideation', 'harming others', 'immediate danger', 'severe acute distress'. Empty array if none."],
  "duration_signals": "any signal of how long this has been going — 'a few days', 'months', 'always', or null",
  "support_signals_mentioned": ["array of supports the person already mentioned — 'my partner', 'therapy', 'manager', 'friends', etc."],
  "request_signals": ["array of what the person is asking for — 'just to vent', 'advice', 'resources', 'someone to talk to', or empty if they didn't say"],
  "sensitive_topics_detected": ["array of any sensitive topics raised — 'finances', 'family conflict', 'health diagnosis', 'workplace conflict', 'bereavement'. Don't expand on these, just flag them."],
  "open_questions_for_brush": ["things downstream Brush should be aware of — e.g., 'duration unclear', 'no specific support mentioned', 'multiple stressors interacting'"]
}

SEVERITY CLASSIFICATION GUIDE:
- crisis_signal: ANY mention of self-harm, suicidal ideation, harming others, immediate danger, or severe acute distress that requires same-day intervention. When in doubt between elevated_concern and crisis_signal, choose crisis_signal — it triggers safer routing.
- elevated_concern: persistent low mood, significant stress, relationship/work struggles affecting function, hopelessness without self-harm mention, prolonged exhaustion, signs the person may not cope without support.
- general_wellbeing: everyday stress, fatigue, sprint pressure, mild overwhelm, life-balance reflections — normal range of human ups and downs.

Rules of engagement:
- DO NOT diagnose. No 'sounds like anxiety/depression/burnout'.
- DO NOT label the person. No 'you are X', no 'this is X disorder'.
- DO use the person's own words back to them in person_own_phrases.
- DO flag sensitive_topics_detected without expanding on them.
- DO err on the side of higher severity if signals are ambiguous around crisis.
- Output ONLY the JSON. No prose before or after."""


def run_intake(checkin_text):
    """Parse a wellness check-in into a structured CHECKIN object."""
    preview = checkin_text[:120].replace("\n", " ")
    logger.info("INTAKE_START | preview={!r}".format(preview))

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                {"role": "user", "content": "Wellness check-in:\n\n" + checkin_text},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        checkin = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None

        severity = checkin.get("severity", "unknown")
        crisis_count = len(checkin.get("crisis_indicators") or [])
        themes_count = len(checkin.get("themes_mentioned") or [])
        name = checkin.get("name") or "<anonymous>"

        logger.info(
            "INTAKE_DONE | tokens={} | name={!r} | severity={} | crisis_indicators={} | themes={}".format(
                tokens_used, name, severity, crisis_count, themes_count)
        )
        return checkin

    except json.JSONDecodeError as exc:
        logger.error("INTAKE_PARSE_FAIL | error={}".format(exc))
        return {"error": "intake_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error("INTAKE_API_FAIL | error={}".format(exc))
        return {"error": "intake_api_failure", "detail": str(exc)}
