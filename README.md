# HALO — Brand & Brief Agent

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
