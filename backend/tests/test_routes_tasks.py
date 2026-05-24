from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient


def test_m29_materialization_route_returns_report(client: TestClient) -> None:
    state = importlib.import_module("app.state").state
    task_id = "task_route_m29_materialization"
    now = datetime.now(UTC).isoformat()
    insert_task(state, task_id, status="completed", now=now)
    task_root = state.settings.storage_root / "m30_1_uploads" / task_id
    report_dir = task_root / "m29_materialized"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "m29_materialized_dsl.json").write_text(json.dumps({"version": "0.1"}), encoding="utf-8")
    (report_dir / "m29_materialization_report.json").write_text(
        json.dumps({"summary": {"visibleNodeCount": 2}, "warnings": [], "skippedItems": [], "replayedNodes": []}),
        encoding="utf-8",
    )
    (task_root / "stage_timings.json").write_text(
        json.dumps({"schemaName": "M3011StageTimings", "stages": [{"stage": "m29_materialization", "status": "completed"}]}),
        encoding="utf-8",
    )

    response = client.get(f"/api/tasks/{task_id}/m29-materialization")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["visibleNodeCount"] == 2
    assert str(data["outputReport"]).endswith("m29_materialization_report.json")
    assert data["stageTimings"]["schemaName"] == "M3011StageTimings"


def test_m29_materialization_route_missing_report(client: TestClient) -> None:
    state = importlib.import_module("app.state").state
    task_id = "task_route_m29_materialization_missing"
    now = datetime.now(UTC).isoformat()
    insert_task(state, task_id, status="completed", now=now)

    response = client.get(f"/api/tasks/{task_id}/m29-materialization")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "M29_MATERIALIZATION_NOT_FOUND"


def insert_task(state, task_id: str, *, status: str, now: str) -> None:
    upload_path = state.storage.upload_path(task_id)
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(b"not-used")
    state.database.insert_task(
        {
            "id": task_id,
            "status": status,
            "stage": "m29_completed" if status == "completed" else "m29_materialization",
            "progress": 100 if status == "completed" else 92,
            "message": "done" if status == "completed" else "processing",
            "original_filename": "input.png",
            "mime_type": "image/png",
            "file_size": 8,
            "upload_path": str(upload_path),
            "created_at": now,
            "updated_at": now,
            "completed_at": now if status == "completed" else None,
            "failed_at": None,
        }
    )
