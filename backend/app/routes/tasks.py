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


@router.get("/tasks/{task_id}/m29-direct-dsl")
def get_task_m29_direct_dsl(task_id: str) -> dict[str, object]:
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
            stage="m29_direct_dsl_lookup",
            task_id=task_id,
        )

    variant_dir = state.settings.storage_root / "m30_1_uploads" / task_id / "m29_direct"
    dsl_path = variant_dir / "m29_direct_replay_dsl.json"
    report_path = variant_dir / "m29_direct_replay_report.json"
    if not dsl_path.exists() or not report_path.exists():
        raise ApiError(
            "M29_DIRECT_DSL_NOT_FOUND",
            "M29 direct DSL variant not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="m29_direct_dsl_lookup",
            task_id=task_id,
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    timings_path = variant_dir.parent / "stage_timings.json"
    timings = json.loads(timings_path.read_text(encoding="utf-8")) if timings_path.exists() else {}
    if not m29_direct_assets_published(timings):
        raise ApiError(
            "M29_DIRECT_DSL_NOT_FOUND",
            "M29 direct DSL variant not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="m29_direct_dsl_lookup",
            task_id=task_id,
        )
    return success_response(
        {
            "dsl": json.loads(dsl_path.read_text(encoding="utf-8")),
            "report": {
                "summary": report.get("summary", {}),
                "warnings": report.get("warnings", []),
                "outputReport": str(report_path),
                "stageTimings": timings,
            },
        }
    )


def m29_direct_assets_published(timings: object) -> bool:
    if not isinstance(timings, dict) or not isinstance(timings.get("stages"), list):
        return False
    for stage in timings["stages"]:
        if isinstance(stage, dict) and stage.get("stage") == "m29_direct_asset_publish":
            return stage.get("status") == "completed"
    return False


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
