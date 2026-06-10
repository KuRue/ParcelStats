from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://parcelstats:parcelstats@localhost:5432/parcelstats"
    redis_url: str = "redis://localhost:6379"
    scrape_headless: bool = True
    model_retrain_schedule: str = "0 3 * * 0"
    model_path: str = "/app/models"

    class Config:
        env_file = ".env"


settings = Settings()
