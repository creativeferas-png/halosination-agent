# HALO — Agent 01: Brand & Brief Agent

**G42 Agentathon submission — Use Case #13 Media Content Generation**
**Team:** HALOsination (solo build — Feras Assil)

---

## About HALO

**HALO** is M42's vision for a single AI-powered employee platform — connecting M365, Oracle, and OneHub so every employee can **work smarter, connect deeper, and live better** through one natural conversation.

HALO is structured as 5 agents across 3 layers:

| # | Agent | Layer | Status |
|---|---|---|---|
| **01** | **Brand & Brief** | Work | This submission |
| 02 | Productivity (meetings, notes) | Work | In build |
| 03 | Task & KPI | Work | In build |
| 04 | Social (connection, interest matching) | Social | In build |
| 05 | Wellness (check-ins, signals) | Wellness | In build |

The agents share a single architectural pattern — **Intake -> Search -> Brush -> Validator -> Route** — applied to 5 different problem domains. This pattern is fully proven end-to-end in Agent 01 and is the template for Agents 02-05.

---

## Agent 01 — Brand & Brief

Lets any G42-group employee request, rebrand, or commission on-brand assets in plain language. The 5 agents enforce brand compliance **at the point of creation**, with the Validator citing specific brand rule IDs in every verdict.

### Architecture

| Agent | Role | Model |
|---|---|---|
| **Intake** | Parses the plain-language request into a structured BRIEF | GPT-4.1 |
| **Search** | Retrieves the top-3 most relevant brand rules from the brand index | text-embedding-3-large |
| **Brush** | Drafts copy + visual spec, grounded in the retrieved brand rules | GPT-5.1 |
| **Validator** | Scores the draft 0-9 on a 3x3 brand rubric, can trigger one revision | GPT-4.1 |
| **Route** | Policy-driven delivery path based on the verdict | (no LLM) |

The Validator -> Brush revision loop is hard-capped at one attempt, then escalates to human review. See **ARCHITECTURE.md** for the full system spec including agent specifications, data flow, case studies, and roadmap.

---

## Setup

    # 1. Create and activate a virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # 2. Install dependencies
    pip install -r requirements.txt

    # 3. Configure environment variables
    cp .env.example .env
    # Edit .env and add your Compass API key

    # 4. Build the brand rules index (one-time)
    python scripts/build_brand_index.py

## Environment variables

| Variable | Description |
|---|---|
| OPENAI_API_KEY | Your Compass API key |
| OPENAI_BASE_URL | Compass endpoint — https://api.core42.ai/v1 |

## Running

Two servers, two ports:

    # Terminal 1 — mandatory API on port 8000
    python run.py

    # Terminal 2 — optional UI on port 8001
    python run_ui.py

Then open **http://localhost:8001** in your browser for the demo interface, or hit the mandatory API directly:

    curl -X POST http://localhost:8000/run \
      -H "Content-Type: application/json" \
      -d @input_examples/01_project_atlas_banner.json

## Compass models in use

- gpt-4.1 — Intake (parsing), Validator (scoring), revision drafting
- gpt-5.1 — Brush (creative drafting at higher temperature)
- text-embedding-3-large — Search (retrieval over the brand rules index)

All three Compass model classes are exercised end-to-end per request.

## Project structure

    halo-agent/
    ├── app/                          # core agent logic
    │   ├── intake_agent.py
    │   ├── search_agent.py
    │   ├── brush_agent.py
    │   └── validator_agent.py
    ├── data/
    │   ├── brand_guidelines.md       # 10 brand rules
    │   └── brand_index.json          # pre-computed embeddings
    ├── scripts/
    │   └── build_brand_index.py      # one-time embedding script
    ├── ui/index.html                 # optional demo UI
    ├── input_examples/               # 4 sample inputs
    ├── output_examples/              # 4 sample outputs (all 9/9)
    ├── logs/                         # auto-generated agent traces
    ├── run.py                        # MANDATORY POST /run on port 8000
    ├── run_ui.py                     # optional UI on port 8001
    ├── requirements.txt
    ├── metadata.json
    ├── .env.example
    ├── ARCHITECTURE.md               # full system documentation
    └── README.md                     # this file

## Sample inputs/outputs

Four stress-test pairs are saved, all scoring **9/9** on the 3x3 rubric (brand_voice / visual_spec / audience_fit) with rule_ids cited by the Validator:

1. Project Atlas launch banner for healthcare audiences
2. "Punchy/disruptive" clinical AI social post for hospital CIOs (tone-pressure test)
3. Pediatric oncology imaging service banner (sensitive-context test)
4. "Revolutionary/crush/dominate" AI platform pitch (forbidden-words stress test)

See input_examples/ and output_examples/ for the full pairs.# HALO — Brand & Brief Agent

**G42 Agentathon submission — Use Case #1 (Multi-Agent Office)**

HALO Brand & Brief Agent is a multi-agent system that lets any G42 employee request, rebrand, or commission on-brand assets in plain language. Marcom owns the brand source-of-truth; the agents serve the whole group.

## Agents

| Agent | Role |
|---|---|
| **Intake** | Parses the employee request and structures the brief |
| **Search** | Retrieves on-brand assets and brand guidelines (embeddings) |
| **Brush** | Generates or adapts content to brand specifications |
| **Route** | Routes the finalised brief or asset to the correct owner |
| **Validator** | Scores output against brand rules, triggers revision loop |

Agents collaborate through a LangGraph state machine. The Validator can return work to the Brush agent for iterative revision (planner ↔ critic ↔ executor pattern).

## Setup

\`\`\`bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env and add your Compass API key
\`\`\`

## Environment variables

| Variable | Description |
|---|---|
| \`OPENAI_API_KEY\` | Your Compass API key |
| \`OPENAI_BASE_URL\` | Compass endpoint — \`https://api.core42.ai/v1\` |

## Running the agent

\`\`\`bash
python run.py
\`\`\`

The server starts on **port 8000** and exposes the mandatory \`POST /run\` endpoint.

## Testing

\`\`\`bash
curl -X POST http://localhost:8000/run \\
  -H "Content-Type: application/json" \\
  -d '{"request": "Create a launch announcement banner for Project Atlas, healthcare audience"}'
\`\`\`

## Models

Calls Compass for all LLM operations:

- \`gpt-4.1\` — Intake, Route, Validator
- \`gpt-5.1\` — Brush (creative generation)
- \`text-embedding-3-large\` — Search (asset retrieval)

## Submission structure

\`\`\`
halo-agent/
├── app/                 # core agent logic
├── data/                # brand guidelines, asset index
├── scripts/             # helper scripts
├── input_examples/      # sample inputs (≥3)
├── output_examples/     # sample outputs (≥3)
├── logs/                # agent-to-agent interaction traces
├── run.py               # MANDATORY entry point
├── requirements.txt
├── metadata.json
├── .env.example
└── README.md
\`\`\`
