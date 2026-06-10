import httpx
from datetime import datetime
from services.scraper.base import BaseCarrierScraper, ScrapedShipment, ScrapedEvent


class USPSPScraper(BaseCarrierScraper):
    slug = "usps"
    name = "USPS"

    async def track(self, tracking_number: str) -> ScrapedShipment:
        events = []
        status = "pending"

        try:
            async with httpx.Client(timeout=30) as client:
                resp = await client.get(
                    f"https://tools.usps.com/go/TrackConfirmAction_ajax",
                    params={"tLabels": tracking_number},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                    },
                )
                data = resp.json()

                track_details = data.get("TrackResults", {}).get("TrackInfo", {}).get("TrackDetail", [])
                if isinstance(track_details, dict):
                    track_details = [track_details]

                for detail in track_details:
                    event_status = detail.get("EventStatus", "")
                    event_city = detail.get("EventCity", "")
                    event_state = detail.get("EventState", "")
                    event_date = detail.get("EventDate", "")
                    event_time_val = detail.get("EventTime", "")

                    location = ", ".join(filter(None, [event_city, event_state]))
                    events.append(ScrapedEvent(
                        status=self.normalize_status(event_status),
                        location_name=location or None,
                        description=event_status,
                        event_time=self._parse_datetime(event_date, event_time_val),
                        raw_data=detail,
                    ))

                if events:
                    status = events[0].status

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
            return datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
        except (ValueError, TypeError):
            return None
