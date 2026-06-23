import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from services.config import settings
from services.scraper.base import (
    BaseCarrierScraper,
    ScrapedShipment,
    ScrapedEvent,
)


class USPSPScraper(BaseCarrierScraper):
    slug = "usps"
    name = "USPS"

    async def track(self, tracking_number: str) -> ScrapedShipment:
        if settings.usps_web_tools_user_id:
            try:
                return await self._track_via_web_tools(tracking_number)
            except Exception:
                pass

        try:
            return await self._track_via_17track(tracking_number)
        except Exception as e:
            msg = str(e)
            if "non-JSON" in msg or "HTML" in msg:
                return self.status_shipment(
                    tracking_number,
                    "carrier_setup_required",
                    "USPS tracking aggregator is temporarily unavailable. "
                    "Set USPS_WEB_TOOLS_USER_ID for direct USPS API access "
                    "(free at registration.shippingapis.com).",
                )
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="error",
                events=[ScrapedEvent(status="error", description=msg)],
            )

    async def _track_via_web_tools(self, tracking_number: str) -> ScrapedShipment:
        xml_req = (
            f'<TrackFieldRequest USERID="{settings.usps_web_tools_user_id}">'
            f'<TrackID ID="{tracking_number}"/>'
            f"</TrackFieldRequest>"
        )

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://secure.shippingapis.com/ShippingAPI.dll",
                params={"API": "TrackV2", "XML": xml_req},
            )
            if resp.status_code != 200:
                raise ValueError(f"USPS Web Tools HTTP {resp.status_code}")

        root = ET.fromstring(resp.text)
        error = root.find(".//Error")
        if error is not None:
            desc = error.findtext("Description", "Unknown USPS API error")
            raise ValueError(f"USPS Web Tools: {desc}")

        track_info = root.find(".//TrackInfo")
        if track_info is None:
            raise ValueError("USPS Web Tools: no tracking info in response")

        track_detail = track_info.findtext("TrackDetail", "")
        track_summary = track_info.findtext("TrackSummary", "")
        status_code = track_info.get("CurrentStatus", "")

        events = []
        raw_status = track_summary or track_detail or status_code or "pending"
        status = self.normalize_status(raw_status)

        for child in track_info.findall(".//TrackDetail"):
            desc = child.text or ""
            if desc:
                events.append(ScrapedEvent(
                    status=self.normalize_status(desc) or "in_transit",
                    description=desc,
                ))

        if track_summary:
            events.insert(0, ScrapedEvent(
                status=status,
                description=track_summary,
            ))

        if not events:
            events = [ScrapedEvent(status="pending", description="Awaiting first scan.")]

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            events=events,
        )

    async def _track_via_17track(self, tracking_number: str) -> ScrapedShipment:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://t.17track.net",
            "Referer": "https://t.17track.net/",
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.post(
                "https://t.17track.net/handlerdirect",
                headers=headers,
                json={
                    "param": [
                        {
                            "f": "1",
                            "e": self._hash_tracking(tracking_number),
                        }
                    ],
                    "gat": 0,
                },
            )

            if r.status_code != 200:
                raise ValueError(f"17track returned HTTP {r.status_code}")

            content_type = r.headers.get("content-type", "")
            if "json" not in content_type:
                raise ValueError(f"17track returned non-JSON response ({content_type})")

            data = r.json()

        if not data or data.get("ret") != 0:
            raise ValueError("17track unexpected response")

        accepted = data.get("dat", {}).get("accepted", [])
        rejected = data.get("dat", {}).get("rejected", [])

        if rejected and not accepted:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="pending",
                events=[ScrapedEvent(status="pending", description="No tracking information available yet.")],
            )

        if not accepted:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="pending",
                events=[ScrapedEvent(status="pending", description="Tracking information not found.")],
            )

        track_data = accepted[0]
        track_info = track_data.get("z", {})

        events = []
        status = "pending"

        for evt in track_info.get("e", []):
            event_status = self.normalize_status(evt.get("z", {}).get("c", ""))
            description = evt.get("z", {}).get("en", "") or evt.get("z", {}).get("c", "")
            loc_parts = []
            for loc_key in ["b", "d", "c"]:
                loc_val = evt.get(loc_key, "")
                if loc_val:
                    loc_parts.append(loc_val)
            location = ", ".join(loc_parts) if loc_parts else None

            event_time = None
            timestamp = evt.get("a", "")
            if timestamp:
                try:
                    if isinstance(timestamp, (int, float)):
                        event_time = datetime.fromtimestamp(timestamp / 1000)
                    elif isinstance(timestamp, str):
                        ts = int(timestamp)
                        if ts > 1e12:
                            event_time = datetime.fromtimestamp(ts / 1000)
                        else:
                            event_time = datetime.fromtimestamp(ts)
                except (ValueError, OSError, OverflowError):
                    pass

            events.append(ScrapedEvent(
                status=event_status,
                location_name=location,
                description=description,
                event_time=event_time,
            ))

        if events:
            status = events[0].status

        estimated_delivery = None
        est_str = track_info.get("y", "")
        if est_str:
            try:
                ts = int(est_str)
                if ts > 1e12:
                    estimated_delivery = datetime.fromtimestamp(ts / 1000)
                else:
                    estimated_delivery = datetime.fromtimestamp(ts)
            except (ValueError, OSError, OverflowError):
                pass

        origin = track_info.get("o", "")
        dest = track_info.get("d", "")

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            estimated_delivery=estimated_delivery,
            origin_name=origin or None,
            dest_name=dest or None,
            events=events,
        )

    @staticmethod
    def _hash_tracking(tracking_number: str) -> str:
        h = 0
        for ch in tracking_number:
            h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
        return str(h & 0x7FFFFFFF)
