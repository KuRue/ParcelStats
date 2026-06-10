from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import predict, scrape, train

app = FastAPI(
    title="ParcelStats ML Service",
    description="AI-powered ETA prediction and carrier scraping service",
    version="0.1.0",
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
    return {"status": "ok", "service": "parcelstats-ml"}
