from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient


def test_asset_metadata_and_file_url(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    from app.state import state

    task_id = "task_asset_route"
    path = state.storage.assets_dir / task_id / "preview" / "asset.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_file[1])
    state.database.insert_asset(
        {
            "asset_id": "preview_visual_asset_001",
            "task_id": task_id,
            "role": "preview_visual_asset",
            "path": str(path),
            "url": f"http://localhost:8000/files/assets/{task_id}/preview/asset.png",
            "mime_type": "image/png",
            "width": 317,
            "height": 2729,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    asset = client.get("/api/assets/preview_visual_asset_001")

    assert asset.status_code == 200
    body = asset.json()
    assert body["success"] is True
    assert body["data"] == {
        "assetId": "preview_visual_asset_001",
        "taskId": task_id,
        "role": "preview_visual_asset",
        "url": f"http://localhost:8000/files/assets/{task_id}/preview/asset.png",
        "mimeType": "image/png",
    }

    asset_file = client.get(f"/files/assets/{task_id}/preview/asset.png")
    assert asset_file.status_code == 200
    assert asset_file.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_missing_asset_returns_asset_not_found(client: TestClient) -> None:
    response = client.get("/api/assets/asset_missing")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "ASSET_NOT_FOUND"
    assert body["error"]["stage"] == "asset_lookup"
