from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://parcelstats:parcelstats@localhost:5432/parcelstats"
    redis_url: str = "redis://localhost:6379"
    scrape_headless: bool = True
    model_retrain_schedule: str = "0 3 * * 0"
    model_path: str = "/app/models"
    usps_web_tools_user_id: str | None = None
    ups_client_id: str | None = None
    ups_client_secret: str | None = None
    ups_merchant_id: str | None = None
    ups_base_url: str = "https://onlinetools.ups.com"
    ups_transaction_src: str = "ParcelStats"
    fedex_client_id: str | None = None
    fedex_client_secret: str | None = None
    fedex_base_url: str = "https://apis.fedex.com"
    fedex_locale: str = "en_US"

    poll_interval_active: int = 1800
    poll_interval_transit: int = 1800
    poll_interval_pending: int = 7200
    poll_interval_others: int = 14400
    poll_max_shipments: int = 50
    poll_check_interval: int = 300

    class Config:
        env_file = ".env"


settings = Settings()
