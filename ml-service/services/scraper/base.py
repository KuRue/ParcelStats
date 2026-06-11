from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

NON_FINAL_DELIVERY_TERMS = [
    "warehouse",
    "facility",
    "hub",
    "sorting",
    "distribution",
    "customs",
    "carrier",
    "partner",
    "agent",
    "post office",
    "service point",
    "pickup point",
    "collection point",
]

DELIVERY_EXCEPTION_TERMS = ["fail", "exception", "attempt"]


class CarrierStatusError(Exception):
    def __init__(self, status: str, message: str, raw_data: Optional[dict] = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.raw_data = raw_data


@dataclass
class ScrapedEvent:
    status: str
    location_name: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    description: Optional[str] = None
    event_time: Optional[datetime] = None
    raw_data: Optional[dict] = None


@dataclass
class ScrapedShipment:
    tracking_number: str
    carrier_slug: str
    status: str
    service_type: Optional[str] = None
    origin_name: Optional[str] = None
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    dest_name: Optional[str] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    weight_kg: Optional[float] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    estimated_delivery: Optional[datetime] = None
    events: list[ScrapedEvent] = None

    def __post_init__(self):
        if self.events is None:
            self.events = []


class BaseCarrierScraper(ABC):
    slug: str = ""
    name: str = ""

    @abstractmethod
    async def track(self, tracking_number: str) -> ScrapedShipment:
        pass

    def status_shipment(
        self,
        tracking_number: str,
        status: str,
        description: str,
        raw_data: Optional[dict] = None,
    ) -> ScrapedShipment:
        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            events=[
                ScrapedEvent(
                    status=status,
                    description=description,
                    raw_data=raw_data,
                )
            ],
        )

    def response_json(self, response):
        if response.status_code >= 300:
            location = response.headers.get("location")
            suffix = f" redirect={location}" if location else ""
            raise ValueError(f"{self.name} returned HTTP {response.status_code}{suffix}")

        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            raise ValueError(
                f"{self.name} returned non-JSON response ({content_type or 'no content type'})"
            )

        return response.json()

    def normalize_status(self, raw_status: str) -> str:
        s = raw_status.lower().strip()
        if any(w in s for w in ["delivered", "delivred", "geliefert"]):
            if any(w in s for w in DELIVERY_EXCEPTION_TERMS):
                return "delivery_exception"
            if any(w in s for w in NON_FINAL_DELIVERY_TERMS):
                return "arrived_at_facility"
            return "delivered"
        if any(w in s for w in ["out for delivery", "on van", "with driver", "out for del"]):
            return "out_for_delivery"
        if any(w in s for w in ["in transit", "in progress", "en route", "on the way", "transiting"]):
            return "in_transit"
        if any(w in s for w in ["custom", "cleared", "customs"]):
            return "customs"
        if any(w in s for w in ["exception", "delayed", "returned", "damaged", "lost"]):
            return "exception"
        if any(w in s for w in ["arrived", "at facility", "at hub", "received at"]):
            return "arrived_at_facility"
        if any(w in s for w in ["departed", "left facility", "shipped from"]):
            return "departed_facility"
        if any(w in s for w in ["label", "pre-ship", "information received", "electronic"]):
            return "label_created"
        if any(w in s for w in ["pending", "picked up", "collected", "acceptance", "possession"]):
            return "pending"
        return raw_status
