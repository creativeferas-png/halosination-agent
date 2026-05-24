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

# Import agents after .env is loaded
from app.intake_agent import run_intake
from app.brush_agent import run_brush

# Configure logging
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

app = FastAPI(title="HALOsination Brand & Brief Agent", version="0.3.0")


class RunRequest(BaseModel):
    request: str
    context: dict | None = None


class RunResponse(BaseModel):
    status: str
    use_case_id: str
    output: dict
    agent_trace: list


@app.get("/")
def health():
    return {"status": "ok", "service": "HALOsination Brand & Brief Agent"}


@app.post("/run", response_model=RunResponse)
def run(payload: RunRequest):
    """
    HALOsination multi-agent pipeline.

    Phase 3 status:
      [x] Intake agent — real Compass call (GPT-4.1)
      [x] Brush agent — real Compass call (GPT-5.1)
      [ ] Validator agent — placeholder (Phase 4)
      [ ] Route agent — placeholder (Phase 5)
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

    # ----- Agent 2: Brush (real handoff from Intake) -----
    logger.info(f"AGENT_HANDOFF | from=Intake | to=Brush | asset_type={brief.get('asset_type')}")
    logger.info("AGENT_STEP | agent=Brush | action=invoke")
    draft = run_brush(brief)
    trace.append({
        "agent": "Brush",
        "action": "draft_asset",
        "input_brief_summary": {
            "asset_type": brief.get("asset_type"),
            "audience": brief.get("audience"),
            "tone_hints": brief.get("tone_hints"),
        },
        "output": draft,
        "status": "error" if "error" in draft else "ok",
    })

    if "error" in draft:
        logger.warning(f"RUN_DEGRADED | brush_failed | {draft.get('error')}")
        return RunResponse(
            status="degraded",
            use_case_id="13",
            output={
                "message": "Brush agent failed to produce a draft asset.",
                "brief": brief,
                "detail": draft,
            },
            agent_trace=trace,
        )

    # ----- Agents 3-4: Validator + Route (placeholders for Phase 4-5) -----
    trace.append({
        "agent": "Validator",
        "action": "placeholder",
        "note": "Phase 4 will wire rubric-based scoring (brand voice / visual spec / audience fit, 0-3 x3) with revision loop.",
    })
    trace.append({
        "agent": "Route",
        "action": "placeholder",
        "note": "Phase 5 will route final asset to requester (and CC Marcom if Validator score < 7).",
    })

    logger.info(f"RUN_DONE | status=success | trace_steps={len(trace)}")
    return RunResponse(
        status="success",
        use_case_id="13",
        output={
            "brief": brief,
            "draft": draft,
            "next_step": "Validator agent will score this draft against brand rubric (Phase 4).",
        },
        agent_trace=trace,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
