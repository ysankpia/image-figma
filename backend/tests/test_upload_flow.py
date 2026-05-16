from __future__ import annotations

from fastapi.testclient import TestClient


def test_upload_png_creates_completed_task_and_dsl(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload", files={"file": png_file})

    assert upload.status_code == 200
    upload_body = upload.json()
    assert upload_body["success"] is True
    task_id = upload_body["data"]["taskId"]
    assert task_id.startswith("task_")
    assert upload_body["data"]["status"] == "completed"
    assert upload_body["data"]["stage"] == "completed"
    assert upload_body["data"]["progress"] == 100

    task = client.get(f"/api/tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["data"] == {
        "taskId": task_id,
        "status": "completed",
        "stage": "completed",
        "progress": 100,
        "message": "Fake DSL is ready.",
    }

    dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    dsl = dsl_response.json()["data"]["dsl"]
    assert dsl["version"] == "0.1"
    assert dsl["taskId"] == task_id
    assets = {asset["assetId"]: asset for asset in dsl["assets"]}
    assert assets["asset_original"]["url"] == f"http://localhost:8000/files/uploads/{task_id}/original.png"
    assert assets["asset_banner"]["url"] == f"http://localhost:8000/files/assets/{task_id}/banner.png"
    assert dsl["root"]["children"][0]["source"]["assetId"] == "asset_original"

    original_file = client.get(f"/files/uploads/{task_id}/original.png")
    assert original_file.status_code == 200
    assert original_file.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_upload_rejects_non_png(client: TestClient) -> None:
    response = client.post("/api/upload", files={"file": ("input.txt", b"not png", "text/plain")})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_FILE_TYPE"
    assert body["error"]["stage"] == "upload"


def test_upload_rejects_large_png(client: TestClient) -> None:
    response = client.post(
        "/api/upload",
        files={"file": ("large.png", b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024), "image/png")},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FILE_TOO_LARGE"


def test_missing_task_returns_task_not_found(client: TestClient) -> None:
    response = client.get("/api/tasks/task_missing")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TASK_NOT_FOUND"
    assert body["error"]["taskId"] == "task_missing"


def test_figma_origin_cors_preflight_is_allowed(client: TestClient) -> None:
    response = client.options(
        "/api/upload",
        headers={
            "Origin": "https://www.figma.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_cors_allow_origins_can_be_restricted(tmp_path, monkeypatch) -> None:
    import importlib
    import sys

    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://www.figma.com,http://localhost:8000")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as restricted_client:
        response = restricted_client.options(
            "/api/upload",
            headers={
                "Origin": "https://www.figma.com",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://www.figma.com"
