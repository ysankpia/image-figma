from __future__ import annotations

from fastapi.testclient import TestClient


def test_asset_metadata_and_file_url(legacy_client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = legacy_client.post("/api/upload", files={"file": png_file})
    task_id = upload.json()["data"]["taskId"]

    asset = legacy_client.get("/api/assets/asset_banner")

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

    asset_file = legacy_client.get(f"/files/assets/{task_id}/banner.png")
    assert asset_file.status_code == 200
    assert asset_file.content.startswith(b"\x89PNG\r\n\x1a\n")

    region_asset = legacy_client.get("/api/assets/asset_region_header")
    assert region_asset.status_code == 200
    assert region_asset.json()["data"] == {
        "assetId": "asset_region_header",
        "taskId": task_id,
        "role": "fallback_region",
        "url": f"http://localhost:8000/files/assets/{task_id}/header.png",
        "mimeType": "image/png",
    }

    region_file = legacy_client.get(f"/files/assets/{task_id}/header.png")
    assert region_file.status_code == 200
    assert region_file.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_missing_asset_returns_asset_not_found(legacy_client: TestClient) -> None:
    response = legacy_client.get("/api/assets/asset_missing")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "ASSET_NOT_FOUND"
    assert body["error"]["stage"] == "asset_lookup"
