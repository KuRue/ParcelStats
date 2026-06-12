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


def test_normalize_delivered_to_warehouse_is_not_terminal():
    class S(BaseCarrierScraper):
        slug = "test"
        name = "Test"
        async def track(self, tracking_number: str) -> ScrapedShipment:
            pass

    s = S()
    assert s.normalize_status("Delivered to warehouse") == "arrived_at_facility"
    assert s.normalize_status("Delivered to destination hub") == "arrived_at_facility"


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
    # Coordinates come from the bundled gazetteer; assert city-level proximity
    assert abs(shipment.origin_lat - 22.54) < 0.1
    assert abs(shipment.origin_lng - 114.06) < 0.1
    assert abs(shipment.dest_lat - 27.91) < 0.1
    assert abs(shipment.dest_lng - (-82.79)) < 0.1
    assert len(shipment.events) == 3
    assert shipment.events[0].status == "arrived_at_facility"
    assert shipment.events[0].location_name == "Chicago IL, US"
    assert abs(shipment.events[0].location_lat - 41.85) < 0.1
    assert abs(shipment.events[0].location_lng - (-87.65)) < 0.1
    assert shipment.events[1].status == "customs"
    assert shipment.events[1].location_name == "US"
    assert shipment.events[1].location_lat is None
    assert shipment.events[1].location_lng is None
    assert shipment.shipped_at == shipment.events[-1].event_time


def _fake_17track_client(payload):
    class FakeResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    return FakeClient


@pytest.mark.asyncio
async def test_usps_parses_17track_response(monkeypatch):
    import services.scraper.usps as usps_mod
    from services.scraper.usps import USPSPScraper

    payload = {
        "ret": 0,
        "dat": {
            "accepted": [
                {
                    "z": {
                        "o": "TAMPA, FL",
                        "d": "JACKSONVILLE, FL",
                        "y": "1781395200000",
                        "e": [
                            {
                                "a": "1781222400000",
                                "b": "JACKSONVILLE",
                                "c": "FL",
                                "z": {"c": "InTransit", "en": "Arrived at USPS Facility"},
                            },
                            {
                                "a": "1781136000000",
                                "b": "TAMPA",
                                "c": "FL",
                                "z": {"c": "InfoReceived", "en": "USPS in possession of item"},
                            },
                        ],
                    }
                }
            ],
            "rejected": [],
        },
    }
    monkeypatch.setattr(usps_mod.httpx, "AsyncClient", _fake_17track_client(payload))

    shipment = await USPSPScraper().track("9400136106196445294475")

    assert shipment.status not in ("error", "pending")
    assert shipment.origin_name == "TAMPA, FL"
    assert shipment.dest_name == "JACKSONVILLE, FL"
    assert shipment.estimated_delivery is not None
    assert len(shipment.events) == 2
    assert shipment.events[0].location_name == "JACKSONVILLE, FL"
    assert shipment.events[0].description == "Arrived at USPS Facility"
    assert shipment.events[0].event_time is not None


@pytest.mark.asyncio
async def test_usps_rejected_means_pending(monkeypatch):
    import services.scraper.usps as usps_mod
    from services.scraper.usps import USPSPScraper

    payload = {"ret": 0, "dat": {"accepted": [], "rejected": [{"e": "x"}]}}
    monkeypatch.setattr(usps_mod.httpx, "AsyncClient", _fake_17track_client(payload))

    shipment = await USPSPScraper().track("9400136106196445294475")

    assert shipment.status == "pending"
    assert "No tracking information" in shipment.events[0].description


@pytest.mark.asyncio
async def test_usps_http_error_returns_error_status(monkeypatch):
    import services.scraper.usps as usps_mod
    from services.scraper.usps import USPSPScraper

    payload = {"ret": 1}
    monkeypatch.setattr(usps_mod.httpx, "AsyncClient", _fake_17track_client(payload))

    shipment = await USPSPScraper().track("9400136106196445294475")

    assert shipment.status == "error"


def test_usps_hash_tracking_is_deterministic():
    from services.scraper.usps import USPSPScraper

    a = USPSPScraper._hash_tracking("9400136106196445294475")
    b = USPSPScraper._hash_tracking("9400136106196445294475")
    c = USPSPScraper._hash_tracking("9400136106196445294476")
    assert a == b
    assert a != c
    assert a.isdigit()


@pytest.mark.asyncio
async def test_ups_returns_client_fetch_without_credentials(monkeypatch):
    from services.config import settings
    from services.scraper.ups import UPSScraper

    monkeypatch.setattr(settings, "ups_client_id", None)
    monkeypatch.setattr(settings, "ups_client_secret", None)
    shipment = await UPSScraper().track("1ZB36H830306448836")

    assert shipment.status == "client_fetch_required"
    assert shipment.events[0].status == "client_fetch_required"


def test_ups_parse_track_api_response():
    from services.scraper.ups import UPSScraper

    scraper = UPSScraper()
    shipment = scraper._shipment_from_api_response(
        "1ZB36H830306448836",
        {
            "trackResponse": {
                "shipment": [
                    {
                        "package": [
                            {
                                "currentStatus": {
                                    "description": "In Transit",
                                },
                                "service": {
                                    "description": "UPS Ground",
                                },
                                "deliveryDate": [
                                    {"type": "SDD", "date": "20260612"},
                                ],
                                "deliveryTime": [
                                    {"type": "EOD", "endTime": "210000"},
                                ],
                                "activity": [
                                    {
                                        "date": "20260610",
                                        "time": "071356",
                                        "location": {
                                            "address": {
                                                "city": "JACKSONVILLE",
                                                "stateProvince": "FL",
                                                "postalCode": "32202",
                                                "countryCode": "US",
                                            }
                                        },
                                        "status": {
                                            "description": "Departed from Facility",
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        },
    )

    assert shipment.status == "in_transit"
    assert shipment.service_type == "UPS Ground"
    assert shipment.estimated_delivery is not None
    assert len(shipment.events) == 1
    assert shipment.events[0].status == "departed_facility"
    assert shipment.events[0].location_name == "JACKSONVILLE, FL, 32202, US"


@pytest.mark.asyncio
async def test_fedex_requires_credentials(monkeypatch):
    from services.config import settings
    from services.scraper.fedex import FedExScraper

    monkeypatch.setattr(settings, "fedex_client_id", None)
    monkeypatch.setattr(settings, "fedex_client_secret", None)
    shipment = await FedExScraper().track("880648105185")

    assert shipment.status == "carrier_setup_required"
    assert shipment.events[0].status == "carrier_setup_required"
    assert "FEDEX_CLIENT_ID" in shipment.events[0].description


def test_fedex_parse_track_api_response():
    from services.scraper.fedex import FedExScraper

    scraper = FedExScraper()
    shipment = scraper._shipment_from_api_response(
        "880648105185",
        {
            "output": {
                "completeTrackResults": [
                    {
                        "trackingNumber": "880648105185",
                        "trackResults": [
                            {
                                "latestStatusDetail": {
                                    "statusByLocale": "In transit",
                                },
                                "serviceDetail": {
                                    "description": "FedEx Ground",
                                },
                                "estimatedDeliveryTimeWindow": {
                                    "window": {
                                        "begins": "2026-06-12T08:00:00-04:00",
                                        "ends": "2026-06-12T20:00:00-04:00",
                                    }
                                },
                                "shipperInformation": {
                                    "address": {
                                        "city": "TAMPA",
                                        "stateOrProvinceCode": "FL",
                                        "countryCode": "US",
                                    }
                                },
                                "recipientInformation": {
                                    "address": {
                                        "city": "JACKSONVILLE",
                                        "stateOrProvinceCode": "FL",
                                        "countryCode": "US",
                                    }
                                },
                                "scanEvents": [
                                    {
                                        "date": "2026-06-10T13:15:00-04:00",
                                        "eventDescription": "Arrived at FedEx location",
                                        "scanLocation": {
                                            "city": "JACKSONVILLE",
                                            "stateOrProvinceCode": "FL",
                                            "postalCode": "32202",
                                            "countryCode": "US",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        },
    )

    assert shipment.status == "in_transit"
    assert shipment.service_type == "FedEx Ground"
    assert shipment.estimated_delivery is not None
    assert shipment.origin_name == "TAMPA, FL, US"
    assert shipment.dest_name == "JACKSONVILLE, FL, US"
    assert len(shipment.events) == 1
    assert shipment.events[0].status == "arrived_at_facility"
    assert shipment.events[0].location_name == "JACKSONVILLE, FL, 32202, US"
