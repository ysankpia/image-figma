from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .asset_slice import AssetSliceCandidateDocument
from .component_annotation import index_dsl_elements
from .component_structure import ComponentStructureDocument, ComponentStructureItem
from .config import Settings
from .icon_candidate import (
    IconCandidateDocument,
    bbox_center_y,
    bbox_in_bounds,
    bbox_inside,
    estimate_background,
    find_foreground_blobs,
    iou,
    merge_nearby_blobs,
    normalize_bbox,
    padded_bbox,
)
from .png_tools import (
    PngMetadata,
    PngPixels,
    UnsupportedPngCropError,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
)
from .text_binding import TextPrimitiveBindingDocument


IconCoverageStatus = Literal["completed", "failed", "skipped"]
IconPlacementStatus = Literal[
    "ready_for_future_visible_icon",
    "needs_fallback_coordination",
    "needs_slice_coordination",
    "blocked",
    "review_required",
]
MissedIconHintStatus = Literal["hint_only", "review_required", "blocked"]

PLACEMENT_STATUSES = {
    "ready_for_future_visible_icon",
    "needs_fallback_coordination",
    "needs_slice_coordination",
    "blocked",
    "review_required",
}
PLACEMENT_ROLES = {"nav_icon", "leading_icon", "title_leading_icon", "field_leading_icon", "unknown_icon"}
MISSED_HINT_SOURCES = {
    "header_left_visual_hint",
    "header_right_visual_hint",
    "right_arrow_hint",
    "bottom_nav_missing_icon_hint",
    "shortcut_missing_icon_hint",
    "field_icon_hint",
    "card_trailing_icon_hint",
    "low_confidence_icon_like_blob",
}
MISSED_HINT_STATUSES = {"hint_only", "review_required", "blocked"}
RISKS = {"low", "medium", "high"}

PLACEMENT_ROLE_BY_SOURCE = {
    "bottom_nav_label_above": "nav_icon",
    "shortcut_card_leading_icon": "leading_icon",
    "tip_title_leading_icon": "title_leading_icon",
    "field_label_leading_icon": "field_leading_icon",
    "component_local_visual_blob": "unknown_icon",
}

OVERLAY_COLORS = {
    "placement": (0, 200, 90),
    "missed_hint": (255, 205, 0),
    "blocked": (235, 64, 52),
    "needs_slice": (0, 122, 255),
    "needs_fallback": (150, 80, 220),
}


@dataclass
class IconCoverageWarning:
    code: str
    message: str
    componentId: str | None = None
    iconCandidateId: str | None = None
    hintId: str | None = None


@dataclass
class IconPlacementItem:
    id: str
    iconCandidateId: str
    assetId: str | None
    componentId: str
    componentRole: str
    placementRole: str
    status: IconPlacementStatus
    bbox: list[int]
    relatedTextElementIds: list[str]
    relatedBindingIds: list[str]
    futureDslNodeHint: dict[str, Any] | None
    collision: dict[str, bool]
    risk: str
    reasons: list[str]


@dataclass
class MissedIconHintItem:
    id: str
    source: str
    status: MissedIconHintStatus
    bbox: list[int]
    componentId: str | None
    componentRole: str | None
    confidence: float
    suggestedNextRule: str
    reasons: list[str]


@dataclass
class CoverageOverlayItem:
    assetId: str
    assetPath: str
    assetUrl: str


@dataclass
class IconCoverageAuditDocument:
    version: str
    taskId: str
    status: IconCoverageStatus
    imageSize: dict[str, int]
    placements: list[IconPlacementItem]
    missedIconHints: list[MissedIconHintItem]
    coverageOverlay: CoverageOverlayItem | None
    blockedIconCandidateIds: list[str]
    warnings: list[IconCoverageWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IconCoverageStorageAdapter:
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
class HintProbe:
    source: str
    search_bbox: list[int]
    component_id: str | None
    component_role: str | None
    geometry_reason: str
    suggested_rule: str


def build_icon_coverage_audit_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    icon_candidate_document: IconCandidateDocument | None,
    asset_slice_document: AssetSliceCandidateDocument | None,
    dsl: dict[str, Any],
    settings: Settings,
    storage: IconCoverageStorageAdapter,
) -> IconCoverageAuditDocument:
    if not settings.icon_coverage_audit_enabled:
        return build_skipped_icon_coverage_document(
            task_id=task_id,
            image=image,
            code="icon_coverage_audit_disabled",
            message="Icon coverage audit is disabled.",
        )
    if icon_candidate_document is None or icon_candidate_document.status != "completed":
        return build_skipped_icon_coverage_document(
            task_id=task_id,
            image=image,
            code="icon_candidate_not_completed",
            message="Icon coverage audit skipped because icon candidates did not complete.",
        )
    if binding_document.status != "completed":
        return build_skipped_icon_coverage_document(
            task_id=task_id,
            image=image,
            code="text_binding_not_completed",
            message="Icon coverage audit skipped because text binding did not complete.",
        )
    if structure_document.status != "completed":
        return build_skipped_icon_coverage_document(
            task_id=task_id,
            image=image,
            code="component_structure_not_completed",
            message="Icon coverage audit skipped because component structure did not complete.",
        )

    elements = index_dsl_elements(dsl)
    components = {component.id: component for component in structure_document.components}
    binding_ids = {binding.id for binding in binding_document.bindings}
    text_bboxes = bboxes_by_role(elements, {"visible_text_replacement"})
    hint_text_bboxes = unique_bboxes(text_bboxes + bboxes_by_role(elements, {"candidate_text"}))
    cover_bboxes = bboxes_by_role(elements, {"text_replacement_cover"})
    fallback_bboxes = fallback_region_bboxes(elements)
    slice_bboxes = asset_slice_bboxes(asset_slice_document)

    placements = build_placements(
        icon_candidate_document=icon_candidate_document,
        components=components,
        binding_ids=binding_ids,
        elements=elements,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        fallback_bboxes=fallback_bboxes,
        slice_bboxes=slice_bboxes,
        image=image,
    )
    blocked_ids = sorted(item.iconCandidateId for item in placements if item.status == "blocked")

    warnings: list[IconCoverageWarning] = []
    pixels: PngPixels | None = None
    try:
        pixels = decode_png_pixels(png_data)
    except UnsupportedPngCropError as error:
        warnings.append(IconCoverageWarning(code="png_pixel_decode_unsupported", message=str(error)))

    missed_hints: list[MissedIconHintItem] = []
    if pixels is not None and settings.icon_coverage_missed_hints_enabled:
        missed_hints = build_missed_icon_hints(
            pixels=pixels,
            image=image,
            components=structure_document.components,
            icon_candidate_document=icon_candidate_document,
            elements=elements,
            text_bboxes=hint_text_bboxes,
            cover_bboxes=cover_bboxes,
            settings=settings,
            warnings=warnings,
        )

    overlay: CoverageOverlayItem | None = None
    if pixels is not None and settings.icon_coverage_overlay_enabled:
        overlay, overlay_warning = build_coverage_overlay(
            task_id=task_id,
            pixels=pixels,
            placements=placements,
            missed_hints=missed_hints,
            storage=storage,
        )
        if overlay_warning is not None:
            warnings.append(overlay_warning)

    document = IconCoverageAuditDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        placements=placements,
        missedIconHints=missed_hints,
        coverageOverlay=overlay,
        blockedIconCandidateIds=blocked_ids,
        warnings=warnings,
        meta=build_meta(icon_candidate_document, placements, missed_hints),
    )
    validation_errors = validate_icon_coverage_audit_document(
        document=document,
        binding_document=binding_document,
        structure_document=structure_document,
        icon_candidate_document=icon_candidate_document,
        dsl=dsl,
        image=image,
    )
    if validation_errors:
        return build_failed_icon_coverage_document(
            task_id=task_id,
            image=image,
            code="ICON_COVERAGE_AUDIT_VALIDATION_FAILED",
            message="Icon coverage audit validation failed.",
            warnings=[
                IconCoverageWarning(code="ICON_COVERAGE_AUDIT_VALIDATION_ERROR", message=error)
                for error in validation_errors
            ],
        )
    return document


def build_placements(
    *,
    icon_candidate_document: IconCandidateDocument,
    components: dict[str, ComponentStructureItem],
    binding_ids: set[str],
    elements: dict[str, dict[str, Any]],
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    fallback_bboxes: list[list[int]],
    slice_bboxes: list[list[int]],
    image: PngMetadata,
) -> list[IconPlacementItem]:
    placements: list[IconPlacementItem] = []
    for index, icon in enumerate([item for item in icon_candidate_document.icons if item.status == "candidate"], start=1):
        placement_role = PLACEMENT_ROLE_BY_SOURCE.get(icon.source, "unknown_icon")
        component = components.get(icon.componentId)
        reasons = ["m20_icon_candidate_found"]
        block_reasons: list[str] = []
        if not icon.assetId or not icon.assetPath or not icon.assetUrl or not Path(icon.assetPath).exists():
            block_reasons.append("asset_missing")
        else:
            reasons.append("asset_exists")
        if component is None:
            block_reasons.append("component_missing")
        elif bbox_inside(icon.bbox, component.bbox):
            reasons.append("inside_component_bbox")
        else:
            block_reasons.append("bbox_outside_component")
        if not bbox_in_bounds(icon.bbox, image):
            block_reasons.append("bbox_out_of_bounds")
        missing_text = [element_id for element_id in icon.relatedTextElementIds if element_id not in elements]
        missing_bindings = [binding_id for binding_id in icon.relatedBindingIds if binding_id not in binding_ids]
        if missing_text:
            block_reasons.append("related_text_missing")
        if missing_bindings:
            block_reasons.append("related_binding_missing")
        if icon.relatedTextElementIds and not missing_text:
            reasons.append("related_text_found")

        collision = {
            "overlapsVisibleText": any(iou(icon.bbox, text_bbox) > 0.10 for text_bbox in text_bboxes),
            "overlapsCover": any(iou(icon.bbox, cover_bbox) > 0.10 for cover_bbox in cover_bboxes),
            "insideFallbackRegion": any(bbox_inside(icon.bbox, fallback_bbox) for fallback_bbox in fallback_bboxes),
            "insideAssetSlice": any(bbox_inside(icon.bbox, slice_bbox) for slice_bbox in slice_bboxes),
        }
        if collision["overlapsVisibleText"]:
            block_reasons.append("overlaps_visible_text")
        if collision["overlapsCover"]:
            block_reasons.append("overlaps_cover")

        if block_reasons:
            status: IconPlacementStatus = "blocked"
            risk = "high"
            reasons.extend(block_reasons)
        elif collision["insideFallbackRegion"]:
            status = "needs_fallback_coordination"
            risk = "medium"
            reasons.append("would_duplicate_existing_fallback_without_partial_replacement")
        elif collision["insideAssetSlice"]:
            status = "needs_slice_coordination"
            risk = "medium"
            reasons.append("inside_component_slice_candidate")
        elif placement_role == "unknown_icon" or icon.source == "component_local_visual_blob":
            status = "review_required"
            risk = "medium"
            reasons.append("placement_role_unclear")
        else:
            status = "ready_for_future_visible_icon"
            risk = "low"
            reasons.append("future_image_node_safe")

        placements.append(
            IconPlacementItem(
                id=f"icon_placement_{index:03d}",
                iconCandidateId=icon.id,
                assetId=icon.assetId,
                componentId=icon.componentId,
                componentRole=icon.componentRole,
                placementRole=placement_role,
                status=status,
                bbox=list(icon.bbox),
                relatedTextElementIds=list(icon.relatedTextElementIds),
                relatedBindingIds=list(icon.relatedBindingIds),
                futureDslNodeHint=future_dsl_node_hint(icon) if icon.assetId else None,
                collision=collision,
                risk=risk,
                reasons=unique_preserve_order(reasons),
            )
        )
    return placements


def future_dsl_node_hint(icon: Any) -> dict[str, Any]:
    return {
        "type": "image",
        "role": "icon_fallback",
        "layout": {
            "x": icon.bbox[0],
            "y": icon.bbox[1],
            "width": icon.bbox[2],
            "height": icon.bbox[3],
        },
        "source": {"assetId": icon.assetId},
        "imageFill": {"mode": "fit"},
    }


def build_missed_icon_hints(
    *,
    pixels: PngPixels,
    image: PngMetadata,
    components: list[ComponentStructureItem],
    icon_candidate_document: IconCandidateDocument,
    elements: dict[str, dict[str, Any]],
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    settings: Settings,
    warnings: list[IconCoverageWarning],
) -> list[MissedIconHintItem]:
    probes = build_hint_probes(image, components, icon_candidate_document, elements)
    existing_icon_bboxes = [icon.bbox for icon in icon_candidate_document.icons if icon.status == "candidate"]
    hints: list[MissedIconHintItem] = []
    for probe in probes:
        if len(hints) >= settings.icon_coverage_max_missed_hints:
            warnings.append(IconCoverageWarning(code="icon_coverage_hint_limit_reached", message="Icon coverage missed hint limit reached."))
            break
        hint = best_hint_for_probe(
            pixels=pixels,
            probe=probe,
            image=image,
            existing_icon_bboxes=existing_icon_bboxes,
            text_bboxes=text_bboxes,
            cover_bboxes=cover_bboxes,
            settings=settings,
            index=len(hints) + 1,
        )
        if hint is None:
            continue
        if any(iou(hint.bbox, existing.bbox) > 0.50 for existing in hints):
            continue
        hints.append(hint)
    return hints


def build_hint_probes(
    image: PngMetadata,
    components: list[ComponentStructureItem],
    icon_candidate_document: IconCandidateDocument,
    elements: dict[str, dict[str, Any]],
) -> list[HintProbe]:
    probes: list[HintProbe] = []
    header_bbox = header_search_bbox(image, elements)
    header_probe_top = header_app_content_top(header_bbox, image)
    header_probe_height = min(header_bbox[1] + header_bbox[3] - header_probe_top, 96)
    left_header = normalize_bbox([0, header_probe_top, min(150, image.width), header_probe_height], image)
    right_header = normalize_bbox([max(0, image.width - 150), header_probe_top, min(150, image.width), header_probe_height], image)
    if left_header is not None:
        probes.append(HintProbe("header_left_visual_hint", left_header, None, "page_header", "header_edge_visual", "header_nav_icon_candidate"))
    if right_header is not None:
        probes.append(HintProbe("header_right_visual_hint", right_header, None, "page_header", "header_edge_visual", "header_action_icon_candidate"))

    icons_by_component = group_candidate_icons_by_component(icon_candidate_document)
    text_elements_by_component = group_text_elements_by_component(components, elements)
    for component in components:
        component_icons = icons_by_component.get(component.id, [])
        if component.role in {"preview_card", "activity_card", "shortcut_card", "tip_card"}:
            trailing = trailing_probe(component, "right_arrow_hint", image)
            if trailing is not None:
                probes.append(trailing)
        if component.role == "bottom_nav_item" and not any(icon.source == "bottom_nav_label_above" for icon in component_icons):
            text_bboxes = text_elements_by_component.get(component.id, [])
            if text_bboxes:
                label = max(text_bboxes, key=lambda bbox: bbox[1])
                search = normalize_bbox([component.bbox[0], component.bbox[1], component.bbox[2], label[1] - component.bbox[1]], image)
                if search is not None:
                    probes.append(HintProbe("bottom_nav_missing_icon_hint", search, component.id, component.role, "above_text_label", "bottom_nav_icon_candidate"))
        if component.role == "shortcut_card" and not any(icon.source == "shortcut_card_leading_icon" for icon in component_icons):
            leading = leading_probe(component, text_elements_by_component.get(component.id, []), "shortcut_missing_icon_hint", "shortcut_leading_icon_candidate", image)
            if leading is not None:
                probes.append(leading)
        if component.role not in {"legend_group", "summary_stat_card", "activity_card", "page_header", "badge", "status_badge"}:
            for field_probe in field_hint_probes(component, text_elements_by_component.get(component.id, []), image):
                probes.append(field_probe)
    return probes


def best_hint_for_probe(
    *,
    pixels: PngPixels,
    probe: HintProbe,
    image: PngMetadata,
    existing_icon_bboxes: list[list[int]],
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    settings: Settings,
    index: int,
) -> MissedIconHintItem | None:
    background = estimate_background(pixels, probe.search_bbox)
    blobs = merge_nearby_blobs(find_foreground_blobs(pixels, probe.search_bbox, background, settings.icon_coverage_foreground_distance))
    candidates: list[tuple[list[int], int, int, bool]] = []
    for blob in blobs:
        bbox = padded_bbox(blob.bbox, 3, image)
        if not bbox_in_bounds(bbox, image):
            continue
        if any(iou(bbox, existing) > 0.50 for existing in existing_icon_bboxes):
            continue
        if any(iou(bbox, text_bbox) > 0.10 for text_bbox in text_bboxes):
            continue
        if any(iou(bbox, cover_bbox) > 0.10 for cover_bbox in cover_bboxes):
            continue
        if not hint_size_like(bbox, settings):
            continue
        thin = is_text_stroke_like(bbox)
        if thin:
            continue
        confidence = score_hint(bbox, blob.contrast, len(blobs), thin, settings)
        if confidence < settings.icon_coverage_min_hint_confidence:
            continue
        candidates.append((bbox, blob.area, blob.contrast, thin))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (score_hint(item[0], item[2], len(blobs), item[3], settings), item[1]), reverse=True)
    bbox, _area, contrast, thin = candidates[0]
    confidence = score_hint(bbox, contrast, len(blobs), thin, settings)
    status: MissedIconHintStatus = "review_required" if thin else "hint_only"
    source = probe.source if not thin else "low_confidence_icon_like_blob"
    return MissedIconHintItem(
        id=f"missed_icon_hint_{index:03d}",
        source=source,
        status=status,
        bbox=bbox,
        componentId=probe.component_id,
        componentRole=probe.component_role,
        confidence=confidence,
        suggestedNextRule=probe.suggested_rule,
        reasons=unique_preserve_order(
            [
                probe.geometry_reason,
                "not_covered_by_m20_icon_candidate",
                "not_overlapping_text",
                "not_overlapping_cover",
                "foreground_contrast_ok" if contrast >= settings.icon_coverage_foreground_distance else "foreground_contrast_low",
                "hint_only_no_crop",
            ]
        ),
    )


def build_coverage_overlay(
    *,
    task_id: str,
    pixels: PngPixels,
    placements: list[IconPlacementItem],
    missed_hints: list[MissedIconHintItem],
    storage: IconCoverageStorageAdapter,
) -> tuple[CoverageOverlayItem | None, IconCoverageWarning | None]:
    rows = [bytearray(row) for row in pixels.rows]
    boxes: list[tuple[int, list[int], tuple[int, int, int]]] = []
    for placement in placements:
        color_key = "placement"
        priority = 1
        if placement.status == "needs_fallback_coordination":
            color_key = "needs_fallback"
            priority = 2
        elif placement.status == "needs_slice_coordination":
            color_key = "needs_slice"
            priority = 3
        elif placement.status in {"blocked", "review_required"}:
            color_key = "blocked"
            priority = 5
        boxes.append((priority, placement.bbox, OVERLAY_COLORS[color_key]))
    for hint in missed_hints:
        boxes.append((4, hint.bbox, OVERLAY_COLORS["missed_hint"]))

    for _priority, bbox, color in sorted(boxes, key=lambda item: item[0]):
        draw_rect(rows, pixels.width, pixels.height, bbox, color, thickness=2)
    try:
        overlay_png = encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])
        filename = "icon_coverage_overlay.png"
        path = storage.write_overlay(task_id, filename, overlay_png)
        return (
            CoverageOverlayItem(
                assetId="asset_icon_coverage_overlay",
                assetPath=str(path),
                assetUrl=storage.overlay_url(task_id, filename),
            ),
            None,
        )
    except (OSError, UnsupportedPngCropError) as error:
        return None, IconCoverageWarning(code="coverage_overlay_write_failed", message=str(error))


def apply_icon_coverage_metadata(dsl: dict[str, Any], document: IconCoverageAuditDocument) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m21_icon_coverage_audit" not in quality_flags:
        quality_flags.append("m21_icon_coverage_audit")
    meta["qualityFlags"] = quality_flags
    meta["iconCoverageCandidateCount"] = int(document.meta.get("iconCandidateCount", 0))
    meta["iconCoveragePlacementCount"] = int(document.meta.get("placementCount", 0))
    meta["iconCoverageMissedHintCount"] = int(document.meta.get("missedIconHintCount", 0))
    meta["iconPlacementReadyCount"] = int(document.meta.get("readyCount", 0))
    meta["iconPlacementNeedsFallbackCoordinationCount"] = int(document.meta.get("needsFallbackCoordinationCount", 0))
    meta["iconPlacementNeedsSliceCoordinationCount"] = int(document.meta.get("needsSliceCoordinationCount", 0))
    meta["iconPlacementBlockedCount"] = int(document.meta.get("blockedCount", 0))
    return next_dsl


def validate_icon_coverage_audit_document(
    *,
    document: IconCoverageAuditDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    icon_candidate_document: IconCandidateDocument,
    dsl: dict[str, Any],
    image: PngMetadata,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    placement_ids = {placement.id for placement in document.placements}
    if len(placement_ids) != len(document.placements):
        errors.append("placement ids must be unique")
    hint_ids = {hint.id for hint in document.missedIconHints}
    if len(hint_ids) != len(document.missedIconHints):
        errors.append("missed hint ids must be unique")

    candidate_icons = {icon.id: icon for icon in icon_candidate_document.icons if icon.status == "candidate"}
    component_ids = {component.id for component in structure_document.components}
    binding_ids = {binding.id for binding in binding_document.bindings}
    elements = index_dsl_elements(dsl)
    for placement in document.placements:
        icon = candidate_icons.get(placement.iconCandidateId)
        if icon is None:
            errors.append(f"placement references missing icon candidate: {placement.id}")
        elif placement.assetId != icon.assetId:
            errors.append(f"placement asset id must match icon candidate: {placement.id}")
        if placement.componentId not in component_ids:
            errors.append(f"placement references missing component: {placement.id}")
        component = next((item for item in structure_document.components if item.id == placement.componentId), None)
        if component is not None and not bbox_inside(placement.bbox, component.bbox):
            errors.append(f"placement bbox must be inside component bbox: {placement.id}")
        if not bbox_in_bounds(placement.bbox, image):
            errors.append(f"placement bbox is out of bounds: {placement.id}")
        if placement.status not in PLACEMENT_STATUSES:
            errors.append(f"invalid placement status: {placement.id}")
        if placement.placementRole not in PLACEMENT_ROLES:
            errors.append(f"invalid placement role: {placement.id}")
        if placement.risk not in RISKS:
            errors.append(f"invalid placement risk: {placement.id}")
        for element_id in placement.relatedTextElementIds:
            if element_id not in elements:
                errors.append(f"placement references missing DSL element: {placement.id}")
        for binding_id in placement.relatedBindingIds:
            if binding_id not in binding_ids:
                errors.append(f"placement references missing binding: {placement.id}")

    for hint in document.missedIconHints:
        if not bbox_in_bounds(hint.bbox, image):
            errors.append(f"missed hint bbox is out of bounds: {hint.id}")
        if hint.source not in MISSED_HINT_SOURCES:
            errors.append(f"invalid missed hint source: {hint.id}")
        if hint.status not in MISSED_HINT_STATUSES:
            errors.append(f"invalid missed hint status: {hint.id}")
        if hint.componentId is not None and hint.componentId not in component_ids:
            errors.append(f"missed hint references missing component: {hint.id}")
        if any(iou(hint.bbox, icon.bbox) > 0.50 for icon in candidate_icons.values()):
            errors.append(f"missed hint overlaps existing icon candidate: {hint.id}")

    if document.coverageOverlay is not None and not Path(document.coverageOverlay.assetPath).exists():
        errors.append("coverage overlay asset path must exist")
    for icon_id in document.blockedIconCandidateIds:
        if icon_id not in candidate_icons:
            errors.append(f"blocked icon candidate id is missing: {icon_id}")
    if document.meta.get("placementCount") != len(document.placements):
        errors.append("meta placementCount must match placements")
    if document.meta.get("missedIconHintCount") != len(document.missedIconHints):
        errors.append("meta missedIconHintCount must match missed hints")
    if document.meta.get("readyCount") != sum(1 for item in document.placements if item.status == "ready_for_future_visible_icon"):
        errors.append("meta readyCount must match placements")
    if document.meta.get("needsFallbackCoordinationCount") != sum(1 for item in document.placements if item.status == "needs_fallback_coordination"):
        errors.append("meta needsFallbackCoordinationCount must match placements")
    if document.meta.get("needsSliceCoordinationCount") != sum(1 for item in document.placements if item.status == "needs_slice_coordination"):
        errors.append("meta needsSliceCoordinationCount must match placements")
    if document.meta.get("blockedCount") != sum(1 for item in document.placements if item.status == "blocked"):
        errors.append("meta blockedCount must match placements")
    if document.meta.get("coverageBySource") != coverage_by_source(icon_candidate_document):
        errors.append("meta coverageBySource must match icon candidates")
    if document.meta.get("missedHintBySource") != missed_hint_by_source(document.missedIconHints):
        errors.append("meta missedHintBySource must match missed hints")
    return errors


def overlay_asset_records(document: IconCoverageAuditDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    if document.coverageOverlay is None:
        return []
    width, height = image_size(document.coverageOverlay.assetPath, document.imageSize)
    return [
        {
            "asset_id": document.coverageOverlay.assetId,
            "task_id": task_id,
            "role": "asset_icon_coverage_overlay",
            "path": document.coverageOverlay.assetPath,
            "url": document.coverageOverlay.assetUrl,
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "created_at": created_at,
        }
    ]


def build_skipped_icon_coverage_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> IconCoverageAuditDocument:
    return IconCoverageAuditDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        placements=[],
        missedIconHints=[],
        coverageOverlay=None,
        blockedIconCandidateIds=[],
        warnings=[IconCoverageWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_icon_coverage_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[IconCoverageWarning] | None = None,
) -> IconCoverageAuditDocument:
    return IconCoverageAuditDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        placements=[],
        missedIconHints=[],
        coverageOverlay=None,
        blockedIconCandidateIds=[],
        warnings=warnings or [IconCoverageWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_meta(
    icon_candidate_document: IconCandidateDocument,
    placements: list[IconPlacementItem],
    hints: list[MissedIconHintItem],
) -> dict[str, Any]:
    return {
        "notes": "icon_coverage_audit_and_placement_readiness",
        "iconCandidateCount": sum(1 for icon in icon_candidate_document.icons if icon.status == "candidate"),
        "placementCount": len(placements),
        "readyCount": sum(1 for item in placements if item.status == "ready_for_future_visible_icon"),
        "needsFallbackCoordinationCount": sum(1 for item in placements if item.status == "needs_fallback_coordination"),
        "needsSliceCoordinationCount": sum(1 for item in placements if item.status == "needs_slice_coordination"),
        "blockedCount": sum(1 for item in placements if item.status == "blocked"),
        "missedIconHintCount": len(hints),
        "coverageBySource": coverage_by_source(icon_candidate_document),
        "missedHintBySource": missed_hint_by_source(hints),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "icon_coverage_audit_and_placement_readiness",
        "iconCandidateCount": 0,
        "placementCount": 0,
        "readyCount": 0,
        "needsFallbackCoordinationCount": 0,
        "needsSliceCoordinationCount": 0,
        "blockedCount": 0,
        "missedIconHintCount": 0,
        "coverageBySource": {},
        "missedHintBySource": {},
    }


def bboxes_by_role(elements: dict[str, dict[str, Any]], roles: set[str]) -> list[list[int]]:
    bboxes: list[list[int]] = []
    for element in elements.values():
        if element.get("role") not in roles:
            continue
        bbox = bbox_from_element(element)
        if bbox is not None:
            bboxes.append(bbox)
    return bboxes


def unique_bboxes(bboxes: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for bbox in bboxes:
        key = (bbox[0], bbox[1], bbox[2], bbox[3])
        if key in seen:
            continue
        result.append(bbox)
        seen.add(key)
    return result


def fallback_region_bboxes(elements: dict[str, dict[str, Any]]) -> list[list[int]]:
    bboxes: list[list[int]] = []
    for element_id, element in elements.items():
        if element_id not in {"fallback_region_header", "fallback_region_content", "fallback_region_bottom", "fallback_full_image"}:
            continue
        bbox = bbox_from_element(element)
        if bbox is not None:
            bboxes.append(bbox)
    return bboxes


def asset_slice_bboxes(document: AssetSliceCandidateDocument | None) -> list[list[int]]:
    if document is None or document.status != "completed":
        return []
    return [item.bbox for item in document.slices if item.status == "candidate"]


def bbox_from_element(element: dict[str, Any] | None) -> list[int] | None:
    if element is None:
        return None
    layout = element.get("layout")
    if not isinstance(layout, dict):
        return None
    return normalize_bbox([layout.get("x"), layout.get("y"), layout.get("width"), layout.get("height")])


def header_search_bbox(image: PngMetadata, elements: dict[str, dict[str, Any]]) -> list[int]:
    bbox = bbox_from_element(elements.get("fallback_region_header"))
    if bbox is not None:
        return bbox
    height = min(max(round(image.height * 0.14), 120), 260)
    return [0, 0, image.width, height]


def header_app_content_top(header_bbox: list[int], image: PngMetadata) -> int:
    status_bar_guard = min(96, max(56, round(image.height * 0.045)))
    return min(header_bbox[1] + header_bbox[3], header_bbox[1] + status_bar_guard)


def group_candidate_icons_by_component(document: IconCandidateDocument) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for icon in document.icons:
        if icon.status != "candidate":
            continue
        grouped.setdefault(icon.componentId, []).append(icon)
    return grouped


def group_text_elements_by_component(
    components: list[ComponentStructureItem],
    elements: dict[str, dict[str, Any]],
) -> dict[str, list[list[int]]]:
    result: dict[str, list[list[int]]] = {}
    for component in components:
        for element in elements.values():
            if element.get("role") != "visible_text_replacement":
                continue
            bbox = bbox_from_element(element)
            if bbox is not None and bbox_inside(bbox, component.bbox):
                result.setdefault(component.id, []).append(bbox)
    for key, values in result.items():
        result[key] = sorted(values, key=lambda bbox: (bbox[1], bbox[0]))
    return result


def trailing_probe(component: ComponentStructureItem, source: str, image: PngMetadata) -> HintProbe | None:
    x, y, width, height = component.bbox
    search_width = min(80, max(24, round(width * 0.22)))
    search_height = min(96, max(24, round(height * 0.55)))
    search = normalize_bbox([x + width - search_width, round(y + height / 2 - search_height / 2), search_width, search_height], image)
    if search is None:
        return None
    return HintProbe(source, search, component.id, component.role, "trailing_visual_region", "card_trailing_icon_candidate")


def leading_probe(
    component: ComponentStructureItem,
    text_bboxes: list[list[int]],
    source: str,
    suggested_rule: str,
    image: PngMetadata,
) -> HintProbe | None:
    if not text_bboxes:
        return None
    cluster = union_bboxes(text_bboxes)
    search_width = min(120, max(36, cluster[0] - component.bbox[0]))
    search = normalize_bbox(
        [
            max(component.bbox[0], cluster[0] - search_width),
            max(component.bbox[1], cluster[1] - 16),
            search_width,
            min(component.bbox[1] + component.bbox[3], cluster[1] + cluster[3] + 16) - max(component.bbox[1], cluster[1] - 16),
        ],
        image,
    )
    if search is None:
        return None
    return HintProbe(source, search, component.id, component.role, "left_of_text_cluster", suggested_rule)


def field_hint_probes(component: ComponentStructureItem, text_bboxes: list[list[int]], image: PngMetadata) -> list[HintProbe]:
    rows = paired_rows(text_bboxes)
    if len(rows) < 2:
        return []
    probes: list[HintProbe] = []
    for row in rows:
        first = min(row, key=lambda bbox: bbox[0])
        search_width = min(max(40, round(first[3] * 2.4)), 96)
        search = normalize_bbox(
            [
                max(component.bbox[0], first[0] - search_width),
                max(component.bbox[1], first[1] - 10),
                max(1, first[0] - max(component.bbox[0], first[0] - search_width) - 4),
                min(component.bbox[1] + component.bbox[3], first[1] + first[3] + 10) - max(component.bbox[1], first[1] - 10),
            ],
            image,
        )
        if search is not None:
            probes.append(HintProbe("field_icon_hint", search, component.id, component.role, "field_leading_visual", "field_icon_candidate"))
    return probes


def paired_rows(bboxes: list[list[int]]) -> list[list[list[int]]]:
    rows: list[list[list[int]]] = []
    for bbox in sorted(bboxes, key=lambda item: (bbox_center_y(item), item[0])):
        for row in rows:
            center = sum(bbox_center_y(item) for item in row) / len(row)
            height = sum(item[3] for item in row) / len(row)
            if abs(bbox_center_y(bbox) - center) <= max(10, height * 0.55):
                row.append(bbox)
                break
        else:
            rows.append([bbox])
    return [sorted(row, key=lambda item: item[0]) for row in rows if len(row) >= 2]


def score_hint(bbox: list[int], contrast: int, blob_count: int, thin: bool, settings: Settings) -> float:
    score = 0.45
    if hint_size_like(bbox, settings):
        score += 0.15
    if contrast >= settings.icon_coverage_foreground_distance:
        score += 0.12
    score += 0.10
    score += 0.08
    if blob_count > 4:
        score -= 0.15
    if thin:
        score -= 0.20
    return round(max(0, min(0.99, score)), 3)


def hint_size_like(bbox: list[int], settings: Settings) -> bool:
    max_hint_size = min(settings.icon_candidate_max_size, 72)
    return settings.icon_candidate_min_size <= bbox[2] <= max_hint_size and settings.icon_candidate_min_size <= bbox[3] <= max_hint_size


def is_text_stroke_like(bbox: list[int]) -> bool:
    ratio = bbox[2] / max(1, bbox[3])
    return bbox[2] < 14 or bbox[3] < 14 or ratio < 0.45 or ratio > 2.8


def draw_rect(
    rows: list[bytearray],
    width: int,
    height: int,
    bbox: list[int],
    rgb: tuple[int, int, int],
    *,
    thickness: int,
) -> None:
    x, y, rect_width, rect_height = bbox
    x1 = max(0, min(width - 1, x))
    y1 = max(0, min(height - 1, y))
    x2 = max(0, min(width - 1, x + rect_width - 1))
    y2 = max(0, min(height - 1, y + rect_height - 1))
    color = bytes(rgb)
    for layer in range(thickness):
        top = min(height - 1, y1 + layer)
        bottom = max(0, y2 - layer)
        left = min(width - 1, x1 + layer)
        right = max(0, x2 - layer)
        for column in range(left, right + 1):
            rows[top][column * 3 : column * 3 + 3] = color
            rows[bottom][column * 3 : column * 3 + 3] = color
        for row_index in range(top, bottom + 1):
            rows[row_index][left * 3 : left * 3 + 3] = color
            rows[row_index][right * 3 : right * 3 + 3] = color


def union_bboxes(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox[0] + bbox[2] for bbox in bboxes)
    y2 = max(bbox[1] + bbox[3] for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def coverage_by_source(document: IconCandidateDocument) -> dict[str, int]:
    summary: dict[str, int] = {}
    for icon in document.icons:
        if icon.status != "candidate":
            continue
        summary[icon.source] = summary.get(icon.source, 0) + 1
    return summary


def missed_hint_by_source(hints: list[MissedIconHintItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for hint in hints:
        summary[hint.source] = summary.get(hint.source, 0) + 1
    return summary


def image_size(path: str, fallback: dict[str, int]) -> tuple[int, int]:
    metadata = read_png_metadata(Path(path).read_bytes())
    if metadata is None:
        return fallback["width"], fallback["height"]
    return metadata.width, metadata.height


def unique_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result
