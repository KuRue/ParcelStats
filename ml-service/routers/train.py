from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from threading import Lock
from services.trainer import ModelTrainer
from services.pattern_miner import mine_patterns
from services.agent.research import RouteResearchAgent
from services.timeutil import utcnow

router = APIRouter()
trainer = ModelTrainer()
_research_lock = Lock()
_research_job = {
    "state": "idle",
    "action": None,
    "phase": "idle",
    "message": "No route research has run since the ML service started.",
    "current": 0,
    "total": 0,
    "candidates": 0,
    "created": 0,
    "skipped": 0,
    "failed": 0,
    "current_lane": None,
    "recent_results": [],
    "started_at": None,
    "updated_at": None,
    "completed_at": None,
}


class LaneResearchRequest(BaseModel):
    carrier_slug: str
    origin_country: str
    dest_country: str


@router.post("/trigger")
async def trigger_training(background_tasks: BackgroundTasks):
    background_tasks.add_task(_train)
    return {"status": "training_started"}


@router.post("/mine-patterns")
async def trigger_mining(background_tasks: BackgroundTasks):
    background_tasks.add_task(_mine)
    return {"status": "mining_started"}


@router.post("/research-lane")
async def trigger_research(req: LaneResearchRequest):
    agent = RouteResearchAgent()
    if not agent.available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI not configured. Set OPENAI_BASE_URL and OPENAI_API_KEY."
        )
    _start_research_job(
        "research_lane",
        f"Researching {req.carrier_slug} {req.origin_country}→{req.dest_country}.",
    )
    _update_research_job({
        "phase": "researching_lane",
        "current": 1,
        "total": 1,
        "lane": {
            "carrier": req.carrier_slug,
            "origin": req.origin_country,
            "dest": req.dest_country,
        },
    })
    try:
        result = agent.research_and_store(
            req.carrier_slug,
            req.origin_country,
            req.dest_country,
        )
        _update_research_job({
            "phase": "lane_complete",
            "current": 1,
            "total": 1,
            "result": result,
        })
        _finish_research_job(
            "failed" if result.get("error") else "completed",
            result.get("error")
            or result.get("message")
            or f"Finished {req.carrier_slug} {req.origin_country}→{req.dest_country}.",
        )
    except Exception as e:
        _finish_research_job("failed", str(e))
        raise
    return result


@router.post("/research-missing")
async def trigger_research_missing(background_tasks: BackgroundTasks):
    # Many lanes x LLM latency: run in the background, poll /research-status
    agent = RouteResearchAgent()
    if not agent.available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI not configured. Set OPENAI_BASE_URL and OPENAI_API_KEY."
        )
    if _research_job_running():
        return {"status": "research_already_running", "job": _research_job_snapshot()}
    _start_research_job("research_missing", "Scanning active shipments for missing route lanes.")
    background_tasks.add_task(_fill_missing_lanes_background)
    return {"status": "research_missing_started", "job": _research_job_snapshot()}


@router.get("/research-status")
async def research_status():
    agent = RouteResearchAgent()
    from database.connection import SessionLocal
    from database.models import RoutePattern, Shipment
    from services.knowledge import country_from_region

    db = SessionLocal()
    try:
        total_patterns = db.query(RoutePattern).count()
        llm_patterns = db.query(RoutePattern).filter(RoutePattern.match_score < 0.5).count()
        mined_patterns = total_patterns - llm_patterns

        active_shipments = db.query(Shipment).filter(
            Shipment.delivered_at.is_(None),
            Shipment.origin_name.isnot(None),
            Shipment.dest_name.isnot(None),
        ).all()

        covered = set()
        for rp in db.query(RoutePattern.carrier_id, RoutePattern.origin_country, RoutePattern.dest_country).all():
            covered.add((rp.carrier_id, rp.origin_country, rp.dest_country))

        missing = 0
        for s in active_shipments:
            oc = country_from_region(s.origin_name or "")
            dc = country_from_region(s.dest_name or "")
            if oc == "??" or dc == "??":
                continue
            if (s.carrier_id, oc, dc) not in covered:
                missing += 1
    finally:
        db.close()

    return {
        "agent_available": agent.available,
        "model": agent.model if agent.available else None,
        "patterns": {
            "total": total_patterns,
            "mined": mined_patterns,
            "llm_researched": llm_patterns,
        },
        "missing_lanes": missing,
        "job": _research_job_snapshot(),
    }


@router.get("/status")
async def training_status():
    from database.connection import SessionLocal
    from database.models import ModelVersion

    db = SessionLocal()
    try:
        active = (
            db.query(ModelVersion)
            .filter(ModelVersion.is_active)
            .all()
        )
        return {
            "models": [
                {
                    "name": m.model_name,
                    "version": m.version,
                    "metrics": m.metrics,
                    "trained_at": m.trained_at.isoformat(),
                }
                for m in active
            ]
        }
    finally:
        db.close()


def _train():
    result = trainer.train_eta_model()
    return result


def _mine():
    result = mine_patterns()
    return result


def _now_iso() -> str:
    return utcnow().isoformat() + "Z"


def _research_job_snapshot() -> dict:
    with _research_lock:
        return {
            **_research_job,
            "current_lane": (
                dict(_research_job["current_lane"])
                if _research_job.get("current_lane")
                else None
            ),
            "recent_results": [dict(row) for row in _research_job["recent_results"]],
        }


def _research_job_running() -> bool:
    with _research_lock:
        return _research_job["state"] == "running"


def _start_research_job(action: str, message: str):
    now = _now_iso()
    with _research_lock:
        _research_job.update({
            "state": "running",
            "action": action,
            "phase": "starting",
            "message": message,
            "current": 0,
            "total": 0,
            "candidates": 0,
            "created": 0,
            "skipped": 0,
            "failed": 0,
            "current_lane": None,
            "recent_results": [],
            "started_at": now,
            "updated_at": now,
            "completed_at": None,
        })


def _finish_research_job(state: str, message: str):
    now = _now_iso()
    with _research_lock:
        _research_job.update({
            "state": state,
            "phase": "complete" if state == "completed" else "failed",
            "message": message,
            "current_lane": None,
            "updated_at": now,
            "completed_at": now,
        })


def _summarize_research_result(result: dict) -> dict:
    return {
        "carrier": result.get("carrier"),
        "origin": result.get("origin"),
        "dest": result.get("dest"),
        "created": bool(result.get("created")),
        "error": result.get("error"),
        "message": result.get("message"),
        "stops_count": result.get("stops_count"),
        "pattern_id": result.get("pattern_id"),
    }


def _update_research_job(update: dict):
    now = _now_iso()
    phase = update.get("phase")
    with _research_lock:
        _research_job["phase"] = phase or _research_job["phase"]
        _research_job["updated_at"] = now
        if update.get("message"):
            _research_job["message"] = update["message"]

        if phase == "lanes_identified":
            _research_job["total"] = int(update.get("total") or 0)
            _research_job["candidates"] = int(update.get("candidates") or 0)
            _research_job["current"] = 0
        elif phase == "researching_lane":
            _research_job["current"] = int(update.get("current") or 0)
            _research_job["total"] = int(update.get("total") or _research_job["total"])
            _research_job["current_lane"] = update.get("lane")
        elif phase == "lane_complete":
            result = update.get("result") or {}
            summary = _summarize_research_result(result)
            if not summary["carrier"] and update.get("lane"):
                summary.update(update["lane"])
            _research_job["recent_results"] = (
                [summary] + _research_job["recent_results"]
            )[:6]
            _research_job["current"] = int(update.get("current") or _research_job["current"])
            _research_job["total"] = int(update.get("total") or _research_job["total"])
            _research_job["current_lane"] = update.get("lane")
            if result.get("created"):
                _research_job["created"] += 1
            elif result.get("error"):
                _research_job["failed"] += 1
            else:
                _research_job["skipped"] += 1


def _fill_missing_lanes_background():
    agent = RouteResearchAgent()
    try:
        result = agent.fill_missing_lanes(progress_callback=_update_research_job)
        researched = result.get("researched", 0)
        candidates = result.get("candidates", 0)
        _finish_research_job(
            "completed",
            f"Route research finished: {researched} new pattern"
            f"{'' if researched == 1 else 's'} from {candidates} candidate lane"
            f"{'' if candidates == 1 else 's'}.",
        )
    except Exception as e:
        _finish_research_job("failed", f"Route research failed: {e}")
        raise
