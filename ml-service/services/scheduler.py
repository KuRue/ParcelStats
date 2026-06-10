import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from services.config import settings
from services.queue import JobQueue
from database.connection import SessionLocal
from database.models import Shipment, Carrier, ScrapeJob

logger = logging.getLogger("parcelstats.scheduler")

STATUS_INTERVALS = {
    "in_transit": "poll_interval_transit",
    "out_for_delivery": "poll_interval_active",
    "arrived_at_facility": "poll_interval_transit",
    "departed_facility": "poll_interval_transit",
    "customs": "poll_interval_transit",
    "pending": "poll_interval_pending",
    "label_created": "poll_interval_pending",
}

NON_POLLABLE_STATUSES = [
    "delivered",
    "delivery_exception",
    "tracking_exception",
    "error",
    "carrier_setup_required",
    "carrier_auth_required",
    "tracking_not_found",
]


class PollScheduler:
    def __init__(self):
        self.queue = JobQueue()
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._last_poll: Optional[datetime] = None
        self._polls_done = 0
        self._jobs_enqueued = 0
        self._started_at: Optional[datetime] = None

    async def start(self):
        if self.running:
            return
        self.running = True
        self._started_at = datetime.utcnow()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"Poll scheduler started (check every {settings.poll_check_interval}s, "
            f"max {settings.poll_max_shipments} shipments/cycle)"
        )

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Poll scheduler stopped")

    async def _run_loop(self):
        while self.running:
            try:
                await self._poll_cycle()
            except Exception as e:
                logger.error(f"Scheduler cycle error: {e}")

            await asyncio.sleep(settings.poll_check_interval)

    async def _poll_cycle(self):
        self._last_poll = datetime.utcnow()
        self._polls_done += 1

        db = SessionLocal()
        try:
            active_shipments = (
                db.query(Shipment)
                .filter(
                    Shipment.delivered_at.is_(None),
                    Shipment.status.notin_(NON_POLLABLE_STATUSES),
                    Shipment.updated_at < datetime.utcnow() - timedelta(minutes=30),
                )
                .order_by(Shipment.updated_at.asc())
                .limit(settings.poll_max_shipments)
                .all()
            )

            if not active_shipments:
                return

            enqueued = 0
            now = datetime.utcnow()

            for shipment in active_shipments:
                interval = self._get_interval(shipment.status)
                min_re_check = now - timedelta(seconds=interval)

                recent_job = (
                    db.query(ScrapeJob)
                    .filter(
                        ScrapeJob.tracking_number == shipment.tracking_number,
                        ScrapeJob.created_at > min_re_check,
                    )
                    .order_by(ScrapeJob.created_at.desc())
                    .first()
                )

                if recent_job and recent_job.status in ("pending", "running"):
                    continue

                carrier = (
                    db.query(Carrier)
                    .filter(Carrier.id == shipment.carrier_id)
                    .first()
                )
                if not carrier:
                    continue

                self.queue.enqueue(
                    tracking_number=shipment.tracking_number,
                    carrier_slug=carrier.slug,
                    shipment_id=str(shipment.id),
                    priority=1 if shipment.status in ("out_for_delivery", "in_transit") else 0,
                )
                enqueued += 1

            if enqueued > 0:
                self._jobs_enqueued += enqueued
                logger.info(f"Enqueued {enqueued} re-scrape jobs (of {len(active_shipments)} candidates)")

        finally:
            db.close()

    def _get_interval(self, status: str) -> int:
        status_lower = status.lower().replace(" ", "_")
        setting_name = STATUS_INTERVALS.get(status_lower)
        if setting_name:
            return getattr(settings, setting_name, settings.poll_interval_others)
        return settings.poll_interval_others

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "polls_done": self._polls_done,
            "jobs_enqueued": self._jobs_enqueued,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": (
                (datetime.utcnow() - self._started_at).total_seconds()
                if self._started_at
                else 0
            ),
            "config": {
                "check_interval": settings.poll_check_interval,
                "max_per_cycle": settings.poll_max_shipments,
                "interval_active": settings.poll_interval_active,
                "interval_transit": settings.poll_interval_transit,
                "interval_pending": settings.poll_interval_pending,
                "interval_others": settings.poll_interval_others,
            },
        }


scheduler = PollScheduler()
