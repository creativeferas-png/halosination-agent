# HALO — Architecture

> **G42 Agentathon submission — Use Case #13 Media Content Generation**
> **Team:** HALOsination (solo build — Feras Assil)
> **Repo:** `creativeferas-png/halosination-agent`

---

## 0. What HALO is now

**HALO** is M42's vision for a single AI platform every employee can use to work smarter, connect deeper, and live better. This submission ships **the platform**, not a single agent.

What's in the repo today:

| | What it does | Status |
|---|---|---|
| **Agent 01** — Brand & Brief | On-brand content from plain-English requests; refuses off-brand asks with rule citations | LIVE |
| **Agent 02** — Productivity | Meeting transcripts → structured summaries; surfaces open questions instead of inventing answers | LIVE |
| **Agent 03** — Task & KPI | Status updates → trackable structure; flags restricted-distribution items when sensitive content is detected | LIVE |
| **Agent 04** — Social | Employee profile → connection suggestions; excludes conflicted suggestions, restricts distribution on sensitive context | LIVE |
| **Agent 05** — Wellness | Self check-ins → care-appropriate responses; severity classification + crisis routing to real M42 resources (SAKINA, Lyra) | LIVE |
| **Router** | Free-form request → right agent, with safety bias (distress always wins over work-topic) | LIVE |
| **Execution** | Agent 01 output → real downloadable branded asset file | LIVE |
| **Aggregate dashboard** | Cross-agent signals → privacy-by-design HR/HC view (aggregate-only, N≥5 threshold, no individual identification) | LIVE |

**Three user-facing surfaces:**
- `/` — architecture-transparent tabbed UI (five agent panels, full validator scoring visible)
- `/halo` — product-feel unified chat: one screen, type what you need, HALO routes and responds
- `/dashboard-ui` — aggregate wellbeing dashboard for HR/HC

**One architectural pattern across five domains.** Every agent uses the same Intake → Search → Brush → Validator → Route spine. One generalised Search agent serves all five. This is the architecture as built — the agents differ in their policies and rubrics, the substrate is shared.

**The codename "HALOsination"** pairs the platform name with the AI failure mode the architecture specifically counters — hallucinated, off-brand, or unsafe output. The Validator agent in every domain refuses to wave through content that fails its rubric, and the most consequential cases (a crisis check-in, an active workplace conflict) are exactly where the system holds the line most carefully.

This document walks through what is built, why each design choice was made, and — equally important — what is *not* built and what real deployment of any of this would require.

---

## 1. Executive summary

HALO is a multi-agent system that lets any M42 / G42-group employee request, structure, or be supported on plain-English asks across five work and wellbeing domains — and ensures every output is verifiably on-policy before it leaves the system.

The pain point is real and operational. Across G42, M42, Core42, Inception, and Mubadala Health, every OpCo produces content, runs meetings, tracks status, makes introductions, and (quietly) carries the weight of its people every day. Marcom owns the brand source-of-truth, but cannot review every asset. Managers want to know who is at risk, but cannot read every status update. HR wants to support wellbeing, but cannot survey everyone every week. **Today, off-brand assets ship, signals get missed, and people in difficulty wait too long for support** — not because anyone is doing a bad job, but because the volume is impossible.

HALO inverts the workflow. Instead of post-hoc review, on-policy behaviour is enforced **at the point of creation** by a chain of cooperating agents that retrieve the relevant rules, draft against them, and score the draft against the same rules before delivery. Every agent's Validator issues a structured 0–9 verdict citing specific rule IDs; below 7/9 triggers one revision attempt, then human escalation.

Concretely, per agent run:

- **4 agents** backed by Compass: Intake, Search, Brush, Validator (plus a thin Route layer for delivery).
- **5 Compass calls** on average: 1 embedding (Search) + up to 4 chat completions (Intake, Brush, Validator, optional revision).
- **~5–15 seconds** end-to-end for a typical request.
- Every verdict **cites rule IDs** from a policy document — making decisions **auditable, not vibes-based**.

Plus the platform layer added on top of the five agents:

- A **Router** that takes a free-form request and dispatches it to the right agent, with a deliberate safety bias: any personal-distress signal wins over any work-topic signal.
- An **Execution layer** that turns Agent 01's structured output into a real downloadable branded asset file.
- An **Aggregate Dashboard** that reads signals across all agents and produces an HR/HC view — aggregate-only, threshold-gated at N≥5, and structurally incapable of identifying individuals.

**Business outcome.** Marcom moves from review bottleneck to standards owner. Meetings produce trackable artefacts. Status reports surface risk rather than hiding it. Employees can find people to learn from without breaching reporting-chain etiquette. People in distress are met with specific named resources in the first sentence, not buried under reflection. And HR/HC gets trend-level visibility into team wellbeing without ever seeing an individual's check-in.

---

## 2. Why this approach

### 2.1 Why a unified platform, not five separate tools

Five disconnected tools means five separate logins, five different UI conventions, five chances for an employee to give up. More importantly, signals don't flow between them — the meeting that surfaced a colleague's stress, the status update where someone wrote "I'm drowning," the wellness check-in where they finally asked for help — these stay in silos.

HALO is one platform with one front door. The unified chat surface (`/halo`) lets an employee type or speak a request in plain language. The router decides which agent handles it. The aggregate dashboard reads across all five so HR sees trends, not isolated points.

The architectural payoff: one pattern, applied five times, produces less code and more consistency than five hand-built tools. Add a sixth domain (Learning? Finance? Travel?) and the cost is one policy file, one rubric, and one thin agent module — not another codebase.

### 2.2 Why multi-agent (not a single LLM call)

A single big LLM call can do impressive things, but it cannot be **audited** and cannot **refuse cleanly**. HALO's multi-agent decomposition does three things a monolithic call cannot:

1. **Separation of concerns.** Intake extracts structure faithfully; Brush drafts; Validator scores. Each step is a smaller, more reliable LLM call than asking one model to do all of it at once.
2. **Critic loop.** The Validator scores Brush's draft against the same rules Brush had access to. Disagreement triggers one revision attempt; persistent disagreement escalates to a human. This is the architectural mechanism that prevents the most consequential failure modes — an off-brand asset shipping, an unsafe wellness response going out, a status with buried sensitive content being broadcast.
3. **Trace.** Every step logs its inputs, outputs, and the rules cited. The agent_trace returned by every endpoint is the audit log.

### 2.3 Why retrieval-augmented (RAG) policies

The Validator does not "just know" the rules — it retrieves them from a versioned policy document and cites the rule IDs in its verdict. This matters for three reasons:

1. **Auditability.** Every decision can be traced to a specific rule. Disagreements with the system's judgement become disagreements about the rule, not arguments with an opaque model.
2. **Updateability.** When a brand guideline, meeting policy, or care protocol changes, you edit a Markdown file and re-run the index builder. No retraining, no prompt rewrite.
3. **Generalisability.** The same retrieval pipeline serves five different policy documents — brand, meeting, task, social, wellness. The script that builds the policy index is the same script for all five. The Search agent is one generalised module that takes an index path and a query builder.

---

## 3. The five agents

Every agent shares the same spine. The detail below covers what each agent's policy emphasises and what its Validator scores against, plus the demo case that best illustrates what each refuses or restricts.

### 3.1 Agent 01 — Brand & Brief

**Domain.** On-brand content creation: launch banners, social posts, internal announcements, clinical communications. The codename "HALOsination" originated here — pairing the platform name with the failure mode (hallucinated, off-brand) the agent specifically counters.

**Policy.** 10 brand rules covering voice, evidence-aware claims (especially in healthcare contexts), forbidden words ("revolutionary," "crush," "dominate"), tone calibration, audience fit, and visual specification standards.

**Rubric (3×3, max 9).** Brand Voice / Visual Spec / Audience Fit.

**Demo case worth seeing.** A "punchy, crush-the-competition" pitch from a hospital CIO context. Brush refuses to use forbidden words; Validator catches any drift; the final asset reframes "crush" as a confident, evidence-aware statement. Bonus: this is the only agent with **real execution** — its output renders into an actual downloadable branded HTML asset file (see Section 4.2).

### 3.2 Agent 02 — Productivity (Meeting Notes)

**Domain.** Meeting transcripts → structured notes (decisions, action items with owners and deadlines, open questions, risks/blockers, follow-ups, distribution decision).

**Policy.** 10 rules covering owner+deadline-or-flag for every action, distinguishing decisions from action items, surfacing rather than burying ambiguity, restricting distribution when HR or contractor-sensitive topics are discussed.

**Rubric.** Completeness / Faithfulness / Ownership Clarity.

**Demo case worth seeing.** The "messy brainstorm" sample — a half-decided product roadmap meeting with mixed signals. Most summarisers paper over the mess and produce a confident-sounding summary. HALO's Agent 02 surfaces **8 open questions** explicitly, with reasoning for each. It refuses to invent owners or deadlines where the transcript doesn't establish them; instead it flags "UNOWNED — see open questions." This is the same architectural virtue as Agent 01's forbidden-word refusal — the system says no when no is correct.

### 3.3 Agent 03 — Task & KPI

**Domain.** Free-form status text → structured tracker (tasks with owner/deadline/status/progress/blocked_by, KPIs with direction, risks, recommendations, distribution decision).

**Policy.** 10 rules including the SMART check on each task (Specific, Measurable, Achievable, Relevant, Time-bound — flagged when missing), distribution restriction when HR or sensitive context surfaces, refusal to fabricate progress numbers, surfacing rather than smoothing the ambiguous status.

**Rubric.** Specificity / Measurability / Risk Awareness.

**Demo case worth seeing.** A "messy standup" sample where the speaker mentions a brewing conflict with a contractor mid-update. Agent 03 produces the structured status — but flags the contractor mention as sensitive, restricts distribution, and surfaces it as an open question rather than including it in the broadcast summary. Sensitive content does not silently propagate.

### 3.4 Agent 04 — Social

**Domain.** Employee self-introduction → connection suggestions (peers, mentors, mentees, cross-OpCo collaborators, horizon-broadeners) and group/channel recommendations.

**Policy.** 10 rules including specificity (every suggestion needs a rationale), diversity (no filter-bubble), privacy (never base suggestions on sensitive personal attributes), Rule 7 (mentor/mentee suggestions need a power-dynamics note explaining bidirectional value), Rule 8 (exclude suggestions that conflict with stated boundaries), Rule 9 (restrict distribution and add a wellbeing note when isolation/relocation/conflict signals fire).

**Rubric.** Relevance / Diversity / Privacy & Care.

**Demo case worth seeing.** The Hassan profile — a PM in active HR dispute who explicitly says "NOT Karim (my line manager), NOT anyone on my current team, NOT anyone in the chain above Karim." HALO produces 5 diverse suggestions, **explicitly excluding** Karim and the consumer-apps chain in a visible `conflicts_excluded` section. The system even coins an illustrative channel name `#product-mentors-outside-chain` whose entire purpose is connecting Hassan to people outside his reporting chain. Rule 8 doesn't just constrain the output — it shapes it into something more useful.

### 3.5 Agent 05 — Wellness

**Domain.** Self check-ins → care-appropriate supportive responses, with severity classification (general_wellbeing / elevated_concern / crisis_signal) determining the response path.

**Policy.** 10 rules grounded in workplace EAP and supportive-listening best practice. The non-negotiables: never give clinical or diagnostic advice (Rule 1); never label the person's experience (Rule 2); recognise severity and route accordingly (Rule 3); on crisis, **lead with resources** and never suggest waiting or scheduling (Rule 4); always offer at least one concrete next step (Rule 7); match the person's tone, never moralise (Rule 9); resources must be specific and current (Rule 10). **Real M42 resources are baked into Rules 4 and 10:** SAKINA (800 SAKINA / 800 725 462, Arabic or English) and Lyra EAP (24/7, code M42XLYRA, 8000 120 120), each with a "confirm against latest official M42 communication" caveat.

**Rubric.** Safety & Severity / Care Language / Actionability. The Validator caps Safety & Severity at 0 on any crisis-handling violation (resources buried, waiting suggested, diagnosis given) and lists the violation explicitly.

**Demo case worth seeing.** The "I can't cope, don't see the point" check-in. Intake correctly classifies as `crisis_signal`. Search retrieves Rule 4 as the top match. Brush's response **leads with SAKINA's number in the first sentence**, acknowledges the pain in the person's own words without minimising or amplifying, offers a concrete next step ("in the next hour, choose one option…"), and explicitly avoids diagnosis. The Validator scores 9/9 with zero safety violations. The response carries a `what_this_response_avoided` self-audit listing seven things deliberately NOT done.

**This is the agent that needs the most explicit caveat.** See Section 5.

---

## 4. The platform layer

These three capabilities sit on top of the five agents and turn HALO from "five specialist tools" into "one platform."

### 4.1 Router — the unified front door

**Endpoint:** `POST /route` — takes free-form text, returns a routing decision plus the chosen agent's full pipeline result, in one call.

**Design.** The router is a small classifier (GPT-4.1) with one overriding rule: **any signal of personal distress routes to Wellness, even when the message also mentions work or deadlines.** A backstop in the router code enforces this — if the model classifies wellbeing_signal_detected=true but routes to a non-Wellness agent, the code overrides and routes to Wellness with a logged warning.

**Why this matters.** The single most consequential routing failure would be misdirecting a struggling person to a task tracker. A naive router sees "I'm so behind on my deadlines and honestly I just can't cope anymore, some days I don't see the point in any of it" and routes to Task (keywords: behind, deadlines). HALO's router routes it to Wellness — *correctly*, and verified end-to-end in the browser, including the full crisis response with resources and HR/EAP flag.

**Tested across:** clear cases for each of the 5 agents, an ambiguous mid-case, and the work-masked-distress case. All correct.

### 4.2 Execution — the one genuinely-executing capability

**Endpoint:** `POST /render_asset` — takes Agent 01's `final_draft` output, returns a downloadable branded HTML file with `Content-Disposition: attachment`.

**Why one capability, not five.** Real execution (creating a Slack channel for Agent 04, writing tasks into a tracker for Agent 03, booking an EAP session for Agent 05) requires write-access to M42's real systems, plus access controls, plus human-in-the-loop on irreversible actions, plus security review. **None of that is a hackathon-window build.**

The file-download path was chosen deliberately because it is genuinely useful, demonstrates the principle, and needs no permissions. The renderer maps Agent 01's real schema (`copy.headline`, `copy.subhead`, `copy.body`, `copy.cta`, `visual_spec.concept`, `visual_spec.mood`, `visual_spec.palette`, `visual_spec.composition`) into a polished HTML asset that uses the agent's own palette as a gradient header. Production would render PNG/PDF via a headless browser or design API — that's a roadmap note, not a missing feature.

**End-to-end verified.** Click the download button in the unified chat after a brand request, get a 4KB HTML file titled with the headline, open it, see a real branded asset using the palette HALO chose.

### 4.3 Aggregate Dashboard — the 6th capability

**Endpoint:** `GET /dashboard` — returns two clearly-separated sections: **real signals** aggregated from this demo's saved agent outputs, and an **illustrative populated view** clearly labelled as synthetic so a viewer can see what the dashboard would look like at organisational scale.

**Three design commitments encoded in the architecture, not just in the doc:**

1. **Aggregate-only.** The aggregator module (`app/aggregator.py`) extracts signals only — counts and flags — from saved agent outputs. It is structurally incapable of producing individual identification: it does not store or surface names, content, or any field traceable to a specific person. The function names tell the story: `extract_signals_agent02`, `extract_signals_agent03`, etc., each returning counts only.
2. **Threshold-gated at N≥5.** Team-level signals are displayed only when at least 5 people have contributed responses in the period. Below threshold, the dashboard renders a visible "Team-level signals hidden" tile explaining why. The illustrative Regulatory Affairs team (3 responses, 6 people) demonstrates this safeguard firing on screen — the safeguard is not theoretical, you can see it blocking a tile.
3. **No manager-of-own-team view.** Deliberately not built. That framing edges toward surveillance and would directly contradict the Wellness agent's promise of "this check-in is restricted to you." The dashboard is an HR/HC trend view only.

**The framing for HR.** Trends and suggested interventions per team, with the evidence-basis always footnoted ("Aggregate signals only — 18 responses across 24 people. No individual data is referenced."). The aim is **earlier care decisions at the team level**, not earlier scrutiny at the individual level.

---

## 5. Safety and ethics — what we did and didn't claim

This is the section that distinguishes a careful submission from an overclaimed one. Read it slowly.

### 5.1 Agent 05 is a demo artifact, not a deployable wellness tool

The crisis-handling path in Agent 05 works correctly in the demo. It classifies severity correctly, retrieves the right rule, leads with real M42 resources, scores 9/9 with zero safety violations.

**None of that constitutes clinical validation.** A 9/9 from an LLM critic means "the rubric we wrote was satisfied by the output we generated." It does not mean a clinician would approve this response, that it would not cause harm to a real person in distress, or that it should be put in front of M42 employees without further review.

Real deployment of a wellness agent that handles crisis signals requires:

- **Human clinical review** of the prompt and the policy text by qualified mental-health professionals.
- **Real escalation pathways** — what happens when the system detects crisis must include a defined, tested path to a human, not just a logged HR/EAP flag.
- **Duty-of-care sign-off** from M42 Legal and HR.
- **Iteration with crisis professionals** on actual response transcripts, not just synthetic test cases.
- **A clear scope statement** — what the tool is for, what it is not for, what users are told upfront.

The demo carries this caveat in the UI itself (the amber-bordered note shown beneath every Wellness response) and in the response metadata returned by the API. We did not hide the limitation; we surfaced it. That is the difference between a thoughtful demo and an irresponsible one.

### 5.2 Crisis resources — what we used and what we deliberately did not

The crisis path uses **real M42 wellbeing resources**: SAKINA (800 SAKINA / 800 725 462, confidential support in Arabic or English) and the Lyra Employee Assistance Program (24/7, access code M42XLYRA, yourmenawellbeing@lyrahealth.com, phone 8000 120 120). These were taken from an actual M42 Human Capital communication.

Two deliberate choices about what is *not* hardcoded:

1. **No specific emergency number** (such as 999) is hardcoded. The policy mentions "local emergency services" generically for situations of immediate physical danger. The decision: do not put a specific number into the code without confirmation that it is the right number for every context the system might serve.
2. **Every resource detail carries the caveat "confirm against latest official M42 communication, as contact information may change."** This is in the policy text, in the system prompt, and in the UI. The system does not present itself as the source of truth on a number that could change without the system knowing.

### 5.3 The aggregate dashboard's confidentiality promise

The Wellness agent tells the employee: "this check-in is restricted to you." The aggregate dashboard is the place where that promise could quietly break — if individual scores were surfaced to managers, the agent's promise would be a lie.

The dashboard's three commitments (aggregate-only, threshold-gated, no manager-of-own-team view) exist specifically to preserve that promise. The architecture is designed so that no path through the code produces individual identification. The aggregator function returns counts; the dashboard endpoint surfaces team-level trends; the UI displays "Team-level signals hidden" rather than showing under-threshold data.

This is *privacy by design*, in the literal sense: it is enforced by what the code can and cannot do, not by what we promise we will not do.

### 5.4 Routing — the safety bias is in the code, not just the prompt

The router's safety bias (any distress signal beats any work signal) is enforced two ways:

1. **In the prompt:** the system prompt to the router LLM explicitly states the overriding rule.
2. **As a code backstop:** if the LLM ever classifies `wellbeing_signal_detected=true` but routes to a non-Wellness agent, the router code overrides the choice and logs a warning. We do not trust the model to always follow the prompt; we enforce the bias regardless.

This is the architectural pattern throughout HALO — **safety constraints are enforced at the code layer, not just the prompt layer.** The Wellness Validator caps Safety & Severity at 0 on any crisis-handling violation (a code-level rule). The dashboard's threshold gate is in code, not in a config the user could change. The aggregator does not have access to names.

### 5.5 What this submission does not claim

To be explicit:

- HALO is not a clinically validated wellness platform.
- HALO does not currently execute actions in real M42 systems (Slack, directory, HR systems) — only the brand-asset file download executes; everything else is structured advice.
- HALO's aggregate dashboard's illustrative populated view is synthetic data, clearly labelled as such, included only to demonstrate what the populated view would look like at scale.
- HALO's router has been tested on a handful of representative cases, not at production scale. Edge cases in routing will exist.
- The 9/9 verdicts in the demo i/o pairs are real but should be read as "passes the rubric we wrote," not "approved by domain experts."

What HALO *does* claim: it demonstrates that the multi-agent pattern (Intake → Search → Brush → Validator → Route) generalises across five very different domains; that safety can be engineered into the substrate, not bolted on; and that one platform can be both useful and disciplined enough to refuse the requests it should refuse.

---

## 6. Built vs. roadmap

| Capability | Status | What real production would need |
|---|---|---|
| 5 specialist agents | **Built, tested** | Iteration with domain owners (Marcom, HR/HC, IT) on policy text and rubric calibration |
| Router with safety bias | **Built, tested** | Production-scale routing eval; more nuanced ambiguity handling |
| File-download execution (Agent 01) | **Built, tested** | Render to PNG/PDF via design API; brand asset store |
| Aggregate dashboard (HR/HC view) | **Built, tested** | Real cross-time-period data; configurable thresholds; data-retention policy sign-off |
| Voice input (speech-to-text) | Not built | Speech-to-text wrapper on the unified chat; same downstream pipeline |
| Real action execution (Slack/directory/calendar) | Not built — roadmap | Per-system OAuth integrations, access controls, human-in-the-loop confirmation flow |
| Production wellness deployment | **Explicitly out of scope** | See Section 5.1 — clinical review, legal sign-off, real escalation pathways |
| Dockerfile | Not built — roadmap | Local Python install (venv + pip) is the canonical install path; a Dockerfile would add a containerised option without changing the architecture. The official rubric DQ for "Docker build fails" only applies if Docker is required for evaluation, which it is not here. |
| Mobile app | Not built | The unified chat (`/halo`) is mobile-responsive; native app is a wrap-and-distribute task, not an architectural one |

The honest read: the agent-pattern half of HALO is genuinely complete. The execution half is one capability built, several capabilities deliberately scoped out because they need access controls and reviews that no hackathon can deliver responsibly.

---

## 7. Running it locally

**Prerequisites.** Python 3.11, a Compass API key (set as `OPENAI_API_KEY` in `.env`, with `OPENAI_BASE_URL=https://api.core42.ai/v1`).

**Setup.**

```bash
---

## 9. Submission compliance

- **Use Case:** #13 Media Content Generation (Agent 01 anchors the submission; Agents 02–05 + platform layer extend HALO into the broader employee-platform vision)
- **Built on Compass:** all 5 agents + router use GPT-4.1 (Intake/Validator/Router) and GPT-5.1 (Brush) via the Compass `/v1/chat/completions` endpoint; Search uses `text-embedding-3-large` for 3072-dim embeddings via `/v1/embeddings`
- **Multi-agent decomposition:** 5 agents per pipeline, plus a Router agent on top; agent_trace returned with every response
- **Retrieval-augmented:** every Validator decision cites rule IDs from a versioned policy document
- **Reproducible:** deterministic temperatures (0.1–0.5), `response_format={"type": "json_object"}` on every Compass call, full agent traces in every response
- **Sample i/o pairs:** 13 total across the 5 agents, all scoring 9/9, including stress tests (forbidden words, messy brainstorm, restricted distribution, active conflict, crisis signal)
- **Safety-explicit:** the Wellness agent's demo-artifact caveat is shown in the UI, not hidden in the doc; the aggregate dashboard's design commitments are stated upfront on the dashboard page

---

## 10. Acknowledgements

Built solo by Feras Assil during the G42 Agentathon sprint window. Submission name "HALOsination" was the original Agent 01 codename; HALO is the platform the agentathon submission grew into. M42 wellbeing resources (SAKINA, Lyra) are taken from an internal M42 Human Capital communication and are used with the explicit caveat that they should be confirmed against the latest official source. The architectural pattern (Intake → Search → Brush → Validator → Route) and the Proposer/Critic framing are widely-known patterns; HALO's contribution is showing they generalise convincingly across five domains with one shared substrate.
