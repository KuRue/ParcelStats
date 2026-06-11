import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from routers import predict, scrape, train
from services.security import require_internal_api_key
from services.worker import get_worker
from services.scheduler import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    w = get_worker()
    await w.start()
    await scheduler.start()
    yield
    await scheduler.stop()
    await w.stop()

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
