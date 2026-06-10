import hmac
import logging
from fastapi import Header, HTTPException
from services.config import settings

logger = logging.getLogger("parcelstats.security")

_warned = False


async def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None),
):
    """Shared-secret auth for service-to-service calls from the frontend.

    If INTERNAL_API_KEY is unset, requests are allowed (local dev) but a
    warning is logged once so misconfigured deployments are visible.
    """
    global _warned
    if not settings.internal_api_key:
        if not _warned:
            logger.warning(
                "INTERNAL_API_KEY is not set - ML service endpoints are unauthenticated. "
                "Set INTERNAL_API_KEY in production."
            )
            _warned = True
        return

    if not x_internal_api_key or not hmac.compare_digest(
        x_internal_api_key, settings.internal_api_key
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
