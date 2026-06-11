from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from services.predictor import ETAPredictor
from services.route_predictor import predict_route as predict_route_stops
from database.models import Shipment

router = APIRouter()

predictor = ETAPredictor()
LEGACY_FALLBACK_MODELS = ["fallback_route_stats", "carrier_estimate", "baseline_eta"]


class ETAPredictionRequest(BaseModel):
    tracking_number: str
    carrier_slug: str
    origin_region: str | None = None
    dest_region: str | None = None
    service_type: str | None = None


class RoutePredictionRequest(BaseModel):
    carrier_slug: str
    origin_region: str
    dest_region: str


@router.post("/eta")
async def predict_eta(req: ETAPredictionRequest):
    origin = req.origin_region or "unknown"
    dest = req.dest_region or "unknown"

    result = predictor.predict(
        carrier_slug=req.carrier_slug,
        origin_region=origin,
        dest_region=dest,
        service_type=req.service_type or "standard",
    )

    if not result:
        return {
            "status": "no_model",
            "message": "Insufficient real completed shipment history for this carrier or lane.",
            "carrier": req.carrier_slug,
        }

    return {"status": "ok", "prediction": result}


@router.get("/accuracy")
async def prediction_accuracy():
    from database.connection import SessionLocal
    from database.models import Prediction, Shipment, Carrier
    from services.accuracy import summarize_accuracy

    db = SessionLocal()
    try:
        rows = (
            db.query(
                Prediction.shipment_id,
                Carrier.slug,
                Prediction.model_version,
                Prediction.created_at,
                Prediction.predicted_delivery,
                Shipment.delivered_at,
            )
            .join(Shipment, Prediction.shipment_id == Shipment.id)
            .join(Carrier, Shipment.carrier_id == Carrier.id)
            .filter(
                Shipment.delivered_at.isnot(None),
                Prediction.model_version.notin_(LEGACY_FALLBACK_MODELS),
            )
            .all()
        )
    finally:
        db.close()

    return {"status": "ok", "accuracy": summarize_accuracy(rows)}


@router.post("/route")
async def predict_route(req: RoutePredictionRequest):
    return {
        "status": "ok",
        "route": {
            "carrier": req.carrier_slug,
            "origin": req.origin_region,
            "destination": req.dest_region,
            "message": "Use /predict/route-for-shipment/{shipment_id} for per-shipment predictions.",
        },
    }


@router.get("/route-for-shipment/{shipment_id}")
async def route_for_shipment(shipment_id: str, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        return {"status": "error", "message": "Shipment not found"}

    result = predict_route_stops(db, shipment)
    if not result:
        return {
            "status": "no_pattern",
            "message": "No route pattern found for this shipment's carrier and lane.",
        }

    return {"status": "ok", "route": result}
