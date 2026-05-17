from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .asset_slice import AssetSliceCandidateDocument
from .component_annotation import ComponentAnnotationDocument, index_dsl_elements
from .component_structure import ComponentStructureDocument, ComponentStructureItem
from .config import Settings
from .icon_candidate import (
    IconCandidateDocument,
    bbox_in_bounds,
    bbox_inside,
    iou,
    unique_preserve_order,
)
from .icon_coverage import (
    IconCoverageAuditDocument,
    bboxes_by_role,
    draw_rect,
    fallback_region_bboxes,
)
from .icon_gap_candidate import IconGapCandidateDocument
from .png_tools import (
    PngMetadata,
    UnsupportedPngCropError,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
)
from .text_binding import TextPrimitiveBindingDocument


IconPlacementPlanStatus = Literal["completed", "failed", "skipped"]
IconPlacementStatus = Literal["planned", "blocked", "deduped", "review_required"]

SOURCE_STAGES = {"m20", "m22"}
PLACEMENT_STATUSES = {"planned", "blocked", "deduped", "review_required"}
PLACEMENT_DECISIONS = {
    "ready_for_visible_icon",
    "needs_fallback_mask",
    "needs_fallback_coordination",
    "needs_slice_coordination",
    "blocked",
    "review_required",
    "deduped",
}
PLACEMENT_ROLES = {
    "nav_icon",
    "leading_icon",
    "title_leading_icon",
    "field_leading_icon",
    "trailing_icon",
    "button_trailing_icon",
    "header_nav_icon",
    "header_action_icon",
    "unknown_icon",
}
RISKS = {"low", "medium", "high"}

M20_ROLE_BY_SOURCE = {
    "bottom_nav_label_above": "nav_icon",
    "shortcut_card_leading_icon": "leading_icon",
    "tip_title_leading_icon": "title_leading_icon",
    "field_label_leading_icon": "field_leading_icon",
    "component_local_visual_blob": "unknown_icon",
}
M22_ROLE_BY_SOURCE = {
    "header_left_nav_icon": "header_nav_icon",
    "header_right_action_icon": "header_action_icon",
    "row_trailing_icon": "trailing_icon",
    "card_trailing_icon": "trailing_icon",
    "button_trailing_icon": "button_trailing_icon",
    "bottom_nav_missing_icon": "nav_icon",
    "shortcut_missing_icon": "leading_icon",
    "field_missing_icon": "field_leading_icon",
}

OVERLAY_COLORS = {
    "ready_for_visible_icon": (0, 200, 90),
    "needs_fallback_mask": (150, 80, 220),
    "needs_slice_coordination": (0, 122, 255),
    "needs_fallback_coordination": (255, 140, 0),
    "review_required": (255, 205, 0),
    "blocked": (235, 64, 52),
    "deduped": (150, 150, 150),
}


@dataclass
class IconPlacementPlanWarning:
    code: str
    message: str
    sourceStage: str | None = None
    sourceIconId: str | None = None


@dataclass
class IconPlacementCollision:
    overlapsVisibleText: bool
    overlapsCover: bool
    overlapsCandidateText: bool
    insideFallbackRegion: bool
    insideAssetSlice: bool
    duplicatesPlacementId: str | None


@dataclass
class IconPlacementPlanItem:
    id: str
    sourceStage: str
    sourceIconId: str
    assetId: str | None
    assetPath: str | None
    assetUrl: str | None
    componentId: str | None
    componentRole: str | None
    placementRole: str
    decision: str
    status: IconPlacementStatus
    bbox: list[int]
    confidence: float
    relatedTextElementIds: list[str]
    relatedBindingIds: list[str]
    relatedSliceCandidateIds: list[str]
    collision: IconPlacementCollision
    futureDslNodeHint: dict[str, Any] | None
    risk: str
    reasons: list[str]


@dataclass
class DedupedIconItem:
    id: str
    droppedSourceStage: str
    droppedSourceIconId: str
    keptPlacementId: str
    reason: str


@dataclass
class BlockedIconItem:
    id: str
    sourceStage: str
    sourceIconId: str
    bbox: list[int]
    reasons: list[str]


@dataclass
class IconPlacementOverlay:
    assetId: str
    assetPath: str
    assetUrl: str


@dataclass
class IconPlacementPlanDocument:
    version: str
    taskId: str
    status: IconPlacementPlanStatus
    imageSize: dict[str, int]
    placements: list[IconPlacementPlanItem]
    dedupedIcons: list[DedupedIconItem]
    blockedIcons: list[BlockedIconItem]
    placementOverlay: IconPlacementOverlay | None
    warnings: list[IconPlacementPlanWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IconPlacementStorageAdapter:
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


@dataclass(frozen=True)
class NormalizedIcon:
    source_stage: str
    source_icon_id: str
    source: str
    asset_id: str | None
    asset_path: str | None
    asset_url: str | None
    bbox: list[int]
    confidence: float
    component_id: str | None
    component_role: str | None
    placement_role: str
    related_text_ids: list[str]
    related_binding_ids: list[str]


def build_icon_placement_plan_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    annotation_document: ComponentAnnotationDocument | None,
    asset_slice_document: AssetSliceCandidateDocument | None,
    icon_candidate_document: IconCandidateDocument | None,
    icon_coverage_document: IconCoverageAuditDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    dsl: dict[str, Any],
    settings: Settings,
    storage: IconPlacementStorageAdapter,
) -> IconPlacementPlanDocument:
    del annotation_document, icon_coverage_document
    if not settings.icon_placement_plan_enabled:
        return build_skipped_icon_placement_plan_document(
            task_id=task_id,
            image=image,
            code="icon_placement_plan_disabled",
            message="Icon placement plan is disabled.",
        )
    if binding_document.status != "completed":
        return build_skipped_icon_placement_plan_document(
            task_id=task_id,
            image=image,
            code="text_binding_not_completed",
            message="Icon placement plan skipped because text binding did not complete.",
        )
    if structure_document.status != "completed":
        return build_skipped_icon_placement_plan_document(
            task_id=task_id,
            image=image,
            code="component_structure_not_completed",
            message="Icon placement plan skipped because component structure did not complete.",
        )

    icon_pool = normalize_icon_pool(icon_candidate_document, icon_gap_document)
    if not icon_pool and (not completed(icon_candidate_document) and not completed(icon_gap_document)):
        return build_skipped_icon_placement_plan_document(
            task_id=task_id,
            image=image,
            code="icon_sources_not_completed",
            message="Icon placement plan skipped because M20 and M22 did not produce completed documents.",
        )

    warnings: list[IconPlacementPlanWarning] = []
    elements = index_dsl_elements(dsl)
    components = {component.id: component for component in structure_document.components}
    binding_ids = {binding.id for binding in binding_document.bindings}
    kept_icons, deduped_icons = dedupe_icon_pool(icon_pool, settings)

    placements: list[IconPlacementPlanItem] = []
    blocked_icons: list[BlockedIconItem] = []
    for index, icon in enumerate(kept_icons[: settings.icon_placement_plan_max_placements], start=1):
        placement, blocked = build_placement(
            index=index,
            icon=icon,
            image=image,
            elements=elements,
            components=components,
            binding_ids=binding_ids,
            asset_slice_document=asset_slice_document,
            settings=settings,
        )
        placements.append(placement)
        if blocked is not None:
            blocked_icons.append(blocked)
    if len(kept_icons) > settings.icon_placement_plan_max_placements:
        warnings.append(
            IconPlacementPlanWarning(
                code="icon_placement_plan_limit_reached",
                message="Icon placement plan limit reached.",
            )
        )

    overlay: IconPlacementOverlay | None = None
    if settings.icon_placement_plan_overlay_enabled:
        overlay, overlay_warning = build_placement_overlay(
            task_id=task_id,
            png_data=png_data,
            placements=placements,
            storage=storage,
        )
        if overlay_warning is not None:
            warnings.append(overlay_warning)

    document = IconPlacementPlanDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        placements=placements,
        dedupedIcons=deduped_icons,
        blockedIcons=blocked_icons,
        placementOverlay=overlay,
        warnings=warnings,
        meta=build_meta(placements, deduped_icons),
    )
    validation_errors = validate_icon_placement_plan_document(
        document=document,
        binding_document=binding_document,
        structure_document=structure_document,
        icon_candidate_document=icon_candidate_document,
        icon_gap_document=icon_gap_document,
        dsl=dsl,
        image=image,
    )
    if validation_errors:
        return build_failed_icon_placement_plan_document(
            task_id=task_id,
            image=image,
            code="ICON_PLACEMENT_PLAN_VALIDATION_FAILED",
            message="Icon placement plan validation failed.",
            warnings=[
                IconPlacementPlanWarning(code="ICON_PLACEMENT_PLAN_VALIDATION_ERROR", message=error)
                for error in validation_errors
            ],
        )
    return document


def normalize_icon_pool(
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
) -> list[NormalizedIcon]:
    icons: list[NormalizedIcon] = []
    if completed(icon_candidate_document):
        for icon in icon_candidate_document.icons:
            if icon.status != "candidate":
                continue
            icons.append(
                NormalizedIcon(
                    source_stage="m20",
                    source_icon_id=icon.id,
                    source=icon.source,
                    asset_id=icon.assetId,
                    asset_path=icon.assetPath,
                    asset_url=icon.assetUrl,
                    bbox=list(icon.bbox),
                    confidence=float(icon.confidence),
                    component_id=icon.componentId,
                    component_role=icon.componentRole,
                    placement_role=M20_ROLE_BY_SOURCE.get(icon.source, "unknown_icon"),
                    related_text_ids=list(icon.relatedTextElementIds),
                    related_binding_ids=list(icon.relatedBindingIds),
                )
            )
    if completed(icon_gap_document):
        for icon in icon_gap_document.gapIcons:
            if icon.status != "candidate":
                continue
            icons.append(
                NormalizedIcon(
                    source_stage="m22",
                    source_icon_id=icon.id,
                    source=icon.source,
                    asset_id=icon.assetId,
                    asset_path=icon.assetPath,
                    asset_url=icon.assetUrl,
                    bbox=list(icon.bbox),
                    confidence=float(icon.confidence),
                    component_id=icon.componentId,
                    component_role=icon.componentRole,
                    placement_role=M22_ROLE_BY_SOURCE.get(icon.source, "unknown_icon"),
                    related_text_ids=list(icon.relatedTextElementIds),
                    related_binding_ids=list(icon.relatedBindingIds),
                )
            )
    return icons


def dedupe_icon_pool(
    icons: list[NormalizedIcon],
    settings: Settings,
) -> tuple[list[NormalizedIcon], list[DedupedIconItem]]:
    kept: list[NormalizedIcon] = []
    deduped: list[DedupedIconItem] = []
    kept_ids: dict[tuple[str, str], str] = {}
    for icon in icons:
        duplicate_index = next(
            (
                index
                for index, kept_icon in enumerate(kept)
                if duplicate_icons(icon, kept_icon, settings.icon_placement_plan_dedup_iou)
            ),
            None,
        )
        if duplicate_index is None:
            kept.append(icon)
            kept_ids[(icon.source_stage, icon.source_icon_id)] = f"icon_place_{len(kept):03d}"
            continue

        current = kept[duplicate_index]
        preferred = preferred_icon(icon, current)
        dropped = current if preferred is icon else icon
        if preferred is icon:
            kept[duplicate_index] = icon
            kept_ids[(icon.source_stage, icon.source_icon_id)] = kept_ids.pop(
                (current.source_stage, current.source_icon_id),
                f"icon_place_{duplicate_index + 1:03d}",
            )
        kept_id = kept_ids.get((preferred.source_stage, preferred.source_icon_id), f"icon_place_{duplicate_index + 1:03d}")
        deduped.append(
            DedupedIconItem(
                id=f"deduped_icon_{len(deduped) + 1:03d}",
                droppedSourceStage=dropped.source_stage,
                droppedSourceIconId=dropped.source_icon_id,
                keptPlacementId=kept_id,
                reason="duplicate_bbox_iou" if iou(icon.bbox, current.bbox) >= settings.icon_placement_plan_dedup_iou else "duplicate_center_size_match",
            )
        )
    return kept, deduped


def duplicate_icons(left: NormalizedIcon, right: NormalizedIcon, dedup_iou: float) -> bool:
    if iou(left.bbox, right.bbox) >= dedup_iou:
        return True
    left_cx, left_cy = bbox_center(left.bbox)
    right_cx, right_cy = bbox_center(right.bbox)
    distance = ((left_cx - right_cx) ** 2 + (left_cy - right_cy) ** 2) ** 0.5
    size = max(6, min(left.bbox[2], left.bbox[3], right.bbox[2], right.bbox[3]) * 0.35)
    width_ratio = left.bbox[2] / max(1, right.bbox[2])
    height_ratio = left.bbox[3] / max(1, right.bbox[3])
    return distance <= size and 0.70 <= width_ratio <= 1.30 and 0.70 <= height_ratio <= 1.30


def preferred_icon(left: NormalizedIcon, right: NormalizedIcon) -> NormalizedIcon:
    special_roles = {"header_nav_icon", "header_action_icon", "trailing_icon", "button_trailing_icon"}
    if left.source_stage == "m22" and left.placement_role in special_roles and right.placement_role not in special_roles:
        return left
    if right.source_stage == "m22" and right.placement_role in special_roles and left.placement_role not in special_roles:
        return right
    left_area = left.bbox[2] * left.bbox[3]
    right_area = right.bbox[2] * right.bbox[3]
    if left_area > right_area * 1.10:
        return left
    if right_area > left_area * 1.10:
        return right
    if left.confidence > right.confidence + 0.01:
        return left
    if right.confidence > left.confidence + 0.01:
        return right
    if left.source_stage == "m20" and right.source_stage != "m20":
        return left
    if right.source_stage == "m20" and left.source_stage != "m20":
        return right
    return left


def build_placement(
    *,
    index: int,
    icon: NormalizedIcon,
    image: PngMetadata,
    elements: dict[str, dict[str, Any]],
    components: dict[str, ComponentStructureItem],
    binding_ids: set[str],
    asset_slice_document: AssetSliceCandidateDocument | None,
    settings: Settings,
) -> tuple[IconPlacementPlanItem, BlockedIconItem | None]:
    text_bboxes = bboxes_by_role(elements, {"visible_text_replacement"})
    cover_bboxes = bboxes_by_role(elements, {"text_replacement_cover"})
    candidate_text_bboxes = bboxes_by_role(elements, {"candidate_text"})
    fallback_bboxes = fallback_region_bboxes(elements)
    matching_slice_ids = matching_asset_slice_ids(icon.bbox, asset_slice_document, settings.icon_placement_plan_slice_overlap_iou)

    reasons = ["icon_asset_exists" if icon.asset_path and Path(icon.asset_path).exists() else "icon_asset_missing"]
    block_reasons: list[str] = []
    if not icon.asset_id or not icon.asset_path or not icon.asset_url or not Path(icon.asset_path).exists():
        block_reasons.append("icon_asset_missing")
    if not bbox_in_bounds(icon.bbox, image):
        block_reasons.append("bbox_invalid")
    else:
        reasons.append("bbox_valid")
    if icon.component_id is not None:
        component = components.get(icon.component_id)
        if component is None:
            block_reasons.append("component_missing")
        elif bbox_inside(icon.bbox, component.bbox):
            reasons.append("inside_component_bbox")
        else:
            block_reasons.append("component_missing")
    missing_text = [element_id for element_id in icon.related_text_ids if element_id not in elements]
    missing_bindings = [binding_id for binding_id in icon.related_binding_ids if binding_id not in binding_ids]
    if missing_text:
        block_reasons.append("related_text_missing")
    if missing_bindings:
        block_reasons.append("related_binding_missing")

    overlaps_visible_text = any(iou(icon.bbox, bbox) > settings.icon_placement_plan_text_overlap_iou for bbox in text_bboxes)
    overlaps_cover = any(iou(icon.bbox, bbox) > settings.icon_placement_plan_text_overlap_iou for bbox in cover_bboxes)
    overlaps_candidate_text = any(iou(icon.bbox, bbox) > settings.icon_placement_plan_text_overlap_iou for bbox in candidate_text_bboxes)
    inside_fallback = any(bbox_inside(icon.bbox, bbox) or overlap_ratio(icon.bbox, bbox) >= 0.80 for bbox in fallback_bboxes)
    inside_slice = bool(matching_slice_ids) and not inside_fallback
    if overlaps_visible_text:
        block_reasons.append("overlaps_visible_text")
    if overlaps_cover:
        block_reasons.append("overlaps_cover")
    if overlaps_candidate_text:
        block_reasons.append("overlaps_candidate_text")

    collision = IconPlacementCollision(
        overlapsVisibleText=overlaps_visible_text,
        overlapsCover=overlaps_cover,
        overlapsCandidateText=overlaps_candidate_text,
        insideFallbackRegion=inside_fallback,
        insideAssetSlice=inside_slice,
        duplicatesPlacementId=None,
    )
    if block_reasons:
        decision = "blocked"
        status: IconPlacementStatus = "blocked"
        risk = "high"
        reasons.extend(block_reasons)
    elif inside_fallback:
        decision = "needs_fallback_mask"
        status = "planned"
        risk = "medium"
        reasons.extend(["inside_fallback_region", "would_duplicate_fallback_without_mask"])
    elif inside_slice:
        decision = "needs_slice_coordination"
        status = "planned"
        risk = "medium"
        reasons.extend(["inside_asset_slice", "needs_slice_coordination"])
    elif icon.placement_role == "unknown_icon":
        decision = "review_required"
        status = "review_required"
        risk = "medium"
        reasons.append("weak_source_requires_review")
    else:
        decision = "ready_for_visible_icon"
        status = "planned"
        risk = "low"
        reasons.append("ready_for_visible_icon")

    placement = IconPlacementPlanItem(
        id=f"icon_place_{index:03d}",
        sourceStage=icon.source_stage,
        sourceIconId=icon.source_icon_id,
        assetId=icon.asset_id,
        assetPath=icon.asset_path,
        assetUrl=icon.asset_url,
        componentId=icon.component_id,
        componentRole=icon.component_role,
        placementRole=icon.placement_role,
        decision=decision,
        status=status,
        bbox=list(icon.bbox),
        confidence=round(icon.confidence, 3),
        relatedTextElementIds=list(icon.related_text_ids),
        relatedBindingIds=list(icon.related_binding_ids),
        relatedSliceCandidateIds=matching_slice_ids,
        collision=collision,
        futureDslNodeHint=future_dsl_node_hint(icon) if icon.asset_id and decision != "blocked" else None,
        risk=risk,
        reasons=unique_preserve_order(reasons),
    )
    blocked = None
    if decision == "blocked":
        blocked = BlockedIconItem(
            id=f"blocked_icon_{index:03d}",
            sourceStage=icon.source_stage,
            sourceIconId=icon.source_icon_id,
            bbox=list(icon.bbox),
            reasons=unique_preserve_order(block_reasons),
        )
    return placement, blocked


def matching_asset_slice_ids(
    icon_bbox: list[int],
    asset_slice_document: AssetSliceCandidateDocument | None,
    slice_overlap_iou: float,
) -> list[str]:
    if not completed(asset_slice_document):
        return []
    matches: list[str] = []
    for item in asset_slice_document.slices:
        if item.status != "candidate":
            continue
        if bbox_inside(icon_bbox, item.bbox) or overlap_ratio(icon_bbox, item.bbox) >= 0.80 or iou(icon_bbox, item.bbox) > slice_overlap_iou:
            matches.append(item.id)
    return matches


def build_placement_overlay(
    *,
    task_id: str,
    png_data: bytes,
    placements: list[IconPlacementPlanItem],
    storage: IconPlacementStorageAdapter,
) -> tuple[IconPlacementOverlay | None, IconPlacementPlanWarning | None]:
    try:
        pixels = decode_png_pixels(png_data)
        rows = [bytearray(row) for row in pixels.rows]
        for placement in placements:
            color = OVERLAY_COLORS.get(placement.decision, OVERLAY_COLORS["review_required"])
            draw_rect(rows, pixels.width, pixels.height, placement.bbox, color, thickness=2)
        data = encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])
        filename = "icon_placement_overlay.png"
        path = storage.write_overlay(task_id, filename, data)
        return IconPlacementOverlay("asset_icon_placement_overlay", str(path), storage.overlay_url(task_id, filename)), None
    except UnsupportedPngCropError as error:
        return None, IconPlacementPlanWarning(code="png_pixel_decode_unsupported", message=str(error))
    except OSError as error:
        return None, IconPlacementPlanWarning(code="overlay_write_failed", message=str(error))


def apply_icon_placement_plan_metadata(dsl: dict[str, Any], document: IconPlacementPlanDocument) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m23_icon_placement_plan" not in quality_flags:
        quality_flags.append("m23_icon_placement_plan")
    meta["qualityFlags"] = quality_flags
    meta["iconPlacementPlanCount"] = int(document.meta.get("placementCount", 0))
    meta["iconPlacementReadyCount"] = int(document.meta.get("readyCount", 0))
    meta["iconPlacementNeedsFallbackMaskCount"] = int(document.meta.get("needsFallbackMaskCount", 0))
    meta["iconPlacementNeedsSliceCoordinationCount"] = int(document.meta.get("needsSliceCoordinationCount", 0))
    meta["iconPlacementNeedsFallbackCoordinationCount"] = int(document.meta.get("needsFallbackCoordinationCount", 0))
    meta["iconPlacementReviewRequiredCount"] = int(document.meta.get("reviewRequiredCount", 0))
    meta["iconPlacementBlockedCount"] = int(document.meta.get("blockedCount", 0))
    meta["iconPlacementDedupedCount"] = int(document.meta.get("dedupedCount", 0))
    return next_dsl


def validate_icon_placement_plan_document(
    *,
    document: IconPlacementPlanDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    dsl: dict[str, Any],
    image: PngMetadata,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    if len({item.id for item in document.placements}) != len(document.placements):
        errors.append("placement ids must be unique")
    if len({item.id for item in document.dedupedIcons}) != len(document.dedupedIcons):
        errors.append("deduped icon ids must be unique")
    if len({item.id for item in document.blockedIcons}) != len(document.blockedIcons):
        errors.append("blocked icon ids must be unique")

    source_icons = source_icon_lookup(icon_candidate_document, icon_gap_document)
    components = {component.id for component in structure_document.components}
    bindings = {binding.id for binding in binding_document.bindings}
    elements = index_dsl_elements(dsl)
    placement_ids = {item.id for item in document.placements}
    blocked_sources = {(item.sourceStage, item.sourceIconId) for item in document.blockedIcons}

    for placement in document.placements:
        source_key = (placement.sourceStage, placement.sourceIconId)
        source = source_icons.get(source_key)
        if placement.sourceStage not in SOURCE_STAGES:
            errors.append(f"invalid source stage: {placement.id}")
        if source is None:
            errors.append(f"placement references missing source icon: {placement.id}")
        elif placement.assetId != source.get("assetId"):
            errors.append(f"placement assetId must match source icon: {placement.id}")
        if placement.status not in PLACEMENT_STATUSES:
            errors.append(f"invalid placement status: {placement.id}")
        if placement.decision not in PLACEMENT_DECISIONS:
            errors.append(f"invalid placement decision: {placement.id}")
        if placement.placementRole not in PLACEMENT_ROLES:
            errors.append(f"invalid placement role: {placement.id}")
        if placement.risk not in RISKS:
            errors.append(f"invalid placement risk: {placement.id}")
        if not bbox_in_bounds(placement.bbox, image):
            errors.append(f"placement bbox is out of bounds: {placement.id}")
        if placement.componentId is not None and placement.componentId not in components:
            errors.append(f"placement references missing component: {placement.id}")
        for element_id in placement.relatedTextElementIds:
            if element_id not in elements:
                errors.append(f"placement references missing DSL element: {placement.id}")
        for binding_id in placement.relatedBindingIds:
            if binding_id not in bindings:
                errors.append(f"placement references missing binding: {placement.id}")
        if placement.status != "blocked":
            if not placement.assetPath or not Path(placement.assetPath).exists():
                errors.append(f"placement asset path must exist: {placement.id}")
        if placement.decision == "blocked" and source_key not in blocked_sources:
            errors.append(f"blocked placement must be mirrored in blockedIcons: {placement.id}")
        if placement.futureDslNodeHint is not None:
            hint = placement.futureDslNodeHint
            if hint.get("type") != "image" or hint.get("role") != "icon_fallback":
                errors.append(f"invalid future DSL hint shape: {placement.id}")
            if hint.get("source", {}).get("assetId") != placement.assetId:
                errors.append(f"future DSL hint source asset must match placement: {placement.id}")

    for deduped in document.dedupedIcons:
        if (deduped.droppedSourceStage, deduped.droppedSourceIconId) not in source_icons:
            errors.append(f"deduped icon references missing source icon: {deduped.id}")
        if deduped.keptPlacementId not in placement_ids:
            errors.append(f"deduped icon references missing kept placement: {deduped.id}")
    for blocked in document.blockedIcons:
        if (blocked.sourceStage, blocked.sourceIconId) not in source_icons:
            errors.append(f"blocked icon references missing source icon: {blocked.id}")
        if not bbox_in_bounds(blocked.bbox, image):
            errors.append(f"blocked icon bbox is out of bounds: {blocked.id}")

    if document.placementOverlay is not None and not Path(document.placementOverlay.assetPath).exists():
        errors.append("placement overlay asset path must exist")
    if document.meta.get("placementCount") != len(document.placements):
        errors.append("meta placementCount must match placements")
    if document.meta.get("dedupedCount") != len(document.dedupedIcons):
        errors.append("meta dedupedCount must match deduped icons")
    if document.meta.get("blockedCount") != sum(1 for item in document.placements if item.decision == "blocked"):
        errors.append("meta blockedCount must match blocked placements")
    if len(document.blockedIcons) != sum(1 for item in document.placements if item.decision == "blocked"):
        errors.append("blockedIcons must match blocked placements")
    if document.meta.get("sourceStageSummary") != summarize_source_stages(document.placements):
        errors.append("meta sourceStageSummary must match placements")
    if document.meta.get("decisionSummary") != summarize_decisions(document.placements):
        errors.append("meta decisionSummary must match placements")
    if document.meta.get("roleSummary") != summarize_roles(document.placements):
        errors.append("meta roleSummary must match placements")
    return errors


def placement_overlay_asset_records(document: IconPlacementPlanDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    if document.placementOverlay is None:
        return []
    width, height = image_size(
        document.placementOverlay.assetPath,
        [0, 0, document.imageSize["width"], document.imageSize["height"]],
    )
    return [
        {
            "asset_id": document.placementOverlay.assetId,
            "task_id": task_id,
            "role": "asset_icon_placement_overlay",
            "path": document.placementOverlay.assetPath,
            "url": document.placementOverlay.assetUrl,
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "created_at": created_at,
        }
    ]


def build_skipped_icon_placement_plan_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> IconPlacementPlanDocument:
    return IconPlacementPlanDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        placements=[],
        dedupedIcons=[],
        blockedIcons=[],
        placementOverlay=None,
        warnings=[IconPlacementPlanWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_icon_placement_plan_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[IconPlacementPlanWarning] | None = None,
) -> IconPlacementPlanDocument:
    return IconPlacementPlanDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        placements=[],
        dedupedIcons=[],
        blockedIcons=[],
        placementOverlay=None,
        warnings=warnings or [IconPlacementPlanWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def future_dsl_node_hint(icon: NormalizedIcon) -> dict[str, Any]:
    return {
        "type": "image",
        "role": "icon_fallback",
        "layout": {
            "x": icon.bbox[0],
            "y": icon.bbox[1],
            "width": icon.bbox[2],
            "height": icon.bbox[3],
        },
        "source": {"assetId": icon.asset_id},
        "imageFill": {"mode": "fit"},
    }


def build_meta(placements: list[IconPlacementPlanItem], deduped_icons: list[DedupedIconItem]) -> dict[str, Any]:
    return {
        "notes": "icon_placement_plan_and_layering_readiness",
        "placementCount": len(placements),
        "readyCount": sum(1 for item in placements if item.decision == "ready_for_visible_icon"),
        "needsFallbackMaskCount": sum(1 for item in placements if item.decision == "needs_fallback_mask"),
        "needsSliceCoordinationCount": sum(1 for item in placements if item.decision == "needs_slice_coordination"),
        "needsFallbackCoordinationCount": sum(1 for item in placements if item.decision == "needs_fallback_coordination"),
        "reviewRequiredCount": sum(1 for item in placements if item.decision == "review_required"),
        "blockedCount": sum(1 for item in placements if item.decision == "blocked"),
        "dedupedCount": len(deduped_icons),
        "sourceStageSummary": summarize_source_stages(placements),
        "decisionSummary": summarize_decisions(placements),
        "roleSummary": summarize_roles(placements),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "icon_placement_plan_and_layering_readiness",
        "placementCount": 0,
        "readyCount": 0,
        "needsFallbackMaskCount": 0,
        "needsSliceCoordinationCount": 0,
        "needsFallbackCoordinationCount": 0,
        "reviewRequiredCount": 0,
        "blockedCount": 0,
        "dedupedCount": 0,
        "sourceStageSummary": {},
        "decisionSummary": {},
        "roleSummary": {},
    }


def summarize_source_stages(placements: list[IconPlacementPlanItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for placement in placements:
        summary[placement.sourceStage] = summary.get(placement.sourceStage, 0) + 1
    return summary


def summarize_decisions(placements: list[IconPlacementPlanItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for placement in placements:
        summary[placement.decision] = summary.get(placement.decision, 0) + 1
    return summary


def summarize_roles(placements: list[IconPlacementPlanItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for placement in placements:
        summary[placement.placementRole] = summary.get(placement.placementRole, 0) + 1
    return summary


def source_icon_lookup(
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    if completed(icon_candidate_document):
        for icon in icon_candidate_document.icons:
            if icon.status == "candidate":
                lookup[("m20", icon.id)] = {"assetId": icon.assetId}
    if completed(icon_gap_document):
        for icon in icon_gap_document.gapIcons:
            if icon.status == "candidate":
                lookup[("m22", icon.id)] = {"assetId": icon.assetId}
    return lookup


def completed(document: Any) -> bool:
    return document is not None and getattr(document, "status", None) == "completed"


def bbox_center(bbox: list[int]) -> tuple[float, float]:
    return bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2


def overlap_ratio(inner: list[int], outer: list[int]) -> float:
    x1 = max(inner[0], outer[0])
    y1 = max(inner[1], outer[1])
    x2 = min(inner[0] + inner[2], outer[0] + outer[2])
    y2 = min(inner[1] + inner[3], outer[1] + outer[3])
    if x2 <= x1 or y2 <= y1:
        return 0
    intersection = (x2 - x1) * (y2 - y1)
    return intersection / max(1, inner[2] * inner[3])


def image_size(path: str, fallback_bbox: list[int]) -> tuple[int, int]:
    metadata = read_png_metadata(Path(path).read_bytes())
    if metadata is None:
        return fallback_bbox[2], fallback_bbox[3]
    return metadata.width, metadata.height
