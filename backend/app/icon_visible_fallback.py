from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .component_annotation import index_dsl_elements
from .config import Settings
from .icon_candidate import bbox_in_bounds, iou, padded_bbox, unique_preserve_order
from .icon_coverage import bboxes_by_role, draw_rect
from .icon_placement_plan import IconPlacementPlanDocument, IconPlacementPlanItem
from .png_tools import (
    PngMetadata,
    UnsupportedPngCropError,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
    sample_region_background,
)


IconVisibleFallbackDocumentStatus = Literal["completed", "failed", "skipped"]
IconVisibleFallbackStatus = Literal["applied", "blocked", "skipped", "failed"]

VISIBLE_FALLBACK_STATUSES = {"applied", "blocked", "skipped", "failed"}
SOURCE_STAGES = {"m20", "m22"}
ALLOWED_ROLE_DEFAULTS = {"nav_icon", "header_nav_icon", "header_action_icon", "leading_icon"}
ROLE_PRIORITY = {
    "nav_icon": 0,
    "header_nav_icon": 1,
    "header_action_icon": 2,
    "leading_icon": 3,
}

OVERLAY_COLORS = {
    "applied_icon": (0, 200, 90),
    "applied_cover": (150, 80, 220),
    "blocked": (235, 64, 52),
    "skipped": (255, 205, 0),
    "failed": (235, 64, 52),
}


@dataclass
class IconVisibleFallbackWarning:
    code: str
    message: str
    placementId: str | None = None


@dataclass
class IconVisibleFallbackMask:
    type: str
    bbox: list[int]
    color: str
    confidence: float
    reasons: list[str]


@dataclass
class IconVisibleFallbackItem:
    id: str
    placementId: str
    sourceStage: str
    sourceIconId: str
    assetId: str
    assetPath: str
    assetUrl: str
    componentId: str | None
    componentRole: str | None
    placementRole: str
    status: Literal["applied"]
    bbox: list[int]
    confidence: float
    coverNodeId: str
    iconNodeId: str
    mask: IconVisibleFallbackMask
    quality: dict[str, Any]


@dataclass
class BlockedVisiblePlacement:
    id: str
    placementId: str
    sourceStage: str
    sourceIconId: str
    bbox: list[int]
    status: Literal["blocked"]
    reasons: list[str]


@dataclass
class IconVisibleFallbackOverlay:
    assetId: str
    assetPath: str
    assetUrl: str


@dataclass
class IconVisibleFallbackDocument:
    version: str
    taskId: str
    status: IconVisibleFallbackDocumentStatus
    imageSize: dict[str, int]
    visibleIcons: list[IconVisibleFallbackItem]
    blockedPlacements: list[BlockedVisiblePlacement]
    visibleFallbackOverlay: IconVisibleFallbackOverlay | None
    warnings: list[IconVisibleFallbackWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IconVisibleFallbackStorageAdapter:
    assets_root: Path
    public_base_url: str

    def overlay_path(self, task_id: str, filename: str) -> Path:
        return self.assets_root / task_id / "debug" / filename

    def overlay_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/debug/{filename}"

    def write_overlay(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.overlay_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


def build_icon_visible_fallback_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    icon_placement_document: IconPlacementPlanDocument | None,
    dsl: dict[str, Any],
    settings: Settings,
    storage: IconVisibleFallbackStorageAdapter,
) -> IconVisibleFallbackDocument:
    if not settings.icon_visible_fallback_enabled:
        return build_skipped_icon_visible_fallback_document(
            task_id=task_id,
            image=image,
            code="icon_visible_fallback_disabled",
            message="Icon visible fallback replay is disabled.",
        )
    if icon_placement_document is None or icon_placement_document.status != "completed":
        return build_skipped_icon_visible_fallback_document(
            task_id=task_id,
            image=image,
            code="icon_placement_plan_not_completed",
            message="Icon visible fallback replay skipped because M23 placement plan did not complete.",
        )

    try:
        pixels = decode_png_pixels(png_data)
    except UnsupportedPngCropError as error:
        return build_skipped_icon_visible_fallback_document(
            task_id=task_id,
            image=image,
            code="png_pixel_decode_unsupported",
            message=str(error),
        )

    elements = index_dsl_elements(dsl)
    text_bboxes = bboxes_by_role(elements, {"visible_text_replacement"})
    cover_bboxes = bboxes_by_role(elements, {"text_replacement_cover"})
    candidate_text_bboxes = bboxes_by_role(elements, {"candidate_text"})
    allowed_roles = set(settings.icon_visible_fallback_allowed_roles or ALLOWED_ROLE_DEFAULTS) & ALLOWED_ROLE_DEFAULTS
    placement_pool = sorted(
        [
            (index, placement)
            for index, placement in enumerate(icon_placement_document.placements)
            if placement.decision == "needs_fallback_mask" and placement.status == "planned"
        ],
        key=lambda item: (
            ROLE_PRIORITY.get(item[1].placementRole, 99),
            -float(item[1].confidence),
            item[0],
        ),
    )

    warnings: list[IconVisibleFallbackWarning] = []
    if len(placement_pool) > settings.icon_visible_fallback_max_placements:
        warnings.append(
            IconVisibleFallbackWarning(
                code="icon_visible_fallback_limit_reached",
                message="Icon visible fallback placement limit reached.",
            )
        )
    selected = placement_pool[: settings.icon_visible_fallback_max_placements]

    visible_icons: list[IconVisibleFallbackItem] = []
    blocked: list[BlockedVisiblePlacement] = []
    for _source_index, placement in selected:
        result = evaluate_visible_fallback_placement(
            placement=placement,
            image=image,
            pixels=pixels,
            text_bboxes=text_bboxes,
            cover_bboxes=cover_bboxes,
            candidate_text_bboxes=candidate_text_bboxes,
            allowed_roles=allowed_roles,
            settings=settings,
            applied_index=len(visible_icons) + 1,
        )
        if isinstance(result, IconVisibleFallbackItem):
            visible_icons.append(result)
        else:
            result.id = f"blocked_visible_icon_{len(blocked) + 1:03d}"
            blocked.append(result)

    overlay: IconVisibleFallbackOverlay | None = None
    if settings.icon_visible_fallback_overlay_enabled:
        overlay, overlay_warning = build_visible_fallback_overlay(
            task_id=task_id,
            png_data=png_data,
            visible_icons=visible_icons,
            blocked_placements=blocked,
            storage=storage,
        )
        if overlay_warning is not None:
            warnings.append(overlay_warning)

    return IconVisibleFallbackDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        visibleIcons=visible_icons,
        blockedPlacements=blocked,
        visibleFallbackOverlay=overlay,
        warnings=warnings,
        meta=build_meta(visible_icons, blocked, skipped_count=0),
    )


def evaluate_visible_fallback_placement(
    *,
    placement: IconPlacementPlanItem,
    image: PngMetadata,
    pixels: Any,
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    candidate_text_bboxes: list[list[int]],
    allowed_roles: set[str],
    settings: Settings,
    applied_index: int,
) -> IconVisibleFallbackItem | BlockedVisiblePlacement:
    reasons: list[str] = ["m23_needs_fallback_mask"]
    block_reasons: list[str] = []

    if placement.sourceStage not in SOURCE_STAGES:
        block_reasons.append("source_stage_invalid")
    if not placement.assetId or not placement.assetPath or not placement.assetUrl:
        block_reasons.append("icon_asset_missing")
    elif not Path(placement.assetPath).exists():
        block_reasons.append("icon_asset_missing")
    else:
        reasons.append("icon_asset_exists")

    bbox = normalize_bbox_for_blocked(placement.bbox)
    if not bbox_in_bounds(placement.bbox, image):
        block_reasons.append("bbox_invalid")
        cover_bbox = list(bbox)
        mask_color = "#FFFFFF"
        mask_confidence = 0.0
        mask_reasons: list[str] = []
    else:
        reasons.append("bbox_valid")
        cover_bbox = padded_bbox(placement.bbox, max(0, settings.icon_visible_fallback_mask_padding), image)
        mask_color, mask_confidence, mask_reasons, mask_block_reason = sample_mask_color(
            pixels=pixels,
            cover_bbox=cover_bbox,
            settings=settings,
        )
        if mask_block_reason is not None:
            block_reasons.append(mask_block_reason)

    if placement.confidence < settings.icon_visible_fallback_min_confidence:
        block_reasons.append("confidence_below_m24_min")
    if placement.placementRole not in allowed_roles:
        block_reasons.append("role_not_allowed_for_m24")
    else:
        reasons.append("role_allowed_for_m24")

    if max(cover_bbox[2], cover_bbox[3]) > settings.icon_visible_fallback_max_mask_size:
        block_reasons.append("mask_bbox_too_large")
    if any(iou(bbox, text_bbox) > 0.10 or iou(cover_bbox, text_bbox) > 0.10 for text_bbox in text_bboxes):
        block_reasons.append("overlaps_visible_text")
    else:
        reasons.append("not_overlapping_visible_text")
    if any(iou(bbox, cover_text_bbox) > 0.10 or iou(cover_bbox, cover_text_bbox) > 0.10 for cover_text_bbox in cover_bboxes):
        block_reasons.append("overlaps_text_replacement_cover")
    else:
        reasons.append("not_overlapping_cover")
    if any(
        iou(bbox, candidate_text_bbox) > 0.10 or iou(cover_bbox, candidate_text_bbox) > 0.10
        for candidate_text_bbox in candidate_text_bboxes
    ):
        block_reasons.append("overlaps_candidate_text")
    else:
        reasons.append("not_overlapping_candidate_text")

    if block_reasons:
        return BlockedVisiblePlacement(
            id=f"blocked_visible_icon_{blocked_index_seed(placement):03d}",
            placementId=placement.id,
            sourceStage=placement.sourceStage,
            sourceIconId=placement.sourceIconId,
            bbox=list(bbox),
            status="blocked",
            reasons=unique_preserve_order(block_reasons),
        )

    item_id = f"visible_icon_fallback_{applied_index:03d}"
    cover_id = f"icon_fallback_cover_{applied_index:03d}"
    mask = IconVisibleFallbackMask(
        type="solid_shape_cover",
        bbox=cover_bbox,
        color=mask_color,
        confidence=mask_confidence,
        reasons=unique_preserve_order(mask_reasons + ["mask_bbox_valid", "not_overlapping_visible_text"]),
    )
    return IconVisibleFallbackItem(
        id=item_id,
        placementId=placement.id,
        sourceStage=placement.sourceStage,
        sourceIconId=placement.sourceIconId,
        assetId=str(placement.assetId),
        assetPath=str(placement.assetPath),
        assetUrl=str(placement.assetUrl),
        componentId=placement.componentId,
        componentRole=placement.componentRole,
        placementRole=placement.placementRole,
        status="applied",
        bbox=list(placement.bbox),
        confidence=round(float(placement.confidence), 3),
        coverNodeId=cover_id,
        iconNodeId=item_id,
        mask=mask,
        quality={
            "risk": "medium",
            "reasons": unique_preserve_order(
                reasons + ["fallback_cover_inserted", "visible_icon_node_inserted"]
            ),
        },
    )


def normalize_bbox_for_blocked(bbox: list[int]) -> list[int]:
    if len(bbox) != 4:
        return [0, 0, 1, 1]
    return list(bbox)


def blocked_index_seed(placement: IconPlacementPlanItem) -> int:
    suffix = placement.id.rsplit("_", 1)[-1]
    try:
        return max(1, int(suffix))
    except ValueError:
        return 1


def sample_mask_color(
    *,
    pixels: Any,
    cover_bbox: list[int],
    settings: Settings,
) -> tuple[str, float, list[str], str | None]:
    try:
        sample = sample_region_background(
            pixels,
            cover_bbox,
            settings.icon_visible_fallback_solid_bg_tolerance,
        )
    except UnsupportedPngCropError:
        return "#FFFFFF", 0.0, [], "solid_background_sample_failed"
    if sample.max_channel_delta > settings.icon_visible_fallback_solid_bg_tolerance:
        return sample.color, sample.confidence, [], "solid_background_sample_failed"
    return sample.color, sample.confidence, ["solid_background_sample_ok"], None


def apply_icon_visible_fallback_to_dsl(
    dsl: dict[str, Any],
    document: IconVisibleFallbackDocument,
) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    assets = next_dsl.setdefault("assets", [])
    if not isinstance(assets, list):
        assets = []
        next_dsl["assets"] = assets
    asset_ids = {asset.get("assetId") for asset in assets if isinstance(asset, dict)}
    root = next_dsl.setdefault("root", {})
    children = root.setdefault("children", [])
    if not isinstance(children, list):
        children = []
        root["children"] = children

    for item in document.visibleIcons:
        if item.assetId not in asset_ids:
            assets.append(icon_asset_dsl_entry(item))
            asset_ids.add(item.assetId)
        children.append(icon_cover_node(item))
        children.append(icon_image_node(item))

    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m24_visible_icon_fallback_replay" not in quality_flags:
        quality_flags.append("m24_visible_icon_fallback_replay")
    meta["qualityFlags"] = quality_flags
    meta["visibleIconFallbackSelectedCount"] = int(document.meta.get("selectedCount", 0))
    meta["visibleIconFallbackAppliedCount"] = int(document.meta.get("appliedCount", 0))
    meta["visibleIconFallbackBlockedCount"] = int(document.meta.get("blockedCount", 0))
    meta["visibleIconFallbackSkippedCount"] = int(document.meta.get("skippedCount", 0))
    return next_dsl


def icon_asset_dsl_entry(item: IconVisibleFallbackItem) -> dict[str, Any]:
    return {
        "assetId": item.assetId,
        "type": "image",
        "role": "asset_icon_visible_fallback",
        "url": item.assetUrl,
        "format": "png",
        "width": item.bbox[2],
        "height": item.bbox[3],
        "storage": "local",
        "meta": {
            "stage": "m24_visible_icon_fallback",
            "sourceStage": item.sourceStage,
            "sourceIconId": item.sourceIconId,
        },
    }


def icon_cover_node(item: IconVisibleFallbackItem) -> dict[str, Any]:
    return {
        "id": item.coverNodeId,
        "type": "shape",
        "role": "icon_fallback_cover",
        "name": f"Icon Fallback Cover / {item.coverNodeId.rsplit('_', 1)[-1]}",
        "layout": {
            "x": item.mask.bbox[0],
            "y": item.mask.bbox[1],
            "width": item.mask.bbox[2],
            "height": item.mask.bbox[3],
        },
        "style": {
            "visible": True,
            "opacity": 1,
            "fill": item.mask.color,
            "radius": 0,
        },
        "meta": {
            "stage": "m24_visible_icon_fallback",
            "placementId": item.placementId,
            "sourceStage": item.sourceStage,
            "sourceIconId": item.sourceIconId,
        },
    }


def icon_image_node(item: IconVisibleFallbackItem) -> dict[str, Any]:
    return {
        "id": item.iconNodeId,
        "type": "image",
        "role": "visible_icon_fallback",
        "name": f"Visible Icon Fallback / {item.iconNodeId.rsplit('_', 1)[-1]}",
        "layout": {
            "x": item.bbox[0],
            "y": item.bbox[1],
            "width": item.bbox[2],
            "height": item.bbox[3],
        },
        "source": {
            "assetId": item.assetId,
        },
        "imageFill": {
            "mode": "fit",
        },
        "style": {
            "visible": True,
            "opacity": 1,
        },
        "meta": {
            "stage": "m24_visible_icon_fallback",
            "placementId": item.placementId,
            "sourceStage": item.sourceStage,
            "sourceIconId": item.sourceIconId,
        },
    }


def validate_icon_visible_fallback_document(
    *,
    document: IconVisibleFallbackDocument,
    icon_placement_document: IconPlacementPlanDocument | None,
    final_dsl: dict[str, Any],
    image: PngMetadata,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    if len({item.id for item in document.visibleIcons}) != len(document.visibleIcons):
        errors.append("visible icon ids must be unique")
    if len({item.id for item in document.blockedPlacements}) != len(document.blockedPlacements):
        errors.append("blocked placement ids must be unique")

    m23_placements = {
        placement.id: placement
        for placement in (icon_placement_document.placements if icon_placement_document is not None else [])
    }
    elements = index_dsl_elements(final_dsl)
    text_bboxes = bboxes_by_role(elements, {"visible_text_replacement"})
    cover_bboxes = bboxes_by_role(elements, {"text_replacement_cover"})
    candidate_text_bboxes = bboxes_by_role(elements, {"candidate_text"})
    dsl_asset_ids = [
        asset.get("assetId")
        for asset in final_dsl.get("assets", [])
        if isinstance(asset, dict)
    ]
    if len(dsl_asset_ids) != len(set(dsl_asset_ids)):
        errors.append("DSL asset ids must be unique")

    for item in document.visibleIcons:
        placement = m23_placements.get(item.placementId)
        if placement is None:
            errors.append(f"visible icon references missing M23 placement: {item.id}")
        else:
            if item.sourceStage != placement.sourceStage:
                errors.append(f"sourceStage must match M23 placement: {item.id}")
            if item.sourceIconId != placement.sourceIconId:
                errors.append(f"sourceIconId must match M23 placement: {item.id}")
            if item.assetId != placement.assetId:
                errors.append(f"assetId must match M23 placement: {item.id}")
        if item.sourceStage not in SOURCE_STAGES:
            errors.append(f"invalid sourceStage: {item.id}")
        if item.status not in VISIBLE_FALLBACK_STATUSES:
            errors.append(f"invalid visible icon status: {item.id}")
        if item.placementRole not in ALLOWED_ROLE_DEFAULTS:
            errors.append(f"invalid visible fallback role: {item.id}")
        if not Path(item.assetPath).exists():
            errors.append(f"visible icon asset path must exist: {item.id}")
        if not bbox_in_bounds(item.bbox, image):
            errors.append(f"visible icon bbox out of bounds: {item.id}")
        if not bbox_in_bounds(item.mask.bbox, image):
            errors.append(f"visible icon mask bbox out of bounds: {item.id}")
        if item.mask.type != "solid_shape_cover":
            errors.append(f"invalid mask type: {item.id}")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", item.mask.color):
            errors.append(f"mask color must be #RRGGBB: {item.id}")
        cover_node = elements.get(item.coverNodeId)
        icon_node = elements.get(item.iconNodeId)
        if cover_node is None:
            errors.append(f"cover node missing from DSL: {item.id}")
        else:
            if cover_node.get("type") != "shape" or cover_node.get("role") != "icon_fallback_cover":
                errors.append(f"invalid cover node type or role: {item.id}")
            fill = cover_node.get("style", {}).get("fill") if isinstance(cover_node.get("style"), dict) else None
            if not isinstance(fill, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", fill):
                errors.append(f"cover node fill must be #RRGGBB: {item.id}")
        if icon_node is None:
            errors.append(f"icon node missing from DSL: {item.id}")
        else:
            if icon_node.get("type") != "image" or icon_node.get("role") != "visible_icon_fallback":
                errors.append(f"invalid icon node type or role: {item.id}")
            if icon_node.get("source", {}).get("assetId") != item.assetId:
                errors.append(f"icon node assetId must match: {item.id}")
            if icon_node.get("imageFill", {}).get("mode") != "fit":
                errors.append(f"icon node imageFill mode must be fit: {item.id}")
        if item.assetId not in dsl_asset_ids:
            errors.append(f"visible icon asset must be present in DSL assets: {item.id}")
        if any(iou(item.bbox, bbox) > 0.10 for bbox in text_bboxes + cover_bboxes + candidate_text_bboxes):
            errors.append(f"visible icon overlaps text or text cover: {item.id}")
        if any(iou(item.mask.bbox, bbox) > 0.10 for bbox in text_bboxes + cover_bboxes + candidate_text_bboxes):
            errors.append(f"visible icon mask overlaps text or text cover: {item.id}")

    for blocked in document.blockedPlacements:
        if blocked.placementId not in m23_placements:
            errors.append(f"blocked placement references missing M23 placement: {blocked.id}")
        if blocked.sourceStage not in SOURCE_STAGES:
            errors.append(f"invalid blocked sourceStage: {blocked.id}")
        if blocked.status not in VISIBLE_FALLBACK_STATUSES:
            errors.append(f"invalid blocked status: {blocked.id}")

    if document.meta.get("selectedCount") != len(document.visibleIcons) + len(document.blockedPlacements):
        errors.append("meta selectedCount must match visible and blocked placements")
    if document.meta.get("appliedCount") != len(document.visibleIcons):
        errors.append("meta appliedCount must match visible icons")
    if document.meta.get("blockedCount") != len(document.blockedPlacements):
        errors.append("meta blockedCount must match blocked placements")
    if document.meta.get("skippedCount") != 0:
        errors.append("meta skippedCount must be zero for v0.1")
    if document.meta.get("roleSummary") != summarize_roles(document.visibleIcons):
        errors.append("meta roleSummary must match visible icons")
    if document.meta.get("blockedReasonSummary") != summarize_blocked_reasons(document.blockedPlacements):
        errors.append("meta blockedReasonSummary must match blocked placements")
    if document.visibleFallbackOverlay is not None:
        if document.visibleFallbackOverlay.assetId != "asset_icon_visible_fallback_overlay":
            errors.append("visible fallback overlay assetId is invalid")
        if not Path(document.visibleFallbackOverlay.assetPath).exists():
            errors.append("visible fallback overlay asset path must exist")
    return errors


def build_visible_fallback_overlay(
    *,
    task_id: str,
    png_data: bytes,
    visible_icons: list[IconVisibleFallbackItem],
    blocked_placements: list[BlockedVisiblePlacement],
    storage: IconVisibleFallbackStorageAdapter,
) -> tuple[IconVisibleFallbackOverlay | None, IconVisibleFallbackWarning | None]:
    try:
        pixels = decode_png_pixels(png_data)
        rows = [bytearray(row) for row in pixels.rows]
        for item in visible_icons:
            draw_rect(rows, pixels.width, pixels.height, item.mask.bbox, OVERLAY_COLORS["applied_cover"], thickness=2)
            draw_rect(rows, pixels.width, pixels.height, item.bbox, OVERLAY_COLORS["applied_icon"], thickness=2)
        for item in blocked_placements:
            draw_rect(rows, pixels.width, pixels.height, item.bbox, OVERLAY_COLORS[item.status], thickness=2)
        data = encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])
        filename = "icon_visible_fallback_overlay.png"
        path = storage.write_overlay(task_id, filename, data)
        return (
            IconVisibleFallbackOverlay(
                assetId="asset_icon_visible_fallback_overlay",
                assetPath=str(path),
                assetUrl=storage.overlay_url(task_id, filename),
            ),
            None,
        )
    except UnsupportedPngCropError as error:
        return None, IconVisibleFallbackWarning(code="png_pixel_decode_unsupported", message=str(error))
    except OSError as error:
        return None, IconVisibleFallbackWarning(code="icon_visible_fallback_overlay_write_failed", message=str(error))


def build_skipped_icon_visible_fallback_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> IconVisibleFallbackDocument:
    return IconVisibleFallbackDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        visibleIcons=[],
        blockedPlacements=[],
        visibleFallbackOverlay=None,
        warnings=[IconVisibleFallbackWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_icon_visible_fallback_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[IconVisibleFallbackWarning] | None = None,
) -> IconVisibleFallbackDocument:
    return IconVisibleFallbackDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        visibleIcons=[],
        blockedPlacements=[],
        visibleFallbackOverlay=None,
        warnings=warnings or [IconVisibleFallbackWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_meta(
    visible_icons: list[IconVisibleFallbackItem],
    blocked: list[BlockedVisiblePlacement],
    *,
    skipped_count: int,
) -> dict[str, Any]:
    return {
        "notes": "visible_icon_fallback_replay_experiment",
        "selectedCount": len(visible_icons) + len(blocked) + skipped_count,
        "appliedCount": len(visible_icons),
        "blockedCount": len(blocked),
        "skippedCount": skipped_count,
        "roleSummary": summarize_roles(visible_icons),
        "blockedReasonSummary": summarize_blocked_reasons(blocked),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "visible_icon_fallback_replay_experiment",
        "selectedCount": 0,
        "appliedCount": 0,
        "blockedCount": 0,
        "skippedCount": 0,
        "roleSummary": {},
        "blockedReasonSummary": {},
    }


def summarize_roles(visible_icons: list[IconVisibleFallbackItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in visible_icons:
        summary[item.placementRole] = summary.get(item.placementRole, 0) + 1
    return summary


def summarize_blocked_reasons(blocked: list[BlockedVisiblePlacement]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in blocked:
        for reason in item.reasons:
            summary[reason] = summary.get(reason, 0) + 1
    return summary


def visible_fallback_overlay_asset_records(
    document: IconVisibleFallbackDocument,
    task_id: str,
    created_at: str,
) -> list[dict[str, Any]]:
    if document.visibleFallbackOverlay is None:
        return []
    width, height = image_size(
        document.visibleFallbackOverlay.assetPath,
        [0, 0, document.imageSize["width"], document.imageSize["height"]],
    )
    return [
        {
            "asset_id": document.visibleFallbackOverlay.assetId,
            "task_id": task_id,
            "role": "asset_icon_visible_fallback_overlay",
            "path": document.visibleFallbackOverlay.assetPath,
            "url": document.visibleFallbackOverlay.assetUrl,
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "created_at": created_at,
        }
    ]


def image_size(path: str, fallback_bbox: list[int]) -> tuple[int, int]:
    metadata = read_png_metadata(Path(path).read_bytes())
    if metadata is None:
        return fallback_bbox[2], fallback_bbox[3]
    return metadata.width, metadata.height
