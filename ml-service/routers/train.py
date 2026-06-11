from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from services.trainer import ModelTrainer
from services.pattern_miner import mine_patterns
from services.agent.research import RouteResearchAgent

router = APIRouter()
trainer = ModelTrainer()


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
async def trigger_research(req: LaneResearchRequest, background_tasks: BackgroundTasks):
    agent = RouteResearchAgent()
    if not agent.available:
        return {"status": "error", "message": "OpenAI not configured. Set OPENAI_BASE_URL and OPENAI_API_KEY."}
    background_tasks.add_task(_research, req.carrier_slug, req.origin_country, req.dest_country)
    return {"status": "research_started", "carrier": req.carrier_slug,
            "origin": req.origin_country, "dest": req.dest_country}


@router.post("/research-missing")
async def trigger_research_missing(background_tasks: BackgroundTasks):
    agent = RouteResearchAgent()
    if not agent.available:
        return {"status": "error", "message": "OpenAI not configured."}
    background_tasks.add_task(_research_missing)
    return {"status": "research_missing_started"}


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
    }
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


def _research(carrier_slug: str, origin_country: str, dest_country: str):
    agent = RouteResearchAgent()
    result = agent.research_and_store(carrier_slug, origin_country, dest_country)
    return result


def _research_missing():
    agent = RouteResearchAgent()
    result = agent.fill_missing_lanes()
    return result
