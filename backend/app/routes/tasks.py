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


@router.get("/tasks/{task_id}/m30-materialization")
def get_task_m30_materialization(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    report_path = state.settings.storage_root / "m30_1_uploads" / task_id / "m30" / "m30_materialization_report.json"
    if not report_path.exists():
        raise ApiError(
            "M30_MATERIALIZATION_NOT_FOUND",
            "M30 materialization report not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="m30_materialization_lookup",
            task_id=task_id,
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    timings_path = report_path.parent.parent / "stage_timings.json"
    timings = json.loads(timings_path.read_text(encoding="utf-8")) if timings_path.exists() else None
    debug = report.get("debug") if isinstance(report.get("debug"), dict) else {}
    preview = debug.get("materializationPreview") if isinstance(debug, dict) else None
    data: dict[str, object] = {
        "taskId": task_id,
        "status": task["status"],
        "stage": task["stage"],
        "summary": report.get("summary", {}),
        "warnings": report.get("warnings", []),
        "skippedItems": report.get("skippedItems", []),
        "textEditabilityDecisions": report.get("textEditabilityDecisions", []),
        "preservedGraphicTextItems": report.get("preservedGraphicTextItems", []),
        "reviewTextItems": report.get("reviewTextItems", []),
        "debugPreviewPath": str(report_path.parent / preview) if isinstance(preview, str) else None,
        "outputDsl": report.get("outputDsl"),
        "stageTimings": timings,
    }
    return success_response(data)


@router.get("/tasks/{task_id}/m31-reconstruction")
def get_task_m31_reconstruction(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    report_path = state.settings.storage_root / "m30_1_uploads" / task_id / "m31" / "m31_reconstruction_tree_report.json"
    if not report_path.exists():
        raise ApiError(
            "M31_RECONSTRUCTION_NOT_FOUND",
            "M31 reconstruction report not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="m31_reconstruction_lookup",
            task_id=task_id,
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    timings_path = report_path.parent.parent / "stage_timings.json"
    timings = json.loads(timings_path.read_text(encoding="utf-8")) if timings_path.exists() else {}
    overlay_path = report_path.parent / "m31_reconstruction_tree_overlay.png"
    data: dict[str, object] = {
        "taskId": task_id,
        "status": task["status"],
        "stage": task["stage"],
        "summary": report.get("summary", {}),
        "warnings": report.get("warnings", []),
        "reviewBuckets": report.get("reviewBuckets", []),
        "unitSummaries": report.get("unitSummaries", []),
        "outputTree": report.get("outputTree"),
        "debugOverlayPath": str(overlay_path) if overlay_path.exists() else None,
        "stageTimings": timings,
    }
    return success_response(data)


@router.get("/tasks/{task_id}/m39-boundary-classification")
def get_task_m39_boundary_classification(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    report_path = state.settings.storage_root / "m30_1_uploads" / task_id / "m39" / "m39_boundary_classification_report.json"
    if not report_path.exists():
        raise ApiError(
            "M39_BOUNDARY_CLASSIFICATION_NOT_FOUND",
            "M39 boundary classification report not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="m39_boundary_classification_lookup",
            task_id=task_id,
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    timings_path = report_path.parent.parent / "stage_timings.json"
    timings = json.loads(timings_path.read_text(encoding="utf-8")) if timings_path.exists() else {}
    data: dict[str, object] = {
        "taskId": task_id,
        "status": task["status"],
        "stage": task["stage"],
        "summary": report.get("summary", {}),
        "warnings": report.get("warnings", []),
        "modelSkippedReason": report.get("modelSkippedReason"),
        "classifiedNodes": report.get("classifiedNodes", []),
        "outputReport": str(report_path),
        "stageTimings": timings,
    }
    return success_response(data)
