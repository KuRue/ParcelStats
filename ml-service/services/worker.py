import asyncio
import json
import logging
import uuid
from collections import deque
from datetime import datetime
from typing import Optional
import redis
from services.queue import JobQueue
from services.scraper import get_scraper
from services.geocode import resolve as geocode_resolve
from services.predictor import ETAPredictor
from services.config import settings
from database.connection import SessionLocal
from database.models import Shipment, ShipmentEvent, Carrier, ScrapeJob
from services.timeutil import utcnow

logger = logging.getLogger("parcelstats.worker")

POLL_INTERVAL = 5
BATCH_SIZE = 5
CONCURRENT_SCRAPE_LIMIT = 3

HEALTH_WINDOW = 50
HEALTH_MIN_SAMPLES = 10
HEALTH_WARN_RATE = 0.5


class ScraperHealth:
    """Rolling per-carrier success metrics for scrape jobs."""

    def __init__(self):
        self._outcomes: dict[str, deque] = {}
        self._last_success: dict[str, datetime] = {}
        self._last_error: dict[str, str] = {}
        self._warned: set[str] = set()

    def record(self, carrier_slug: str, success: bool, error: str | None = None):
        window = self._outcomes.setdefault(carrier_slug, deque(maxlen=HEALTH_WINDOW))
        window.append(success)
        if success:
            self._last_success[carrier_slug] = utcnow()
        elif error:
            self._last_error[carrier_slug] = error[:200]

        rate = self.success_rate(carrier_slug)
        if rate is not None and rate < HEALTH_WARN_RATE:
            if carrier_slug not in self._warned:
                self._warned.add(carrier_slug)
                logger.warning(
                    f"Scraper health degraded for {carrier_slug}: "
                    f"{rate:.0%} success over last {len(window)} jobs "
                    f"(last error: {self._last_error.get(carrier_slug)})"
                )
        else:
            self._warned.discard(carrier_slug)

    def success_rate(self, carrier_slug: str) -> float | None:
        window = self._outcomes.get(carrier_slug)
        if not window or len(window) < HEALTH_MIN_SAMPLES:
            return None
        return sum(window) / len(window)

    def get_stats(self) -> dict:
        stats = {}
        for slug, window in self._outcomes.items():
            rate = self.success_rate(slug)
            last_success = self._last_success.get(slug)
            stats[slug] = {
                "jobs_in_window": len(window),
                "success_rate": round(rate, 3) if rate is not None else None,
                "degraded": rate is not None and rate < HEALTH_WARN_RATE,
                "last_success": last_success.isoformat() if last_success else None,
                "last_error": self._last_error.get(slug),
            }
        return stats


class ScrapeWorker:
    def __init__(self):
        self.queue = JobQueue()
        self.predictor = ETAPredictor()
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(CONCURRENT_SCRAPE_LIMIT)
        self._last_cleared = utcnow()
        self._processed = 0
        self._failed = 0
        self._started_at: Optional[datetime] = None
        self._redis_pub = redis.from_url(settings.redis_url, decode_responses=True)
        self.health = ScraperHealth()
        # lane_key -> datetime; prevents re-researching the same lane too often
        self._last_lane_research: dict[str, datetime] = {}

    async def start(self):
        if self.running:
            return
        self.running = True
        self._started_at = utcnow()
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
        now = utcnow()
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

                # Fill missing endpoint coordinates from the offline gazetteer
                if shipment.origin_name and shipment.origin_lat is None:
                    hit = geocode_resolve(shipment.origin_name)
                    if hit:
                        shipment.origin_lat = hit.lat
                        shipment.origin_lng = hit.lng
                if shipment.dest_name and shipment.dest_lat is None:
                    hit = geocode_resolve(shipment.dest_name)
                    if hit:
                        shipment.dest_lat = hit.lat
                        shipment.dest_lng = hit.lng

                for event in result.events:
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
                                ShipmentEvent.shipment_id == shipment_id,
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
                                shipment_id=shipment_id,
                                status=event.status,
                                location_name=event.location_name,
                                location_lat=event_lat,
                                location_lng=event_lng,
                                description=event.description,
                                event_time=event.event_time or utcnow(),
                                raw_data=event.raw_data,
                            )
                        )

                db.commit()

                try:
                    prediction = self.predictor.predict_for_shipment(shipment_id)
                    if prediction:
                        self._publish_event(
                            event_type="prediction_updated",
                            shipment_id=shipment_id,
                            tracking_number=tracking_number,
                            carrier_slug=carrier_slug,
                            status=result.status,
                            user_id=shipment.user_id,
                            data={
                                "predicted_delivery": prediction.get("predicted_delivery"),
                                "confidence_pct": prediction.get("confidence_pct"),
                                "model_version": prediction.get("model_version"),
                            },
                        )
                except Exception as e:
                    logger.warning(f"Prediction failed for {shipment_id}: {e}")

                self._research_lane_if_needed(shipment, result)

                scrape_job.status = "completed"
                scrape_job.completed_at = utcnow()
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
                self.health.record(carrier_slug, success=True)
                logger.info(f"Completed {carrier_slug}:{tracking_number}")

                if result.status == "delivered":
                    try:
                        from services.calibration import update_lane_stats_for_shipment
                        update_lane_stats_for_shipment(db, shipment)
                    except Exception as e:
                        logger.warning(f"Lane calibration update failed: {e}")
                    self._check_retrain()

            except Exception as e:
                self._failed += 1
                self.health.record(carrier_slug, success=False, error=str(e))
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
                            shipment.updated_at = utcnow()
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
            "timestamp": utcnow().isoformat(),
        }
        try:
            self._redis_pub.publish("parcelstats:global", json.dumps(event))
            if user_id:
                self._redis_pub.publish(
                    f"parcelstats:user:{user_id}", json.dumps(event)
                )
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

    def _research_lane_if_needed(self, shipment, result):
        """After a successful scrape, research the lane if it has no pattern.

        Uses in-memory rate limiting (once per lane per 24h).
        """
        from services.knowledge import country_from_region
        from services.agent.research import RouteResearchAgent

        agent = RouteResearchAgent()
        if not agent.available:
            return

        oc = country_from_region(shipment.origin_name or "")
        dc = country_from_region(shipment.dest_name or "")
        if oc == "??" or dc == "??":
            return

        lane_key = f"{shipment.carrier_id}:{oc}:{dc}"
        now = utcnow()
        last = self._last_lane_research.get(lane_key)
        if last and (now - last).total_seconds() < 86400:
            return

        db = SessionLocal()
        try:
            from database.models import RoutePattern
            has_pattern = db.query(RoutePattern).filter(
                RoutePattern.carrier_id == shipment.carrier_id,
                RoutePattern.origin_country == oc,
                RoutePattern.dest_country == dc,
            ).first()
            if has_pattern:
                self._last_lane_research[lane_key] = now
                return
        finally:
            db.close()

        self._last_lane_research[lane_key] = now
        try:
            result = agent.research_and_store(
                shipment.carrier.slug if hasattr(shipment, "carrier") else None or "",
                oc, dc,
            )
            if result.get("created"):
                logger.info(f"Event-driven research created pattern for {lane_key}")
        except Exception as e:
            logger.warning(f"Event-driven research failed for {lane_key}: {e}")

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
                (utcnow() - self._started_at).total_seconds()
                if self._started_at
                else 0
            ),
            "concurrent_limit": CONCURRENT_SCRAPE_LIMIT,
            "poll_interval": POLL_INTERVAL,
            "scraper_health": self.health.get_stats(),
        }

    def _check_retrain(self):
        try:
            db = SessionLocal()
            try:
                delivered_count = db.query(Shipment).filter(
                    Shipment.delivered_at.isnot(None),
                    Shipment.shipped_at.isnot(None),
                ).count()
                if delivered_count >= 10 and delivered_count % 10 == 0:
                    logger.info(f"Auto-retrain triggered ({delivered_count} completed shipments)")
                    from services.trainer import ModelTrainer
                    trainer = ModelTrainer()
                    result = trainer.train_eta_model()
                    logger.info(f"Auto-retrain result: {result}")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Auto-retrain check failed: {e}")


worker: Optional["ScrapeWorker"] = None


def get_worker() -> "ScrapeWorker":
    global worker
    if worker is None:
        worker = ScrapeWorker()
    return worker
