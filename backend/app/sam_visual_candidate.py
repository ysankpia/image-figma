from __future__ import annotations

import importlib
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .component_annotation import index_dsl_elements
from .config import Settings
from .icon_business_candidate import IconBusinessCandidateDocument, is_line_like, is_text_like, unique_bboxes
from .icon_candidate import IconCandidateDocument, bbox_in_bounds, iou, normalize_bbox
from .icon_coverage import bboxes_by_role, draw_rect
from .icon_gap_candidate import IconGapCandidateDocument
from .icon_placement_plan import IconPlacementPlanDocument
from .perception_benchmark import infer_sam2_config, resize_rgb_for_sam2, sam2_bbox_to_image_bbox, sam2_device
from .png_tools import PngMetadata, PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png


SamVisualDocumentStatus = Literal["completed", "failed", "skipped"]
SamVisualCandidateSource = Literal["sam2_automatic_mask"]
SamVisualRisk = Literal["low", "medium", "high"]

DOCUMENT_STATUSES = {"completed", "failed", "skipped"}
CANDIDATE_KINDS = {
    "business_icon_candidate",
    "component_candidate",
    "image_candidate",
    "button_candidate",
    "card_candidate",
    "nav_candidate",
    "text_like",
    "unknown_visual",
}
SOURCES = {"sam2_automatic_mask"}
RISKS = {"low", "medium", "high"}

OVERLAY_COLORS = {
    "accepted_visual": (0, 200, 90),
    "accepted_component": (0, 122, 255),
    "text_conflict": (255, 205, 0),
    "invalid": (235, 64, 52),
    "exclusion": (150, 80, 220),
    "duplicate": (128, 128, 128),
}


@dataclass
class SamVisualWarning:
    code: str
    message: str
    candidateId: str | None = None


@dataclass
class SamVisualQuality:
    risk: SamVisualRisk
    reasons: list[str]


@dataclass
class SamVisualComponentHint:
    region: str
    componentId: str | None
    componentRole: str | None


@dataclass
class SamVisualCandidate:
    id: str
    bbox: list[int]
    maskArea: int
    area: int
    kind: str
    source: SamVisualCandidateSource
    confidence: float
    placementRoleHint: str | None
    componentHint: SamVisualComponentHint
    quality: SamVisualQuality


@dataclass
class BlockedSamVisualCandidate:
    id: str
    bbox: list[int]
    maskArea: int
    kind: str
    source: SamVisualCandidateSource
    confidence: float
    status: Literal["blocked"] = "blocked"
    reasons: list[str] = field(default_factory=list)


@dataclass
class SamVisualOverlay:
    assetId: str
    assetPath: str
    assetUrl: str


@dataclass
class SamVisualRuntime:
    model: str
    device: str
    checkpoint: str
    elapsedMs: int
    rawMaskCount: int
    maxImageEdge: int


@dataclass
class SamVisualCandidateDocument:
    version: str
    taskId: str
    status: SamVisualDocumentStatus
    imageSize: dict[str, int]
    sam: SamVisualRuntime
    candidates: list[SamVisualCandidate]
    blockedCandidates: list[BlockedSamVisualCandidate]
    overlay: SamVisualOverlay | None
    warnings: list[SamVisualWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SamVisualStorageAdapter:
    assets_root: Path
    public_base_url: str

    def overlay_path(self, task_id: str) -> Path:
        return self.assets_root / task_id / "debug" / "sam_visual_candidate_overlay.png"

    def overlay_url(self, task_id: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/debug/sam_visual_candidate_overlay.png"

    def write_overlay(self, task_id: str, data: bytes) -> Path:
        path = self.overlay_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


@dataclass(frozen=True)
class SamVisualContext:
    task_id: str
    image: PngMetadata
    png_data: bytes
    dsl: dict[str, Any]
    settings: Settings
    storage: SamVisualStorageAdapter
    icon_candidate_document: IconCandidateDocument | None
    icon_gap_document: IconGapCandidateDocument | None
    icon_placement_document: IconPlacementPlanDocument | None
    icon_business_document: IconBusinessCandidateDocument | None
    pixels: PngPixels | None
    text_bboxes: list[list[int]]
    cover_bboxes: list[list[int]]
    existing_icon_bboxes: list[list[int]]
    status_bar_bboxes: list[list[int]]
    header_title_bboxes: list[list[int]]
    illustration_bboxes: list[list[int]]
    bed_map_bboxes: list[list[int]]


def build_sam_visual_candidate_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    dsl: dict[str, Any],
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    icon_placement_document: IconPlacementPlanDocument | None,
    icon_business_document: IconBusinessCandidateDocument | None,
    settings: Settings,
    storage: SamVisualStorageAdapter,
) -> SamVisualCandidateDocument:
    if not settings.sam_visual_candidate_enabled:
        return build_skipped_sam_visual_document(
            task_id=task_id,
            image=image,
            code="sam_visual_candidate_disabled",
            message="SAM visual candidate filtering is disabled.",
        )

    started = time.perf_counter()
    checkpoint = settings.sam_visual_candidate_checkpoint
    if not checkpoint or not Path(checkpoint).exists():
        return build_skipped_sam_visual_document(
            task_id=task_id,
            image=image,
            code="SAM_VISUAL_PROVIDER_UNAVAILABLE",
            message="SAM2 checkpoint is not configured or does not exist.",
            warning_code="model_missing",
        )

    try:
        torch = importlib.import_module("torch")
        np = importlib.import_module("numpy")
        build_module = importlib.import_module("sam2.build_sam")
        mask_module = importlib.import_module("sam2.automatic_mask_generator")
    except Exception as error:
        return build_skipped_sam_visual_document(
            task_id=task_id,
            image=image,
            code="SAM_VISUAL_PROVIDER_UNAVAILABLE",
            message=f"SAM2 dependency import failed: {error}",
            warning_code="dependency_missing",
        )

    try:
        pixels = decode_png_pixels(png_data)
    except UnsupportedPngCropError:
        return build_skipped_sam_visual_document(
            task_id=task_id,
            image=image,
            code="SAM_VISUAL_PROVIDER_UNAVAILABLE",
            message="PNG pixels could not be decoded.",
            warning_code="png_decode_unsupported",
        )

    elements = index_dsl_elements(dsl)
    context = SamVisualContext(
        task_id=task_id,
        image=image,
        png_data=png_data,
        dsl=dsl,
        settings=settings,
        storage=storage,
        icon_candidate_document=icon_candidate_document,
        icon_gap_document=icon_gap_document,
        icon_placement_document=icon_placement_document,
        icon_business_document=icon_business_document,
        pixels=pixels,
        text_bboxes=unique_bboxes(
            bboxes_by_role(elements, {"visible_text_replacement"}) + bboxes_by_role(elements, {"candidate_text"})
        ),
        cover_bboxes=unique_bboxes(bboxes_by_role(elements, {"text_replacement_cover"})),
        existing_icon_bboxes=collect_existing_icon_bboxes(
            icon_candidate_document=icon_candidate_document,
            icon_gap_document=icon_gap_document,
            icon_placement_document=icon_placement_document,
            icon_business_document=icon_business_document,
            elements=elements,
        ),
        status_bar_bboxes=status_bar_zones(image),
        header_title_bboxes=header_title_zones(image),
        illustration_bboxes=illustration_zones(image),
        bed_map_bboxes=bed_map_zones(image),
    )

    try:
        device = sam2_device(settings.sam_visual_candidate_device, torch)
        config = settings.sam_visual_candidate_model_cfg or infer_sam2_config(checkpoint)
        rgb = np.frombuffer(b"".join(pixels.rows), dtype=np.uint8).reshape((image.height, image.width, 3))
        scaled_rgb, scale = resize_rgb_for_sam2(rgb, settings.sam_visual_candidate_max_image_edge, np)
        model = build_module.build_sam2(config, checkpoint, device=device, apply_postprocessing=False)
        generator = mask_module.SAM2AutomaticMaskGenerator(
            model,
            points_per_side=16,
            points_per_batch=32,
            pred_iou_thresh=0.72,
            stability_score_thresh=0.82,
            crop_n_layers=0,
            min_mask_region_area=16,
            output_mode="binary_mask",
        )
        with torch.inference_mode():
            masks = generator.generate(scaled_rgb)
    except Exception as error:
        return build_failed_sam_visual_document(
            task_id=task_id,
            image=image,
            code="SAM_VISUAL_CANDIDATE_FAILED",
            message=str(error),
        )

    candidates: list[SamVisualCandidate] = []
    blocked: list[BlockedSamVisualCandidate] = []
    warnings: list[SamVisualWarning] = []
    sorted_masks = sorted(masks, key=lambda item: float(item.get("predicted_iou") or 0), reverse=True)
    for raw_mask in sorted_masks[: settings.sam_visual_candidate_max_masks]:
        bbox = sam2_bbox_to_image_bbox(raw_mask.get("bbox"), scale, image)
        if bbox is None:
            continue
        mask_area = int(round(float(raw_mask.get("area") or 0) / max(scale * scale, 0.000001)))
        append_mask_candidate(
            context=context,
            candidates=candidates,
            blocked=blocked,
            bbox=bbox,
            mask_area=mask_area,
            raw_confidence=raw_sam_confidence(raw_mask),
            raw_reasons=raw_sam_reasons(raw_mask),
        )
        if len(candidates) >= settings.sam_visual_candidate_max_candidates:
            warnings.append(
                SamVisualWarning(
                    code="sam_visual_candidate_limit_reached",
                    message="SAM visual candidate max candidate limit reached.",
                )
            )
            break

    elapsed = elapsed_ms(started)
    if elapsed > 20000:
        warnings.append(SamVisualWarning(code="runtime_over_threshold", message="SAM visual candidate runtime exceeded 20s."))
    overlay = build_overlay(context, candidates, blocked) if settings.sam_visual_candidate_overlay_enabled else None
    if overlay is None and settings.sam_visual_candidate_overlay_enabled:
        warnings.append(SamVisualWarning(code="overlay_write_failed", message="SAM visual candidate overlay could not be written."))

    document = SamVisualCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        sam=SamVisualRuntime(
            model=config,
            device=device,
            checkpoint="configured",
            elapsedMs=elapsed,
            rawMaskCount=len(masks),
            maxImageEdge=settings.sam_visual_candidate_max_image_edge,
        ),
        candidates=candidates,
        blockedCandidates=blocked,
        overlay=overlay,
        warnings=warnings,
        meta=build_meta(candidates, blocked, len(masks)),
    )
    validation_errors = validate_sam_visual_candidate_document(document, image)
    if validation_errors:
        return build_failed_sam_visual_document(
            task_id=task_id,
            image=image,
            code="SAM_VISUAL_CANDIDATE_VALIDATION_FAILED",
            message="SAM visual candidate validation failed.",
            warnings=[SamVisualWarning(code="SAM_VISUAL_CANDIDATE_VALIDATION_ERROR", message=error) for error in validation_errors],
        )
    return document


def append_mask_candidate(
    *,
    context: SamVisualContext,
    candidates: list[SamVisualCandidate],
    blocked: list[BlockedSamVisualCandidate],
    bbox: list[int],
    mask_area: int,
    raw_confidence: float,
    raw_reasons: list[str],
) -> None:
    kind = classify_kind(bbox, mask_area, context)
    block_reasons = classify_block_reasons(bbox, mask_area, raw_confidence, context)
    confidence = score_candidate(bbox, mask_area, raw_confidence, block_reasons, context)
    if confidence < context.settings.sam_visual_candidate_min_confidence and not block_reasons:
        block_reasons.append("confidence_below_threshold")
    if any(iou(bbox, item.bbox) > 0.80 for item in candidates):
        block_reasons.append("duplicate_existing_icon")
    block_reasons = unique_strings(block_reasons)
    if block_reasons:
        blocked.append(
            BlockedSamVisualCandidate(
                id=f"blocked_sam_visual_{len(blocked) + 1:03d}",
                bbox=bbox,
                maskArea=mask_area,
                kind=kind,
                source="sam2_automatic_mask",
                confidence=round(confidence, 3),
                reasons=block_reasons,
            )
        )
        return
    accepted_reasons = unique_strings(
        ["sam2_automatic_mask", "bbox_valid", "mask_area_valid", "no_text_overlap", "not_existing_icon_duplicate"] + raw_reasons
    )
    candidates.append(
        SamVisualCandidate(
            id=f"sam_visual_candidate_{len(candidates) + 1:03d}",
            bbox=bbox,
            maskArea=mask_area,
            area=bbox[2] * bbox[3],
            kind=kind,
            source="sam2_automatic_mask",
            confidence=round(confidence, 3),
            placementRoleHint=placement_role_hint(bbox, kind, context),
            componentHint=SamVisualComponentHint(region=region_hint(bbox, context.image), componentId=None, componentRole=None),
            quality=SamVisualQuality(risk="low" if confidence >= 0.82 else "medium", reasons=accepted_reasons),
        )
    )


def raw_sam_confidence(mask: dict[str, Any]) -> float:
    predicted = float(mask.get("predicted_iou") or 0.0)
    stability = float(mask.get("stability_score") or 0.0)
    if predicted <= 0 and stability <= 0:
        return 0.65
    return round(max(0.0, min(0.99, predicted * 0.65 + stability * 0.35)), 3)


def raw_sam_reasons(mask: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if float(mask.get("predicted_iou") or 0.0) >= 0.72 or float(mask.get("stability_score") or 0.0) >= 0.82:
        reasons.append("sam_quality_score_ok")
    return reasons


def classify_block_reasons(
    bbox: list[int],
    mask_area: int,
    raw_confidence: float,
    context: SamVisualContext,
) -> list[str]:
    reasons: list[str] = []
    settings = context.settings
    if not bbox_in_bounds(bbox, context.image):
        reasons.append("bbox_invalid")
    if mask_area < settings.sam_visual_candidate_min_area or bbox[2] < 8 or bbox[3] < 8:
        reasons.append("mask_area_too_small")
    if bbox[2] * bbox[3] > context.image.width * context.image.height * settings.sam_visual_candidate_max_area_ratio:
        reasons.extend(["mask_area_too_large", "background_like"])
    if is_line_like(bbox):
        reasons.append("line_like")
    if is_text_like(bbox):
        reasons.append("text_overlap")
    if any(iou(bbox, text_bbox) > settings.sam_visual_candidate_text_overlap_iou for text_bbox in context.text_bboxes):
        reasons.append("candidate_text_overlap")
    if any(iou(bbox, cover_bbox) > settings.sam_visual_candidate_text_overlap_iou for cover_bbox in context.cover_bboxes):
        reasons.append("cover_overlap")
    if any(iou(bbox, existing) > settings.sam_visual_candidate_existing_icon_iou for existing in context.existing_icon_bboxes):
        reasons.append("duplicate_existing_icon")
    if any(overlap_ratio(bbox, zone) > 0.35 for zone in context.status_bar_bboxes):
        reasons.append("inside_status_bar")
    if any(overlap_ratio(bbox, zone) > 0.35 for zone in context.header_title_bboxes):
        reasons.append("inside_header_title")
    if any(overlap_ratio(bbox, zone) > 0.35 for zone in context.illustration_bboxes):
        reasons.append("inside_illustration_zone")
    if any(overlap_ratio(bbox, zone) > 0.20 for zone in context.bed_map_bboxes):
        reasons.append("inside_bed_map_zone")
    if is_border_like(bbox, context.image):
        reasons.append("border_like")
    if is_button_background_like(bbox, context.image):
        reasons.append("button_background_like")
    if is_card_background_like(bbox, context.image):
        reasons.append("card_background_like")
    if raw_confidence < 0.55:
        reasons.append("confidence_below_threshold")
    return unique_strings(reasons)


def score_candidate(
    bbox: list[int],
    mask_area: int,
    raw_confidence: float,
    block_reasons: list[str],
    context: SamVisualContext,
) -> float:
    score = 0.55
    if 8 <= bbox[2] <= 120 and 8 <= bbox[3] <= 120:
        score += 0.10
    if context.settings.sam_visual_candidate_min_area <= mask_area <= bbox[2] * bbox[3]:
        score += 0.08
    if not any(reason in block_reasons for reason in {"text_overlap", "candidate_text_overlap", "cover_overlap"}):
        score += 0.08
    if region_hint(bbox, context.image) in {"content", "bottom_nav", "button", "card"}:
        score += 0.06
    if "duplicate_existing_icon" not in block_reasons:
        score += 0.05
    if raw_confidence >= 0.72:
        score += 0.05
    if any(reason in block_reasons for reason in {"text_overlap", "candidate_text_overlap"}):
        score -= 0.25
    if any(reason in block_reasons for reason in {"line_like", "border_like"}):
        score -= 0.25
    if any(reason in block_reasons for reason in {"background_like", "card_background_like", "button_background_like"}):
        score -= 0.25
    if any(reason.startswith("inside_") for reason in block_reasons):
        score -= 0.25
    if "duplicate_existing_icon" in block_reasons:
        score -= 0.20
    return max(0.0, min(0.99, round(score, 3)))


def classify_kind(bbox: list[int], mask_area: int, context: SamVisualContext) -> str:
    region = region_hint(bbox, context.image)
    if region == "bottom_nav" and icon_sized(bbox):
        return "nav_candidate"
    if is_button_like_zone(bbox, context.image) and icon_sized(bbox):
        return "button_candidate"
    if icon_sized(bbox):
        return "business_icon_candidate"
    if bbox[2] >= context.image.width * 0.45 and 28 <= bbox[3] <= 120:
        return "button_candidate"
    if 80 <= bbox[2] <= context.image.width * 0.92 and 50 <= bbox[3] <= context.image.height * 0.25:
        return "card_candidate"
    if mask_area > context.image.width * context.image.height * 0.04:
        return "image_candidate"
    if is_text_like(bbox):
        return "text_like"
    return "unknown_visual"


def placement_role_hint(bbox: list[int], kind: str, context: SamVisualContext) -> str | None:
    region = region_hint(bbox, context.image)
    center_x = bbox[0] + bbox[2] / 2
    if kind == "nav_candidate":
        return "nav_icon"
    if kind == "button_candidate":
        return "button_trailing_icon" if center_x > context.image.width * 0.55 else "button_leading_icon"
    if region == "content" and icon_sized(bbox):
        return "status_icon" if center_x < context.image.width * 0.35 else "leading_icon"
    return None


def region_hint(bbox: list[int], image: PngMetadata) -> str:
    center_y = bbox[1] + bbox[3] / 2
    if center_y < image.height * 0.055:
        return "status_bar"
    if center_y < image.height * 0.12:
        return "header"
    if center_y > image.height * 0.84:
        return "bottom_nav"
    if image.height * 0.62 <= center_y <= image.height * 0.88:
        return "button"
    if bbox[2] >= image.width * 0.35 and bbox[3] >= 48:
        return "card"
    return "content"


def build_overlay(
    context: SamVisualContext,
    candidates: list[SamVisualCandidate],
    blocked: list[BlockedSamVisualCandidate],
) -> SamVisualOverlay | None:
    if context.pixels is None:
        return None
    rows = [bytearray(row) for row in context.pixels.rows]
    for item in blocked:
        draw_rect(rows, context.image.width, context.image.height, item.bbox, blocked_color(item.reasons), thickness=2)
    for item in candidates:
        color = OVERLAY_COLORS["accepted_component"] if item.kind in {"component_candidate", "image_candidate", "card_candidate"} else OVERLAY_COLORS["accepted_visual"]
        draw_rect(rows, context.image.width, context.image.height, item.bbox, color, thickness=2)
    try:
        data = encode_rgb_png(context.image.width, context.image.height, [bytes(row) for row in rows])
        path = context.storage.write_overlay(context.task_id, data)
        return SamVisualOverlay(
            assetId="asset_sam_visual_candidate_overlay",
            assetPath=str(path),
            assetUrl=context.storage.overlay_url(context.task_id),
        )
    except (OSError, UnsupportedPngCropError):
        return None


def blocked_color(reasons: list[str]) -> tuple[int, int, int]:
    if "duplicate_existing_icon" in reasons:
        return OVERLAY_COLORS["duplicate"]
    if any(reason.startswith("inside_") for reason in reasons):
        return OVERLAY_COLORS["exclusion"]
    if any(reason in {"text_overlap", "candidate_text_overlap", "cover_overlap"} for reason in reasons):
        return OVERLAY_COLORS["text_conflict"]
    return OVERLAY_COLORS["invalid"]


def validate_sam_visual_candidate_document(document: SamVisualCandidateDocument, image: PngMetadata) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    if document.status not in DOCUMENT_STATUSES:
        errors.append("document status is invalid")
    candidate_ids = [item.id for item in document.candidates]
    blocked_ids = [item.id for item in document.blockedCandidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("candidate ids must be unique")
    if len(blocked_ids) != len(set(blocked_ids)):
        errors.append("blocked ids must be unique")
    for item in document.candidates:
        if item.kind not in CANDIDATE_KINDS:
            errors.append(f"candidate kind is invalid: {item.id}")
        if item.source not in SOURCES:
            errors.append(f"candidate source is invalid: {item.id}")
        if item.quality.risk not in RISKS:
            errors.append(f"candidate risk is invalid: {item.id}")
        if item.maskArea < 0 or item.area < 0:
            errors.append(f"candidate area is invalid: {item.id}")
        if not bbox_in_bounds(item.bbox, image):
            errors.append(f"candidate bbox out of bounds: {item.id}")
    for item in document.blockedCandidates:
        if item.kind not in CANDIDATE_KINDS:
            errors.append(f"blocked kind is invalid: {item.id}")
        if item.source not in SOURCES:
            errors.append(f"blocked source is invalid: {item.id}")
        if item.maskArea < 0:
            errors.append(f"blocked mask area is invalid: {item.id}")
        if not bbox_in_bounds(item.bbox, image):
            errors.append(f"blocked bbox out of bounds: {item.id}")
    if document.meta.get("candidateCount") != len(document.candidates):
        errors.append("meta candidateCount must match candidates")
    if document.meta.get("blockedCount") != len(document.blockedCandidates):
        errors.append("meta blockedCount must match blockedCandidates")
    if document.meta.get("rawMaskCount", 0) < 0:
        errors.append("meta rawMaskCount must be non-negative")
    if document.meta.get("kindSummary") != summarize_kinds(document.candidates):
        errors.append("meta kindSummary must match candidates")
    if document.meta.get("blockedReasonSummary") != summarize_blocked_reasons(document.blockedCandidates):
        errors.append("meta blockedReasonSummary must match blockedCandidates")
    if document.overlay is not None:
        if document.overlay.assetId != "asset_sam_visual_candidate_overlay":
            errors.append("overlay asset id is invalid")
        if not Path(document.overlay.assetPath).exists():
            errors.append("overlay asset path must exist")
    return errors


def sam_visual_overlay_asset_records(document: SamVisualCandidateDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    if document.overlay is None:
        return []
    return [
        {
            "asset_id": document.overlay.assetId,
            "task_id": task_id,
            "role": "asset_sam_visual_candidate_overlay",
            "path": document.overlay.assetPath,
            "url": document.overlay.assetUrl,
            "mime_type": "image/png",
            "width": document.imageSize["width"],
            "height": document.imageSize["height"],
            "created_at": created_at,
        }
    ]


def build_skipped_sam_visual_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warning_code: str | None = None,
) -> SamVisualCandidateDocument:
    warning = SamVisualWarning(code=warning_code or code, message=message)
    return SamVisualCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        sam=empty_runtime(),
        candidates=[],
        blockedCandidates=[],
        overlay=None,
        warnings=[warning],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_sam_visual_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[SamVisualWarning] | None = None,
) -> SamVisualCandidateDocument:
    return SamVisualCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        sam=empty_runtime(),
        candidates=[],
        blockedCandidates=[],
        overlay=None,
        warnings=warnings or [SamVisualWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_meta(candidates: list[SamVisualCandidate], blocked: list[BlockedSamVisualCandidate], raw_mask_count: int) -> dict[str, Any]:
    return {
        "notes": "sam2_visual_candidate_filtering",
        "candidateCount": len(candidates),
        "blockedCount": len(blocked),
        "rawMaskCount": raw_mask_count,
        "kindSummary": summarize_kinds(candidates),
        "blockedReasonSummary": summarize_blocked_reasons(blocked),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "sam2_visual_candidate_filtering",
        "candidateCount": 0,
        "blockedCount": 0,
        "rawMaskCount": 0,
        "kindSummary": {},
        "blockedReasonSummary": {},
    }


def empty_runtime() -> SamVisualRuntime:
    return SamVisualRuntime(model="", device="", checkpoint="", elapsedMs=0, rawMaskCount=0, maxImageEdge=0)


def summarize_kinds(candidates: list[SamVisualCandidate]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in candidates:
        summary[item.kind] = summary.get(item.kind, 0) + 1
    return summary


def summarize_blocked_reasons(blocked: list[BlockedSamVisualCandidate]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in blocked:
        for reason in item.reasons:
            summary[reason] = summary.get(reason, 0) + 1
    return summary


def collect_existing_icon_bboxes(
    *,
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    icon_placement_document: IconPlacementPlanDocument | None,
    icon_business_document: IconBusinessCandidateDocument | None,
    elements: dict[str, dict[str, Any]],
) -> list[list[int]]:
    bboxes: list[list[int]] = []
    if icon_candidate_document is not None and icon_candidate_document.status == "completed":
        bboxes.extend([icon.bbox for icon in icon_candidate_document.icons if icon.status == "candidate"])
    if icon_gap_document is not None and icon_gap_document.status == "completed":
        bboxes.extend([icon.bbox for icon in icon_gap_document.gapIcons if icon.status == "candidate"])
    if icon_placement_document is not None and icon_placement_document.status == "completed":
        bboxes.extend([item.bbox for item in icon_placement_document.placements if item.status == "planned"])
    if icon_business_document is not None and icon_business_document.status == "completed":
        bboxes.extend([item.bbox for item in icon_business_document.businessIcons if item.status == "candidate"])
    bboxes.extend(bboxes_by_role(elements, {"visible_icon_fallback"}))
    return unique_bboxes(bboxes)


def status_bar_zones(image: PngMetadata) -> list[list[int]]:
    return [[0, 0, image.width, round(image.height * 0.055)]]


def header_title_zones(image: PngMetadata) -> list[list[int]]:
    return [[round(image.width * 0.18), round(image.height * 0.04), round(image.width * 0.64), round(image.height * 0.07)]]


def illustration_zones(image: PngMetadata) -> list[list[int]]:
    return [[0, round(image.height * 0.10), image.width, round(image.height * 0.18)]]


def bed_map_zones(image: PngMetadata) -> list[list[int]]:
    return [[round(image.width * 0.04), round(image.height * 0.30), round(image.width * 0.92), round(image.height * 0.34)]]


def overlap_ratio(left: list[int], right: list[int]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    if x2 <= x1 or y2 <= y1:
        return 0
    return ((x2 - x1) * (y2 - y1)) / max(1, left[2] * left[3])


def icon_sized(bbox: list[int]) -> bool:
    return 8 <= bbox[2] <= 120 and 8 <= bbox[3] <= 120


def is_button_like_zone(bbox: list[int], image: PngMetadata) -> bool:
    center_y = bbox[1] + bbox[3] / 2
    return image.height * 0.55 <= center_y <= image.height * 0.90


def is_border_like(bbox: list[int], image: PngMetadata) -> bool:
    if bbox[2] >= image.width * 0.70 and bbox[3] <= 8:
        return True
    if bbox[3] >= image.height * 0.10 and bbox[2] <= 8:
        return True
    return False


def is_button_background_like(bbox: list[int], image: PngMetadata) -> bool:
    return bbox[2] >= image.width * 0.45 and 32 <= bbox[3] <= 96


def is_card_background_like(bbox: list[int], image: PngMetadata) -> bool:
    area_ratio = bbox[2] * bbox[3] / max(1, image.width * image.height)
    return bbox[2] >= image.width * 0.35 and bbox[3] >= 80 and area_ratio > 0.025


def elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
