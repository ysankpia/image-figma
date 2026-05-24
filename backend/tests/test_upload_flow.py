from __future__ import annotations

from fastapi.testclient import TestClient


def test_removed_pre_m29_upload_surface_is_not_registered(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    assert client.post("/api/upload", files={"file": png_file}).status_code == 404

    legacy_endpoints = [
        "/api/tasks/task_missing/primitives",
        "/api/tasks/task_missing/ocr",
        "/api/tasks/task_missing/dsl-patch",
        "/api/tasks/task_missing/text-replacements",
        "/api/tasks/task_missing/text-bindings",
        "/api/tasks/task_missing/component-structures",
        "/api/tasks/task_missing/component-annotations",
        "/api/tasks/task_missing/layer-separation-candidates",
        "/api/tasks/task_missing/asset-slice-candidates",
        "/api/tasks/task_missing/icon-candidates",
        "/api/tasks/task_missing/icon-coverage-audit",
        "/api/tasks/task_missing/icon-gap-candidates",
        "/api/tasks/task_missing/icon-placement-plan",
        "/api/tasks/task_missing/icon-visible-fallback",
        "/api/tasks/task_missing/icon-business-candidates",
        "/api/tasks/task_missing/perception-benchmark",
        "/api/tasks/task_missing/sam-visual-candidates",
    ]
    for endpoint in legacy_endpoints:
        assert client.get(endpoint).status_code == 404


def test_current_upload_surface_returns_m29_plan_driven_dsl(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload-m30-preview", files={"file": png_file})

    assert upload.status_code == 200
    task_id = upload.json()["data"]["taskId"]

    task = client.get(f"/api/tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["data"]["status"] == "completed"
    assert task.json()["data"]["stage"] == "m29_completed"

    dsl = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl.status_code == 200
    body = dsl.json()["data"]["dsl"]
    assert "m29_plan_driven_materialization" in body["meta"]["qualityFlags"]
    assert any(child.get("role") == "fallback_region" for child in body["root"]["children"])
    assert any(child.get("role") == "m29_text" for child in body["root"]["children"])
    assert not any(child.get("role") == "m30_text_member" for child in body["root"]["children"])

    report = client.get(f"/api/tasks/{task_id}/m29-materialization")
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["summary"]["visibleNodeCount"] >= 1
    assert report_data["stageTimings"]["schemaName"] == "M3011StageTimings"


def test_m30_upload_rejects_invalid_uploads(client: TestClient) -> None:
    text = client.post("/api/upload-m30-preview", files={"file": ("input.txt", b"not png", "text/plain")})
    assert text.status_code == 400
    assert text.json()["error"]["code"] == "INVALID_FILE_TYPE"

    broken = client.post("/api/upload-m30-preview", files={"file": ("broken.png", b"\x89PNG\r\n\x1a\n", "image/png")})
    assert broken.status_code == 400
    assert broken.json()["error"]["code"] == "INVALID_IMAGE_DIMENSIONS"

    large = client.post(
        "/api/upload-m30-preview",
        files={"file": ("large.png", b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024), "image/png")},
    )
    assert large.status_code == 413
    assert large.json()["error"]["code"] == "FILE_TOO_LARGE"
