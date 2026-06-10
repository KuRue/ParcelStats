import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import predict, scrape, train
from services.worker import worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await worker.start()
    yield
    await worker.stop()

app = FastAPI(
    title="ParcelStats ML Service",
    description="AI-powered ETA prediction and carrier scraping service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router, prefix="/predict", tags=["predictions"])
app.include_router(scrape.router, prefix="/scrape", tags=["scraping"])
app.include_router(train.router, prefix="/train", tags=["training"])


@app.get("/health")
async def health():
    from services.queue import JobQueue
    queue = JobQueue()
    return {
        "status": "ok",
        "service": "parcelstats-ml",
        "worker": worker.get_status(),
        "queue": queue.get_stats(),
    }
