import pytest

try:
    from main import app as _app  # noqa: F401
    HAS_DEPS = True
except Exception:
    HAS_DEPS = False


@pytest.mark.skipif(not HAS_DEPS, reason="Full dependencies not installed")
def test_health_response_structure():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "parcelstats-ml"
