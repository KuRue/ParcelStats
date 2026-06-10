import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.sax.saxutils import escape
from services.scraper.base import BaseCarrierScraper, ScrapedShipment, ScrapedEvent
from services.config import settings


class USPSPScraper(BaseCarrierScraper):
    slug = "usps"
    name = "USPS"

    async def track(self, tracking_number: str) -> ScrapedShipment:
        try:
            if settings.usps_web_tools_user_id:
                return await self._track_web_tools(tracking_number)
            return await self._track_public_json(tracking_number)

        except Exception as e:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="error",
                events=[ScrapedEvent(status="error", description=str(e))],
            )

    async def _track_web_tools(self, tracking_number: str) -> ScrapedShipment:
        request_xml = (
            f'<TrackRequest USERID="{escape(settings.usps_web_tools_user_id or "")}">'
            f'<TrackID ID="{escape(tracking_number)}"></TrackID>'
            "</TrackRequest>"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://secure.shippingapis.com/ShippingAPI.dll",
                params={"API": "TrackV2", "XML": request_xml},
                headers={"User-Agent": "ParcelStats/1.0"},
            )
            if resp.status_code >= 300:
                raise ValueError(f"USPS Web Tools returned HTTP {resp.status_code}")

        root = ET.fromstring(resp.text)
        error = root.find(".//Error")
        if error is not None:
            message = self._xml_text(error, "Description") or self._xml_text(error, "Number") or "USPS Web Tools error"
            raise ValueError(message)

        track_info = root.find(".//TrackInfo")
        if track_info is None:
            raise ValueError("USPS Web Tools returned no tracking information")

        return self._shipment_from_xml(tracking_number, track_info)

    async def _track_public_json(self, tracking_number: str) -> ScrapedShipment:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            resp = await client.get(
                "https://tools.usps.com/go/TrackConfirmAction_ajax",
                params={"tLabels": tracking_number},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}",
                },
            )

        if resp.status_code in {301, 302, 403}:
            raise ValueError(
                "USPS public tracking endpoint is blocked or redirected; configure USPS_WEB_TOOLS_USER_ID"
            )

        data = self.response_json(resp)
        return self._shipment_from_public_json(tracking_number, data)

    def _shipment_from_xml(self, tracking_number: str, track_info: ET.Element) -> ScrapedShipment:
        events = []

        summary = track_info.find("TrackSummary")
        if summary is not None:
            event = self._event_from_xml(summary)
            if event:
                events.append(event)

        for detail in track_info.findall("TrackDetail"):
            event = self._event_from_xml(detail)
            if event:
                events.append(event)

        status = events[0].status if events else "pending"
        service_type = self._xml_text(track_info, "MailClass") or self._xml_text(track_info, "Class")
        estimated_delivery = self._parse_datetime(
            self._xml_text(track_info, "ExpectedDeliveryDate")
            or self._xml_text(track_info, "PredictedDeliveryDate"),
            self._xml_text(track_info, "ExpectedDeliveryTime")
            or self._xml_text(track_info, "PredictedDeliveryTime"),
        )

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            service_type=service_type,
            estimated_delivery=estimated_delivery,
            events=events,
        )

    def _event_from_xml(self, node: ET.Element) -> ScrapedEvent | None:
        event_status = self._xml_text(node, "Event")
        if not event_status:
            return None

        location = ", ".join(
            filter(
                None,
                [
                    self._xml_text(node, "EventCity"),
                    self._xml_text(node, "EventState"),
                    self._xml_text(node, "EventZIPCode"),
                    self._xml_text(node, "EventCountry"),
                ],
            )
        )

        return ScrapedEvent(
            status=self.normalize_status(event_status),
            location_name=location or None,
            description=event_status,
            event_time=self._parse_datetime(
                self._xml_text(node, "EventDate"),
                self._xml_text(node, "EventTime"),
            ),
            raw_data={child.tag: child.text for child in node if child.text},
        )

    def _shipment_from_public_json(self, tracking_number: str, data: dict) -> ScrapedShipment:
        events = []
        track_info = data.get("TrackResults", {}).get("TrackInfo", {})
        if isinstance(track_info, list):
            track_info = track_info[0] if track_info else {}

        track_details = track_info.get("TrackDetail", [])
        if isinstance(track_details, dict):
            track_details = [track_details]

        summary = track_info.get("TrackSummary")
        if isinstance(summary, dict):
            track_details = [summary, *track_details]

        for detail in track_details:
            event_status = detail.get("EventStatus") or detail.get("Event") or ""
            event_city = detail.get("EventCity", "")
            event_state = detail.get("EventState", "")
            event_zip = detail.get("EventZIPCode", "")
            event_country = detail.get("EventCountry", "")
            event_date = detail.get("EventDate", "")
            event_time_val = detail.get("EventTime", "")

            location = ", ".join(filter(None, [event_city, event_state, event_zip, event_country]))
            events.append(ScrapedEvent(
                status=self.normalize_status(event_status),
                location_name=location or None,
                description=event_status,
                event_time=self._parse_datetime(event_date, event_time_val),
                raw_data=detail,
            ))

        status = events[0].status if events else "pending"
        estimated_delivery = self._parse_datetime(
            track_info.get("ExpectedDeliveryDate") or track_info.get("PredictedDeliveryDate", ""),
            track_info.get("ExpectedDeliveryTime") or track_info.get("PredictedDeliveryTime", ""),
        )

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            service_type=track_info.get("MailClass") or track_info.get("Class"),
            estimated_delivery=estimated_delivery,
            events=events,
        )

    def _xml_text(self, node: ET.Element, tag: str) -> str:
        child = node.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    def _parse_datetime(self, date_str: str, time_str: str) -> datetime | None:
        date_str = (date_str or "").strip()
        time_str = (time_str or "").strip()
        if not date_str:
            return None

        if not time_str:
            for fmt in ["%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except (ValueError, TypeError):
                    continue
            return None

        try:
            return datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %I:%M %p")
        except (ValueError, TypeError):
            pass

        for fmt in ["%b %d, %Y %I:%M %p", "%m/%d/%Y %I:%M %p"]:
            try:
                return datetime.strptime(f"{date_str} {time_str}", fmt)
            except (ValueError, TypeError):
                continue

        return None
