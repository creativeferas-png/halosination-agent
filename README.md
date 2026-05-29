# HALO — One AI platform for every employee

**G42 Agentathon submission — Use Case #13 Media Content Generation**
**Team:** HALOsination (solo build — Feras Assil)

> **Tagline:** One AI platform. Every employee. Work smarter, connect deeper, live better.

---

## What's in the repo

This submission ships **the platform**, not a single agent. Five specialist agents plus the platform layer that ties them together:

| | What it does | Status |
|---|---|---|
| **Agent 01** — Brand & Brief | On-brand content from plain-English requests | LIVE |
| **Agent 02** — Productivity | Meeting transcripts to structured summaries | LIVE |
| **Agent 03** — Task & KPI | Status updates to trackable structure | LIVE |
| **Agent 04** — Social | Employee profile to connection suggestions | LIVE |
| **Agent 05** — Wellness | Self check-ins to care-appropriate responses (demo artifact — see ARCHITECTURE.md section 5) | LIVE |
| **Router** | Free-form request to right agent, with safety bias | LIVE |
| **Execution** | Agent 01 output to real downloadable branded asset | LIVE |
| **Aggregate dashboard** | Cross-agent signals to privacy-by-design HR view | LIVE |

**Three user surfaces** (see Setup + Run below):

- `http://localhost:8001/` — tabbed UI, one panel per agent (architecture-transparent demo)
- `http://localhost:8001/halo` — unified single-screen chat (product-feel demo)
- `http://localhost:8001/dashboard-ui` — aggregate wellbeing dashboard

**One architectural pattern, five domains.** Every agent shares the same Intake -> Search -> Brush -> Validator -> Route spine. One generalised Search agent serves all five. The agents differ in their policies and rubrics; the substrate is shared. See **ARCHITECTURE.md** for the full design rationale, safety/ethics framing, and the built-vs-roadmap table.

---

## A note on Docker

This submission runs as a **local Python application** — no Docker required. The Setup section below uses `venv` + `pip install -r requirements.txt`, which is the same install path the official Agentathon checklist describes when Docker is not provided. The rubric's Docker-related disqualification rule only applies *when Docker is required for evaluation*; since HALO does not include a Dockerfile, the local Python path is the canonical install.

To run locally:

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python run.py    # API on port 8000
    python run_ui.py # UI on port 8001 (separate window)

A Dockerfile is on the roadmap (see ARCHITECTURE.md section 6) but is intentionally out of scope for the demo submission.

---

## Setup

    # 1. Create and activate a virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # 2. Install dependencies
    pip install -r requirements.txt

    # 3. Configure environment variables
    cp .env.example .env
    # Edit .env: add OPENAI_API_KEY and set OPENAI_BASE_URL=https://api.core42.ai/v1

    # 4. Build the 5 policy indexes (one-time)
    python scripts/build_policy_index.py data/brand_index.md       data/brand_index.json
    python scripts/build_policy_index.py data/meeting_policy.md    data/meeting_policy_index.json
    python scripts/build_policy_index.py data/task_policy.md       data/task_policy_index.json
    python scripts/build_policy_index.py data/social_policy.md     data/social_policy_index.json
    python scripts/build_policy_index.py data/wellness_policy.md   data/wellness_policy_index.json

## Run

Two windows:

    # Window 1 — API on port 8000
    python run.py

    # Window 2 — UI on port 8001
    python run_ui.py

Then open `http://localhost:8001/halo` for the product-feel demo, or `http://localhost:8001/` for the architecture-transparent tabbed view.

## API endpoints

All on port 8000:

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Compass connectivity verification (returns ok + model + base_url) |
| POST | /run | Agent 01 (Brand & Brief) — the mandatory submission endpoint |
| POST | /run_meeting | Agent 02 (Productivity) |
| POST | /run_status | Agent 03 (Task & KPI) |
| POST | /run_social | Agent 04 (Social) |
| POST | /run_wellness | Agent 05 (Wellness) |
| POST | /route | Unified router: classify + dispatch + run, in one call |
| POST | /render_asset | Render Agent 01 output to a downloadable HTML asset |
| GET | /dashboard | Aggregate wellbeing dashboard data |

### Smoke test

The mandatory submission entry point:

    curl -X POST http://localhost:8000/run \
      -H "Content-Type: application/json" \
      -d '{"request": "Create a launch announcement banner for Project Atlas, healthcare audience"}'

The unified router (the platform front door):

    curl -X POST http://localhost:8000/route \
      -H "Content-Type: application/json" \
      -d '{"request_text": "Write me a launch banner for our new cardiology app, going to hospital partners next week"}'

## Models

All LLM operations via Compass:

- `gpt-4.1` — Intake, Validator, Router
- `gpt-5.1` — Brush (creative generation)
- `text-embedding-3-large` — Search (3072-dim policy retrieval)

## Repo map

    halo-agent/
    |-- app/
    |   |-- intake_agent.py + search_agent.py + brush_agent.py + validator_agent.py   (Agent 01)
    |   |-- agent02..05/   (intake, search, brush, validator per agent)
    |   |-- router.py            (unified front door)
    |   |-- asset_render.py      (Agent 01 execution)
    |   |-- aggregator.py        (cross-agent signal aggregation)
    |   `-- dashboard_synth.py   (illustrative team data, clearly labelled)
    |-- data/                    (5 policy docs + 5 indexes)
    |-- scripts/build_policy_index.py
    |-- input_examples/agent01..05/   (13 sample inputs)
    |-- output_examples/agent01..05/  (13 matching outputs, all 9/9)
    |-- ui/index.html + halo.html + dashboard.html
    |-- run.py                   (FastAPI app — 9 endpoints)
    |-- run_ui.py
    |-- README.md
    |-- ARCHITECTURE.md          (full platform doc — design rationale + safety + roadmap)
    |-- metadata.json            (use_case_id "13")
    `-- .env                     (Compass API key, gitignored)

---

## A note on the Compass URL

The official Agentathon checklist lists `https://compass.core42.ai/v1` as the Compass base URL. That URL serves the **Compass web portal** (the page where you log in to view your API key), not the API itself. The actual API endpoint that returns model lists and serves completions is `https://api.core42.ai/v1`, which is what this submission uses.

If a judge runs the checklist's verification curl literally against `compass.core42.ai/v1/models`, the response will be HTML (the portal page). To verify this submission's Compass integration cleanly, use the `/health` endpoint:

    curl http://localhost:8000/health

This calls Compass directly through whatever URL is configured in `.env`. A working integration returns:

    {"status":"ok","compass_connection":"ok","model":"gpt-4.1","base_url":"https://api.core42.ai/v1","reply_preview":"ok"}

---

## Important — Wellness agent caveat

Agent 05 (Wellness) handles self check-ins including potential crisis signals. **It is a demo artifact.** A 9/9 from an automated critic is not clinical validation. Real deployment of crisis-handling requires human clinical review, real escalation pathways, and duty-of-care sign-off. The caveat is shown in the UI alongside every Wellness response and detailed in **ARCHITECTURE.md section 5**.

If you are using this code as a starting point for anything that would touch a real person in distress, please read ARCHITECTURE.md section 5 first.
