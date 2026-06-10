from services.scraper.base import BaseCarrierScraper, ScrapedShipment


def test_normalize_delivered():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    s = S()
    assert s.normalize_status("Delivered") == "delivered"
    assert s.normalize_status("DELIVERED") == "delivered"
    assert s.normalize_status("Package delivered") == "delivered"


def test_normalize_delivery_exception():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    s = S()
    assert s.normalize_status("Delivered - exception") == "delivery_exception"
    assert s.normalize_status("Delivered failure") == "delivery_exception"


def test_normalize_in_transit():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    s = S()
    assert s.normalize_status("In Transit") == "in_transit"
    assert s.normalize_status("in transit to next facility") == "in_transit"


def test_normalize_exception():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    s = S()
    assert s.normalize_status("Exception - delayed") == "exception"
    assert s.normalize_status("Delivery exception") == "exception"


def test_normalize_out_for_delivery():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    s = S()
    assert s.normalize_status("Out for delivery") == "out_for_delivery"


def test_normalize_customs():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    s = S()
    assert s.normalize_status("Cleared customs") == "customs"


def test_get_api_scrapers():
    from services.scraper import get_scraper

    assert get_scraper("usps") is not None
    assert get_scraper("ups") is not None
    assert get_scraper("fedex") is not None
    assert get_scraper("dhl-express") is not None


def test_api_scraper_slugs():
    from services.scraper import _registry

    assert "usps" in _registry
    assert "ups" in _registry
    assert "fedex" in _registry
    assert "dhl-express" in _registry
    assert len(_registry) == 4
