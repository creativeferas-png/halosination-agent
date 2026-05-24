# HALOsination — Architecture

> **G42 Agentathon submission — Use Case #13 Media Content Generation**
> Solo build by Feras Assil. Repo: `creativeferas-png/halosination-agent`.

---

## 1. Executive summary

HALOsination is a multi-agent system that lets any G42-group employee request, rebrand, or commission on-brand media assets in plain English — and ensures every output is verifiably on-brand before it leaves the system.

The pain point is real and operational: across G42, M42, Core42, Inception, and Mubadala Health, every OpCo produces assets daily — launch banners, social posts, internal announcements, clinical communications. Marcom owns the brand source-of-truth, but they cannot review every request from every team in every OpCo. So today, **off-brand assets ship**, and Marcom catches them after the fact (or doesn't catch them at all).

HALOsination inverts the workflow. Instead of post-hoc review, brand compliance is enforced **at the point of creation** by a chain of cooperating agents that retrieve the relevant brand rules, draft against them, and score the draft against the same rules before delivery. The Validator agent issues a structured 0–9 verdict citing specific rule IDs; below 7/9 triggers one revision attempt, then human escalation.

Concretely:

- 4 agents, all backed by Compass: Intake, Search, Brush, Validator (plus Route for delivery).
- 5 Compass calls per request on average: 1 embedding (Search) + up to 4 chat completions (Intake, Brush, Validator, optional revision).
- ~5–10 seconds end-to-end for a typical request.
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

### 3.1 High-level flow (Mermaid)

```mermaid
INDEX[(Brand Index<br/>10 rules × 3072-dim<br/>data/brand_index.json)]
### 6.5 Error handling and graceful degradation

Every agent returns either its expected dict or `{"error": "<reason>", "detail": ...}`. The orchestrator in `run.py` checks for `"error" in output` at every handoff:

- **Intake fails** → return `status=degraded`, surface the error to the requester (intake is unrecoverable without something to draft from)
- **Search fails** → log warning, continue with empty retrieved_rules (Brush and Validator still work, using priors only)
- **Brush fails** → return `status=degraded` with the BRIEF preserved (the requester can manually re-submit or escalate)
- **Validator fails** → return `status=degraded` with both BRIEF and DRAFT preserved (Marcom can review unscored)
- **Revision re-score fails** → fall back to the original draft + original verdict (don't penalise the requester for an LLM hiccup)

The principle is: **the system never crashes a request, even when an agent fails. It degrades, surfaces the failure in `agent_trace`, and lets a human decide.**

### 6.6 Determinism and reproducibility

- Validator runs at temperature 0.1 for consistency. Same draft → same score (within tiny LLM variance).
- Validator total is computed locally from the scores object, never trusted from the model.
- The brand index is a content hash of `brand_guidelines.md` at build time — re-running `build_brand_index.py` after editing the guidelines is the only step needed to update the system.
- Logs are timestamped and structured, so trace replay is possible from the JSONL events alone.

---

## 7. Limitations and roadmap

### 7.1 Current limitations

- **No image generation.** Brush produces a *visual spec* (concept, palette, composition) but does not call `gpt-image-1` to render the actual image. This is deliberate for the submission — the spec is more reusable than a single rendered image — but it's a natural Phase-6 addition.
- **Brand index is small.** 10 rules. Real Marcom-grade governance might index 50–200 rules including OpCo-specific overrides. The retrieval architecture scales straightforwardly (still well under a vector-DB threshold up to ~1k rules).
- **Single-revision loop.** The Validator → Brush loop is hard-capped at one revision, then escalates. For more complex briefs this might be too aggressive — but unbounded revision loops were a worse failure mode.
- **No persistent memory between sessions.** Each `POST /run` is stateless. H-MEM integration (per Sam's primitives) would let HALOsination learn from past requests across sessions — a credible Phase-7 enhancement.

### 7.2 Roadmap if selected for incubation

| Phase | Addition | Why it earns its place |
|---|---|---|
| 6 | Real delivery (Slack DM to requester, Marcom asset library write) | Closes the loop from request to delivered asset |
| 7 | H-MEM integration for cross-session memory | Lets HALOsination learn from accepted/rejected outputs |
| 8 | Image rendering via `gpt-image-1` | Demo-ready visual outputs, not just specs |
| 9 | Per-OpCo brand index overrides | M42-specific rules don't leak into Core42 work |
| 10 | Analytics dashboard for brand drift | Marcom sees, per OpCo per month, where briefs strain the brand |

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
- [x] ≥3 input_examples (4 saved)
- [x] ≥3 output_examples (4 saved)
- [x] logs/ populated with real agent interaction traces
- [x] Architecture documentation (this document)

---

## 9. Acknowledgements

- The agentic-pairings pattern (Proposer ↔ Critic, Context-Packer ↔ Actor) was introduced by Sam during the 21 May programme check-in. HALOsination's revision loop is a direct application of that pattern.
- The Meterless agentic primitives (H-MEM, Markovian Engine, World Model) were not integrated for the initial submission but are the natural extension points for cross-session memory, long-context handling, and shared world state respectively.
- Brand-guidelines wording is loosely modelled on common enterprise-technology brand patterns. No confidential G42 material is included in the repository.
