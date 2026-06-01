# HALO — Architecture

> **G42 Agentathon submission — Use Case #13 Media Content Generation**
> **Team:** HALOsination (solo build — Feras Assil)
> **Repo:** `creativeferas-png/halosination-agent`

---

## 0. What HALO is

**HALO is an agentic orchestration layer for the modern enterprise workplace** — designed and prototyped against M42 as the case study. The vision is one place an employee talks to, in plain language, that quietly coordinates with the systems they already use — calendar, email, brand assets, Yammer, HR.

This submission ships **the orchestration layer's reasoning substrate**: five specialist agents that demonstrate the pattern works across very different domains, plus a unified router with a safety bias, real file execution for the brand domain, and an aggregate wellbeing dashboard built privacy-first.

The hard part of an agentic platform is not the integrations — it is the reasoning, the policy retrieval, the rule-cited validation, the safety routing, the refusal to act when the request is ambiguous or unsafe. **That is what is shipped here.** The connectors (M365, brand library, Yammer, HR systems) are deployment work, scoped and named in Section 7.

What is in the repo today:

| | What it does | Status |
|---|---|---|
| **Agent 01** — Brand & Brief | On-brand content from plain-English requests; refuses off-brand asks with rule citations | LIVE |
| **Agent 02** — Productivity | Meeting transcripts → structured summaries; surfaces open questions instead of inventing answers | LIVE |
| **Agent 03** — Task & KPI | Status updates → trackable structure; flags restricted-distribution items when sensitive content is detected | LIVE |
| **Agent 04** — Social | Employee profile → connection suggestions; excludes conflicted suggestions, restricts distribution on sensitive context | LIVE |
| **Agent 05** — Wellness | Self check-ins → care-appropriate responses; severity classification + crisis routing to real M42 resources (SAKINA, Lyra) | LIVE (demo artifact — see §6) |
| **Router** | Free-form request → right agent, with safety bias (distress always wins over work-topic) | LIVE |
| **Execution** | Agent 01 output → real downloadable branded asset file | LIVE |
| **Aggregate dashboard** | Cross-agent signals → privacy-by-design HR/HC view (aggregate-only, N≥5 threshold, no individual identification) | LIVE |

**Three user-facing surfaces:**
- `/` — architecture-transparent tabbed UI (five agent panels, full validator scoring visible)
- `/halo` — product-feel unified chat: one screen, type what you need, HALO routes and responds
- `/dashboard-ui` — aggregate wellbeing dashboard for HR/HC

**One architectural pattern across five domains.** Every agent shares the same Intake → Search → Brush → Validator → Route spine. One generalised Search agent serves all five. The agents differ in their policies and rubrics; the substrate is shared.

This document walks through the vision (§1), the architecture (§2–§3), the five agents (§4), the platform layer (§5), the safety and ethics framing (§6), the built-vs-roadmap picture including the deployment connectors (§7), and how to run it locally (§8).

---

## 1. The HALO Vision

Imagine the morning of a typical knowledge worker in any large enterprise — at M42, where this prototype was built, or at any organisation running M365 and a modern HR platform. They say or type:

- *"Squeeze a meeting with Ahmed tomorrow for 30 minutes."*
- *"Remind me to call the event supplier in 3 days."*
- *"Any important emails I missed this week?"*
- *"Fix this presentation per M42 brand guidelines."*
- *"I need the M42 logo in PNG format."*
- *"Find me people working on federated learning who are open to chat."*
- *"I have been struggling this week, what support is available?"*

One conversation. No tab-switching, no menu hunting, no second-guessing which system owns what. That is HALO.

### The thesis

This experience emerges from two layers working together:

1. **The agentic reasoning layer** — intent classification, policy retrieval, rule-cited validation, safety-biased routing, output drafting. This is the hard part. **This is what this submission ships.**
2. **The connector layer** — the enterprise systems any modern organisation already runs: M365 (calendar, email, files), a brand asset library, Yammer/Teams, ServiceNow, an HRIS, an EAP. At M42 specifically that means M365 + Oracle Fusion / OneHub + the M42 brand library + Lyra/SAKINA; at another organisation the analogues would be different but the integration points are the same. **This is the deployment work that turns HALO into the product.**

Every voice-command example above maps to a clear engineering path. Each one has a "reasoning half" (already shipped) and a "connector half" (named, scoped, ready to integrate):

| Vision example | Reasoning half (shipped today) | Connector half (deployment work) |
|---|---|---|
| Squeeze a meeting | Router intent classification + policy reasoning (is Ahmed in a focus block? does the wellness agent have a flag?) | Microsoft Graph Calendar API · OAuth per user · ~1–2 weeks |
| Set a reminder | Intake → Validator (specific, measurable, time-bound) | M365 To-Do API or Postgres + cron · ~3–4 days |
| Important missed emails | Importance classification policy + restricted-distribution reasoning (Agents 02, 03) | Microsoft Graph Mail (read scope) · ~1–2 weeks + governance |
| Fix presentation per brand | Brand rule retrieval + violation detection + drafted fix (Agent 01) — already does this for headlines and visual specs | python-pptx file I/O + diff-and-rewrite agent · ~2–3 weeks. **Closest to shippable.** |
| Get M42 logo as PNG | Search agent retrieval pattern generalises | Brand asset library API (you have the library; this is plumbing) · ~1 week |
| Find peers in X domain | Connection suggestion + bias exclusion + privacy rules (Agent 04) | Directory + Yammer/Teams group APIs · weeks of governance work |
| Wellbeing support | Severity classification + real M42 resources (Agent 05) | Self-service already complete; HR escalation pathway is a programme, not a sprint |

The deployment targets named above (M365 Graph, Oracle Fusion / OneHub) are M42-specific instances of a wider pattern. Any organisation running M365 plus a modern HRIS (Oracle Fusion HCM, Workday, BambooHR, SAP SuccessFactors) would have analogous connector requirements; the agentic reasoning layer is portable across them.

### What this submission demonstrates

The five specialist agents in this submission are not five separate prototypes — they are **the reasoning halves of seven future deployed capabilities**, all sharing the same architectural pattern: Intake → Search → Brush → Validator → Route. The Router on top is the front door that turns "five separate APIs" into "one conversation."

If a judge has time for only one read, it is this: **HALO is one architectural pattern, applied across five domains today, designed to extend into the enterprise deployment connectors — M365, a modern HRIS, brand asset libraries — that any knowledge-work organisation already runs. M42 is the case study; the pattern is general.** The hard part is already shipped. The integration work is named.

---

## 2. Executive summary

HALO is a multi-agent system that lets any employee in a knowledge-work organisation request, structure, or be supported on plain-English asks across five work and wellbeing domains — and ensures every output is verifiably on-policy before it leaves the system. M42 was the case study during development; the architecture, policies, and integration patterns generalise to any organisation running M365 plus a modern HRIS.

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

## 3. Why this approach

### 3.1 Why a unified platform, not five separate tools

Five disconnected tools means five separate logins, five different UI conventions, five chances for an employee to give up. More importantly, signals do not flow between them — the meeting that surfaced a colleague's stress, the status update where someone wrote "I am drowning," the wellness check-in where they finally asked for help — these stay in silos.

HALO is one platform with one front door. The unified chat surface (`/halo`) lets an employee type or speak a request in plain language. The router decides which agent handles it. The aggregate dashboard reads across all five so HR sees trends, not isolated points.

The architectural payoff: one pattern, applied five times, produces less code and more consistency than five hand-built tools. Add a sixth domain (Learning? Finance? Travel?) and the cost is one policy file, one rubric, and one thin agent module — not another codebase.

### 3.2 Why multi-agent (not a single LLM call)

A single big LLM call can do impressive things, but it cannot be **audited** and cannot **refuse cleanly**. HALO's multi-agent decomposition does three things a monolithic call cannot:

1. **Separation of concerns.** Intake extracts structure faithfully; Brush drafts; Validator scores. Each step is a smaller, more reliable LLM call than asking one model to do all of it at once.
2. **Critic loop.** The Validator scores Brush's draft against the same rules Brush had access to. Disagreement triggers one revision attempt; persistent disagreement escalates to a human. This is the architectural mechanism that prevents the most consequential failure modes — an off-brand asset shipping, an unsafe wellness response going out, a status with buried sensitive content being broadcast.
3. **Trace.** Every step logs its inputs, outputs, and the rules cited. The agent_trace returned by every endpoint is the audit log.

**A note on what the committed trace shows — and what it doesn't.**

The committed reference trace at `logs/agent_trace.jsonl` contains 12 events from two real `/run` calls, both passing 9/9 first time. The Validator → Brush revision loop is fully implemented (`run.py` lines 277-295, `app/brush_agent.py::run_brush_revision`) but did not fire on these particular inputs because **Brush self-disciplines against retrieved rules** — it refuses forbidden words (e.g., "crush") from the input prompt *before* Validator sees the draft. The same pattern held across all 13 sample i/o pairs covering stress-test inputs (off-brand language, sensitive HR context, active workplace conflict, crisis signals): zero triggered revision. Brush refused at the drafting layer; Validator ratified at the scoring layer.

This is intentional architecture: **Validator is a safety net, not a regular-flow component.** Removing it would still measurably change outputs — the safety net would no longer be there to catch any drift Brush missed, and the rule-citation audit trail would disappear. But on rule-grounded inputs handled by a well-disciplined Brush, the net catches little. We read this as evidence the substrate works, not as evidence it doesn\'t.

**To observe the revision loop firing in real time:** raise the Validator pass-threshold in `app/validator_agent.py` from 7/9 to 8/9. A 7/9 Brush draft will then trigger one revision attempt before passing or escalating. The loop is one configuration knob away from being routinely visible — we kept the threshold at 7/9 in the submitted build because it reflects the production calibration we\'d defend, not the demo behaviour we want to manufacture.


### 3.3 Why retrieval-augmented (RAG) policies

The Validator does not "just know" the rules — it retrieves them from a versioned policy document and cites the rule IDs in its verdict. This matters for three reasons:

1. **Auditability.** Every decision can be traced to a specific rule. Disagreements with the system's judgement become disagreements about the rule, not arguments with an opaque model.
2. **Updateability.** When a brand guideline, meeting policy, or care protocol changes, you edit a Markdown file and re-run the index builder. No retraining, no prompt rewrite.
3. **Generalisability.** The same retrieval pipeline serves five different policy documents — brand, meeting, task, social, wellness. The script that builds the policy index is the same script for all five. The Search agent is one generalised module that takes an index path and a query builder.

---

## 4. The five agents

Every agent shares the same spine. The detail below covers what each agent's policy emphasises and what its Validator scores against, plus the demo case that best illustrates what each refuses or restricts.

### 4.1 Agent 01 — Brand & Brief

**Domain.** On-brand content creation: launch banners, social posts, internal announcements, clinical communications. The codename "HALOsination" originated here — pairing the platform name with the failure mode (hallucinated, off-brand) the agent specifically counters.

**Policy.** 10 brand rules covering voice, evidence-aware claims (especially in healthcare contexts), forbidden words ("revolutionary," "crush," "dominate"), tone calibration, audience fit, and visual specification standards.

**Rubric (3×3, max 9).** Brand Voice / Visual Spec / Audience Fit.

**Demo case worth seeing.** A "punchy, crush-the-competition" pitch from a hospital CIO context. Brush refuses to use forbidden words; Validator catches any drift; the final asset reframes "crush" as a confident, evidence-aware statement. Bonus: this is the only agent with **real execution** — its output renders into an actual downloadable branded HTML asset file (see §5.2).

### 4.2 Agent 02 — Productivity (Meeting Notes)

**Domain.** Meeting transcripts → structured notes (decisions, action items with owners and deadlines, open questions, risks/blockers, follow-ups, distribution decision).

**Policy.** 10 rules covering owner+deadline-or-flag for every action, distinguishing decisions from action items, surfacing rather than burying ambiguity, restricting distribution when HR or contractor-sensitive topics are discussed.

**Rubric.** Completeness / Faithfulness / Ownership Clarity.

**Demo case worth seeing.** The "messy brainstorm" sample — a half-decided product roadmap meeting with mixed signals. Most summarisers paper over the mess and produce a confident-sounding summary. HALO's Agent 02 surfaces **8 open questions** explicitly, with reasoning for each. It refuses to invent owners or deadlines where the transcript doesn't establish them; instead it flags "UNOWNED — see open questions." This is the same architectural virtue as Agent 01's forbidden-word refusal — the system says no when no is correct.

### 4.3 Agent 03 — Task & KPI

**Domain.** Free-form status text → structured tracker (tasks with owner/deadline/status/progress/blocked_by, KPIs with direction, risks, recommendations, distribution decision).

**Policy.** 10 rules including the SMART check on each task (Specific, Measurable, Achievable, Relevant, Time-bound — flagged when missing), distribution restriction when HR or sensitive context surfaces, refusal to fabricate progress numbers, surfacing rather than smoothing the ambiguous status.

**Rubric.** Specificity / Measurability / Risk Awareness.

**Demo case worth seeing.** A "messy standup" sample where the speaker mentions a brewing conflict with a contractor mid-update. Agent 03 produces the structured status — but flags the contractor mention as sensitive, restricts distribution, and surfaces it as an open question rather than including it in the broadcast summary. Sensitive content does not silently propagate.

### 4.4 Agent 04 — Social

**Domain.** Employee self-introduction → connection suggestions (peers, mentors, mentees, cross-OpCo collaborators, horizon-broadeners) and group/channel recommendations.

**Policy.** 10 rules including specificity (every suggestion needs a rationale), diversity (no filter-bubble), privacy (never base suggestions on sensitive personal attributes), Rule 7 (mentor/mentee suggestions need a power-dynamics note explaining bidirectional value), Rule 8 (exclude suggestions that conflict with stated boundaries), Rule 9 (restrict distribution and add a wellbeing note when isolation/relocation/conflict signals fire).

**Rubric.** Relevance / Diversity / Privacy & Care.

**Demo case worth seeing.** The Hassan profile — a PM in active HR dispute who explicitly says "NOT Karim (my line manager), NOT anyone on my current team, NOT anyone in the chain above Karim." HALO produces 5 diverse suggestions, **explicitly excluding** Karim and the consumer-apps chain in a visible `conflicts_excluded` section. The system even coins an illustrative channel name `#product-mentors-outside-chain` whose entire purpose is connecting Hassan to people outside his reporting chain. Rule 8 doesn't just constrain the output — it shapes it into something more useful.

### 4.5 Agent 05 — Wellness

**Domain.** Self check-ins → care-appropriate supportive responses, with severity classification (general_wellbeing / elevated_concern / crisis_signal) determining the response path.

**Policy.** 10 rules grounded in workplace EAP and supportive-listening best practice. The non-negotiables: never give clinical or diagnostic advice (Rule 1); never label the person's experience (Rule 2); recognise severity and route accordingly (Rule 3); on crisis, **lead with resources** and never suggest waiting or scheduling (Rule 4); always offer at least one concrete next step (Rule 7); match the person's tone, never moralise (Rule 9); resources must be specific and current (Rule 10). **Real M42 resources are baked into Rules 4 and 10:** SAKINA (800 SAKINA / 800 725 462, Arabic or English) and Lyra EAP (24/7, code M42XLYRA, 8000 120 120), each with a "confirm against latest official M42 communication" caveat.

**Rubric.** Safety & Severity / Care Language / Actionability. The Validator caps Safety & Severity at 0 on any crisis-handling violation (resources buried, waiting suggested, diagnosis given) and lists the violation explicitly.

**Demo case worth seeing.** The "I can't cope, don't see the point" check-in. Intake correctly classifies as `crisis_signal`. Search retrieves Rule 4 as the top match. Brush's response **leads with SAKINA's number in the first sentence**, acknowledges the pain in the person's own words without minimising or amplifying, offers a concrete next step ("in the next hour, choose one option…"), and explicitly avoids diagnosis. The Validator scores 9/9 with zero safety violations. The response carries a `what_this_response_avoided` self-audit listing seven things deliberately NOT done.

**This is the agent that needs the most explicit caveat.** See §6.

---

## 5. The platform layer

These three capabilities sit on top of the five agents and turn HALO from "five specialist tools" into "one platform."

### 5.1 Router — the unified front door

**Endpoint:** `POST /route` — takes free-form text, returns a routing decision plus the chosen agent's full pipeline result, in one call.

**Design.** The router is a small classifier (GPT-4.1) with one overriding rule: **any signal of personal distress routes to Wellness, even when the message also mentions work or deadlines.** A backstop in the router code enforces this — if the model classifies wellbeing_signal_detected=true but routes to a non-Wellness agent, the code overrides and routes to Wellness with a logged warning.

**Why this matters.** The single most consequential routing failure would be misdirecting a struggling person to a task tracker. A naive router sees "I'm so behind on my deadlines and honestly I just can't cope anymore, some days I don't see the point in any of it" and routes to Task (keywords: behind, deadlines). HALO's router routes it to Wellness — *correctly*, and verified end-to-end in the browser, including the full crisis response with resources and HR/EAP flag.

**Tested across:** clear cases for each of the 5 agents, an ambiguous mid-case, and the work-masked-distress case. All correct.

### 5.2 Execution — the one genuinely-executing capability

**Endpoint:** `POST /render_asset` — takes Agent 01's `final_draft` output, returns a downloadable branded HTML file with `Content-Disposition: attachment`.

**Why one capability, not five.** Real execution (creating a Slack channel for Agent 04, writing tasks into a tracker for Agent 03, booking an EAP session for Agent 05) requires write-access to M42's real systems, plus access controls, plus human-in-the-loop on irreversible actions, plus security review. **None of that is a hackathon-window build.** These are exactly the connectors §1 and §7 name as deployment work.

The file-download path was chosen deliberately because it is genuinely useful, demonstrates the principle, and needs no permissions. The renderer maps Agent 01's real schema (`copy.headline`, `copy.subhead`, `copy.body`, `copy.cta`, `visual_spec.concept`, `visual_spec.mood`, `visual_spec.palette`, `visual_spec.composition`) into a polished HTML asset that uses the agent's own palette as a gradient header. Production would render PNG/PDF via a headless browser or design API — that's a roadmap note, not a missing feature.

**End-to-end verified.** Click the download button in the unified chat after a brand request, get a 4KB HTML file titled with the headline, open it, see a real branded asset using the palette HALO chose.

### 5.3 Aggregate Dashboard — the 6th capability

**Endpoint:** `GET /dashboard` — returns two clearly-separated sections: **real signals** aggregated from this demo's saved agent outputs, and an **illustrative populated view** clearly labelled as synthetic so a viewer can see what the dashboard would look like at organisational scale.

**Three design commitments encoded in the architecture, not just in the doc:**

1. **Aggregate-only.** The aggregator module (`app/aggregator.py`) extracts signals only — counts and flags — from saved agent outputs. It is structurally incapable of producing individual identification: it does not store or surface names, content, or any field traceable to a specific person. The function names tell the story: `extract_signals_agent02`, `extract_signals_agent03`, etc., each returning counts only.
2. **Threshold-gated at N≥5.** Team-level signals are displayed only when at least 5 people have contributed responses in the period. Below threshold, the dashboard renders a visible "Team-level signals hidden" tile explaining why. The illustrative Regulatory Affairs team (3 responses, 6 people) demonstrates this safeguard firing on screen — the safeguard is not theoretical, you can see it blocking a tile.
3. **No manager-of-own-team view.** Deliberately not built. That framing edges toward surveillance and would directly contradict the Wellness agent's promise of "this check-in is restricted to you." The dashboard is an HR/HC trend view only.

**The framing for HR.** Trends and suggested interventions per team, with the evidence-basis always footnoted ("Aggregate signals only — 18 responses across 24 people. No individual data is referenced."). The aim is **earlier care decisions at the team level**, not earlier scrutiny at the individual level.

---

## 6. Safety and ethics — what we did and didn't claim

This is the section that distinguishes a careful submission from an overclaimed one. Read it slowly.

### 6.1 Agent 05 is a demo artifact, not a deployable wellness tool

The crisis-handling path in Agent 05 works correctly in the demo. It classifies severity correctly, retrieves the right rule, leads with real M42 resources, scores 9/9 with zero safety violations.

**None of that constitutes clinical validation.** A 9/9 from an LLM critic means "the rubric we wrote was satisfied by the output we generated." It does not mean a clinician would approve this response, that it would not cause harm to a real person in distress, or that it should be put in front of M42 employees without further review.

Real deployment of a wellness agent that handles crisis signals requires:

- **Human clinical review** of the prompt and the policy text by qualified mental-health professionals.
- **Real escalation pathways** — what happens when the system detects crisis must include a defined, tested path to a human, not just a logged HR/EAP flag.
- **Duty-of-care sign-off** from M42 Legal and HR.
- **Iteration with crisis professionals** on actual response transcripts, not just synthetic test cases.
- **A clear scope statement** — what the tool is for, what it is not for, what users are told upfront.

The demo carries this caveat in the UI itself (the amber-bordered note shown beneath every Wellness response) and in the response metadata returned by the API. We did not hide the limitation; we surfaced it. That is the difference between a thoughtful demo and an irresponsible one.

### 6.2 Crisis resources — what we used and what we deliberately did not

The crisis path uses **real M42 wellbeing resources**: SAKINA (800 SAKINA / 800 725 462, confidential support in Arabic or English) and the Lyra Employee Assistance Program (24/7, access code M42XLYRA, yourmenawellbeing@lyrahealth.com, phone 8000 120 120). These were taken from an actual M42 Human Capital communication.

Two deliberate choices about what is *not* hardcoded:

1. **No specific emergency number** (such as 999) is hardcoded. The policy mentions "local emergency services" generically for situations of immediate physical danger.
2. **Every resource detail carries the caveat "confirm against latest official M42 communication, as contact information may change."** This is in the policy text, in the system prompt, and in the UI.

### 6.3 The aggregate dashboard's confidentiality promise

The Wellness agent tells the employee: "this check-in is restricted to you." The aggregate dashboard is the place where that promise could quietly break — if individual scores were surfaced to managers, the agent's promise would be a lie.

The dashboard's three commitments (aggregate-only, threshold-gated, no manager-of-own-team view) exist specifically to preserve that promise. The architecture is designed so that no path through the code produces individual identification.

This is *privacy by design*, in the literal sense: it is enforced by what the code can and cannot do, not by what we promise we will not do.

### 6.4 Routing — the safety bias is in the code, not just the prompt

The router's safety bias (any distress signal beats any work signal) is enforced two ways:

1. **In the prompt:** the system prompt to the router LLM explicitly states the overriding rule.
2. **As a code backstop:** if the LLM ever classifies `wellbeing_signal_detected=true` but routes to a non-Wellness agent, the router code overrides the choice and logs a warning. We do not trust the model to always follow the prompt; we enforce the bias regardless.

This is the architectural pattern throughout HALO — **safety constraints are enforced at the code layer, not just the prompt layer.**

### 6.5 What this submission does not claim

To be explicit:

- HALO is not a clinically validated wellness platform.
- HALO does not currently execute actions in real M42 systems (Slack, directory, HR systems, M365, brand library) — only the brand-asset file download executes; everything else is structured advice. **The connector roadmap in §7 names these explicitly.**
- HALO's aggregate dashboard's illustrative populated view is synthetic data, clearly labelled as such.
- HALO's router has been tested on a handful of representative cases, not at production scale.
- The 9/9 verdicts in the demo i/o pairs are real but should be read as "passes the rubric we wrote," not "approved by domain experts."

What HALO *does* claim: it demonstrates that the multi-agent pattern (Intake → Search → Brush → Validator → Route) generalises across five very different domains; that safety can be engineered into the substrate, not bolted on; and that one platform can be both useful and disciplined enough to refuse the requests it should refuse.

---

## 7. Built vs roadmap (including the deployment connectors)

This is the full picture: what is in the repo today, what the deployment connectors look like to turn HALO into the product, and what is explicitly out of scope.

### 7.1 Built and tested

| Capability | Status |
|---|---|
| 5 specialist agents (Brand, Productivity, Task, Social, Wellness) | **Built, tested** |
| Router with safety-biased dispatch | **Built, tested** |
| File-download execution (Agent 01) | **Built, tested** |
| Aggregate dashboard (HR/HC view) | **Built, tested** |
| 3 user-facing surfaces (tabbed, unified chat, dashboard) | **Built** |
| Structured agent traces (JSONL, rubric-format) | **Built, committed reference file** |
| /health endpoint with real Compass round-trip | **Built, tested** |

### 7.2 Deployment connectors — the path from agentic reasoning to agentic action

These are the integrations that turn the shipped reasoning substrate into the product vision described in §1. The specific targets below are illustrated against M42's stack (M365 + Oracle Fusion HCM); any organisation running an analogous enterprise stack (Workday, BambooHR, SAP SuccessFactors, etc.) would have equivalent integration points. None of these is technically blocked; all of them are integration/governance work.

| Connector | What it unlocks | Effort estimate | Status |
|---|---|---|---|
| **M365 To-Do / Tasks API** | "Remind me to call the event supplier in 3 days." | ~3–4 days | Roadmap |
| **Microsoft Graph Calendar** | "Squeeze a meeting with Ahmed tomorrow for 30 minutes." | ~1–2 weeks + per-user OAuth | Roadmap |
| **Brand asset library API** | "I need the M42 logo in PNG format." | ~1 week (you have the library) | Roadmap |
| **python-pptx + diff-and-rewrite agent** | "Fix this presentation per M42 brand guidelines." | ~2–3 weeks. **Closest to shippable.** | Roadmap |
| **Microsoft Graph Mail (read scope)** | "Any important emails I missed this week?" | ~1–2 weeks + governance | Roadmap |
| **Directory + Yammer/Teams group APIs** | Real connection suggestions from Agent 04 | Weeks + governance | Roadmap |
| **PNG/PDF asset render** | Replace the Agent 01 HTML download with branded image/document | ~1 week | Roadmap |
| **Dockerfile** | Optional containerised install path | ~1 day | Roadmap — local Python install is the canonical path today |

### 7.3 Explicitly out of scope for the submission

| Capability | Why out of scope |
|---|---|
| Production wellness deployment | Requires human clinical review, real escalation pathways, duty-of-care sign-off. See §6.1. |
| Voice input | Speech-to-text wrapper on the unified chat; same downstream pipeline. Not a sprint task; product decision. |
| Write-actions in HR systems | Requires per-system access controls + human-in-the-loop + security review. |
| Mobile native app | The unified chat is mobile-responsive; native app is wrap-and-distribute, not architectural. |

The honest read: **the agentic reasoning half of HALO is genuinely complete. The connector half is named, scoped, and ready for deployment work.**

---

## 8. Running it locally

**Prerequisites.** Python 3.11, a Compass API key (set as `OPENAI_API_KEY` in `.env`, with `OPENAI_BASE_URL=https://api.core42.ai/v1`).

**Setup.**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Build the 5 policy indexes** (one-time):

```bash
python scripts/build_policy_index.py data/brand_index.md data/brand_index.json
python scripts/build_policy_index.py data/meeting_policy.md data/meeting_policy_index.json
python scripts/build_policy_index.py data/task_policy.md data/task_policy_index.json
python scripts/build_policy_index.py data/social_policy.md data/social_policy_index.json
python scripts/build_policy_index.py data/wellness_policy.md data/wellness_policy_index.json
```

**Run.** Two windows:

```bash
# Window 1 — API on port 8000
python run.py

# Window 2 — UI on port 8001
python run_ui.py
```

**Open the three surfaces** in a browser:

- `http://localhost:8001` — tabbed architecture view (one tab per agent, full validator scoring visible)
- `http://localhost:8001/halo` — unified single-screen chat (the product-feel demo)
- `http://localhost:8001/dashboard-ui` — aggregate wellbeing dashboard

**API endpoints** (all on port 8000):

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Compass connectivity verification (real round-trip) |
| POST | `/run` | Agent 01 (Brand & Brief) — the mandatory submission endpoint |
| POST | `/run_meeting` | Agent 02 (Productivity) full pipeline |
| POST | `/run_status` | Agent 03 (Task & KPI) full pipeline |
| POST | `/run_social` | Agent 04 (Social) full pipeline |
| POST | `/run_wellness` | Agent 05 (Wellness) full pipeline |
| POST | `/route` | Unified router: classify request, dispatch to agent, return both |
| POST | `/render_asset` | Render Agent 01 output to a downloadable branded HTML file |
| GET | `/dashboard` | Aggregate wellbeing dashboard data (real + illustrative) |

---

## 9. Repo map
---

## 10. Submission compliance

- **Use Case:** #13 Media Content Generation (Agent 01 anchors the submission; the platform extension demonstrates the architectural pattern's reach and sets up the orchestration-layer vision described in §1)
- **Built on Compass:** all 5 agents + router use GPT-4.1 (Intake/Validator/Router) and GPT-5.1 (Brush) via the Compass `/v1/chat/completions` endpoint; Search uses `text-embedding-3-large` for 3072-dim embeddings via `/v1/embeddings`
- **Multi-agent decomposition:** 5 agents per pipeline, plus a Router agent on top; structured agent_trace returned with every response
- **Retrieval-augmented:** every Validator decision cites rule IDs from a versioned policy document
- **Reproducible:** deterministic temperatures (0.1–0.5), `response_format={"type": "json_object"}` on every Compass call, full agent traces in every response, reference JSONL trace committed
- **Sample i/o pairs:** 13 total across the 5 agents, all scoring 9/9, including stress tests (forbidden words, messy brainstorm, restricted distribution, active conflict, crisis signal)
- **Safety-explicit:** the Wellness agent's demo-artifact caveat is shown in the UI, not hidden in the doc; the aggregate dashboard's design commitments are stated upfront on the dashboard page

---

## 11. Acknowledgements

Built solo by Feras Assil during the G42 Agentathon sprint window. Submission name "HALOsination" was the original Agent 01 codename; HALO is the platform the agentathon submission grew into. M42 wellbeing resources (SAKINA, Lyra) are taken from an internal M42 Human Capital communication and are used with the explicit caveat that they should be confirmed against the latest official source. The architectural patterns (Intake → Search → Brush → Validator → Route, Proposer + Critic, Context-Packer + Actor) are the agentic governance patterns named in the official Agentathon guidance; **HALO's contribution is showing that the orchestration layer pattern generalises across domains, and naming the deployment connectors that turn agentic reasoning into agentic action inside any knowledge-work organisation — with M42 as the case study that grounded the design in concrete user, role, and integration realities.**
