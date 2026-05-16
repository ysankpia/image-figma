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


@router.get("/tasks/{task_id}/text-replacements")
def get_task_text_replacements(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_text_replacement_result(task_id)
    if result is None:
        raise ApiError(
            "TEXT_REPLACEMENT_NOT_FOUND",
            "Text replacement result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="text_replacement_lookup",
            task_id=task_id,
        )

    replacement_path = Path(result["replacement_path"] or "")
    if not replacement_path.exists():
        raise ApiError(
            "TEXT_REPLACEMENT_NOT_FOUND",
            "Text replacement file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="text_replacement_lookup",
            task_id=task_id,
        )

    document = json.loads(replacement_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "mode": result["mode"],
        "decisions": document.get("decisions", []),
        "warnings": document.get("warnings", []),
        "meta": document.get("meta", {}),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)


@router.get("/tasks/{task_id}/text-bindings")
def get_task_text_bindings(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_text_binding_result(task_id)
    if result is None:
        raise ApiError(
            "TEXT_BINDING_NOT_FOUND",
            "Text binding result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="text_binding_lookup",
            task_id=task_id,
        )

    binding_path = Path(result["binding_path"] or "")
    if not binding_path.exists():
        raise ApiError(
            "TEXT_BINDING_NOT_FOUND",
            "Text binding file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="text_binding_lookup",
            task_id=task_id,
        )

    document = json.loads(binding_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "containers": document.get("containers", []),
        "bindings": document.get("bindings", []),
        "unboundTextIds": document.get("unboundTextIds", []),
        "warnings": document.get("warnings", []),
        "meta": document.get("meta", {}),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)


@router.get("/tasks/{task_id}/component-structures")
def get_task_component_structures(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_component_structure_result(task_id)
    if result is None:
        raise ApiError(
            "COMPONENT_STRUCTURE_NOT_FOUND",
            "Component structure result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="component_structure_lookup",
            task_id=task_id,
        )

    structure_path = Path(result["structure_path"] or "")
    if not structure_path.exists():
        raise ApiError(
            "COMPONENT_STRUCTURE_NOT_FOUND",
            "Component structure file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="component_structure_lookup",
            task_id=task_id,
        )

    document = json.loads(structure_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "components": document.get("components", []),
        "groups": document.get("groups", []),
        "unstructuredContainerIds": document.get("unstructuredContainerIds", []),
        "warnings": document.get("warnings", []),
        "meta": document.get("meta", {}),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)


@router.get("/tasks/{task_id}/component-annotations")
def get_task_component_annotations(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_component_annotation_result(task_id)
    if result is None:
        raise ApiError(
            "COMPONENT_ANNOTATION_NOT_FOUND",
            "Component annotation result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="component_annotation_lookup",
            task_id=task_id,
        )

    annotation_path = Path(result["annotation_path"] or "")
    if not annotation_path.exists():
        raise ApiError(
            "COMPONENT_ANNOTATION_NOT_FOUND",
            "Component annotation file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="component_annotation_lookup",
            task_id=task_id,
        )

    document = json.loads(annotation_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "annotations": document.get("annotations", []),
        "groupHints": document.get("groupHints", []),
        "unannotatedElementIds": document.get("unannotatedElementIds", []),
        "unresolvedComponentIds": document.get("unresolvedComponentIds", []),
        "warnings": document.get("warnings", []),
        "meta": document.get("meta", {}),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)


@router.get("/tasks/{task_id}/layer-separation-candidates")
def get_task_layer_separation_candidates(task_id: str) -> dict[str, object]:
    task = state.database.get_task(task_id)
    if task is None:
        raise ApiError(
            "TASK_NOT_FOUND",
            "Task not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="task_lookup",
            task_id=task_id,
        )

    result = state.database.get_layer_separation_result(task_id)
    if result is None:
        raise ApiError(
            "LAYER_SEPARATION_NOT_FOUND",
            "Layer separation result not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="layer_separation_lookup",
            task_id=task_id,
        )

    separation_path = Path(result["separation_path"] or "")
    if not separation_path.exists():
        raise ApiError(
            "LAYER_SEPARATION_NOT_FOUND",
            "Layer separation file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="layer_separation_lookup",
            task_id=task_id,
        )

    document = json.loads(separation_path.read_text(encoding="utf-8"))
    data: dict[str, object] = {
        "taskId": task_id,
        "status": result["status"],
        "candidates": document.get("candidates", []),
        "fallbackContexts": document.get("fallbackContexts", []),
        "blockedComponentIds": document.get("blockedComponentIds", []),
        "warnings": document.get("warnings", []),
        "meta": document.get("meta", {}),
    }
    if document.get("error"):
        data["error"] = document["error"]
    return success_response(data)
