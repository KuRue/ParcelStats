import pytest

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
    assert get_scraper("speedpak") is not None


def test_response_json_rejects_non_json_redirects():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test Carrier"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    class Response:
        status_code = 302
        headers = {"location": "https://example.test/redirect"}

        def json(self):
            return {}

    with pytest.raises(ValueError, match="HTTP 302"):
        S().response_json(Response())


def test_api_scraper_slugs():
    from services.scraper import _registry

    assert "usps" in _registry
    assert "ups" in _registry
    assert "fedex" in _registry
    assert "dhl-express" in _registry
    assert "speedpak" in _registry
    assert len(_registry) == 5


def test_speedpak_parse_waybill():
    from services.scraper.speedpak import SpeedPAKScraper

    scraper = SpeedPAKScraper()
    shipment = scraper._parse_waybill(
        "ES1003208628616UN0101240600N",
        {
            "trackingNumber": "ES1003208628616UN0101240600N",
            "consignmentCityName": "SHENZHEN",
            "consignmentCountryName": "China",
            "consigneeCityName": "Largo",
            "consigneeCountryName": "UnitedStates",
            "lastStatus": "Arrived at Regional Distribution Center",
            "lastTimestamp": 1781055293000,
            "projectCode": "eBay",
            "traces": [
                {
                    "eventDesc": "Arrived at Regional Distribution Center",
                    "oprCity": "Chicago IL",
                    "oprCountry": "US",
                    "oprTimestamp": 1781055293000,
                },
                {
                    "eventDesc": "Import Customs Clearance Completed",
                    "oprCountry": "US",
                    "oprTimestamp": 1780938360000,
                },
                {
                    "eventDesc": "Package Received",
                    "oprCity": "ShenZhen",
                    "oprCountry": "CN",
                    "oprTimestamp": 1780500070000,
                },
            ],
        },
    )

    assert shipment.status == "arrived_at_facility"
    assert shipment.service_type == "eBay"
    assert shipment.origin_name == "SHENZHEN, China"
    assert shipment.dest_name == "Largo, UnitedStates"
    assert shipment.origin_lat == 22.5431
    assert shipment.origin_lng == 114.0579
    assert shipment.dest_lat == 27.9095
    assert shipment.dest_lng == -82.7873
    assert len(shipment.events) == 3
    assert shipment.events[0].status == "arrived_at_facility"
    assert shipment.events[0].location_name == "Chicago IL, US"
    assert shipment.events[0].location_lat == 41.8781
    assert shipment.events[0].location_lng == -87.6298
    assert shipment.events[1].status == "customs"
    assert shipment.events[1].location_name == "US"
    assert shipment.events[1].location_lat is None
    assert shipment.events[1].location_lng is None
    assert shipment.shipped_at == shipment.events[-1].event_time
