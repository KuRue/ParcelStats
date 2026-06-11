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


def _research(carrier_slug: str, origin_country: str, dest_country: str):
    agent = RouteResearchAgent()
    result = agent.research_and_store(carrier_slug, origin_country, dest_country)
    return result


def _research_missing():
    agent = RouteResearchAgent()
    result = agent.fill_missing_lanes()
    return result
