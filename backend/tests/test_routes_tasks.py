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
    (task_root / "stage_timings.json").write_text(
        json.dumps({"schemaName": "M3011StageTimings", "stages": [{"stage": "m29_direct_asset_publish", "status": "completed"}]}),
        encoding="utf-8",
    )

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


def test_m29_direct_dsl_route_returns_variant(client: TestClient) -> None:
    state = importlib.import_module("app.state").state
    task_id = "task_route_m29_direct"
    now = datetime.now(UTC).isoformat()
    insert_task(state, task_id, status="completed", now=now)
    task_root = state.settings.storage_root / "m30_1_uploads" / task_id
    variant_dir = task_root / "m29_direct"
    variant_dir.mkdir(parents=True, exist_ok=True)
    dsl = {
        "version": "0.1",
        "taskId": f"{task_id}_m29_direct",
        "page": {"width": 100, "height": 80},
        "assets": [],
        "root": {"id": "root", "type": "frame", "role": "screen", "layout": {"x": 0, "y": 0, "width": 100, "height": 80}, "children": []},
        "meta": {"m29DirectReplay": True},
    }
    (variant_dir / "m29_direct_replay_dsl.json").write_text(json.dumps(dsl), encoding="utf-8")
    (variant_dir / "m29_direct_replay_report.json").write_text(json.dumps({"summary": {"visibleNodeCount": 0}, "warnings": []}), encoding="utf-8")
    (task_root / "stage_timings.json").write_text(
        json.dumps(
            {
                "schemaName": "M3011StageTimings",
                "stages": [{"stage": "m29_direct_asset_publish", "status": "completed"}],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/tasks/{task_id}/m29-direct-dsl")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dsl"]["meta"]["m29DirectReplay"] is True
    assert data["report"]["summary"]["visibleNodeCount"] == 0
    assert str(data["report"]["outputReport"]).endswith("m29_direct_replay_report.json")
    assert data["report"]["stageTimings"]["schemaName"] == "M3011StageTimings"


def test_m29_direct_dsl_route_waits_for_completion(client: TestClient) -> None:
    state = importlib.import_module("app.state").state
    task_id = "task_route_m29_direct_processing"
    now = datetime.now(UTC).isoformat()
    insert_task(state, task_id, status="processing", now=now)

    response = client.get(f"/api/tasks/{task_id}/m29-direct-dsl")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DSL_NOT_READY"


def test_m29_direct_dsl_route_missing_variant(client: TestClient) -> None:
    state = importlib.import_module("app.state").state
    task_id = "task_route_m29_direct_missing"
    now = datetime.now(UTC).isoformat()
    insert_task(state, task_id, status="completed", now=now)

    response = client.get(f"/api/tasks/{task_id}/m29-direct-dsl")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "M29_DIRECT_DSL_NOT_FOUND"


def insert_task(state, task_id: str, *, status: str, now: str) -> None:
    upload_path = state.storage.upload_path(task_id)
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(b"not-used")
    state.database.insert_task(
        {
            "id": task_id,
            "status": status,
            "stage": "m30_completed" if status == "completed" else "m29_direct_replay",
            "progress": 100 if status == "completed" else 22,
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
