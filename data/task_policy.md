# HALO Agent 03 — Task & KPI Policy (Reference)

> Public-domain placeholder used by HALO Agent 03 (Task & KPI) for
> retrieval-grounded status-update structuring and scoring. Not a confidential
> or proprietary document. Modelled on common PMO / OKR / SMART-goal standards.

## Rule 1 — Tasks must be SMART
Every task captured from a status update must be: Specific (concrete deliverable,
not a theme), Measurable (a way to know it's done), Achievable (within scope),
Relevant (tied to a stated goal or KPI), and Time-bound (explicit deadline).
A task that fails any of these dimensions must be flagged as 'task draft —
needs SMART-ing' rather than silently passed through as if complete.

## Rule 2 — KPI deltas need direction, magnitude, and timeframe
Any KPI mentioned in a status update must be captured with three things: the
direction of change (up / down / flat), the magnitude (a number, percentage,
or 'unspecified'), and the timeframe of comparison ('vs last week', 'vs Q2',
'YTD'). 'NPS is up a few points' is not a complete KPI delta — it must be
surfaced as needing magnitude and timeframe specification.

## Rule 3 — Risks must name the impact, not just the threat
A risk is only useful if it describes (a) what is at risk, (b) what the
business impact is if it materialises, and (c) what the trigger or root cause
is. 'Deadline at risk' is not a risk statement — it's a worry. A risk
statement is: 'Q3 launch date at risk due to schema migration delays,
impact: ~\$200K deferred revenue.'

## Rule 4 — Owners and deadlines on every task
Every task must have a named owner (a person, not a team or function) and an
explicit deadline (a calendar date, not 'this week' or 'soon'). Tasks lacking
either must use the explicit placeholders 'UNOWNED — see open questions' or
'NO DEADLINE — see open questions' and the gap must appear in open_questions.

## Rule 5 — Distinguish blocked / at-risk / on-track
Every task must be classified into exactly one of three states: blocked
(work cannot proceed without external action), at-risk (work proceeding but
unlikely to meet deadline), or on-track (work proceeding on plan). Conflating
these creates false confidence and hides escalations.

## Rule 6 — Progress must be quantified, not narrated
Status updates often say things like 'made good progress' or 'about 60% done'.
The structured output must extract progress as a number (percent complete,
units shipped, milestones hit) wherever possible. If a quantification is
asserted but not supported (like '60% done' with no breakdown), it must be
flagged as 'progress — self-reported, unverified.'

## Rule 7 — Dependencies must be surfaced
If a task depends on another team, decision, or external event, the dependency
must be surfaced as a structured field on the task ('blocked_by' or
'waiting_on'). Hidden dependencies are the most common cause of missed
deadlines.

## Rule 8 — Recommendations require rationale
If the system produces a recommendation (escalate / reassign / re-scope / hold
review), the recommendation must include a one-sentence rationale tied to a
specific risk or rule. Recommendations without rationale are advice; with
rationale they are accountable judgement calls.

## Rule 9 — Sensitive performance signals get flagged
If a status update implies individual performance concerns (chronic missed
deadlines by named individuals, team conflicts, capability gaps), the output
must flag this for HR-aware handling and restrict the distribution of the
notes. People-performance signals must never appear in widely-distributed
status reports without an HR review step.

## Rule 10 — Status digests must be readable in 90 seconds
The top-level digest of a status update must be readable in under 90 seconds.
A senior reader should walk away knowing: what shipped, what slipped, what's
at risk, what's the single most important next decision. Detail can follow
underneath, but the digest must be self-contained.
