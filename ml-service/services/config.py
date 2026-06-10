from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://parcelstats:parcelstats@localhost:5432/parcelstats"
    redis_url: str = "redis://localhost:6379"
    scrape_headless: bool = True
    model_retrain_schedule: str = "0 3 * * 0"
    model_path: str = "/app/models"

    poll_interval_active: int = 1800
    poll_interval_transit: int = 1800
    poll_interval_pending: int = 7200
    poll_interval_others: int = 14400
    poll_max_shipments: int = 50
    poll_check_interval: int = 300

    class Config:
        env_file = ".env"


settings = Settings()
