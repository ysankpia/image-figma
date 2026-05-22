from __future__ import annotations

import json
import importlib
from datetime import UTC, datetime

from fastapi.testclient import TestClient


def test_m39_1_unit_structure_readiness_route_returns_report(client: TestClient) -> None:
    state = importlib.import_module("app.state").state
    task_id = "task_route_m391"
    now = datetime.now(UTC).isoformat()
    upload_path = state.storage.upload_path(task_id)
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(b"not-used")
    state.database.insert_task(
        {
            "id": task_id,
            "status": "completed",
            "stage": "m30_completed",
            "progress": 100,
            "message": "done",
            "original_filename": "input.png",
            "mime_type": "image/png",
            "file_size": 8,
            "upload_path": str(upload_path),
            "created_at": now,
            "updated_at": now,
            "completed_at": now,
            "failed_at": None,
        }
    )
    task_root = state.settings.storage_root / "m30_1_uploads" / task_id
    report_path = task_root / "m39_1" / "unit_structure_readiness_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "summary": {"candidateUnitCount": 1},
                "warnings": [],
                "modelSkippedReason": "missing_model",
                "candidateUnits": [{"candidateId": "m391_candidate_0001"}],
                "promotionHints": [],
            }
        ),
        encoding="utf-8",
    )
    (task_root / "stage_timings.json").write_text(json.dumps({"schemaName": "M3011StageTimings", "stages": []}), encoding="utf-8")

    response = client.get(f"/api/tasks/{task_id}/m39-1-unit-structure-readiness")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["candidateUnitCount"] == 1
    assert data["modelSkippedReason"] == "missing_model"
    assert data["candidateUnits"] == [{"candidateId": "m391_candidate_0001"}]
    assert str(data["outputReport"]).endswith("unit_structure_readiness_report.json")
    assert data["stageTimings"]["schemaName"] == "M3011StageTimings"


def test_m39_1_unit_structure_readiness_route_missing_report(client: TestClient) -> None:
    state = importlib.import_module("app.state").state
    task_id = "task_route_m391_missing"
    now = datetime.now(UTC).isoformat()
    upload_path = state.storage.upload_path(task_id)
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(b"not-used")
    state.database.insert_task(
        {
            "id": task_id,
            "status": "completed",
            "stage": "m30_completed",
            "progress": 100,
            "message": "done",
            "original_filename": "input.png",
            "mime_type": "image/png",
            "file_size": 8,
            "upload_path": str(upload_path),
            "created_at": now,
            "updated_at": now,
            "completed_at": now,
            "failed_at": None,
        }
    )

    response = client.get(f"/api/tasks/{task_id}/m39-1-unit-structure-readiness")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "M39_1_UNIT_STRUCTURE_READINESS_NOT_FOUND"
