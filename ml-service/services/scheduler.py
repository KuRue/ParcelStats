import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from services.config import settings
from services.queue import JobQueue
from database.connection import SessionLocal
from database.models import Shipment, ShipmentEvent, Carrier, ScrapeJob
from services.geocode import resolve as geocode_resolve
from services.timeutil import utcnow
from services.pattern_miner import mine_patterns
from services.agent.research import RouteResearchAgent

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
        # shipment_id -> last sweep time; prevents re-enqueueing an orphaned
        # shipment every cycle while its job is still waiting in Redis
        self._swept: dict[str, datetime] = {}
        # location strings the gazetteer could not resolve; avoids
        # re-attempting them every backfill cycle
        self._ungeocodable: set[str] = set()
        self._last_mining: Optional[datetime] = None
        self._last_research: Optional[datetime] = None
        self._last_flight_cache: Optional[datetime] = None

    async def start(self):
        if self.running:
            return
        self.running = True
        self._started_at = utcnow()
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
        self._last_poll = utcnow()
        self._polls_done += 1

        db = SessionLocal()
        try:
            self._sweep_orphaned_pending(db)
            self._geocode_backfill(db)
            self._mine_patterns_if_due(db)
            self._research_missing_if_due()
            await self._update_flight_cache_if_due()

            active_shipments = (
                db.query(Shipment)
                .filter(
                    Shipment.delivered_at.is_(None),
                    Shipment.status.notin_(NON_POLLABLE_STATUSES),
                    Shipment.updated_at < utcnow() - timedelta(minutes=30),
                )
                .order_by(Shipment.updated_at.asc())
                .limit(settings.poll_max_shipments)
                .all()
            )

            if not active_shipments:
                return

            enqueued = 0
            now = utcnow()

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

    def _sweep_orphaned_pending(self, db):
        """Pick up shipments whose initial scrape trigger never landed.

        When the ML service is down at creation time, the frontend's
        fire-and-forget /scrape/trigger call is lost and the shipment sits in
        'pending' with no scrape job. The main poll loop only considers
        shipments older than 30 minutes, so sweep these up right away.
        """
        orphans = (
            db.query(Shipment)
            .filter(
                Shipment.status == "pending",
                Shipment.created_at > utcnow() - timedelta(days=2),
                ~db.query(ScrapeJob.id)
                .filter(ScrapeJob.tracking_number == Shipment.tracking_number)
                .exists(),
            )
            .limit(settings.poll_max_shipments)
            .all()
        )

        now = utcnow()
        self._swept = {
            sid: t for sid, t in self._swept.items()
            if now - t < timedelta(hours=1)
        }

        enqueued = 0
        for shipment in orphans:
            sid = str(shipment.id)
            if sid in self._swept:
                continue
            carrier = (
                db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
            )
            if not carrier:
                continue
            self._swept[sid] = now
            self.queue.enqueue(
                tracking_number=shipment.tracking_number,
                carrier_slug=carrier.slug,
                shipment_id=str(shipment.id),
                priority=1,
            )
            enqueued += 1

        if enqueued:
            self._jobs_enqueued += enqueued
            logger.info(f"Swept {enqueued} pending shipments with no scrape job")

    def _geocode_backfill(self, db):
        """Resolve coordinates for rows that predate the offline geocoder."""
        resolved = 0

        event_query = db.query(ShipmentEvent).filter(
            ShipmentEvent.location_name.isnot(None),
            ShipmentEvent.location_lat.is_(None),
        )
        if self._ungeocodable:
            # Exclude known-unresolvable names so they don't permanently
            # occupy the limited batch window
            event_query = event_query.filter(
                ShipmentEvent.location_name.notin_(self._ungeocodable)
            )
        events = event_query.limit(500).all()
        for event in events:
            name = event.location_name
            if name in self._ungeocodable:
                continue
            hit = geocode_resolve(name)
            if hit:
                event.location_lat = hit.lat
                event.location_lng = hit.lng
                resolved += 1
            else:
                self._ungeocodable.add(name)

        shipments = (
            db.query(Shipment)
            .filter(
                (Shipment.origin_name.isnot(None) & Shipment.origin_lat.is_(None))
                | (Shipment.dest_name.isnot(None) & Shipment.dest_lat.is_(None))
            )
            .limit(250)
            .all()
        )
        for shipment in shipments:
            for name_attr, lat_attr, lng_attr in (
                ("origin_name", "origin_lat", "origin_lng"),
                ("dest_name", "dest_lat", "dest_lng"),
            ):
                name = getattr(shipment, name_attr)
                if not name or getattr(shipment, lat_attr) is not None:
                    continue
                if name in self._ungeocodable:
                    continue
                hit = geocode_resolve(name)
                if hit:
                    setattr(shipment, lat_attr, hit.lat)
                    setattr(shipment, lng_attr, hit.lng)
                    resolved += 1
                else:
                    self._ungeocodable.add(name)

        if resolved:
            db.commit()
            logger.info(f"Geocode backfill resolved {resolved} locations")

        # Bound the negative cache
        if len(self._ungeocodable) > 5000:
            self._ungeocodable.clear()

    def _get_interval(self, status: str) -> int:
        status_lower = status.lower().replace(" ", "_")
        setting_name = STATUS_INTERVALS.get(status_lower)
        if setting_name:
            return getattr(settings, setting_name, settings.poll_interval_others)
        return settings.poll_interval_others

    async def _update_flight_cache_if_due(self):
        """Refresh cached cargo flight positions every 60 seconds."""
        now = utcnow()
        if self._last_flight_cache and (now - self._last_flight_cache).total_seconds() < 60:
            return
        self._last_flight_cache = now
        try:
            from services.flights import update_flight_cache
            await update_flight_cache()
        except Exception as e:
            logger.debug(f"Flight cache update failed: {e}")

    def _mine_patterns_if_due(self, db):
        """Run route pattern mining every 6 hours."""
        now = utcnow()
        if self._last_mining and (now - self._last_mining).total_seconds() < 21600:
            return
        self._last_mining = now
        try:
            mine_patterns()
        except Exception as e:
            logger.error(f"Route pattern mining failed: {e}")

    def _research_missing_if_due(self):
        """Research lanes with no patterns via LLM, every 24 hours."""
        now = utcnow()
        if self._last_research and (now - self._last_research).total_seconds() < 86400:
            return
        self._last_research = now
        agent = RouteResearchAgent()
        if not agent.available:
            return
        try:
            agent.fill_missing_lanes()
        except Exception as e:
            logger.error(f"Route research failed: {e}")

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "polls_done": self._polls_done,
            "jobs_enqueued": self._jobs_enqueued,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "last_flight_cache": self._last_flight_cache.isoformat() if self._last_flight_cache else None,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": (
                (utcnow() - self._started_at).total_seconds()
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
