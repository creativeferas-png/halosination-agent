"""HALO dashboard illustrative data - CLEARLY SYNTHETIC.

This module exists to demonstrate what a populated HR/HC dashboard would look
like at organisational scale. The numbers here are MADE UP for illustration.
The aggregator module (app/aggregator.py) is the only source of real signals;
this module is never confused with that.

Includes one team deliberately below the N>=5 threshold so the safeguard's
"Not enough check-ins yet" tile is demonstrated in the UI.
"""

MIN_RESPONSES_THRESHOLD = 5

ILLUSTRATIVE_TEAMS = [
    {
        "team_name": "Cardiology Analytics",
        "team_size": 24,
        "responses_this_period": 18,
        "period_label": "Last 30 days",
        "signals": {
            "wellness": {"general_wellbeing": 9, "elevated_concern": 7, "crisis_signal": 2},
            "isolation_signals": 4,
            "active_tasks_avg_per_person": 6.2,
            "restricted_distribution_count": 3,
        },
        "trend_vs_previous": {
            "elevated_concern_change_pct": 40,
            "meeting_load_change_pct": 28,
            "direction_summary": "elevated_concern signals up; meeting load up",
        },
    },
    {
        "team_name": "Platform Engineering",
        "team_size": 42,
        "responses_this_period": 31,
        "period_label": "Last 30 days",
        "signals": {
            "wellness": {"general_wellbeing": 22, "elevated_concern": 8, "crisis_signal": 1},
            "isolation_signals": 2,
            "active_tasks_avg_per_person": 4.1,
            "restricted_distribution_count": 1,
        },
        "trend_vs_previous": {
            "elevated_concern_change_pct": -12,
            "meeting_load_change_pct": -5,
            "direction_summary": "stable to slightly improving",
        },
    },
    {
        "team_name": "Regulatory Affairs",
        "team_size": 6,
        "responses_this_period": 3,
        "period_label": "Last 30 days",
        "signals": None,
        "trend_vs_previous": None,
        "below_threshold_reason": "Only 3 check-ins this period; minimum {} required before any team-level signals are shown. This protects individual confidentiality.".format(MIN_RESPONSES_THRESHOLD),
    },
]


SUGGESTED_INTERVENTIONS = [
    {
        "for_team": "Cardiology Analytics",
        "suggestion": "Elevated_concern signals are up 40% with meeting load up 28%. Consider a team recovery week, an EAP awareness reminder, and reviewing whether the current cardiology programme deadlines are sustainable.",
        "evidence_basis": "Aggregate signals only (18 responses across 24 people). No individual data is referenced.",
    },
    {
        "for_team": "Platform Engineering",
        "suggestion": "Trends stable; no team-level intervention indicated. Continue regular cadence.",
        "evidence_basis": "Aggregate signals (31 responses across 42 people).",
    },
]


def get_illustrative_view():
    """Return the illustrative dashboard payload, with the synthetic-data flag prominent."""
    return {
        "is_illustrative_data": True,
        "data_source_note": "These numbers are SYNTHETIC, included to demonstrate how a populated dashboard would look at organisational scale. The 'real signals' section above is the only source of actual data.",
        "threshold_setting": MIN_RESPONSES_THRESHOLD,
        "teams": ILLUSTRATIVE_TEAMS,
        "interventions": SUGGESTED_INTERVENTIONS,
    }
