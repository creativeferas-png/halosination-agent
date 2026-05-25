# HALOsination — Architecture

> **G42 Agentathon submission — Use Case #13 Media Content Generation**
> **Team:** HALOsination (solo build — Feras Assil)
> Repo: `creativeferas-png/halosination-agent`

---

## 0. HALO context

This submission ships **Agent 01** of **HALO** — M42's vision for a single AI-powered employee platform that connects M365, Oracle, and OneHub so every employee can **work smarter, connect deeper, and live better** through one natural conversation.

HALO is structured as 5 agents across 3 layers, all sharing one architectural pattern (Intake -> Search -> Brush -> Validator -> Route) applied to 5 different problem domains:

| # | Agent | Layer | Status in this submission |
|---|---|---|---|
| **01** | **Brand & Brief** | Work | **Live — this document covers it in detail** |
| 02 | Productivity (meetings, notes) | Work | In active build (same pattern, meeting domain) |
| 03 | Task & KPI | Work | Planned (same pattern, status/KPI domain) |
| 04 | Social (connection, interest matching) | Social | Planned (same pattern, similarity-driven) |
| 05 | Wellness (check-ins, signals) | Wellness | Planned (same pattern, care-appropriate validator) |

**Codename for Agent 01 is "HALOsination"** — the team name and the working title of this submission. It pairs the platform name "HALO" with the AI failure mode it specifically counters: hallucinated, off-brand output. Agent 01 enforces brand truth at the point of creation.

The rest of this document describes Agent 01 in full. The pattern proven here — multi-agent decomposition + retrieval-grounded drafting + critic loop with rule citations — is the architectural template for Agents 02-05.

---

## 1. Executive summary

HALOsination is a multi-agent system that lets any G42-group employee request, rebrand, or commission on-brand media assets in plain English — and ensures every output is verifiably on-brand before it leaves the system.

The pain point is real and operational: across G42, M42, Core42, Inception, and Mubadala Health, every OpCo produces assets daily — launch banners, social posts, internal announcements, clinical communications. Marcom owns the brand source-of-truth, but they cannot review every request from every team in every OpCo. So today, **off-brand assets ship**, and Marcom catches them after the fact (or doesn't catch them at all).

HALOsination inverts the workflow. Instead of post-hoc review, brand compliance is enforced **at the point of creation** by a chain of cooperating agents that retrieve the relevant brand rules, draft against them, and score the draft against the same rules before delivery. The Validator agent issues a structured 0-9 verdict citing specific rule IDs; below 7/9 triggers one revision attempt, then human escalation.

Concretely:

- 4 agents, all backed by Compass: Intake, Search, Brush, Validator (plus Route for delivery).
- 5 Compass calls per request on average: 1 embedding (Search) + up to 4 chat completions (Intake, Brush, Validator, optional revision).
- ~5-10 seconds end-to-end for a typical request.
- Every verdict cites rule IDs from a public brand-guidelines document — making brand decisions **auditable**, not vibes-based.

**Business outcome:** Marcom moves from review bottleneck to standards owner. Any employee can self-serve on-brand content. Brand drift across OpCos becomes measurable.

---

## 2. Problem statement and business case

### 2.1 Why this problem
Across G42 group OpCos, the brand-content pipeline is asymmetric: ~1 central Marcom team versus hundreds of asset-producing teams. Marcom cannot scale linearly with content demand. The status quo produces three failure modes:

1. **Off-brand assets ship unchecked** — particularly damaging in healthcare contexts (M42), where tone and imagery decisions can affect patient trust and regulatory posture.
2. **High-quality requesters are bottlenecked** — leadership, clinical, and external-comms requests queue behind low-stakes work.
3. **Brand drift accumulates** — without measurable enforcement, each OpCo's voice gradually diverges from group brand standards.

### 2.2 Why multi-agent (not a single LLM call)
A single LLM prompt can produce content, but it cannot **enforce a governance loop**. The judging rubric explicitly rewards "critic/validator agents that score and trigger revisions" and "agents with shared memory; branching workflows; retry/escalation behaviour" — because those patterns are what differentiate an agentic system from a chatbot.

HALOsination's architecture decomposes the problem into competencies that are individually optimisable and observably testable:

| Competency | Agent | Why it's separate |
|---|---|---|
| Understanding messy human intent | **Intake** | Structured-extraction task, benefits from low temperature |
| Grounding output in authoritative brand rules | **Search** | Retrieval problem, embedding-shaped, not generative |
| Creative generation within constraints | **Brush** | High-temperature, creative, GPT-5.1's strength |
| Independent quality judgment | **Validator** | Needs structured scoring + ability to push back on the generator |
| Delivery decision-making | **Route** | Policy-driven (verdict shapes path), not generative |

Crucially: **the Validator sees the same retrieved rules Brush saw**. This is what makes the critic loop substantive rather than theatrical. The Critic can cite the exact rule the Proposer should have honoured.

### 2.3 Why retrieval-augmented (RAG)
Brand rules change. Hard-coding them into prompts means every rule change requires a code release. Retrieval-augmented generation means Marcom can edit `data/brand_guidelines.md`, re-run `scripts/build_brand_index.py`, and the entire agent system updates without touching code. This is how the system stays alive in production.

---

## 3. System architecture

### 3.1 High-level flow
### 3.2 Why this topology

The pipeline is deliberately **linear in the happy path** (Intake -> Search -> Brush -> Validator -> Route) with **one observable feedback edge** (Validator -> Brush) for revision. This matches the "Proposer <-> Critic" agentic pairing pattern: linear progress with a single concrete loop that has a clear termination criterion (max 1 revision attempt, then escalation).

Linear-with-one-loop is intentional. Multi-loop architectures look impressive in diagrams but are hard to debug, hard to demo, and easy to break in production. We chose the simplest topology that demonstrates real multi-agent collaboration: every step is observable in logs, every decision has structured output, and the loop has a hard cap.

---

## 4. Agent specifications

Each agent is a discrete Python module under `app/`. All four use the Compass OpenAI-compatible endpoint (`https://api.core42.ai/v1`) via the official `openai` SDK. All chat agents request `response_format={"type": "json_object"}` so downstream consumers parse without regex fragility.

### 4.1 Intake — `app/intake_agent.py`

**Purpose.** Convert a messy plain-language employee request into a structured BRIEF.
**Model.** `gpt-4.1`, temperature `0.2`, JSON response mode.
**Inputs.** A single string: the employee's request.
**Outputs.** A BRIEF dict with these fields: asset_type, project, audience, deadline, tone_hints[], format, opco_context, key_message, open_questions[], risks[].

**Why a separate agent.** Plain-language parsing is a different problem from creative drafting. Solving them with one LLM call would either over-constrain creativity (low temp) or hallucinate brief fields (high temp). Decoupling lets each agent be tuned independently.

**Failure mode.** JSON parse failure on the LLM response returns `{"error": "intake_parse_failure", "raw": ...}`. The pipeline degrades gracefully — it returns a `degraded` status response rather than crashing.

### 4.2 Search — `app/search_agent.py`

**Purpose.** Retrieve the top-K most relevant brand rules for a given BRIEF.
**Model.** `text-embedding-3-large` (3072 dimensions).
**Index.** `data/brand_index.json` — pre-built one-time from `data/brand_guidelines.md` via `scripts/build_brand_index.py`. 10 rules indexed.
**Inputs.** The BRIEF dict from Intake.
**Outputs.** Top-K (default 3) rules with cosine similarity scores.

**Mechanics.** Search constructs a query string from BRIEF's high-signal fields (asset_type, audience, opco_context, tone_hints, key_message), embeds it via a single Compass embedding call, then does in-memory cosine similarity against the pre-indexed rules. No vector DB needed at this scale.

**Why this matters for the judging rubric.** Multi-agent rubrics reward "agents with shared memory" — the retrieved rules ARE the shared memory between Brush (uses them to draft) and Validator (uses them to score). The same evidence flows to both, ensuring the Critic can ground its verdicts in what the Proposer was shown.

**Failure mode.** If the brand index is missing or the embedding call fails, Search returns an error dict. The pipeline downgrades gracefully — Brush and Validator continue without retrieved rules (using GPT priors only) and the trace logs the degradation.

### 4.3 Brush — `app/brush_agent.py`

**Purpose.** Draft the actual asset content — copy + visual spec — grounded in retrieved brand rules.
**Model.** `gpt-5.1`, temperature `0.7` (initial draft) / `0.5` (revision), JSON response mode.
**Inputs.** BRIEF (from Intake) + retrieved_rules (from Search).
**Outputs.** A DRAFT dict containing copy (headline, subhead, body, cta), visual_spec (concept, mood, palette, composition, must_include, must_avoid), and rationale citing rule_ids.

**Why GPT-5.1 here specifically.** Creative drafting benefits from a stronger model. GPT-5.1's higher reasoning capacity also helps it navigate the tension between brief intent and retrieved brand rules.

The system prompt explicitly tells Brush that retrieved rules are "authoritative" and "hard constraints" — this is what stops Brush from blindly complying with off-brand requests.

### 4.4 Validator — `app/validator_agent.py`

**Purpose.** Score Brush's draft against a 3-dimensional rubric, with access to the same retrieved rules Brush had.
**Model.** `gpt-4.1`, temperature `0.1` (consistency over creativity), JSON response mode.
**Rubric.** Three dimensions, each 0-3 (max 9): brand_voice, visual_spec, audience_fit.
**Threshold.** >= 7/9 = pass. < 7/9 = revise (one attempt). Still < 7/9 after revision = escalate.

**Output.** A verdict dict containing scores, total (computed locally), verdict label, reasoning per dimension citing rule_ids, rules_cited[], and a fix instruction if total < 7.

**Why arithmetic is enforced locally.** LLMs are unreliable at simple addition. We compute `total` in Python from the scores object and overwrite whatever the model claims. Defence-in-depth.

**Revision triggering.** If `is_revision=False` and `total < 7`, the pipeline invokes `run_brush_revision()` with the original draft, the fix instruction, and the same retrieved rules. After revision, the Validator re-scores with `is_revision=True` — at which point a still-failing total escalates to human review rather than triggering another revision.

### 4.5 Route — orchestrator-side logic in `run.py`

**Purpose.** Decide the delivery path based on the final verdict.
**Implementation.** Policy-driven, not generative — no LLM call. Verdict -> path mapping: `pass` -> `deliver_to_requester`, `escalate` -> `deliver_to_requester_cc_marcom`.

**Why this is an agent and not a function.** It's named in the agent_trace as a discrete step with structured I/O. In future phases it becomes a real agent that actually dispatches assets via Slack/email/Marcom asset library. For the submission, it's exposed as part of the multi-agent topology because the verdict-driven path decision is itself a piece of system behaviour the judges should be able to observe.

---

## 5. Data flow and evidence

### 5.1 Trace structure

Every `POST /run` invocation produces a JSONL-style log file in `logs/` with structured events: RUN_START, AGENT_STEP, AGENT_HANDOFF events between every pair of agents, per-agent START/DONE events with token counts, and RUN_DONE summarising trace_steps and verdict. The `AGENT_HANDOFF` events make multi-agent collaboration observable line-by-line.

### 5.2 Case study — the disruptive pitch (`input_examples/04_disruptive_pitch.json`)

A deliberately stress-testing brief was sent:

> "Need a social post for our revolutionary new AI platform — make it bold and disruptive, we're going to crush the competition and dominate the healthcare AI market. Best-in-class technology that will revolutionize patient care."

The brief contains **five forbidden words** explicitly listed in brand Rule 1 (revolutionary, crush, dominate, best-in-class, revolutionize), plus combative framing inappropriate for a healthcare-CIO audience per brand Rule 2.

**System response:**

| Stage | Behaviour |
|---|---|
| Intake | Faithfully recorded user tone (`bold, disruptive, punchy, confident`) but proactively flagged 3 risks: overpromising, competitor alienation, regulatory misalignment |
| Search | Top-K retrieval returned Rule 10 (OpCo voice — M42 healthcare-precise), Rule 8 (audience register — CIOs expect evidence-aware), Rule 1 (forbidden-words list) |
| Brush | Did NOT comply with off-brand asks. Translated "crush the competition" into headline *"AI you can trust at the bedside"*. Replaced "revolutionize patient care" with "support safer, more consistent care". Mood shifted from user's bold/disruptive to `confident, evidence-led, forward-looking`. Brush's rationale field explicitly cited Rules 1, 8, 10 to justify the translation. |
| Validator | Scored 9/9 (voice:3, visual:3, audience:3). Reasoning cited Rules 1, 8, 10. Verdict: pass. |

This is the system working as designed: **rule retrieval prevented off-brand output at the draft stage rather than catching it at the validation stage.** The revision loop did not fire because there was nothing to revise — Brush self-corrected because the retrieved rules were authoritative in its prompt.

### 5.3 Coverage of stress tests

Four input/output pairs are saved, all passing 9/9:

| # | Brief | Audience | Notes |
|---|---|---|---|
| 01 | Project Atlas launch banner | M42 healthcare | Standard launch brief |
| 02 | "Punchy/disruptive" clinical AI social post | Hospital CIOs | Tone-pressure test |
| 03 | "Joyful celebration" pediatric oncology banner | Referring physicians | Sensitive-context test |
| 04 | "Revolutionary/crush/dominate" AI platform pitch | CIOs + CMOs | Forbidden-words stress test |

---

## 6. Technical implementation

### 6.1 Stack

| Layer | Choice |
|---|---|
| Runtime | Python 3.11 |
| HTTP framework | FastAPI + Uvicorn (mandatory POST /run on port 8000) |
| LLM client | `openai` SDK (OpenAI-protocol compatible with Compass) |
| HTTP transport | `httpx` 0.27.2 pinned (avoids 0.28+ incompatibility) |
| Orchestration | Custom Python in `run.py` — no framework dependency |
| Validation | Pydantic (via FastAPI) |
| Vector storage | JSON on disk (10 vectors × 3072 dim) |

### 6.2 Why no agent framework

The Agentathon allows custom Python. HALOsination's orchestration is ~150 lines of plain Python in `run.py` — every handoff, every error path, every log line is visible. A framework would have added a dependency, indirection, and a learning curve in exchange for code that already exists and works.

### 6.3 Compass integration

- **Endpoint:** `https://api.core42.ai/v1`
- **Auth:** `OPENAI_API_KEY` env variable, loaded from `.env` via `python-dotenv`
- **Models in use:** `gpt-4.1`, `gpt-5.1`, `text-embedding-3-large` — all three Compass model classes
- **Response format:** All chat agents use `response_format={"type": "json_object"}`

### 6.4 Error handling

Every agent returns either its expected dict or `{"error": "<reason>", "detail": ...}`. The orchestrator in `run.py` checks for `"error" in output` at every handoff:

- **Intake fails** -> return `status=degraded`, surface the error to the requester
- **Search fails** -> log warning, continue with empty retrieved_rules (Brush and Validator still work using priors only)
- **Brush fails** -> return `status=degraded` with the BRIEF preserved
- **Validator fails** -> return `status=degraded` with both BRIEF and DRAFT preserved
- **Revision re-score fails** -> fall back to the original draft + original verdict

The principle: **the system never crashes a request, even when an agent fails. It degrades, surfaces the failure in `agent_trace`, and lets a human decide.**

### 6.5 Determinism and reproducibility

- Validator runs at temperature 0.1 for consistency. Same draft -> same score (within tiny LLM variance).
- Validator total is computed locally from the scores object, never trusted from the model.
- Re-running `build_brand_index.py` after editing the guidelines is the only step needed to update the system.
- Logs are timestamped and structured, so trace replay is possible from the JSONL events alone.

---

## 7. HALO platform roadmap

Agent 01 (this submission) proves the architectural pattern. The same Intake -> Search -> Brush -> Validator -> Route spine extends to four more agents, all building toward the full HALO platform vision.

| Agent | Domain | What Brush drafts | What Validator scores |
|---|---|---|---|
| **02 Productivity** | Meetings, notes | Structured meeting notes, action items, decisions | Completeness / actionability / clarity |
| **03 Task & KPI** | Status updates | Structured tasks + KPI deltas + risks | SMART compliance / measurability / risk-awareness |
| **04 Social** | Connection matching | Connection suggestions + group recommendations | Relevance / diversity / privacy-respect |
| **05 Wellness** | Self check-ins | Care-appropriate response + resources + (anonymized) signals | Care language / resource match / signal anonymization |

**Phase 7+ (post-submission, if selected for incubation):**
- Real delivery via Slack DM / Marcom asset library write
- H-MEM integration for cross-session memory (learn from accepted/rejected outputs)
- Image rendering via `gpt-image-1`
- Per-OpCo brand index overrides (M42 rules don't leak into Core42 work)
- M365 / Oracle / OneHub integrations for live employee data
- Analytics dashboard for brand drift across OpCos

---

## 8. Submission compliance checklist

Verified against the G42 Agentathon disqualification list:

- [x] Standard execution interface — FastAPI `POST /run` on port 8000
- [x] No manual setup required — `pip install -r requirements.txt && python run.py`
- [x] No hardcoded outputs — every response is the result of live Compass calls visible in logs
- [x] `metadata.json` present and conformant
- [x] Evidence of multi-agent behaviour in logs — `AGENT_HANDOFF` events between every pair of agents
- [x] Compass API connection in submitted version — all four agents call `https://api.core42.ai/v1`
- [x] No API keys committed — `.env` excluded by `.gitignore`; `.env.example` template only
- [x] Submission can run as required — verified with all four input examples

Plus the submission artifacts:

- [x] GitHub repository (private until judging)
- [x] README.md with setup, env vars, run instructions
- [x] requirements.txt with pinned versions
- [x] >=3 input_examples (4 saved)
- [x] >=3 output_examples (4 saved)
- [x] logs/ populated with real agent interaction traces
- [x] Architecture documentation (this document)
- [x] Optional UI on port 8001 (live demo of all 5 agents collaborating)

---

## 9. Acknowledgements

- The agentic-pairings pattern (Proposer <-> Critic) introduced during the 21 May programme check-in. HALOsination's revision loop is a direct application of that pattern.
- Brand-guidelines wording is loosely modelled on common enterprise-technology brand patterns. No confidential G42 material is included in the repository.
