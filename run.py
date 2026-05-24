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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from app.intake_agent import run_intake
from app.search_agent import run_search
from app.brush_agent import run_brush
from app.validator_agent import run_validator, run_brush_revision, PASS_THRESHOLD

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

app = FastAPI(title="HALOsination Brand & Brief Agent", version="0.5.0")

# Allow the optional UI on port 8001 to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    HALOsination multi-agent pipeline with retrieval-grounded drafting.

    Pipeline:
      Intake -> Search -> Brush -> Validator
        if Validator.verdict == "pass"   -> Route -> deliver
        if Validator.verdict == "revise" -> Brush revises ONCE -> Validator re-scores
          if still failing               -> escalate to human (route + CC Marcom)

    Phase 5: Search agent grounds Brush in retrieved brand rules via
    text-embedding-3-large. The retrieved rules also accompany the draft
    into Validator, giving the Critic concrete brand evidence to score against.
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
            status="degraded", use_case_id="13",
            output={"message": "Intake agent failed.", "detail": brief},
            agent_trace=trace,
        )

    # ----- Agent 2: Search (NEW: retrieve brand rules) -----
    logger.info(f"AGENT_HANDOFF | from=Intake | to=Search | asset_type={brief.get('asset_type')}")
    logger.info("AGENT_STEP | agent=Search | action=retrieve_brand_rules")
    search_result = run_search(brief, top_k=3)
    trace.append({
        "agent": "Search",
        "action": "retrieve_brand_rules",
        "output": search_result,
        "status": "error" if "error" in search_result else "ok",
    })
    if "error" in search_result:
        # Search failure is non-fatal — Brush can still produce output without retrieved rules.
        # We log it as a degradation but continue with empty rules.
        logger.warning(f"SEARCH_DEGRADED | continuing without retrieved rules | {search_result.get('error')}")
        retrieved_rules = []
    else:
        retrieved_rules = search_result.get("retrieved_rules", [])

    # ----- Agent 3: Brush (initial draft, now grounded in retrieved rules) -----
    logger.info(f"AGENT_HANDOFF | from=Search | to=Brush | rules_retrieved={len(retrieved_rules)}")
    logger.info("AGENT_STEP | agent=Brush | action=invoke")
    draft = run_brush(brief, retrieved_rules=retrieved_rules)
    trace.append({
        "agent": "Brush",
        "action": "draft_asset",
        "rules_used": [r["rule_id"] for r in retrieved_rules],
        "output": draft,
        "status": "error" if "error" in draft else "ok",
    })
    if "error" in draft:
        logger.warning(f"RUN_DEGRADED | brush_failed | {draft.get('error')}")
        return RunResponse(
            status="degraded", use_case_id="13",
            output={"message": "Brush agent failed.", "brief": brief, "detail": draft},
            agent_trace=trace,
        )

    # ----- Agent 4: Validator (first scoring, sees the same retrieved rules) -----
    logger.info(f"AGENT_HANDOFF | from=Brush | to=Validator | round=1")
    logger.info("AGENT_STEP | agent=Validator | action=score_initial")
    verdict_v1 = run_validator(brief, draft, is_revision=False, retrieved_rules=retrieved_rules)
    trace.append({
        "agent": "Validator",
        "action": "score_initial",
        "output": verdict_v1,
        "status": "error" if "error" in verdict_v1 else "ok",
    })
    if "error" in verdict_v1:
        logger.warning(f"RUN_DEGRADED | validator_failed | {verdict_v1.get('error')}")
        return RunResponse(
            status="degraded", use_case_id="13",
            output={"message": "Validator failed.", "brief": brief, "draft": draft, "detail": verdict_v1},
            agent_trace=trace,
        )

    final_draft = draft
    final_verdict = verdict_v1
    revision_attempted = False

    # ----- Revision loop: if Validator says revise, Brush revises ONCE -----
    if verdict_v1.get("verdict") == "revise":
        revision_attempted = True
        fix = verdict_v1.get("fix", "")
        logger.info(f"REVISION_TRIGGERED | total={verdict_v1.get('total')}/9 | fix={fix[:80]!r}")
        logger.info(f"AGENT_HANDOFF | from=Validator | to=Brush | action=revise")
        logger.info("AGENT_STEP | agent=Brush | action=revise")
        revised_draft = run_brush_revision(brief, draft, fix, retrieved_rules=retrieved_rules)
        trace.append({
            "agent": "Brush",
            "action": "revise",
            "fix_applied": fix,
            "output": revised_draft,
            "status": "error" if "error" in revised_draft else "ok",
        })

        if "error" not in revised_draft:
            logger.info(f"AGENT_HANDOFF | from=Brush | to=Validator | round=2")
            logger.info("AGENT_STEP | agent=Validator | action=score_revised")
            verdict_v2 = run_validator(brief, revised_draft, is_revision=True, retrieved_rules=retrieved_rules)
            trace.append({
                "agent": "Validator",
                "action": "score_revised",
                "output": verdict_v2,
                "status": "error" if "error" in verdict_v2 else "ok",
            })
            if "error" not in verdict_v2:
                final_draft = revised_draft
                final_verdict = verdict_v2
            else:
                logger.warning("RUN_PARTIAL | rescore_failed | falling back to original draft")

    # ----- Determine delivery path -----
    verdict_label = final_verdict.get("verdict", "unknown")
    if verdict_label == "pass":
        delivery_path = "deliver_to_requester"
        message = "Draft passed brand rubric. Ready to deliver."
    elif verdict_label == "escalate":
        delivery_path = "deliver_to_requester_cc_marcom"
        message = "Draft still below threshold after one revision. Escalating to human review (Marcom)."
    else:
        delivery_path = "deliver_to_requester_cc_marcom"
        message = f"Verdict: {verdict_label}. Routing with human review."

    # ----- Agent 5: Route (placeholder, driven by Validator's verdict) -----
    trace.append({
        "agent": "Route",
        "action": "decide_delivery_path",
        "delivery_path": delivery_path,
        "driven_by_verdict": verdict_label,
        "note": "Phase 6 will wire actual delivery (email/Slack/Marcom asset library).",
    })

    logger.info(
        f"RUN_DONE | status=success | verdict={verdict_label} | "
        f"revision_attempted={revision_attempted} | rules_retrieved={len(retrieved_rules)} | "
        f"trace_steps={len(trace)}"
    )

    return RunResponse(
        status="success",
        use_case_id="13",
        output={
            "brief": brief,
            "retrieved_rules": retrieved_rules,
            "final_draft": final_draft,
            "verdict": final_verdict,
            "revision_attempted": revision_attempted,
            "delivery": {
                "path": delivery_path,
                "message": message,
            },
        },
        agent_trace=trace,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
