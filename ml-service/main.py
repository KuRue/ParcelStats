import logging
from contextlib import asynccontextmanager
import sqlalchemy as sa
from fastapi import Depends, FastAPI
from routers import predict, scrape, train, flights
from services.security import require_internal_api_key
from services.worker import get_worker
from services.scheduler import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    _migrate()
    w = get_worker()
    await w.start()
    await scheduler.start()
    yield
    await scheduler.stop()
    await w.stop()


def _migrate():
    """Apply schema migrations for tables that init.sql may not have created."""
    from database.connection import engine

    with engine.connect() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS route_patterns (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    carrier_id UUID NOT NULL REFERENCES carriers(id),
                    origin_country TEXT NOT NULL,
                    dest_country TEXT NOT NULL,
                    service_type TEXT,
                    label TEXT,
                    stops JSONB NOT NULL,
                    sample_count INTEGER NOT NULL DEFAULT 1,
                    match_score DECIMAL(4,2),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS idx_route_patterns_lookup "
                "ON route_patterns(carrier_id, origin_country, dest_country)"
            )
        )
        conn.execute(
            sa.text(
                """
                UPDATE shipment_events
                SET status = 'arrived_at_facility'
                WHERE status = 'delivered'
                  AND lower(concat_ws(' ', description, location_name)) LIKE '%warehouse%'
                """
            )
        )
        conn.execute(
            sa.text(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (shipment_id)
                        shipment_id,
                        lower(concat_ws(' ', status, description, location_name)) AS text
                    FROM shipment_events
                    ORDER BY shipment_id, event_time DESC
                )
                UPDATE shipments AS s
                SET status = 'arrived_at_facility',
                    delivered_at = NULL
                FROM latest
                WHERE s.id = latest.shipment_id
                  AND s.status = 'delivered'
                  AND latest.text LIKE '%warehouse%'
                """
            )
        )
        conn.commit()

app = FastAPI(
    title="ParcelStats ML Service",
    description="AI-powered ETA prediction and carrier scraping service",
    version="0.1.0",
    lifespan=lifespan,
)

# Service-to-service API only (called by the Next.js backend over the Docker
# network), so no CORS middleware - browsers should never call this directly.
auth = [Depends(require_internal_api_key)]
app.include_router(predict.router, prefix="/predict", tags=["predictions"], dependencies=auth)
app.include_router(scrape.router, prefix="/scrape", tags=["scraping"], dependencies=auth)
app.include_router(train.router, prefix="/train", tags=["training"], dependencies=auth)
app.include_router(flights.router, tags=["flights"], dependencies=auth)


@app.get("/health")
async def health():
    from services.queue import JobQueue
    queue = JobQueue()
    return {
        "status": "ok",
        "service": "parcelstats-ml",
        "worker": get_worker().get_status(),
        "scheduler": scheduler.get_status(),
        "queue": queue.get_stats(),
    }
