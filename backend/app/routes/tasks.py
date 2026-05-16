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


@router.get("/tasks/{task_id}/primitives")
def get_task_primitives(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_primitive_result(task_id)
    if result is None:
        raise ApiError(
            "PRIMITIVE_NOT_FOUND",
            "Primitive result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="primitive_lookup",
            task_id=task_id,
        )

    primitive_path = Path(result["primitive_path"] or "")
    if not primitive_path.exists():
        raise ApiError(
            "PRIMITIVE_NOT_FOUND",
            "Primitive file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="primitive_lookup",
            task_id=task_id,
        )

    document = json.loads(primitive_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "provider": result["provider"],
        "model": result["model"],
        "primitives": document.get("primitives", []),
        "relations": document.get("relations", []),
        "warnings": document.get("warnings", []),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)


@router.get("/tasks/{task_id}/ocr")
def get_task_ocr(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_ocr_result(task_id)
    if result is None:
        raise ApiError(
            "OCR_NOT_FOUND",
            "OCR result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="ocr_lookup",
            task_id=task_id,
        )

    ocr_path = Path(result["ocr_path"] or "")
    if not ocr_path.exists():
        raise ApiError(
            "OCR_NOT_FOUND",
            "OCR file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="ocr_lookup",
            task_id=task_id,
        )

    document = json.loads(ocr_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "provider": result["provider"],
        "model": result["model"],
        "blocks": document.get("blocks", []),
        "warnings": document.get("warnings", []),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)


@router.get("/tasks/{task_id}/dsl-patch")
def get_task_dsl_patch(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_dsl_patch_result(task_id)
    if result is None:
        raise ApiError(
            "DSL_PATCH_NOT_FOUND",
            "DSL patch result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="dsl_patch_lookup",
            task_id=task_id,
        )

    patch_path = Path(result["patch_path"] or "")
    if not patch_path.exists():
        raise ApiError(
            "DSL_PATCH_NOT_FOUND",
            "DSL patch file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="dsl_patch_lookup",
            task_id=task_id,
        )

    document = json.loads(patch_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "mode": result["mode"],
        "patches": document.get("patches", []),
        "warnings": document.get("warnings", []),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)
