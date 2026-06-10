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
    from services.worker import worker
    return worker.get_status()
