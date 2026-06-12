from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.connection import SessionLocal
from database.models import Shipment, ScrapeJob
from services.queue import JobQueue
from services.scraper import get_scraper

router = APIRouter()


class ScrapeRequest(BaseModel):
    tracking_number: str
    carrier_slug: str
    shipment_id: str | None = None


class ClientFetchResult(BaseModel):
    tracking_number: str
    shipment_id: str
    raw_data: dict


@router.post("/trigger")
async def trigger_scrape(req: ScrapeRequest):
    scraper = get_scraper(req.carrier_slug)
    if not scraper:
        raise HTTPException(status_code=400, detail=f"No scraper for carrier: {req.carrier_slug}")

    if not req.shipment_id:
        db = SessionLocal()
        try:
            shipment = (
                db.query(Shipment)
                .filter(Shipment.tracking_number == req.tracking_number)
                .first()
            )
            if shipment:
                req.shipment_id = shipment.id
        finally:
            db.close()

    if not req.shipment_id:
        raise HTTPException(status_code=400, detail="shipment_id required")

    queue = JobQueue()
    job_id = queue.enqueue(
        tracking_number=req.tracking_number,
        carrier_slug=req.carrier_slug,
        shipment_id=req.shipment_id,
    )

    return {
        "status": "queued",
        "job_id": job_id,
        "tracking_number": req.tracking_number,
        "carrier": req.carrier_slug,
        "queue_size": queue.get_queue_size(),
    }


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


@router.get("/queue")
async def queue_status():
    from services.worker import get_worker
    return get_worker().get_status()


@router.post("/client-fetch")
async def client_fetch_result(req: ClientFetchResult):
    import uuid
    from datetime import datetime as utcnow, timezone
    from services.scraper.ups import UPSScraper
    from database.models import ShipmentEvent
    from services.geocode import resolve as geocode_resolve

    shipment_result = UPSScraper.parse_client_events(req.tracking_number, req.raw_data)

    if not shipment_result.events:
        return {"status": "no_data", "events": 0}

    db = SessionLocal()
    try:
        shipment = db.query(Shipment).filter(Shipment.id == req.shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        shipment.status = shipment_result.status
        if shipment_result.service_type:
            shipment.service_type = shipment_result.service_type

        for event in shipment_result.events:
            event_lat = event.location_lat
            event_lng = event.location_lng
            if event_lat is None and event.location_name:
                hit = geocode_resolve(event.location_name)
                if hit:
                    event_lat = hit.lat
                    event_lng = hit.lng

            existing = None
            if event.event_time:
                existing = (
                    db.query(ShipmentEvent)
                    .filter(
                        ShipmentEvent.shipment_id == req.shipment_id,
                        ShipmentEvent.event_time == event.event_time,
                        ShipmentEvent.status == event.status,
                    )
                    .first()
                )

            if existing:
                if event.location_name:
                    existing.location_name = event.location_name
                if event_lat is not None:
                    existing.location_lat = event_lat
                    existing.location_lng = event_lng
                if event.description:
                    existing.description = event.description
                if event.raw_data:
                    existing.raw_data = event.raw_data
            else:
                db.add(
                    ShipmentEvent(
                        id=str(uuid.uuid4()),
                        shipment_id=req.shipment_id,
                        status=event.status,
                        location_name=event.location_name,
                        location_lat=event_lat,
                        location_lng=event_lng,
                        description=event.description,
                        event_time=event.event_time or utcnow.now(timezone.utc),
                        raw_data=event.raw_data,
                    )
                )

        db.commit()
    finally:
        db.close()

    return {"status": "ok", "events": len(shipment_result.events)}
