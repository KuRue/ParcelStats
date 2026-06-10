from fastapi import APIRouter, BackgroundTasks
from services.trainer import ModelTrainer

router = APIRouter()
trainer = ModelTrainer()


@router.post("/trigger")
async def trigger_training(background_tasks: BackgroundTasks):
    background_tasks.add_task(_train)
    return {"status": "training_started"}


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
