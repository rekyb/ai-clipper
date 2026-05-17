from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "error" in body
    assert body["data"]["status"] in {"ok", "degraded"}
