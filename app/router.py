"""HALO Router - the unified front door.

Takes a free-form request (what the user typed or said) and decides which of the
five HALO agents should handle it. Returns the agent key, confidence, and a short
human-readable reason (good for showing the user "routing to Wellness because...").

SAFETY-CRITICAL: any signal of personal distress routes to Wellness (agent05),
even if the message also mentions work/tasks. A wellbeing check-in must NEVER be
mis-routed to a task tracker. When in doubt between wellness and anything else,
choose wellness.

Model: GPT-4.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.router")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

# Maps router output to the actual endpoints
AGENT_ENDPOINTS = {
    "agent01_brand": {"endpoint": "/run", "label": "Brand & Brief", "field": "request"},
    "agent02_productivity": {"endpoint": "/run_meeting", "label": "Productivity", "field": "transcript"},
    "agent03_task": {"endpoint": "/run_status", "label": "Task & KPI", "field": "status_text"},
    "agent04_social": {"endpoint": "/run_social", "label": "Social", "field": "profile_text"},
    "agent05_wellness": {"endpoint": "/run_wellness", "label": "Wellness", "field": "checkin_text"},
}

ROUTER_SYSTEM_PROMPT = """You are the Router for HALO, an AI employee platform with five specialist agents.
Your job: read the user's request and decide which ONE agent should handle it.

The five agents:
- agent01_brand: Creating on-brand content, marketing assets, copy, briefs, launch banners, posts, brand-voice writing.
- agent02_productivity: Summarising meetings, transcripts, brainstorms; turning messy notes into structured summaries and action items.
- agent03_task: Structuring status updates, project progress, KPI reporting, standup notes into clear trackable form.
- agent04_social: Employee connection - suggesting people to meet, mentors, groups, networking, "who should I talk to".
- agent05_wellness: Personal wellbeing check-ins - how the person is feeling, stress, exhaustion, struggling, low mood, or any personal distress.

OVERRIDING SAFETY RULE:
If the request contains ANY signal of personal distress, low mood, exhaustion, feeling overwhelmed,
hopelessness, struggling to cope, or anything about the person's emotional/mental state -- route to
agent05_wellness, EVEN IF the message also mentions work, tasks, deadlines, or projects. A wellbeing
signal always wins over a work-topic signal. When genuinely unsure whether something is a wellbeing
matter, choose agent05_wellness. Mis-routing a struggling person to a task tracker is the worst
possible error.

Output STRICT JSON ONLY (no markdown, no code fences):

{
  "agent": "one of: agent01_brand | agent02_productivity | agent03_task | agent04_social | agent05_wellness",
  "confidence": "high | medium | low",
  "reason": "ONE short sentence the user could read, explaining why this agent fits. Written warmly, e.g. 'This looks like a wellbeing check-in, so I'm routing it to the Wellness agent.'",
  "wellbeing_signal_detected": true | false,
  "alternatives": ["array of other agent keys that could plausibly fit, may be empty"]
}

Output ONLY the JSON."""


def route_request(request_text):
    """Classify a free-form request to one of the five HALO agents."""
    preview = request_text[:100].replace("\n", " ")
    logger.info("ROUTER_START | preview={!r}".format(preview))

    try:
        response = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": "User request:\n\n" + request_text},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)
        tokens = response.usage.total_tokens if response.usage else None

        agent = result.get("agent", "")
        # Safety backstop: if model flagged a wellbeing signal but didn't route to wellness, override.
        if result.get("wellbeing_signal_detected") and agent != "agent05_wellness":
            logger.warning("ROUTER_SAFETY_OVERRIDE | model_chose={} | forcing agent05_wellness".format(agent))
            result["agent"] = "agent05_wellness"
            result["reason"] = "A wellbeing signal was detected, so this is routed to the Wellness agent for a careful, supportive response."
            result["safety_override_applied"] = True
            agent = "agent05_wellness"

        meta = AGENT_ENDPOINTS.get(agent)
        if not meta:
            logger.warning("ROUTER_UNKNOWN_AGENT | agent={!r} | defaulting to agent01".format(agent))
            result["agent"] = "agent01_brand"
            meta = AGENT_ENDPOINTS["agent01_brand"]
        result["endpoint"] = meta["endpoint"]
        result["agent_label"] = meta["label"]
        result["input_field"] = meta["field"]

        logger.info("ROUTER_DONE | tokens={} | agent={} | confidence={} | wellbeing_signal={} | override={}".format(
            tokens, result["agent"], result.get("confidence"),
            result.get("wellbeing_signal_detected"), result.get("safety_override_applied", False)))
        return result

    except json.JSONDecodeError as exc:
        logger.error("ROUTER_PARSE_FAIL | error={}".format(exc))
        return {"error": "router_parse_failure", "raw": raw}
    except Exception as exc:
        logger.error("ROUTER_API_FAIL | error={}".format(exc))
        return {"error": "router_api_failure", "detail": str(exc)}
