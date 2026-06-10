from datetime import datetime, timezone

import httpx

from services.scraper.base import BaseCarrierScraper, ScrapedEvent, ScrapedShipment
from services.geo import resolve_location, same_country


class SpeedPAKScraper(BaseCarrierScraper):
    slug = "speedpak"
    name = "SpeedPAK"
    api_url = (
        "https://azure-cn.orangeconnex.com/oc/"
        "capricorn-website/website/v1/tracking/traces"
    )

    async def track(self, tracking_number: str) -> ScrapedShipment:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.api_url,
                    json={
                        "trackingNumbers": [tracking_number],
                        "language": "en-US",
                    },
                    headers={
                        "Accept": "application/json",
                        "Accept-Language": "en-US",
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36"
                        ),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="error",
                events=[ScrapedEvent(status="error", description=str(e))],
            )

        try:
            return self._parse_response(tracking_number, data)
        except Exception as e:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="error",
                events=[ScrapedEvent(status="error", description=str(e))],
            )

    def _parse_response(self, tracking_number: str, data: dict) -> ScrapedShipment:
        result = data.get("result") or {}
        not_found = set(result.get("notExistsTrackingNumbers") or [])
        waybills = result.get("waybills") or []

        if tracking_number in not_found or not waybills:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="not_found",
                events=[
                    ScrapedEvent(
                        status="not_found",
                        description="Tracking number not found by Orange Connex",
                        event_time=datetime.utcnow(),
                        raw_data=data,
                    )
                ],
            )

        waybill = next(
            (
                item
                for item in waybills
                if item.get("trackingNumber") == tracking_number
            ),
            waybills[0],
        )

        return self._parse_waybill(tracking_number, waybill)

    def _parse_waybill(self, tracking_number: str, waybill: dict) -> ScrapedShipment:
        traces = waybill.get("traces") or []
        origin = self._format_location(
            waybill.get("consignmentCityName"),
            waybill.get("consignmentCountryName"),
        )
        destination = self._format_location(
            waybill.get("consigneeCityName"),
            waybill.get("consigneeCountryName"),
        )
        origin_coords = resolve_location(
            waybill.get("consignmentCityName"),
            waybill.get("consignmentCountryName"),
        )
        destination_coords = resolve_location(
            waybill.get("consigneeCityName"),
            waybill.get("consigneeCountryName"),
        )
        origin_country = waybill.get("consignmentCountryCode") or waybill.get(
            "consignmentCountryName"
        )
        destination_country = waybill.get("consigneeCountryCode") or waybill.get(
            "consigneeCountryName"
        )

        events = [
            self._parse_trace(
                trace,
                origin_country=origin_country,
                destination_country=destination_country,
                origin_coords=origin_coords,
                destination_coords=destination_coords,
            )
            for trace in traces
        ]
        events = [event for event in events if event is not None]

        raw_status = waybill.get("lastStatus") or ""
        status = self.normalize_status(raw_status) if raw_status else "pending"

        delivered_at = None
        if status == "delivered":
            delivered_at = self._parse_timestamp(waybill.get("lastTimestamp"))

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            service_type=waybill.get("projectCode"),
            origin_name=origin,
            origin_lat=origin_coords[0] if origin_coords else None,
            origin_lng=origin_coords[1] if origin_coords else None,
            dest_name=destination,
            dest_lat=destination_coords[0] if destination_coords else None,
            dest_lng=destination_coords[1] if destination_coords else None,
            shipped_at=events[-1].event_time if events else None,
            delivered_at=delivered_at,
            events=events,
        )

    def _parse_trace(
        self,
        trace: dict,
        origin_country: str | None = None,
        destination_country: str | None = None,
        origin_coords: tuple[float, float] | None = None,
        destination_coords: tuple[float, float] | None = None,
    ) -> ScrapedEvent | None:
        description = trace.get("eventDesc") or trace.get("eventDescCn") or ""
        event_time = self._parse_timestamp(trace.get("oprTimestamp"))
        if not description and not event_time:
            return None

        city = trace.get("oprCity")
        country = trace.get("oprCountry")
        coords = self._resolve_trace_coords(
            city=city,
            country=country,
            origin_country=origin_country,
            destination_country=destination_country,
            origin_coords=origin_coords,
            destination_coords=destination_coords,
        )

        return ScrapedEvent(
            status=self.normalize_status(description) if description else "unknown",
            location_name=self._format_location(city, country),
            location_lat=coords[0] if coords else None,
            location_lng=coords[1] if coords else None,
            description=description or None,
            event_time=event_time,
            raw_data=trace,
        )

    def _resolve_trace_coords(
        self,
        city: str | None,
        country: str | None,
        origin_country: str | None,
        destination_country: str | None,
        origin_coords: tuple[float, float] | None,
        destination_coords: tuple[float, float] | None,
    ) -> tuple[float, float] | None:
        if not city and destination_coords and same_country(country, destination_country):
            return destination_coords
        if not city and origin_coords and same_country(country, origin_country):
            return origin_coords
        return resolve_location(city, country)

    def _parse_timestamp(self, value) -> datetime | None:
        try:
            timestamp = float(value) / 1000
        except (TypeError, ValueError):
            return None

        return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)

    def _format_location(self, city: str | None, country: str | None) -> str | None:
        parts = [part for part in [city, country] if part]
        return ", ".join(parts) if parts else None
