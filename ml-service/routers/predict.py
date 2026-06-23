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
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        shipment = (
            db.query(Shipment)
            .filter(Shipment.tracking_number == req.tracking_number)
            .first()
        )
        if shipment:
            result = predictor.predict_for_shipment(shipment.id)
            if result:
                return {"status": "ok", "prediction": result}
    finally:
        db.close()

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


@router.get("/carrier-stats")
async def carrier_stats():
    from database.connection import SessionLocal
    from database.models import Shipment, Carrier

    db = SessionLocal()
    try:
        carriers = db.query(Carrier).all()

        results = []
        for carrier in carriers:
            total = db.query(Shipment).filter(
                Shipment.carrier_id == carrier.id,
            ).count()

            delivered = db.query(Shipment).filter(
                Shipment.carrier_id == carrier.id,
                Shipment.delivered_at.isnot(None),
                Shipment.shipped_at.isnot(None),
            ).all()

            active = db.query(Shipment).filter(
                Shipment.carrier_id == carrier.id,
                Shipment.delivered_at.is_(None),
                Shipment.status.notin_(["error", "tracking_not_found", "carrier_setup_required"]),
            ).count()

            transit_times = []
            for s in delivered:
                if s.shipped_at and s.delivered_at:
                    days = (s.delivered_at - s.shipped_at).total_seconds() / 86400
                    if 0 < days < 365:
                        transit_times.append(days)

            on_time = 0
            for s in delivered:
                if s.shipped_at and s.estimated_delivery:
                    if s.delivered_at <= s.estimated_delivery:
                        on_time += 1

            avg_transit = round(sum(transit_times) / len(transit_times), 1) if transit_times else None
            on_time_pct = round(100 * on_time / len(delivered), 1) if delivered else None

            origins = db.query(Shipment.origin_name).filter(
                Shipment.carrier_id == carrier.id,
                Shipment.origin_name.isnot(None),
            ).distinct().limit(10).all()

            results.append({
                "slug": carrier.slug,
                "name": carrier.name,
                "total_shipments": total,
                "delivered": len(delivered),
                "active": active,
                "avg_transit_days": avg_transit,
                "on_time_pct": on_time_pct,
                "median_transit_days": round(sorted(transit_times)[len(transit_times)//2], 1) if transit_times else None,
                "fastest_days": round(min(transit_times), 1) if transit_times else None,
                "slowest_days": round(max(transit_times), 1) if transit_times else None,
                "top_lanes": list(set(
                    f"{(o[0] or '?').split(',')[-1].strip()}"
                    for o in origins
                    if o[0]
                ))[:5],
            })

        results.sort(key=lambda x: x["delivered"], reverse=True)
        return {"status": "ok", "carriers": results}
    finally:
        db.close()
