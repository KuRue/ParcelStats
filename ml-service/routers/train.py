from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from services.trainer import ModelTrainer

router = APIRouter()
trainer = ModelTrainer()


class SeedRequest(BaseModel):
    count: int = 2000


@router.post("/trigger")
async def trigger_training(background_tasks: BackgroundTasks):
    background_tasks.add_task(_train)
    return {"status": "training_started"}


@router.post("/seed")
async def seed_synthetic_data(req: SeedRequest, background_tasks: BackgroundTasks):
    count = max(100, min(10000, req.count))
    background_tasks.add_task(_seed_and_train, count)
    return {"status": "seeding_started", "count": count}


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


def _seed_and_train(count: int):
    from services.data_generator import generate_synthetic_shipments
    import logging
    logger = logging.getLogger("parcelstats.seed")

    logger.info(f"Starting synthetic data generation ({count} shipments)")
    result = generate_synthetic_shipments(count)
    logger.info(f"Seed result: {result}")

    if result.get("status") == "success":
        logger.info("Training model with new data...")
        train_result = trainer.train_eta_model()
        logger.info(f"Training result: {train_result}")
