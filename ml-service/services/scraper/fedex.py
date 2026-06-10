import time
from datetime import datetime

import httpx

from services.config import settings
from services.scraper.base import (
    BaseCarrierScraper,
    CarrierStatusError,
    ScrapedEvent,
    ScrapedShipment,
)


class FedExScraper(BaseCarrierScraper):
    slug = "fedex"
    name = "FedEx"

    def __init__(self):
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    async def track(self, tracking_number: str) -> ScrapedShipment:
        try:
            if not settings.fedex_client_id or not settings.fedex_client_secret:
                return self.status_shipment(
                    tracking_number,
                    "carrier_setup_required",
                    "FedEx tracking requires FedEx Developer API credentials. Set FEDEX_CLIENT_ID and FEDEX_CLIENT_SECRET.",
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

        resp = await client.post(
            f"{settings.fedex_base_url.rstrip('/')}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.fedex_client_id or "",
                "client_secret": settings.fedex_client_secret or "",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        if resp.status_code in {400, 401, 403}:
            raise CarrierStatusError(
                "carrier_auth_required",
                "FedEx rejected the configured API credentials. Check FEDEX_CLIENT_ID and FEDEX_CLIENT_SECRET.",
                self._safe_error_data(resp),
            )

        data = self.response_json(resp)
        access_token = data.get("access_token")
        if not access_token:
            raise CarrierStatusError(
                "carrier_auth_required",
                "FedEx did not return an OAuth access token. Check the FedEx project credentials.",
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
        resp = await client.post(
            f"{settings.fedex_base_url.rstrip('/')}/track/v1/trackingnumbers",
            json={
                "includeDetailedScans": True,
                "trackingInfo": [
                    {
                        "trackingNumberInfo": {
                            "trackingNumber": tracking_number,
                        }
                    }
                ],
            },
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "x-locale": settings.fedex_locale,
            },
        )

        if resp.status_code in {401, 403}:
            raise CarrierStatusError(
                "carrier_auth_required",
                "FedEx rejected the tracking API token. Check FedEx project access and credentials.",
                self._safe_error_data(resp),
            )
        if resp.status_code in {400, 404, 422}:
            raise CarrierStatusError(
                "tracking_not_found",
                self._api_error_message(resp) or "FedEx did not find tracking information for this number.",
                self._safe_error_data(resp),
            )

        data = self.response_json(resp)
        return self._shipment_from_api_response(tracking_number, data)

    def _shipment_from_api_response(self, tracking_number: str, data: dict) -> ScrapedShipment:
        result = self._first_track_result(data)
        if not result:
            raise CarrierStatusError(
                "tracking_not_found",
                "FedEx returned no tracking details for this number.",
                data,
            )

        status_detail = result.get("latestStatusDetail") or {}
        raw_status = (
            status_detail.get("statusByLocale")
            or status_detail.get("description")
            or status_detail.get("code")
            or result.get("derivedStatus")
            or ""
        )
        status = self.normalize_status(raw_status) if raw_status else "pending"
        service_type = (result.get("serviceDetail") or {}).get("description") or (
            result.get("serviceDetail") or {}
        ).get("type")

        events = []
        for event in result.get("scanEvents") or []:
            event_status = (
                event.get("eventDescription")
                or event.get("derivedStatus")
                or event.get("exceptionDescription")
                or event.get("eventType")
                or ""
            )
            events.append(
                ScrapedEvent(
                    status=self.normalize_status(event_status) if event_status else "pending",
                    location_name=self._location_from_scan(event),
                    description=event_status or None,
                    event_time=self._parse_datetime(event.get("date") or event.get("dateAndTime")),
                    raw_data=event,
                )
            )

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            service_type=service_type,
            origin_name=self._address_location((result.get("shipperInformation") or {}).get("address") or {}),
            dest_name=self._address_location((result.get("recipientInformation") or {}).get("address") or {}),
            shipped_at=self._date_time_by_type(result, {"ACTUAL_PICKUP", "SHIP"}),
            delivered_at=self._date_time_by_type(result, {"ACTUAL_DELIVERY"}),
            estimated_delivery=self._estimated_delivery(result),
            events=events,
        )

    def _first_track_result(self, data: dict) -> dict:
        complete_results = data.get("output", {}).get("completeTrackResults") or []
        for complete in complete_results:
            track_results = complete.get("trackResults") or []
            if track_results:
                return track_results[0]
        return {}

    def _location_from_scan(self, event: dict) -> str | None:
        return self._address_location(event.get("scanLocation") or {})

    def _address_location(self, address: dict) -> str | None:
        location = ", ".join(
            filter(
                None,
                [
                    address.get("city"),
                    address.get("stateOrProvinceCode"),
                    address.get("postalCode"),
                    address.get("countryCode") or address.get("countryName"),
                ],
            )
        )
        return location or None

    def _date_time_by_type(self, result: dict, wanted_types: set[str]) -> datetime | None:
        for item in result.get("dateAndTimes") or []:
            if item.get("type") in wanted_types:
                parsed = self._parse_datetime(item.get("dateTime"))
                if parsed:
                    return parsed
        return None

    def _estimated_delivery(self, result: dict) -> datetime | None:
        window = (result.get("estimatedDeliveryTimeWindow") or {}).get("window") or {}
        for key in ("begins", "ends"):
            parsed = self._parse_datetime(window.get(key))
            if parsed:
                return parsed
        return self._date_time_by_type(
            result,
            {"ESTIMATED_DELIVERY", "COMMITMENT", "APPOINTMENT_DELIVERY"},
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        value = (value or "").strip()
        if not value:
            return None

        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None)
        except ValueError:
            pass

        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S"]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        return None

    def _api_error_message(self, response: httpx.Response) -> str | None:
        data = self._safe_error_data(response)
        errors = data.get("errors") or data.get("transactionDetail", {}).get("errors") or []
        if errors:
            first = errors[0]
            return first.get("message") or first.get("code")
        return data.get("message")

    def _safe_error_data(self, response: httpx.Response) -> dict:
        try:
            return response.json()
        except ValueError:
            return {"status_code": response.status_code}
