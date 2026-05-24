from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, status

from ..errors import ApiError, success_response
from ..state import state

router = APIRouter(prefix="/api")


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    return success_response(
        {
            "taskId": task["id"],
            "status": task["status"],
            "stage": task["stage"],
            "progress": task["progress"],
            "message": task["message"],
        }
    )


@router.get("/tasks/{task_id}/dsl")
def get_task_dsl(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )
    if task["status"] != "completed":
        raise ApiError(
            "DSL_NOT_READY",
            "DSL is not ready.",
            status_code=status.HTTP_409_CONFLICT,
            stage="dsl_lookup",
            task_id=task_id,
        )

    result = state.database.get_dsl_result(task_id)
    if result is None:
        raise ApiError(
            "DSL_NOT_FOUND",
            "DSL result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="dsl_lookup",
            task_id=task_id,
        )

    dsl_path = Path(result["dsl_path"])
    if not dsl_path.exists():
        raise ApiError(
            "DSL_NOT_FOUND",
            "DSL file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="dsl_lookup",
            task_id=task_id,
        )

    return success_response({"dsl": json.loads(dsl_path.read_text(encoding="utf-8"))})


@router.get("/tasks/{task_id}/materialization")
def get_task_materialization(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    report_path = state.settings.storage_root / "upload_previews" / task_id / "materialized_design" / "materialization_report.json"
    if not report_path.exists():
        raise ApiError(
            "MATERIALIZATION_NOT_FOUND",
            "Materialization report not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="materialization_lookup",
            task_id=task_id,
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    timings_path = report_path.parent.parent / "stage_timings.json"
    timings = json.loads(timings_path.read_text(encoding="utf-8")) if timings_path.exists() else None
    output_dsl = report_path.parent / "design.dsl.json"
    data: dict[str, object] = {
        "taskId": task_id,
        "status": task["status"],
        "stage": task["stage"],
        "summary": report.get("summary", {}),
        "warnings": report.get("warnings", []),
        "skippedItems": report.get("skippedItems", []),
        "replayedNodes": report.get("replayedNodes", []),
        "outputDsl": str(output_dsl),
        "outputReport": str(report_path),
        "stageTimings": timings,
    }
    return success_response(data)
