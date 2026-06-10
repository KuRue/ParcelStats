from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from database.connection import SessionLocal
from database.models import Shipment, ShipmentEvent, Carrier, ScrapeJob
from services.scraper import get_scraper
from services.predictor import ETAPredictor
from datetime import datetime

router = APIRouter()


class ScrapeRequest(BaseModel):
    tracking_number: str
    carrier_slug: str
    shipment_id: str | None = None


@router.post("/trigger")
async def trigger_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    scraper = get_scraper(req.carrier_slug)
    if not scraper:
        raise HTTPException(status_code=400, detail=f"No scraper for carrier: {req.carrier_slug}")

    background_tasks.add_task(_run_scrape, req.tracking_number, req.carrier_slug, req.shipment_id)
    return {"status": "queued", "tracking_number": req.tracking_number, "carrier": req.carrier_slug}


@router.get("/status/{tracking_number}")
async def scrape_status(tracking_number: str):
    db = SessionLocal()
    try:
        jobs = (
            db.query(ScrapeJob)
            .filter(ScrapeJob.tracking_number == tracking_number)
            .order_by(ScrapeJob.created_at.desc())
            .all()
        )
        if not jobs:
            return {"status": "not_found"}
        job = jobs[0]
        return {
            "status": job.status,
            "attempts": job.attempts,
            "last_error": job.last_error,
            "next_attempt_at": job.next_attempt_at.isoformat() if job.next_attempt_at else None,
        }
    finally:
        db.close()


@router.get("/carriers")
async def list_carrier_scrapers():
    from services.scraper import list_scrapers
    return {"carriers": list_scrapers()}


async def _run_scrape(tracking_number: str, carrier_slug: str, shipment_id: str | None):
    db = SessionLocal()
    try:
        carrier = db.query(Carrier).filter(Carrier.slug == carrier_slug).first()
        if not carrier:
            return

        if shipment_id:
            shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        else:
            shipment = (
                db.query(Shipment)
                .filter(Shipment.tracking_number == tracking_number, Shipment.carrier_id == carrier.id)
                .first()
            )

        if not shipment:
            return

        job = ScrapeJob(
            shipment_id=shipment.id,
            carrier_id=carrier.id,
            tracking_number=tracking_number,
            status="running",
            attempts=0,
        )
        db.add(job)
        db.commit()

        try:
            scraper = get_scraper(carrier_slug)
            if not scraper:
                raise ValueError(f"No scraper for {carrier_slug}")

            result = await scraper.track(tracking_number)

            if result.status == "error":
                job.status = "failed"
                job.last_error = result.events[0].description if result.events else "Unknown error"
                job.attempts += 1
                job.next_attempt_at = datetime.utcnow()
                db.commit()
                return

            shipment.status = result.status
            shipment.service_type = result.service_type or shipment.service_type
            shipment.origin_name = result.origin_name or shipment.origin_name
            shipment.dest_name = result.dest_name or shipment.dest_name
            shipment.shipped_at = result.shipped_at or shipment.shipped_at
            shipment.delivered_at = result.delivered_at or shipment.delivered_at
            shipment.estimated_delivery = result.estimated_delivery or shipment.estimated_delivery

            for event in result.events:
                existing = (
                    db.query(ShipmentEvent)
                    .filter(
                        ShipmentEvent.shipment_id == shipment.id,
                        ShipmentEvent.status == event.status,
                        ShipmentEvent.event_time == event.event_time if event.event_time else True,
                    )
                    .first()
                )

                if not existing:
                    db.add(ShipmentEvent(
                        shipment_id=shipment.id,
                        status=event.status,
                        location_name=event.location_name,
                        description=event.description,
                        event_time=event.event_time or datetime.utcnow(),
                        raw_data=event.raw_data,
                    ))

            db.commit()

            predictor = ETAPredictor()
            if predictor.is_ready:
                predictor.predict_for_shipment(shipment.id)

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            job.status = "failed"
            job.last_error = str(e)
            job.attempts += 1
            job.next_attempt_at = datetime.utcnow()
            db.commit()

    finally:
        db.close()
