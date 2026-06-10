import httpx
from datetime import datetime
from services.scraper.base import BaseCarrierScraper, ScrapedShipment, ScrapedEvent


class UPSScraper(BaseCarrierScraper):
    slug = "ups"
    name = "UPS"

    async def track(self, tracking_number: str) -> ScrapedShipment:
        events = []
        status = "pending"

        try:
            async with httpx.Client(timeout=30) as client:
                resp = await client.get(
                    f"https://www.ups.com/track/api/Track/{tracking_number}",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                    },
                )
                data = resp.json()

                track_details = (
                    data.get("trackDetails", [{}])[0]
                    if data.get("trackDetails")
                    else {}
                )

                shipment_status = track_details.get("shipmentProgress", {}).get("type", "")
                status = self.normalize_status(shipment_status) if shipment_status else "pending"

                for activity in track_details.get("activity", []):
                    location_data = activity.get("location", {})
                    location = ", ".join(filter(None, [
                        location_data.get("city"),
                        location_data.get("stateProvince"),
                        location_data.get("country"),
                    ]))

                    date_str = activity.get("date", "")
                    time_str = activity.get("time", "")

                    events.append(ScrapedEvent(
                        status=self.normalize_status(activity.get("status", {}).get("type", "")),
                        location_name=location or None,
                        description=activity.get("status", {}).get("description", ""),
                        event_time=self._parse_datetime(date_str, time_str),
                        raw_data=activity,
                    ))

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

    def _parse_datetime(self, date_str: str, time_str: str) -> datetime | None:
        try:
            return datetime.strptime(f"{date_str}{time_str}", "%m/%d/%Y%I:%M %p")
        except (ValueError, TypeError):
            return None
