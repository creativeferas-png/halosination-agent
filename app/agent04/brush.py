"""HALO Agent 04 (Social) - Brush (Suggestion Drafter)

Role: Takes the structured PROFILE object from Intake + retrieved social-policy
rules from Search, and drafts polished, policy-compliant connection suggestions.

Pattern: Proposer half of the Proposer/Critic pairing.
Model: GPT-5.1 via Compass.
"""
import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger("halo.agent04.brush")

_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

BRUSH_SYSTEM_PROMPT = """You are the Suggestion Drafter (Brush) agent for HALO Agent 04 (Social).

You draft polished, policy-compliant connection and group suggestions from
a structured PROFILE object.

You receive:
1. A structured PROFILE object (JSON) from the Intake agent.
2. RETRIEVED POLICY RULES - the top-K most relevant rules pulled by the Search
   agent from the social-policy guidelines. These are authoritative.

NOTE: You do NOT have access to a real employee directory. INVENT plausible
illustrative suggestions (named people, group names, channels) that fit the
profile's stated expertise/interests/goals - but make clear in each suggestion
that they are illustrative examples a real connector tool would resolve against
the actual M42 employee directory.

Output STRICT JSON ONLY. Schema:

{
  "summary_60s": "Short suggestion-set readable in 60 seconds. 2-4 sentences.",
  "metadata": {
    "name": "the person's name or null",
    "role": "their role",
    "career_stage": "career stage as captured",
    "for_employee_only": true or false
  },
  "people_suggestions": [
    {
      "suggestion_type": "peer | cross_opco_collaborator | mentor | mentee | horizon_broadener",
      "illustrative_name": "An invented illustrative name - make clear it is illustrative",
      "illustrative_role": "Their plausible role e.g. Director of Regulatory Affairs at G42 Health",
      "relevance_rationale": "ONE sentence naming the concrete overlap (Rule 2)",
      "why_now": "Timely reason this connection makes sense NOW, or null",
      "power_dynamics_note": "If mentor/mentee, name the dynamic and value to both sides (Rule 7), else null",
      "basis": "professional | mixed | personal - must NOT be sensitive (Rule 4)"
    }
  ],
  "group_suggestions": [
    {
      "channel_or_group_name": "An invented illustrative channel name",
      "what_it_does": "One sentence describing the group's purpose",
      "why_this_employee_fits": "One sentence on why this profile specifically benefits (Rule 6)",
      "frequency_or_cadence": "How often the group meets/posts, or null"
    }
  ],
  "diversity_note": "One sentence explaining how the suggestion set spans different connection types (Rule 3)",
  "wellbeing_note": "If Rule 9 fires, a CARE-APPROPRIATE one-sentence note recommending HR/manager check-in support. Else null.",
  "conflicts_excluded": [
    "If conflict signals detected, list excluded suggestion types (Rule 8). Else empty array."
  ],
  "distribution": "wide | restricted",
  "distribution_reason": "If Rule 9 fired or sensitive context present, explain why distribution is restricted. Else null.",
  "rationale": "2-3 sentences citing which RETRIEVED RULES (by rule_id) most informed each decision."
}

Rules of engagement:
- Aim for 3-5 people_suggestions and 1-3 group_suggestions (Rule 10).
- EVERY people_suggestion MUST have relevance_rationale (Rule 2).
- The suggestion set MUST span at least 3 different suggestion_types (Rule 3).
- NEVER base on sensitive attributes (Rule 4). basis must always be professional or mixed.
- If conflict_signals were detected, EXCLUDE conflicted suggestions and explain in conflicts_excluded (Rule 8).
- If isolation_or_loneliness_signal is true, set distribution=restricted and populate wellbeing_note (Rule 9).
- Mentor/mentee suggestions MUST have power_dynamics_note (Rule 7).
- If a why_now reason is genuine, include it (Rule 5).
- Cite rule_ids in rationale.
- Output ONLY the JSON."""


def _format_rules_for_prompt(retrieved_rules):
    if not retrieved_rules:
        return "(no rules retrieved)"
    lines = []
    for r in retrieved_rules:
        sim = r.get("similarity")
        sim_str = " (similarity: {:.3f})".format(sim) if sim is not None else ""
        lines.append("### Rule {} - {}{}\n{}".format(r["rule_id"], r["title"], sim_str, r["text"]))
    return "\n\n".join(lines)


def run_brush(profile, retrieved_rules=None):
    """Draft polished connection suggestions from a structured PROFILE object."""
    retrieved_rules = retrieved_rules or []
    name = profile.get("name", "<unnamed>")
    expertise_count = len(profile.get("expertise_areas") or [])
    rules_count = len(retrieved_rules)
    logger.info("BRUSH_START | name={!r} | expertise={} | rules_provided={}".format(name, expertise_count, rules_count))

    rules_block = _format_rules_for_prompt(retrieved_rules)

    user_message = (
        "RETRIEVED POLICY RULES (authoritative):\n"
        + rules_block
        + "\n\nPROFILE object from Intake:\n"
        + json.dumps(profile, indent=2)
        + "\n\nProduce the SUGGESTIONS JSON per the schema. Cite rule_ids in rationale."
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-5.1",
            messages=[
                {"role": "system", "content": BRUSH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw_output = response.choices[0].message.content
        suggestions = json.loads(raw_output)
        tokens_used = response.usage.total_tokens if response.usage else None
        people_count = len(suggestions.get("people_suggestions") or [])
        groups_count = len(suggestions.get("group_suggestions") or [])
        distribution = suggestions.get("distribution", "wide")
        wellbeing = suggestions.get("wellbeing_note") is not None
        logger.info("BRUSH_DONE | tokens={} | people={} | groups={} | distribution={} | wellbeing_note={}".format(
            tokens_used, people_count, groups_count, distribution, wellbeing))
        return suggestions

    except json.JSONDecodeError as exc:
        logger.error("BRUSH_PARSE_FAIL | error={}".format(exc))
        return {"error": "brush_parse_failure", "raw": raw_output}
    except Exception as exc:
        logger.error("BRUSH_API_FAIL | error={}".format(exc))
        return {"error": "brush_api_failure", "detail": str(exc)}
