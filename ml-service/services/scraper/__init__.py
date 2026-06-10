from services.scraper.base import BaseCarrierScraper
from services.scraper.usps import USPSPScraper
from services.scraper.ups import UPSScraper
from services.scraper.fedex import FedExScraper
from services.scraper.dhl import DHLExpressScraper

_registry: dict[str, BaseCarrierScraper] = {
    "usps": USPSPScraper(),
    "ups": UPSScraper(),
    "fedex": FedExScraper(),
    "dhl-express": DHLExpressScraper(),
}


def get_scraper(carrier_slug: str) -> BaseCarrierScraper | None:
    if carrier_slug in _registry:
        return _registry[carrier_slug]

    from services.scraper.generic import get_playwright_scraper
    pw_scraper = get_playwright_scraper(carrier_slug)
    if pw_scraper:
        return pw_scraper

    return None


def list_scrapers() -> list[dict]:
    from services.scraper.generic import SCRAPER_CONFIGS

    result = []
    for slug, scraper in _registry.items():
        result.append({"slug": slug, "name": scraper.name, "type": "api"})
    for slug, config in SCRAPER_CONFIGS.items():
        result.append({"slug": slug, "name": config["name"], "type": "playwright"})
    return result
