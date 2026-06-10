from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.predictor import ETAPredictor

router = APIRouter()

predictor = ETAPredictor()


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
        result = predictor.fallback_estimate(req.carrier_slug, origin, dest)
        if not result:
            return {
                "status": "no_model",
                "message": "Insufficient historical data. Predictions improve as more shipments are tracked.",
                "carrier": req.carrier_slug,
            }

    return {"status": "ok", "prediction": result}


@router.post("/route")
async def predict_route(req: RoutePredictionRequest):
    return {
        "status": "ok",
        "route": {
            "carrier": req.carrier_slug,
            "origin": req.origin_region,
            "destination": req.dest_region,
            "message": "Route prediction requires more historical data.",
        },
    }
