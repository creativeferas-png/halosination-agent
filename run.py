"""
HALOsination Brand & Brief Agent — Entry Point
Mandatory POST /run endpoint on port 8000 per G42 Agentathon spec.
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env BEFORE importing agents
load_dotenv()

# Import agents after .env is loaded so the OpenAI client gets the right keys
from app.intake_agent import run_intake

# Configure logging — writes to logs/ for multi-agent collaboration evidence
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("halo")

app = FastAPI(title="HALOsination Brand & Brief Agent", version="0.2.0")


class RunRequest(BaseModel):
    """Input schema for POST /run."""
    request: str
    context: dict | None = None


class RunResponse(BaseModel):
    """Output schema for POST /run."""
    status: str
    use_case_id: str
    output: dict
    agent_trace: list


@app.get("/")
def health():
    """Simple health check."""
    return {"status": "ok", "service": "HALOsination Brand & Brief Agent"}


@app.post("/run", response_model=RunResponse)
def run(payload: RunRequest):
    """
    Mandatory entry point. Accepts an employee request and routes it
    through the HALOsination multi-agent system.

    Phase 2: Intake agent is live (real Compass call → structured BRIEF).
    Downstream agents (Search, Brush, Validator, Route) are still placeholders.
    """
    logger.info(f"RUN_START | request={payload.request[:100]!r}")
    trace = []

    # ----- Agent 1: Intake -----
    logger.info("AGENT_STEP | agent=Intake | action=invoke")
    brief = run_intake(payload.request)
    trace.append({
        "agent": "Intake",
        "action": "parse_request",
        "input_preview": payload.request[:120],
        "output": brief,
        "status": "error" if "error" in brief else "ok",
    })

    if "error" in brief:
        logger.warning(f"RUN_DEGRADED | intake_failed | {brief.get('error')}")
        return RunResponse(
            status="degraded",
            use_case_id="13",
            output={
                "message": "Intake agent failed to produce a structured brief.",
                "detail": brief,
            },
            agent_trace=trace,
        )

    # ----- Agents 2-5 (Search / Brush / Validator / Route): placeholders for now -----
    trace.append({
        "agent": "Brush",
        "action": "placeholder",
        "note": "Phase 3 will wire real Compass call for asset generation.",
    })
    trace.append({
        "agent": "Validator",
        "action": "placeholder",
        "note": "Phase 4 will wire rubric-based scoring with revision loop.",
    })

    logger.info(f"RUN_DONE | status=success | trace_steps={len(trace)}")
    return RunResponse(
        status="success",
        use_case_id="13",
        output={
            "brief": brief,
            "next_step": "Brush agent will draft asset from this brief (Phase 3).",
        },
        agent_trace=trace,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
