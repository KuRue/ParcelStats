import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional
import redis
from services.queue import JobQueue
from services.scraper import get_scraper
from services.predictor import ETAPredictor
from services.config import settings
from database.connection import SessionLocal
from database.models import Shipment, ShipmentEvent, Carrier, ScrapeJob

logger = logging.getLogger("parcelstats.worker")

POLL_INTERVAL = 5
BATCH_SIZE = 5
CONCURRENT_SCRAPE_LIMIT = 3


class ScrapeWorker:
    def __init__(self):
        self.queue = JobQueue()
        self.predictor = ETAPredictor()
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(CONCURRENT_SCRAPE_LIMIT)
        self._last_cleared = datetime.utcnow()
        self._processed = 0
        self._failed = 0
        self._started_at: Optional[datetime] = None
        self._redis_pub = redis.from_url(settings.redis_url, decode_responses=True)

    async def start(self):
        if self.running:
            return
        self.running = True
        self._started_at = datetime.utcnow()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scrape worker started")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scrape worker stopped")

    async def _run_loop(self):
        while self.running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.error(f"Worker batch error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    async def _process_batch(self):
        now = datetime.utcnow()
        if (now - self._last_cleared).total_seconds() > 300:
            self.queue.clear_stale_processing()
            self._last_cleared = now

        tasks = []
        for _ in range(BATCH_SIZE):
            job = self.queue.dequeue()
            if not job:
                break

            tasks.append(self._process_job(job))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_job(self, job: dict):
        async with self._semaphore:
            tracking_number = job["tracking_number"]
            carrier_slug = job["carrier_slug"]
            shipment_id = job["shipment_id"]
            attempts = job.get("attempts", 1)
            scrape_job = None

            logger.info(
                f"Processing {carrier_slug}:{tracking_number} (attempt {attempts})"
            )

            db = SessionLocal()
            shipment = None
            try:
                shipment = (
                    db.query(Shipment).filter(Shipment.id == shipment_id).first()
                )
                if not shipment:
                    logger.warning(f"Shipment {shipment_id} not found, skipping")
                    return

                carrier = (
                    db.query(Carrier)
                    .filter(Carrier.slug == carrier_slug)
                    .first()
                )
                if not carrier:
                    logger.warning(f"Carrier {carrier_slug} not found, skipping")
                    return

                scrape_job = ScrapeJob(
                    id=str(uuid.uuid4()),
                    shipment_id=shipment_id,
                    carrier_id=carrier.id,
                    tracking_number=tracking_number,
                    status="running",
                    attempts=attempts,
                )
                db.add(scrape_job)
                db.commit()

                scraper = get_scraper(carrier_slug)
                if not scraper:
                    raise ValueError(f"No scraper for carrier: {carrier_slug}")

                result = await scraper.track(tracking_number)

                if result.status == "error":
                    error_msg = (
                        result.events[0].description if result.events else "Unknown error"
                    )
                    raise RuntimeError(error_msg)

                shipment.status = result.status
                if result.service_type:
                    shipment.service_type = result.service_type
                if result.origin_name:
                    shipment.origin_name = result.origin_name
                if result.origin_lat is not None:
                    shipment.origin_lat = result.origin_lat
                if result.origin_lng is not None:
                    shipment.origin_lng = result.origin_lng
                if result.dest_name:
                    shipment.dest_name = result.dest_name
                if result.dest_lat is not None:
                    shipment.dest_lat = result.dest_lat
                if result.dest_lng is not None:
                    shipment.dest_lng = result.dest_lng
                if result.shipped_at and not shipment.shipped_at:
                    shipment.shipped_at = result.shipped_at
                if result.delivered_at:
                    shipment.delivered_at = result.delivered_at
                if result.estimated_delivery and not shipment.estimated_delivery:
                    shipment.estimated_delivery = result.estimated_delivery

                for event in result.events:
                    existing = None
                    if event.event_time:
                        existing = (
                            db.query(ShipmentEvent)
                            .filter(
                                ShipmentEvent.shipment_id == shipment_id,
                                ShipmentEvent.event_time == event.event_time,
                                ShipmentEvent.status == event.status,
                            )
                            .first()
                        )

                    if existing:
                        if event.location_name:
                            existing.location_name = event.location_name
                        existing.location_lat = event.location_lat
                        existing.location_lng = event.location_lng
                        if event.description:
                            existing.description = event.description
                        if event.raw_data:
                            existing.raw_data = event.raw_data
                    else:
                        db.add(
                            ShipmentEvent(
                                id=str(uuid.uuid4()),
                                shipment_id=shipment_id,
                                status=event.status,
                                location_name=event.location_name,
                                location_lat=event.location_lat,
                                location_lng=event.location_lng,
                                description=event.description,
                                event_time=event.event_time or datetime.utcnow(),
                                raw_data=event.raw_data,
                            )
                        )

                db.commit()

                if self.predictor.is_ready:
                    try:
                        self.predictor.predict_for_shipment(shipment_id)
                    except Exception as e:
                        logger.warning(f"Prediction failed for {shipment_id}: {e}")

                scrape_job.status = "completed"
                scrape_job.completed_at = datetime.utcnow()
                db.commit()

                self._publish_event(
                    event_type="shipment_updated",
                    shipment_id=shipment_id,
                    tracking_number=tracking_number,
                    carrier_slug=carrier_slug,
                    status=result.status,
                    user_id=shipment.user_id,
                )

                self._processed += 1
                logger.info(f"Completed {carrier_slug}:{tracking_number}")

            except Exception as e:
                self._failed += 1
                logger.error(
                    f"Failed {carrier_slug}:{tracking_number}: {e}"
                )

                try:
                    requeued = self.queue.requeue_failed(job, str(e))
                    if scrape_job:
                        scrape_job.status = "failed"
                        scrape_job.last_error = str(e)[:500]
                        scrape_job.attempts = attempts
                        retry_at = job.get("retry_at")
                        if retry_at:
                            try:
                                scrape_job.next_attempt_at = datetime.fromisoformat(retry_at)
                            except ValueError:
                                pass
                    if not requeued:
                        if shipment:
                            shipment.status = "tracking_exception"
                            shipment.updated_at = datetime.utcnow()
                        logger.warning(
                            f"Max retries reached for {carrier_slug}:{tracking_number}"
                        )
                    db.commit()
                except Exception:
                    pass

            finally:
                db.close()

    def _publish_event(self, event_type: str, shipment_id: str,
                       tracking_number: str, carrier_slug: str,
                       status: str, user_id: str | None = None,
                       data: dict | None = None):
        event = {
            "type": event_type,
            "shipment_id": str(shipment_id),
            "tracking_number": tracking_number,
            "carrier_slug": carrier_slug,
            "status": status,
            "user_id": str(user_id) if user_id else None,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            self._redis_pub.publish("parcelstats:global", json.dumps(event))
            if user_id:
                self._redis_pub.publish(
                    f"parcelstats:user:{user_id}", json.dumps(event)
                )
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

    def get_status(self) -> dict:
        queue_stats = self.queue.get_stats()
        return {
            "running": self.running,
            "processed": self._processed,
            "failed": self._failed,
            "queue_size": queue_stats["queue_size"],
            "processing": queue_stats["processing"],
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": (
                (datetime.utcnow() - self._started_at).total_seconds()
                if self._started_at
                else 0
            ),
            "concurrent_limit": CONCURRENT_SCRAPE_LIMIT,
            "poll_interval": POLL_INTERVAL,
        }


worker = ScrapeWorker()
