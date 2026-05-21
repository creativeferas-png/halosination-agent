"""
HALO Brand & Brief Agent — Entry Point
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

# Load environment variables from .env
load_dotenv()

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

app = FastAPI(title="HALO Brand & Brief Agent", version="0.1.0")


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
    return {"status": "ok", "service": "HALO Brand & Brief Agent"}


@app.post("/run", response_model=RunResponse)
def run(payload: RunRequest):
    """
    Mandatory entry point. Accepts an employee request and routes it
    through the HALO multi-agent system.

    Phase 1: returns a placeholder response so the interface is
    verifiable. Phase 2+ wires in the real LangGraph agents.
    """
    logger.info(f"Received request: {payload.request}")

    # Placeholder agent trace — will be replaced with real LangGraph trace
    trace = [
        {"agent": "Intake", "action": "received", "input": payload.request},
        {"agent": "Validator", "action": "placeholder_check", "result": "ok"},
    ]
    for step in trace:
        logger.info(f"AGENT_STEP | {json.dumps(step)}")

    response = RunResponse(
        status="success",
        use_case_id="1",
        output={
            "message": "HALO scaffolding online. Real agents wired in Phase 2.",
            "request_echo": payload.request,
        },
        agent_trace=trace,
    )
    logger.info(f"Completed request: {response.status}")
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
