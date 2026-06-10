import pytest
from fastapi import HTTPException

from services.security import require_internal_api_key
from services.config import settings


@pytest.mark.asyncio
async def test_allows_when_no_key_configured(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", None)
    await require_internal_api_key(x_internal_api_key=None)


@pytest.mark.asyncio
async def test_rejects_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "secret")
    with pytest.raises(HTTPException) as exc:
        await require_internal_api_key(x_internal_api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "secret")
    with pytest.raises(HTTPException) as exc:
        await require_internal_api_key(x_internal_api_key="wrong")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_accepts_correct_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "secret")
    await require_internal_api_key(x_internal_api_key="secret")
