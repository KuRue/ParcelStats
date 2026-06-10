import httpx
from datetime import datetime
from services.scraper.base import BaseCarrierScraper, ScrapedShipment, ScrapedEvent


class FedExScraper(BaseCarrierScraper):
    slug = "fedex"
    name = "FedEx"

    async def track(self, tracking_number: str) -> ScrapedShipment:
        events = []
        status = "pending"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://www.fedex.com/trackingCal/track",
                    data={
                        "data": f'{{"TrackPackagesRequest":{{"appDeviceType":"DESKTOP","uniqueTrackingNumber":"{tracking_number}","trackingNumberList":[{{"trackNumberInfo":{{"trackingNumber":"{tracking_number}"}}}}]}}}}'
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                data = self.response_json(resp)

                track_results = (
                    data.get("TrackPackagesResponse", {})
                    .get("packageList", [{}])
                )

                if track_results:
                    pkg = track_results[0]
                    raw_status = pkg.get("keyStatus", "")
                    status = self.normalize_status(raw_status) if raw_status else "pending"

                    scan_events = pkg.get("scanEventList", [])
                    for event in scan_events:
                        location = ", ".join(filter(None, [
                            event.get("scanLocation", ""),
                            event.get("country", ""),
                        ]))

                        date_str = event.get("date", "")
                        time_str = event.get("time", "")

                        events.append(ScrapedEvent(
                            status=self.normalize_status(event.get("status", "")),
                            location_name=location or None,
                            description=event.get("status", ""),
                            event_time=self._parse_datetime(date_str, time_str),
                            raw_data=event,
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
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None
