import time
import uuid
from datetime import datetime
from urllib.parse import quote

import httpx

from services.config import settings
from services.scraper.base import (
    BaseCarrierScraper,
    CarrierStatusError,
    ScrapedEvent,
    ScrapedShipment,
)


class UPSScraper(BaseCarrierScraper):
    slug = "ups"
    name = "UPS"

    def __init__(self):
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    async def track(self, tracking_number: str) -> ScrapedShipment:
        try:
            if not settings.ups_client_id or not settings.ups_client_secret:
                return self.status_shipment(
                    tracking_number,
                    "carrier_setup_required",
                    "UPS tracking requires UPS Developer OAuth credentials. Set UPS_CLIENT_ID and UPS_CLIENT_SECRET.",
                )

            async with httpx.AsyncClient(timeout=30) as client:
                token = await self._access_token_for(client)
                return await self._track_with_api(client, tracking_number, token)

        except CarrierStatusError as e:
            return self.status_shipment(
                tracking_number,
                e.status,
                e.message,
                e.raw_data,
            )
        except Exception as e:
            return self.status_shipment(tracking_number, "error", str(e))

    async def _access_token_for(self, client: httpx.AsyncClient) -> str:
        if self._access_token and self._token_expires_at > time.time() + 60:
            return self._access_token

        headers = {"Accept": "application/json"}
        if settings.ups_merchant_id:
            headers["x-merchant-id"] = settings.ups_merchant_id

        resp = await client.post(
            f"{settings.ups_base_url.rstrip('/')}/security/v1/oauth/token",
            data={"grant_type": "client_credentials"},
            headers=headers,
            auth=(settings.ups_client_id or "", settings.ups_client_secret or ""),
        )

        if resp.status_code in {400, 401, 403}:
            raise CarrierStatusError(
                "carrier_auth_required",
                "UPS rejected the configured API credentials. Check UPS_CLIENT_ID and UPS_CLIENT_SECRET.",
                self._safe_error_data(resp),
            )

        data = self.response_json(resp)
        access_token = data.get("access_token")
        if not access_token:
            raise CarrierStatusError(
                "carrier_auth_required",
                "UPS did not return an OAuth access token. Check the UPS app products and credentials.",
                data,
            )

        try:
            expires_in = int(data.get("expires_in") or 3600)
        except (TypeError, ValueError):
            expires_in = 3600

        self._access_token = access_token
        self._token_expires_at = time.time() + expires_in
        return access_token

    async def _track_with_api(
        self,
        client: httpx.AsyncClient,
        tracking_number: str,
        token: str,
    ) -> ScrapedShipment:
        resp = await client.get(
            f"{settings.ups_base_url.rstrip('/')}/api/track/v1/details/{quote(tracking_number)}",
            params={
                "locale": "en_US",
                "returnSignature": "false",
                "returnMilestones": "false",
                "returnPOD": "false",
            },
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "transId": str(uuid.uuid4()),
                "transactionSrc": settings.ups_transaction_src,
            },
        )

        if resp.status_code in {401, 403}:
            raise CarrierStatusError(
                "carrier_auth_required",
                "UPS rejected the tracking API token. Check the UPS app access and credentials.",
                self._safe_error_data(resp),
            )
        if resp.status_code in {400, 404}:
            raise CarrierStatusError(
                "tracking_not_found",
                self._api_error_message(resp) or "UPS did not find tracking information for this number.",
                self._safe_error_data(resp),
            )

        data = self.response_json(resp)
        return self._shipment_from_api_response(tracking_number, data)

    def _shipment_from_api_response(self, tracking_number: str, data: dict) -> ScrapedShipment:
        shipments = data.get("trackResponse", {}).get("shipment", [])
        shipment = shipments[0] if shipments else {}
        packages = shipment.get("package", [])
        package = packages[0] if packages else {}

        if not package:
            raise CarrierStatusError(
                "tracking_not_found",
                "UPS returned no package details for this tracking number.",
                data,
            )

        status_data = package.get("currentStatus") or {}
        raw_status = (
            status_data.get("description")
            or status_data.get("simplifiedTextDescription")
            or package.get("statusDescription")
            or ""
        )
        status = self.normalize_status(raw_status) if raw_status else "pending"
        service_type = (package.get("service") or {}).get("description")

        events = []
        for activity in package.get("activity", []):
            activity_status = activity.get("status") or {}
            event_status = (
                activity_status.get("description")
                or activity_status.get("simplifiedTextDescription")
                or activity_status.get("type")
                or activity_status.get("code")
                or ""
            )
            events.append(
                ScrapedEvent(
                    status=self.normalize_status(event_status) if event_status else "pending",
                    location_name=self._location_from_activity(activity),
                    description=event_status or None,
                    event_time=self._parse_datetime(
                        activity.get("date") or activity.get("gmtDate") or "",
                        activity.get("time") or activity.get("gmtTime") or "",
                    ),
                    raw_data=activity,
                )
            )

        delivered_at = self._date_time_by_type(package, "DEL")
        estimated_delivery = (
            self._date_time_by_type(package, "RDD")
            or self._date_time_by_type(package, "SDD")
        )

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            service_type=service_type,
            delivered_at=delivered_at,
            estimated_delivery=estimated_delivery,
            events=events,
        )

    def _location_from_activity(self, activity: dict) -> str | None:
        address = (
            activity.get("location", {})
            .get("address", {})
        )
        location = ", ".join(
            filter(
                None,
                [
                    address.get("city"),
                    address.get("stateProvince"),
                    address.get("postalCode"),
                    address.get("countryCode") or address.get("country"),
                ],
            )
        )
        return location or None

    def _date_time_by_type(self, package: dict, date_type: str) -> datetime | None:
        dates = package.get("deliveryDate") or []
        times = package.get("deliveryTime") or []

        date_value = next((d.get("date") for d in dates if d.get("type") == date_type), "")
        if not date_value:
            return None

        time_value = next(
            (
                t.get("startTime") or t.get("endTime")
                for t in times
                if t.get("type") in {date_type, "EDW", "CDW", "IDW", "CMT", "EOD"}
            ),
            "",
        )
        return self._parse_datetime(date_value, time_value)

    def _parse_datetime(self, date_str: str, time_str: str = "") -> datetime | None:
        date_str = (date_str or "").strip()
        time_str = (time_str or "").strip()
        if not date_str:
            return None

        if len(date_str) == 8 and date_str.isdigit():
            clean_time = "".join(ch for ch in time_str if ch.isdigit())
            if len(clean_time) >= 6:
                try:
                    return datetime.strptime(f"{date_str}{clean_time[:6]}", "%Y%m%d%H%M%S")
                except ValueError:
                    pass
            try:
                return datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                return None

        for fmt in ["%m/%d/%Y%I:%M %p", "%m/%d/%Y %I:%M %p", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(f"{date_str}{time_str}", fmt)
            except (ValueError, TypeError):
                continue

        return None

    def _api_error_message(self, response: httpx.Response) -> str | None:
        data = self._safe_error_data(response)
        errors = data.get("response", {}).get("errors") or data.get("errors") or []
        if errors:
            first = errors[0]
            return first.get("message") or first.get("code")
        return None

    def _safe_error_data(self, response: httpx.Response) -> dict:
        try:
            return response.json()
        except ValueError:
            return {"status_code": response.status_code}
