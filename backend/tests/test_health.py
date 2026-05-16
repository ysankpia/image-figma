from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_success(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["version"] == "0.1.0"
    assert "time" in body["data"]
