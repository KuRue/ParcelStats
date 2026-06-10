import httpx
from datetime import datetime
from services.scraper.base import BaseCarrierScraper, ScrapedShipment, ScrapedEvent


class DHLExpressScraper(BaseCarrierScraper):
    slug = "dhl-express"
    name = "DHL Express"

    async def track(self, tracking_number: str) -> ScrapedShipment:
        events = []
        status = "pending"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://www.dhl.com/shipmentTracking",
                    params={"AWB": tracking_number},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                    },
                )
                data = self.response_json(resp)

                shipments = data.get("shipments", [])
                if shipments:
                    shipment = shipments[0]
                    raw_status = shipment.get("status", "pending")
                    status = self.normalize_status(raw_status)

                    details = shipment.get("details", {})
                    origin = details.get("origin", {}).get("description", "")
                    destination = details.get("destination", {}).get("description", "")

                    for event in shipment.get("events", []):
                        location = event.get("location", {}).get("address", {}).get("addressLocality", "")
                        date_str = event.get("timestamp", "")

                        events.append(ScrapedEvent(
                            status=self.normalize_status(event.get("statusCode", "")),
                            location_name=location or None,
                            description=event.get("description", ""),
                            event_time=self._parse_datetime(date_str),
                            raw_data=event,
                        ))

                    return ScrapedShipment(
                        tracking_number=tracking_number,
                        carrier_slug=self.slug,
                        status=status,
                        origin_name=origin or None,
                        dest_name=destination or None,
                        events=events,
                    )

        except Exception as e:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="error",
                events=[ScrapedEvent(status="error", description=str(e))],
            )

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            events=events,
        )

    def _parse_datetime(self, date_str: str) -> datetime | None:
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
        return None
