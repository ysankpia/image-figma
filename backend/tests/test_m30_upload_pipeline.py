from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.png_tools import PngPixels, encode_rgb_png


def test_upload_m30_preview_completes_and_serves_m30_dsl(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload-m30-preview", files={"file": png_file})

    assert upload.status_code == 200
    body = upload.json()
    assert body["success"] is True
    task_id = body["data"]["taskId"]
    assert body["data"]["status"] in {"processing", "completed"}
    assert body["data"]["stage"] in {"m30_queued", "m30_completed"}

    task = client.get(f"/api/tasks/{task_id}")
    assert task.status_code == 200
    task_data = task.json()["data"]
    assert task_data["status"] == "completed"
    assert task_data["stage"] == "m30_completed"

    dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    dsl = dsl_response.json()["data"]["dsl"]
    assert "m30_evidence_grounded_materialization" in dsl["meta"]["qualityFlags"]
    assert has_role(dsl, "fallback_region")
    assert has_role(dsl, "m30_text_member")
    assert not any(child.get("type") == "icon" for child in dsl["root"]["children"])
    assert visible_audit_only_children(dsl) == 0

    for asset in dsl["assets"]:
        if asset.get("role") in {"fallback_region", "m30_visual_asset"}:
            assert str(asset["url"]).startswith(f"http://localhost:8000/files/assets/{task_id}/m30/")
            file_response = client.get(str(asset["url"]).replace("http://localhost:8000", ""))
            assert file_response.status_code == 200
            assert file_response.content.startswith(b"\x89PNG\r\n\x1a\n")

    report = client.get(f"/api/tasks/{task_id}/m30-materialization")
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["summary"]["fallbackPreserved"] is True
    assert report_data["summary"]["permissionViolationCount"] == 0
    assert report_data["summary"]["createdNewBBoxCount"] == 0


def test_upload_m30_preview_rejects_non_png(client: TestClient) -> None:
    response = client.post("/api/upload-m30-preview", files={"file": ("input.txt", b"not png", "text/plain")})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_FILE_TYPE"
    assert body["error"]["stage"] == "upload_m30_preview"


def test_upload_m30_preview_records_ocr_failure(tmp_path: Path, monkeypatch) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("OCR_PROVIDER", "baidu_ppocrv5")
    monkeypatch.delenv("BAIDU_PADDLE_OCR_TOKEN", raising=False)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        response = local_client.post(
            "/api/upload-m30-preview",
            files={"file": ("input.png", make_png(80, 80), "image/png")},
        )
        assert response.status_code == 200
        task_id = response.json()["data"]["taskId"]

        task = local_client.get(f"/api/tasks/{task_id}")
        assert task.status_code == 200
        data = task.json()["data"]
        assert data["status"] == "failed"
        assert data["stage"] == "ocr"
        assert "BAIDU_PADDLE_OCR_TOKEN" in data["message"]

        dsl = local_client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl.status_code == 409


def has_role(dsl: dict, role: str) -> bool:
    return any(child.get("role") == role for child in dsl["root"]["children"] if isinstance(child, dict))


def visible_audit_only_children(dsl: dict) -> int:
    count = 0
    for child in dsl["root"]["children"]:
        if not isinstance(child, dict):
            continue
        meta = child.get("meta") if isinstance(child.get("meta"), dict) else {}
        if meta.get("sourceKind") in {"m2913_audit", "m29032_review", "mixed_symbol_text_candidate"}:
            count += 1
    return count


def make_png(width: int, height: int) -> bytes:
    canvas = PngPixels(width=width, height=height, rows=[bytes((240, 240, 240)) * width for _ in range(height)])
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)
