from __future__ import annotations

from fastapi.testclient import TestClient


def test_asset_metadata_and_file_url(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload", files={"file": png_file})
    task_id = upload.json()["data"]["taskId"]

    asset = client.get("/api/assets/asset_banner")

    assert asset.status_code == 200
    body = asset.json()
    assert body["success"] is True
    assert body["data"] == {
        "assetId": "asset_banner",
        "taskId": task_id,
        "role": "fallback_region",
        "url": f"http://localhost:8000/files/assets/{task_id}/banner.png",
        "mimeType": "image/png",
    }

    asset_file = client.get(f"/files/assets/{task_id}/banner.png")
    assert asset_file.status_code == 200
    assert asset_file.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_missing_asset_returns_asset_not_found(client: TestClient) -> None:
    response = client.get("/api/assets/asset_missing")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "ASSET_NOT_FOUND"
    assert body["error"]["stage"] == "asset_lookup"
