from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .ocr import OCRBlock, OCRDocument
from .visual_primitives import VisualPrimitive, VisualPrimitiveDocument


PatchStatus = Literal["completed", "partial", "failed", "skipped"]


@dataclass
class DSLPatchWarning:
    code: str
    message: str
    patchId: str | None = None


@dataclass
class DSLPatch:
    id: str
    operation: Literal["add_element"]
    targetParentId: str
    element: dict[str, Any]


@dataclass
class DSLPatchDocument:
    version: str
    taskId: str
    sourceDslVersion: str
    mode: str
    patches: list[DSLPatch]
    warnings: list[DSLPatchWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    status: PatchStatus = "completed"
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_dsl_patch(
    *,
    base_dsl: dict[str, Any],
    ocr_document: OCRDocument,
    primitive_document: VisualPrimitiveDocument,
    mode: str,
) -> DSLPatchDocument:
    normalized_mode = normalize_patch_mode(mode)
    if normalized_mode == "off":
        return DSLPatchDocument(
            version="0.1",
            taskId=str(base_dsl.get("taskId") or ocr_document.taskId),
            sourceDslVersion=str(base_dsl.get("version") or "0.1"),
            mode="off",
            patches=[],
            warnings=[],
            meta={"notes": "dsl_patch_harness"},
            status="skipped",
        )

    patches = [
        build_text_patch(block, primitive_document)
        for block in ocr_document.blocks
    ]
    warnings: list[DSLPatchWarning] = []
    if normalized_mode == "apply":
        warnings.append(
            DSLPatchWarning(
                code="DSL_PATCH_APPLY_NOT_IMPLEMENTED",
                message="DSL_PATCH_MODE=apply is reserved for M10; M9 keeps OCR text candidates hidden.",
            )
        )

    return DSLPatchDocument(
        version="0.1",
        taskId=str(base_dsl.get("taskId") or ocr_document.taskId),
        sourceDslVersion=str(base_dsl.get("version") or "0.1"),
        mode=normalized_mode,
        patches=patches,
        warnings=warnings,
        meta={"notes": "dsl_patch_harness"},
        status="completed",
    )


def build_failed_patch_document(
    *,
    task_id: str,
    mode: str,
    code: str,
    message: str,
) -> DSLPatchDocument:
    return DSLPatchDocument(
        version="0.1",
        taskId=task_id,
        sourceDslVersion="0.1",
        mode=normalize_patch_mode(mode),
        patches=[],
        warnings=[DSLPatchWarning(code=code, message=message)],
        meta={"notes": "dsl_patch_harness"},
        status="failed",
        error={"code": code, "message": message},
    )


def build_text_patch(block: OCRBlock, primitive_document: VisualPrimitiveDocument) -> DSLPatch:
    element_id = f"text_{safe_id(block.id)}"
    nearest = nearest_primitive(block.bbox, primitive_document.primitives)
    meta: dict[str, Any] = {
        "source": "ocr",
        "candidate": True,
        "sourceBoxId": block.id,
        "reason": "m9_ocr_candidate_hidden_by_default",
        "ocrConfidence": block.confidence,
    }
    if nearest is not None:
        meta["nearestPrimitiveId"] = nearest.id
        if nearest.sourceRegionId:
            meta["sourceRegionId"] = nearest.sourceRegionId

    return DSLPatch(
        id=f"patch_{element_id}",
        operation="add_element",
        targetParentId="root",
        element={
            "id": element_id,
            "type": "text",
            "role": "candidate_text",
            "name": f"OCR Text Candidate / {block.id}",
            "layout": {
                "x": block.bbox[0],
                "y": block.bbox[1],
                "width": block.bbox[2],
                "height": block.bbox[3],
            },
            "style": {
                "visible": False,
                "opacity": 1,
                "color": "#111111",
                "fontSize": max(10, min(round(block.bbox[3] * 0.75), 32)),
                "fontWeight": 400,
            },
            "content": {
                "text": block.text,
            },
            "meta": meta,
        },
    )


def apply_dsl_patch(base_dsl: dict[str, Any], patch_document: DSLPatchDocument) -> dict[str, Any]:
    if patch_document.mode == "off" or patch_document.status != "completed":
        return deepcopy(base_dsl)

    next_dsl = deepcopy(base_dsl)
    root = next_dsl.setdefault("root", {})
    children = root.setdefault("children", [])
    for patch in patch_document.patches:
        if patch.operation == "add_element" and patch.targetParentId == "root":
            children.append(deepcopy(patch.element))

    meta = next_dsl.setdefault("meta", {})
    notes = str(meta.get("notes") or "")
    if "m9_patch_debug" not in notes:
        meta["notes"] = f"{notes}+m9_patch_debug" if notes else "m9_patch_debug"
    quality_flags = list(meta.get("qualityFlags") or [])
    if patch_document.patches and "m9_hidden_text_candidates" not in quality_flags:
        quality_flags.append("m9_hidden_text_candidates")
    if quality_flags:
        meta["qualityFlags"] = quality_flags
    meta["elementCount"] = len(children)
    return next_dsl


def validate_enhanced_dsl(dsl: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if dsl.get("version") != "0.1":
        errors.append("version must be 0.1")
    if not dsl.get("taskId"):
        errors.append("taskId is required")
    if not isinstance(dsl.get("root"), dict) or dsl["root"].get("type") != "frame":
        errors.append("root.type must be frame")

    assets = dsl.get("assets") if isinstance(dsl.get("assets"), list) else []
    asset_ids = {
        asset.get("assetId")
        for asset in assets
        if isinstance(asset, dict) and isinstance(asset.get("assetId"), str)
    }
    ids: set[str] = set()
    validate_element(dsl.get("root"), asset_ids, ids, errors)
    return errors


def validate_element(element: Any, asset_ids: set[str], ids: set[str], errors: list[str]) -> None:
    if not isinstance(element, dict):
        errors.append("element must be object")
        return
    element_id = element.get("id")
    if not isinstance(element_id, str) or not element_id:
        errors.append("element.id is required")
    elif element_id in ids:
        errors.append(f"duplicate element id: {element_id}")
    else:
        ids.add(element_id)

    layout = element.get("layout")
    if not isinstance(layout, dict) or not is_positive_number(layout.get("width")) or not is_positive_number(layout.get("height")):
        errors.append(f"invalid layout for element: {element_id}")

    if element.get("type") == "text":
        content = element.get("content")
        if not isinstance(content, dict) or not isinstance(content.get("text"), str) or not content["text"].strip():
            errors.append(f"text content required for element: {element_id}")

    if element.get("type") == "image":
        source = element.get("source")
        if not isinstance(source, dict):
            errors.append(f"image source required for element: {element_id}")
        elif isinstance(source.get("assetId"), str) and source["assetId"] not in asset_ids:
            errors.append(f"image asset missing for element: {element_id}")

    children = element.get("children")
    if children is not None:
        if not isinstance(children, list):
            errors.append(f"children must be array for element: {element_id}")
        else:
            for child in children:
                validate_element(child, asset_ids, ids, errors)


def nearest_primitive(bbox: list[int], primitives: list[VisualPrimitive]) -> VisualPrimitive | None:
    if not primitives:
        return None
    center_x = bbox[0] + bbox[2] / 2
    center_y = bbox[1] + bbox[3] / 2
    return min(
        primitives,
        key=lambda primitive: distance_to_bbox_center(center_x, center_y, primitive.bbox),
    )


def distance_to_bbox_center(x: float, y: float, bbox: list[int]) -> float:
    primitive_x = bbox[0] + bbox[2] / 2
    primitive_y = bbox[1] + bbox[3] / 2
    return abs(x - primitive_x) + abs(y - primitive_y)


def safe_id(value: str) -> str:
    normalized = "".join(char if char.isalnum() or char == "_" else "_" for char in value.strip())
    return normalized or "unknown"


def normalize_patch_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized in {"off", "debug", "apply"}:
        return normalized
    return "debug"


def is_positive_number(value: Any) -> bool:
    return isinstance(value, int | float) and value > 0
