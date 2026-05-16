from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .component_structure import ComponentStructureDocument
from .config import Settings
from .layer_separation import LayerSeparationCandidate, LayerSeparationDocument
from .png_tools import (
    PngFillOperation,
    PngMetadata,
    PngRegion,
    UnsupportedPngCropError,
    crop_and_fill_png,
    crop_png,
    read_png_metadata,
)


AssetSliceDocumentStatus = Literal["completed", "failed", "skipped"]
AssetSliceStatus = Literal["candidate", "blocked", "failed", "skipped"]

SLICE_STATUSES = {"candidate", "blocked", "failed", "skipped"}
SLICE_STRATEGIES = {"local_slice_original", "local_slice_with_simple_fill", "blocked", "failed"}
FILL_MODES = {"solid_color_fill"}
SLICE_PRIORITY_ROLES = {"activity_card", "shortcut_card", "preview_card", "tip_card", "hero_profile"}


@dataclass
class AssetSliceWarning:
    code: str
    message: str
    componentId: str | None = None
    sliceId: str | None = None


@dataclass
class AssetSliceItem:
    id: str
    componentId: str
    componentRole: str
    layerSeparationCandidateId: str
    sourceStrategy: str
    status: AssetSliceStatus
    strategy: str
    bbox: list[int]
    assetId: str | None
    assetPath: str | None
    assetUrl: str | None
    filledAssetId: str | None
    filledAssetPath: str | None
    filledAssetUrl: str | None
    fillOperations: list[dict[str, Any]]
    quality: dict[str, Any]


@dataclass
class AssetSliceCandidateDocument:
    version: str
    taskId: str
    status: AssetSliceDocumentStatus
    imageSize: dict[str, int]
    slices: list[AssetSliceItem]
    blockedComponentIds: list[str]
    warnings: list[AssetSliceWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssetSliceStorageAdapter:
    assets_root: Path
    public_base_url: str

    def slice_path(self, task_id: str, filename: str) -> Path:
        return self.assets_root / task_id / "slices" / filename

    def slice_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/slices/{filename}"

    def write_slice(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.slice_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


def build_asset_slice_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    layer_separation_document: LayerSeparationDocument,
    structure_document: ComponentStructureDocument,
    dsl: dict[str, Any],
    settings: Settings,
    storage: AssetSliceStorageAdapter,
) -> AssetSliceCandidateDocument:
    del dsl
    if not settings.asset_slice_enabled:
        return build_skipped_asset_slice_document(
            task_id=task_id,
            image=image,
            code="asset_slice_disabled",
            message="Asset slice generation is disabled.",
        )
    if layer_separation_document.status != "completed":
        return build_skipped_asset_slice_document(
            task_id=task_id,
            image=image,
            code="layer_separation_not_completed",
            message="Asset slice generation skipped because layer separation did not complete.",
        )

    components_by_id = {component.id: component for component in structure_document.components}
    slices: list[AssetSliceItem] = []
    warnings: list[AssetSliceWarning] = []
    blocked_ids: list[str] = []
    selected_count = 0
    for index, candidate in enumerate(layer_separation_document.candidates, start=1):
        item, item_warnings = build_slice_for_candidate(
            task_id=task_id,
            index=index,
            image=image,
            png_data=png_data,
            candidate=candidate,
            component_confidence=float(getattr(components_by_id.get(candidate.componentId), "confidence", 0.0) or 0.0),
            settings=settings,
            storage=storage,
            selected_count=selected_count,
        )
        if item.status == "candidate":
            selected_count += 1
        if item.status == "blocked":
            blocked_ids.append(candidate.componentId)
        slices.append(item)
        warnings.extend(item_warnings)

    document = AssetSliceCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        slices=slices,
        blockedComponentIds=blocked_ids,
        warnings=warnings,
        meta=build_meta(slices),
    )
    validation_errors = validate_asset_slice_document(
        document=document,
        layer_separation_document=layer_separation_document,
        structure_document=structure_document,
        image=image,
    )
    if validation_errors:
        return build_failed_asset_slice_document(
            task_id=task_id,
            image=image,
            code="ASSET_SLICE_VALIDATION_FAILED",
            message="Asset slice validation failed.",
            warnings=[AssetSliceWarning(code="ASSET_SLICE_VALIDATION_ERROR", message=error) for error in validation_errors],
        )
    return document


def build_slice_for_candidate(
    *,
    task_id: str,
    index: int,
    image: PngMetadata,
    png_data: bytes,
    candidate: LayerSeparationCandidate,
    component_confidence: float,
    settings: Settings,
    storage: AssetSliceStorageAdapter,
    selected_count: int,
) -> tuple[AssetSliceItem, list[AssetSliceWarning]]:
    warnings: list[AssetSliceWarning] = []
    slice_id = f"asset_slice_{index:03d}"
    reasons = ["m18_candidate_found"]
    bbox = [int(value) for value in candidate.bbox]

    block_reason = slice_block_reason(
        candidate=candidate,
        component_confidence=component_confidence,
        bbox=bbox,
        image=image,
        settings=settings,
        selected_count=selected_count,
    )
    if block_reason is not None:
        reasons.append(block_reason)
        skipped = block_reason in {"component_role_not_slice_priority", "m18_candidate_not_simple_fill"}
        return (
            AssetSliceItem(
                id=slice_id,
                componentId=candidate.componentId,
                componentRole=candidate.componentRole,
                layerSeparationCandidateId=candidate.id,
                sourceStrategy=candidate.strategy,
                status="skipped" if skipped else "blocked",
                strategy="blocked",
                bbox=bbox,
                assetId=None,
                assetPath=None,
                assetUrl=None,
                filledAssetId=None,
                filledAssetPath=None,
                filledAssetUrl=None,
                fillOperations=[],
                quality={"risk": "medium" if skipped else "high", "reasons": reasons},
            ),
            warnings,
        )

    reasons.extend(["m18_candidate_low_risk", "crop_bbox_valid"])
    base_filename = safe_filename(candidate.componentId)
    asset_id = f"asset_slice_{candidate.componentId}"
    asset_path: Path | None = None
    asset_url: str | None = None
    try:
        cropped = crop_png(png_data, PngRegion(base_filename, bbox[0], bbox[1], bbox[2], bbox[3]))
        asset_path = storage.write_slice(task_id, f"{base_filename}.png", cropped)
        asset_url = storage.slice_url(task_id, f"{base_filename}.png")
    except UnsupportedPngCropError as error:
        warnings.append(AssetSliceWarning(code="png_crop_unsupported", message=str(error), componentId=candidate.componentId, sliceId=slice_id))
        return failed_slice(slice_id, candidate, bbox, reasons + ["png_crop_unsupported"])
    except OSError as error:
        warnings.append(AssetSliceWarning(code="asset_write_failed", message=str(error), componentId=candidate.componentId, sliceId=slice_id))
        return failed_slice(slice_id, candidate, bbox, reasons + ["asset_write_failed"])

    fill_operations, fill_reason = build_fill_operations(candidate, bbox, image)
    filled_asset_id: str | None = None
    filled_asset_path: Path | None = None
    filled_asset_url: str | None = None
    strategy = "local_slice_original"
    if settings.asset_slice_generate_filled and fill_operations and fill_reason is None:
        reasons.extend(["simple_fill_available", "simple_fill_applied"])
        try:
            png_operations = [
                PngFillOperation(
                    x=operation["sliceLocalBBox"][0],
                    y=operation["sliceLocalBBox"][1],
                    width=operation["sliceLocalBBox"][2],
                    height=operation["sliceLocalBBox"][3],
                    rgb=hex_to_rgb_tuple(operation["color"]),
                )
                for operation in fill_operations
            ]
            filled = crop_and_fill_png(png_data, PngRegion(base_filename, bbox[0], bbox[1], bbox[2], bbox[3]), png_operations)
            filled_filename = f"{base_filename}.filled.png"
            filled_asset_path = storage.write_slice(task_id, filled_filename, filled)
            filled_asset_url = storage.slice_url(task_id, filled_filename)
            filled_asset_id = f"asset_slice_filled_{candidate.componentId}"
            strategy = "local_slice_with_simple_fill"
        except (UnsupportedPngCropError, ValueError) as error:
            warnings.append(AssetSliceWarning(code="png_fill_unsupported", message=str(error), componentId=candidate.componentId, sliceId=slice_id))
            reasons.append("png_fill_unsupported")
    elif fill_reason is not None:
        reasons.append(fill_reason)

    return (
        AssetSliceItem(
            id=slice_id,
            componentId=candidate.componentId,
            componentRole=candidate.componentRole,
            layerSeparationCandidateId=candidate.id,
            sourceStrategy=candidate.strategy,
            status="candidate",
            strategy=strategy,
            bbox=bbox,
            assetId=asset_id,
            assetPath=str(asset_path),
            assetUrl=asset_url,
            filledAssetId=filled_asset_id,
            filledAssetPath=str(filled_asset_path) if filled_asset_path is not None else None,
            filledAssetUrl=filled_asset_url,
            fillOperations=fill_operations if strategy == "local_slice_with_simple_fill" else [],
            quality={"risk": "low", "reasons": unique_preserve_order(reasons)},
        ),
        warnings,
    )


def failed_slice(
    slice_id: str,
    candidate: LayerSeparationCandidate,
    bbox: list[int],
    reasons: list[str],
) -> tuple[AssetSliceItem, list[AssetSliceWarning]]:
    return (
        AssetSliceItem(
            id=slice_id,
            componentId=candidate.componentId,
            componentRole=candidate.componentRole,
            layerSeparationCandidateId=candidate.id,
            sourceStrategy=candidate.strategy,
            status="failed",
            strategy="failed",
            bbox=bbox,
            assetId=None,
            assetPath=None,
            assetUrl=None,
            filledAssetId=None,
            filledAssetPath=None,
            filledAssetUrl=None,
            fillOperations=[],
            quality={"risk": "high", "reasons": unique_preserve_order(reasons)},
        ),
        [],
    )


def slice_block_reason(
    *,
    candidate: LayerSeparationCandidate,
    component_confidence: float,
    bbox: list[int],
    image: PngMetadata,
    settings: Settings,
    selected_count: int,
) -> str | None:
    if candidate.componentRole not in SLICE_PRIORITY_ROLES:
        return "component_role_not_slice_priority"
    if candidate.status != "candidate" or candidate.strategy != "image_slice_with_simple_fill_candidate":
        return "fallback_context_not_sliceable" if candidate.strategy == "fallback_context_only" else "m18_candidate_not_simple_fill"
    if selected_count >= settings.asset_slice_max_candidates:
        return "asset_slice_candidate_limit_reached"
    if component_confidence < settings.asset_slice_min_confidence:
        return "component_confidence_low"
    if not bbox_in_bounds(bbox, image):
        return "crop_bbox_out_of_bounds"
    if bbox[2] * bbox[3] <= 16:
        return "crop_bbox_too_small"
    if bbox[2] * bbox[3] / max(1, image.width * image.height) > settings.asset_slice_max_area_ratio:
        return "crop_bbox_too_large"
    return None


def build_fill_operations(
    candidate: LayerSeparationCandidate,
    crop_bbox: list[int],
    image: PngMetadata,
) -> tuple[list[dict[str, Any]], str | None]:
    fill = candidate.fillCandidate
    if not fill.get("enabled") or fill.get("mode") != "solid_color_fill":
        return [], "simple_fill_unavailable"
    color = fill.get("color")
    if not isinstance(color, str) or hex_to_rgb_tuple(color) is None:
        return [], "png_fill_unsupported"
    operations: list[dict[str, Any]] = []
    crop_x, crop_y, crop_width, crop_height = crop_bbox
    crop_area = crop_width * crop_height
    for target in fill.get("targetBBoxes") or []:
        if not bbox_in_bounds(target, image):
            return [], "fill_target_out_of_bounds"
        source_bbox = [int(value) for value in target]
        local = [source_bbox[0] - crop_x, source_bbox[1] - crop_y, source_bbox[2], source_bbox[3]]
        if local[0] < 0 or local[1] < 0 or local[0] + local[2] > crop_width or local[1] + local[3] > crop_height:
            return [], "fill_target_outside_crop"
        if local[2] * local[3] / max(1, crop_area) > 0.40:
            return [], "fill_target_too_large"
        operations.append(
            {
                "mode": "solid_color_fill",
                "sourceBBox": source_bbox,
                "sliceLocalBBox": local,
                "color": color.upper(),
                "confidence": round(float(fill.get("confidence", 0) or 0), 3),
            }
        )
    if not operations:
        return [], "simple_fill_unavailable"
    return operations, None


def apply_asset_slice_metadata(dsl: dict[str, Any], document: AssetSliceCandidateDocument) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m19_local_asset_slice_candidates" not in quality_flags:
        quality_flags.append("m19_local_asset_slice_candidates")
    meta["qualityFlags"] = quality_flags
    meta["assetSliceCandidateCount"] = int(document.meta.get("sliceCount", 0))
    meta["assetSliceFilledCandidateCount"] = int(document.meta.get("filledSliceCount", 0))
    meta["assetSliceBlockedCount"] = int(document.meta.get("blockedCount", 0))
    meta["assetSliceFailedCount"] = int(document.meta.get("failedSliceCount", 0))
    return next_dsl


def validate_asset_slice_document(
    *,
    document: AssetSliceCandidateDocument,
    layer_separation_document: LayerSeparationDocument,
    structure_document: ComponentStructureDocument,
    image: PngMetadata,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    slice_ids = {item.id for item in document.slices}
    if len(slice_ids) != len(document.slices):
        errors.append("slice ids must be unique")
    component_ids = {component.id for component in structure_document.components}
    candidate_ids = {candidate.id for candidate in layer_separation_document.candidates}
    for item in document.slices:
        if item.componentId not in component_ids:
            errors.append(f"slice references missing component: {item.id}")
        if item.layerSeparationCandidateId not in candidate_ids:
            errors.append(f"slice references missing layer separation candidate: {item.id}")
        if item.status not in SLICE_STATUSES:
            errors.append(f"invalid slice status: {item.id}")
        if item.strategy not in SLICE_STRATEGIES:
            errors.append(f"invalid slice strategy: {item.id}")
        if not bbox_in_bounds(item.bbox, image):
            errors.append(f"slice bbox is out of bounds: {item.id}")
        if item.status == "candidate":
            if not item.assetPath or not Path(item.assetPath).exists():
                errors.append(f"candidate slice asset path must exist: {item.id}")
            if not item.assetUrl:
                errors.append(f"candidate slice asset url is required: {item.id}")
        if item.strategy == "local_slice_with_simple_fill":
            if not item.filledAssetPath or not Path(item.filledAssetPath).exists():
                errors.append(f"filled slice asset path must exist: {item.id}")
            if not item.filledAssetUrl:
                errors.append(f"filled slice asset url is required: {item.id}")
        for operation in item.fillOperations:
            if operation.get("mode") not in FILL_MODES:
                errors.append(f"invalid fill mode: {item.id}")
            if not bbox_in_bounds(operation.get("sourceBBox") or [], image):
                errors.append(f"fill source bbox is out of bounds: {item.id}")
            local = operation.get("sliceLocalBBox") or []
            if not bbox_in_bounds(local, PngMetadata(item.bbox[2], item.bbox[3], 8, 2, 0, 0, 0)):
                errors.append(f"fill local bbox is out of slice bounds: {item.id}")
    if document.meta.get("sliceCount") != sum(1 for item in document.slices if item.status == "candidate"):
        errors.append("meta sliceCount must match candidate slices")
    if document.meta.get("filledSliceCount") != sum(1 for item in document.slices if item.strategy == "local_slice_with_simple_fill"):
        errors.append("meta filledSliceCount must match filled slices")
    if document.meta.get("blockedCount") != sum(1 for item in document.slices if item.status == "blocked"):
        errors.append("meta blockedCount must match blocked slices")
    if document.meta.get("failedSliceCount") != sum(1 for item in document.slices if item.status == "failed"):
        errors.append("meta failedSliceCount must match failed slices")
    if document.meta.get("roleSummary") != summarize_roles(document.slices):
        errors.append("meta roleSummary must match slices")
    if document.meta.get("strategySummary") != summarize_strategies(document.slices):
        errors.append("meta strategySummary must match slices")
    return errors


def build_skipped_asset_slice_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> AssetSliceCandidateDocument:
    return AssetSliceCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        slices=[],
        blockedComponentIds=[],
        warnings=[AssetSliceWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_asset_slice_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[AssetSliceWarning] | None = None,
) -> AssetSliceCandidateDocument:
    return AssetSliceCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        slices=[],
        blockedComponentIds=[],
        warnings=warnings or [AssetSliceWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_meta(slices: list[AssetSliceItem]) -> dict[str, Any]:
    return {
        "notes": "local_asset_slice_experiment_harness",
        "sliceCount": sum(1 for item in slices if item.status == "candidate"),
        "filledSliceCount": sum(1 for item in slices if item.strategy == "local_slice_with_simple_fill"),
        "blockedCount": sum(1 for item in slices if item.status == "blocked"),
        "failedSliceCount": sum(1 for item in slices if item.status == "failed"),
        "roleSummary": summarize_roles(slices),
        "strategySummary": summarize_strategies(slices),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "local_asset_slice_experiment_harness",
        "sliceCount": 0,
        "filledSliceCount": 0,
        "blockedCount": 0,
        "failedSliceCount": 0,
        "roleSummary": {},
        "strategySummary": {},
    }


def summarize_roles(slices: list[AssetSliceItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in slices:
        summary[item.componentRole] = summary.get(item.componentRole, 0) + 1
    return summary


def summarize_strategies(slices: list[AssetSliceItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in slices:
        summary[item.strategy] = summary.get(item.strategy, 0) + 1
    return summary


def bbox_in_bounds(bbox: Any, image: PngMetadata) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    try:
        x, y, width, height = [int(value) for value in bbox]
    except (TypeError, ValueError):
        return False
    return width > 0 and height > 0 and x >= 0 and y >= 0 and x + width <= image.width and y + height <= image.height


def hex_to_rgb_tuple(value: str) -> tuple[int, int, int] | None:
    normalized = value.strip().lstrip("#")
    if len(normalized) != 6:
        return None
    try:
        return (int(normalized[0:2], 16), int(normalized[2:4], 16), int(normalized[4:6], 16))
    except ValueError:
        return None


def safe_filename(value: str) -> str:
    allowed = []
    for character in value:
        if character.isalnum() or character in {"_", "-"}:
            allowed.append(character)
        else:
            allowed.append("_")
    filename = "".join(allowed).strip("_")
    return filename or "slice"


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def slice_asset_records(document: AssetSliceCandidateDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in document.slices:
        if item.assetId and item.assetPath and item.assetUrl:
            width, height = image_size(item.assetPath, item.bbox)
            records.append(
                {
                    "asset_id": item.assetId,
                    "task_id": task_id,
                    "role": "asset_slice_candidate",
                    "path": item.assetPath,
                    "url": item.assetUrl,
                    "mime_type": "image/png",
                    "width": width,
                    "height": height,
                    "created_at": created_at,
                }
            )
        if item.filledAssetId and item.filledAssetPath and item.filledAssetUrl:
            width, height = image_size(item.filledAssetPath, item.bbox)
            records.append(
                {
                    "asset_id": item.filledAssetId,
                    "task_id": task_id,
                    "role": "asset_slice_filled_candidate",
                    "path": item.filledAssetPath,
                    "url": item.filledAssetUrl,
                    "mime_type": "image/png",
                    "width": width,
                    "height": height,
                    "created_at": created_at,
                }
            )
    return records


def image_size(path: str, fallback_bbox: list[int]) -> tuple[int, int]:
    metadata = read_png_metadata(Path(path).read_bytes())
    if metadata is None:
        return fallback_bbox[2], fallback_bbox[3]
    return metadata.width, metadata.height
