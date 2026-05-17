from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .component_annotation import index_dsl_elements
from .component_structure import ComponentStructureDocument, ComponentStructureItem
from .config import Settings
from .icon_candidate import (
    ForegroundBlob,
    IconCandidateDocument,
    bbox_in_bounds,
    bbox_inside,
    bboxes_near,
    estimate_background,
    find_foreground_blobs,
    iou,
    normalize_bbox,
    padded_bbox,
    union_bboxes,
    unique_preserve_order,
)
from .icon_coverage import (
    IconCoverageAuditDocument,
    MissedIconHintItem,
    bbox_from_element,
    bboxes_by_role,
    draw_rect,
    group_candidate_icons_by_component,
    group_text_elements_by_component,
    header_app_content_top,
    header_search_bbox,
    leading_probe,
    trailing_probe,
    unique_bboxes,
)
from .png_tools import (
    PngMetadata,
    PngPixels,
    PngRegion,
    UnsupportedPngCropError,
    crop_png,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
)
from .text_binding import TextPrimitiveBindingDocument


IconGapDocumentStatus = Literal["completed", "failed", "skipped"]
IconGapStatus = Literal["candidate", "blocked", "failed", "skipped"]

GAP_STATUSES = {"candidate", "blocked", "failed", "skipped"}
GAP_SOURCES = {
    "header_left_nav_icon",
    "header_right_action_icon",
    "row_trailing_icon",
    "button_trailing_icon",
    "card_trailing_icon",
    "bottom_nav_missing_icon",
    "shortcut_missing_icon",
    "field_missing_icon",
}
M21_HINT_TO_GAP_SOURCE = {
    "header_left_visual_hint": "header_left_nav_icon",
    "header_right_visual_hint": "header_right_action_icon",
    "right_arrow_hint": "row_trailing_icon",
    "card_trailing_icon_hint": "card_trailing_icon",
    "bottom_nav_missing_icon_hint": "bottom_nav_missing_icon",
    "shortcut_missing_icon_hint": "shortcut_missing_icon",
    "field_icon_hint": "field_missing_icon",
}
RISKS = {"low", "medium", "high"}

OVERLAY_COLORS = {
    "candidate": (0, 200, 90),
    "blocked": (255, 205, 0),
    "failed": (235, 64, 52),
    "edge_retry": (0, 122, 255),
    "region_probe": (150, 80, 220),
}


@dataclass
class IconGapWarning:
    code: str
    message: str
    hintId: str | None = None
    gapIconId: str | None = None


@dataclass
class IconGapItem:
    id: str
    source: str
    sourceHintId: str | None
    status: IconGapStatus
    bbox: list[int]
    confidence: float
    componentId: str | None
    componentRole: str | None
    assetId: str | None
    assetPath: str | None
    assetUrl: str | None
    relatedTextElementIds: list[str]
    relatedBindingIds: list[str]
    quality: dict[str, Any]


@dataclass
class BlockedGapHint:
    id: str
    sourceHintId: str | None
    source: str
    status: Literal["blocked", "skipped"]
    bbox: list[int]
    confidence: float
    reasons: list[str]


@dataclass
class IconGapOverlay:
    assetId: str
    assetPath: str
    assetUrl: str


@dataclass
class IconGapCandidateDocument:
    version: str
    taskId: str
    status: IconGapDocumentStatus
    imageSize: dict[str, int]
    gapIcons: list[IconGapItem]
    blockedHints: list[BlockedGapHint]
    gapOverlay: IconGapOverlay | None
    warnings: list[IconGapWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IconGapStorageAdapter:
    assets_root: Path
    public_base_url: str

    def icon_path(self, task_id: str, filename: str) -> Path:
        return self.assets_root / task_id / "icons_gap" / filename

    def icon_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/icons_gap/{filename}"

    def overlay_path(self, task_id: str, filename: str) -> Path:
        return self.assets_root / task_id / "debug" / filename

    def overlay_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/debug/{filename}"

    def write_icon(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.icon_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_overlay(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.overlay_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


@dataclass(frozen=True)
class GapProbe:
    source: str
    search_bbox: list[int]
    source_hint_id: str | None
    hint_bbox: list[int] | None
    component_id: str | None
    component_role: str | None
    related_text_ids: list[str]
    related_binding_ids: list[str]
    geometry_reason: str
    proactive: bool = False


@dataclass(frozen=True)
class CandidatePick:
    bbox: list[int]
    contrast: int
    blob_count: int
    reasons: list[str]


def build_icon_gap_candidate_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    icon_candidate_document: IconCandidateDocument | None,
    icon_coverage_document: IconCoverageAuditDocument | None,
    dsl: dict[str, Any],
    settings: Settings,
    storage: IconGapStorageAdapter,
) -> IconGapCandidateDocument:
    if not settings.icon_gap_candidate_enabled:
        return build_skipped_icon_gap_document(
            task_id=task_id,
            image=image,
            code="icon_gap_candidate_disabled",
            message="Icon gap candidate extraction is disabled.",
        )
    if icon_coverage_document is None or icon_coverage_document.status != "completed":
        return build_skipped_icon_gap_document(
            task_id=task_id,
            image=image,
            code="icon_coverage_audit_not_completed",
            message="Icon gap candidate extraction skipped because icon coverage audit did not complete.",
        )
    if icon_candidate_document is None or icon_candidate_document.status != "completed":
        return build_skipped_icon_gap_document(
            task_id=task_id,
            image=image,
            code="icon_candidate_not_completed",
            message="Icon gap candidate extraction skipped because icon candidates did not complete.",
        )
    if binding_document.status != "completed":
        return build_skipped_icon_gap_document(
            task_id=task_id,
            image=image,
            code="text_binding_not_completed",
            message="Icon gap candidate extraction skipped because text binding did not complete.",
        )
    if structure_document.status != "completed":
        return build_skipped_icon_gap_document(
            task_id=task_id,
            image=image,
            code="component_structure_not_completed",
            message="Icon gap candidate extraction skipped because component structure did not complete.",
        )

    warnings: list[IconGapWarning] = []
    try:
        pixels = decode_png_pixels(png_data)
    except UnsupportedPngCropError as error:
        warnings.append(IconGapWarning(code="png_pixel_decode_unsupported", message=str(error)))
        document = IconGapCandidateDocument(
            version="0.1",
            taskId=task_id,
            status="completed",
            imageSize={"width": image.width, "height": image.height},
            gapIcons=[],
            blockedHints=[],
            gapOverlay=None,
            warnings=warnings,
            meta=empty_meta(),
        )
        return document

    elements = index_dsl_elements(dsl)
    components = {component.id: component for component in structure_document.components}
    binding_ids = {binding.id for binding in binding_document.bindings}
    text_bboxes = unique_bboxes(
        bboxes_by_role(elements, {"visible_text_replacement"})
        + bboxes_by_role(elements, {"candidate_text"})
    )
    cover_bboxes = bboxes_by_role(elements, {"text_replacement_cover"})
    existing_icon_bboxes = [icon.bbox for icon in icon_candidate_document.icons if icon.status == "candidate"]

    gap_icons: list[IconGapItem] = []
    blocked_hints: list[BlockedGapHint] = []
    seen_gap_bboxes: list[list[int]] = []
    probes = build_gap_probes(
        image=image,
        structure_document=structure_document,
        icon_candidate_document=icon_candidate_document,
        icon_coverage_document=icon_coverage_document,
        elements=elements,
    )
    for probe in probes:
        if len([icon for icon in gap_icons if icon.status == "candidate"]) >= settings.icon_gap_candidate_max_candidates:
            warnings.append(IconGapWarning(code="icon_gap_candidate_limit_reached", message="Icon gap candidate limit reached."))
            break
        result = build_gap_icon_for_probe(
            task_id=task_id,
            image=image,
            png_data=png_data,
            pixels=pixels,
            probe=probe,
            components=components,
            binding_ids=binding_ids,
            existing_icon_bboxes=existing_icon_bboxes,
            seen_gap_bboxes=seen_gap_bboxes,
            text_bboxes=text_bboxes,
            cover_bboxes=cover_bboxes,
            settings=settings,
            storage=storage,
            index=len(gap_icons) + 1,
        )
        if isinstance(result, IconGapItem):
            gap_icons.append(result)
            if result.status == "candidate":
                seen_gap_bboxes.append(result.bbox)
        elif result is not None:
            blocked_hints.append(result)

    overlay: IconGapOverlay | None = None
    if settings.icon_gap_candidate_overlay_enabled:
        overlay, overlay_warning = build_gap_overlay(
            task_id=task_id,
            pixels=pixels,
            gap_icons=gap_icons,
            blocked_hints=blocked_hints,
            storage=storage,
        )
        if overlay_warning is not None:
            warnings.append(overlay_warning)

    document = IconGapCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        gapIcons=gap_icons,
        blockedHints=blocked_hints,
        gapOverlay=overlay,
        warnings=warnings,
        meta=build_meta(gap_icons, blocked_hints),
    )
    validation_errors = validate_icon_gap_candidate_document(
        document=document,
        binding_document=binding_document,
        structure_document=structure_document,
        icon_candidate_document=icon_candidate_document,
        icon_coverage_document=icon_coverage_document,
        dsl=dsl,
        image=image,
    )
    if validation_errors:
        return build_failed_icon_gap_document(
            task_id=task_id,
            image=image,
            code="ICON_GAP_CANDIDATE_VALIDATION_FAILED",
            message="Icon gap candidate validation failed.",
            warnings=[IconGapWarning(code="ICON_GAP_CANDIDATE_VALIDATION_ERROR", message=error) for error in validation_errors],
        )
    return document


def build_gap_probes(
    *,
    image: PngMetadata,
    structure_document: ComponentStructureDocument,
    icon_candidate_document: IconCandidateDocument,
    icon_coverage_document: IconCoverageAuditDocument,
    elements: dict[str, dict[str, Any]],
) -> list[GapProbe]:
    probes: list[GapProbe] = []
    for hint in icon_coverage_document.missedIconHints:
        probe = probe_from_hint(hint, image)
        if probe is not None:
            probes.append(probe)
        elif hint.source == "low_confidence_icon_like_blob":
            probes.append(
                GapProbe(
                    source="field_missing_icon",
                    search_bbox=hint.bbox,
                    source_hint_id=hint.id,
                    hint_bbox=hint.bbox,
                    component_id=hint.componentId,
                    component_role=hint.componentRole,
                    related_text_ids=[],
                    related_binding_ids=[],
                    geometry_reason="low_confidence_icon_like_blob",
                )
            )

    existing_hint_boxes = [probe.hint_bbox for probe in probes if probe.hint_bbox is not None]
    icons_by_component = group_candidate_icons_by_component(icon_candidate_document)
    text_elements_by_component = group_text_elements_by_component(structure_document.components, elements)
    for probe in proactive_header_probes(image, elements):
        if not any(iou(probe.search_bbox, bbox) > 0.35 for bbox in existing_hint_boxes):
            probes.append(probe)
    for component in structure_document.components:
        component_icons = icons_by_component.get(component.id, [])
        if component.role in {"preview_card", "activity_card", "tip_card"}:
            source = "card_trailing_icon"
            if component.role == "activity_card":
                source = "row_trailing_icon"
            trailing = trailing_probe(component, source, image)
            if trailing is not None and not any(icon.source in {"row_trailing_icon", "card_trailing_icon"} for icon in component_icons):
                probes.append(
                    GapProbe(
                        source=source,
                        search_bbox=trailing.search_bbox,
                        source_hint_id=None,
                        hint_bbox=None,
                        component_id=component.id,
                        component_role=component.role,
                        related_text_ids=[],
                        related_binding_ids=[],
                        geometry_reason="trailing_icon_zone",
                        proactive=True,
                    )
                )
        if component.role in {"primary_button", "outline_button"}:
            trailing = trailing_probe(component, "button_trailing_icon", image)
            if trailing is not None:
                probes.append(
                    GapProbe(
                        source="button_trailing_icon",
                        search_bbox=trailing.search_bbox,
                        source_hint_id=None,
                        hint_bbox=None,
                        component_id=component.id,
                        component_role=component.role,
                        related_text_ids=[],
                        related_binding_ids=[],
                        geometry_reason="trailing_icon_zone",
                        proactive=True,
                    )
                )
        if component.role == "bottom_nav_item" and not any(icon.source == "bottom_nav_label_above" for icon in component_icons):
            text_bboxes = text_elements_by_component.get(component.id, [])
            if text_bboxes:
                label = max(text_bboxes, key=lambda bbox: bbox[1])
                search = normalize_bbox([component.bbox[0], component.bbox[1], component.bbox[2], label[1] - component.bbox[1]], image)
                if search is not None:
                    probes.append(
                        GapProbe(
                            source="bottom_nav_missing_icon",
                            search_bbox=search,
                            source_hint_id=None,
                            hint_bbox=None,
                            component_id=component.id,
                            component_role=component.role,
                            related_text_ids=[],
                            related_binding_ids=[],
                            geometry_reason="bottom_nav_gap_zone",
                            proactive=True,
                        )
                    )
        if component.role == "shortcut_card" and not any(icon.source == "shortcut_card_leading_icon" for icon in component_icons):
            leading = leading_probe(component, text_elements_by_component.get(component.id, []), "shortcut_missing_icon_hint", "shortcut_missing_icon", image)
            if leading is not None:
                probes.append(
                    GapProbe(
                        source="shortcut_missing_icon",
                        search_bbox=leading.search_bbox,
                        source_hint_id=None,
                        hint_bbox=None,
                        component_id=component.id,
                        component_role=component.role,
                        related_text_ids=[],
                        related_binding_ids=[],
                        geometry_reason="shortcut_gap_zone",
                        proactive=True,
                    )
                )
    return dedupe_probes(probes)


def probe_from_hint(hint: MissedIconHintItem, image: PngMetadata) -> GapProbe | None:
    source = M21_HINT_TO_GAP_SOURCE.get(hint.source)
    if source is None:
        return None
    search_padding = 8 if source != "field_missing_icon" else 4
    search = padded_bbox(hint.bbox, search_padding, image)
    return GapProbe(
        source=source,
        search_bbox=search,
        source_hint_id=hint.id,
        hint_bbox=hint.bbox,
        component_id=hint.componentId,
        component_role=hint.componentRole,
        related_text_ids=[],
        related_binding_ids=[],
        geometry_reason=geometry_reason_for_source(source),
    )


def proactive_header_probes(image: PngMetadata, elements: dict[str, dict[str, Any]]) -> list[GapProbe]:
    header_bbox = header_search_bbox(image, elements)
    top = header_app_content_top(header_bbox, image)
    height = min(header_bbox[1] + header_bbox[3] - top, 96)
    probes: list[GapProbe] = []
    left = normalize_bbox([0, top, min(150, image.width), height], image)
    right = normalize_bbox([max(0, image.width - 150), top, min(150, image.width), height], image)
    if left is not None:
        probes.append(GapProbe("header_left_nav_icon", left, None, None, None, "page_header", [], [], "header_action_zone", True))
    if right is not None:
        probes.append(GapProbe("header_right_action_icon", right, None, None, None, "page_header", [], [], "header_action_zone", True))
    return probes


def build_gap_icon_for_probe(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    pixels: PngPixels,
    probe: GapProbe,
    components: dict[str, ComponentStructureItem],
    binding_ids: set[str],
    existing_icon_bboxes: list[list[int]],
    seen_gap_bboxes: list[list[int]],
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    settings: Settings,
    storage: IconGapStorageAdapter,
    index: int,
) -> IconGapItem | BlockedGapHint | None:
    if probe.source not in GAP_SOURCES:
        return blocked_hint(index, probe, "gap_source_unsupported")
    component = components.get(probe.component_id) if probe.component_id else None
    if probe.component_id is not None and component is None:
        return blocked_hint(index, probe, "component_missing")
    if probe.source == "field_missing_icon" and probe.source_hint_id is not None:
        if probe.hint_bbox is not None and is_text_stroke_like(probe.hint_bbox, field_strict=True):
            return blocked_hint(index, probe, "gap_bbox_text_like")
    pick = pick_candidate_bbox(
        pixels=pixels,
        image=image,
        probe=probe,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        existing_icon_bboxes=existing_icon_bboxes,
        seen_gap_bboxes=seen_gap_bboxes,
        settings=settings,
    )
    if pick is None:
        return blocked_hint(index, probe, "no_foreground_blob") if probe.source_hint_id else None
    if "edge_clipped_unresolved" in pick.reasons:
        return blocked_hint(index, probe, "edge_clipped_unresolved", pick.bbox)
    reasons = list(pick.reasons)
    if component is not None and not bbox_inside(pick.bbox, component.bbox):
        return blocked_hint(index, probe, "gap_bbox_outside_component", pick.bbox)
    if probe.component_id is not None and component is not None:
        reasons.append("inside_component_bbox")
    if not bbox_in_bounds(pick.bbox, image):
        return blocked_hint(index, probe, "gap_bbox_out_of_bounds", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.50 for bbox in existing_icon_bboxes):
        return blocked_hint(index, probe, "gap_bbox_duplicate_m20", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.70 for bbox in seen_gap_bboxes):
        return blocked_hint(index, probe, "duplicate_gap_candidate", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.10 for bbox in text_bboxes):
        return blocked_hint(index, probe, "gap_bbox_overlaps_text", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.10 for bbox in cover_bboxes):
        return blocked_hint(index, probe, "gap_bbox_overlaps_cover", pick.bbox)
    if is_status_bar_bbox(pick.bbox, probe, image):
        return blocked_hint(index, probe, "gap_bbox_status_bar", pick.bbox)
    if not gap_size_like(pick.bbox, probe.source, settings):
        return blocked_hint(index, probe, "gap_bbox_too_large" if max(pick.bbox[2], pick.bbox[3]) > settings.icon_gap_candidate_max_size else "gap_bbox_too_small", pick.bbox)
    if is_text_stroke_like(pick.bbox, field_strict=probe.source == "field_missing_icon"):
        return blocked_hint(index, probe, "gap_bbox_text_like", pick.bbox)

    confidence = score_gap_candidate(probe, pick, settings)
    if confidence < settings.icon_gap_candidate_min_confidence:
        return blocked_hint(index, probe, "candidate_confidence_low", pick.bbox, confidence)
    gap_id = f"icon_gap_{index:03d}"
    filename = f"{gap_id}.png"
    try:
        cropped = crop_png(png_data, PngRegion(gap_id, pick.bbox[0], pick.bbox[1], pick.bbox[2], pick.bbox[3]))
        path = storage.write_icon(task_id, filename, cropped)
    except UnsupportedPngCropError:
        return failed_gap_icon(index, probe, pick.bbox, "png_crop_unsupported", confidence)
    except OSError:
        return failed_gap_icon(index, probe, pick.bbox, "asset_write_failed", confidence)

    reasons.extend(
        [
            "m21_missed_hint_found" if probe.source_hint_id else "region_guided_probe",
            probe.geometry_reason,
            "not_status_bar",
            "not_overlapping_text",
            "not_overlapping_cover",
            "not_overlapping_candidate_text",
            "not_duplicate_m20_icon",
            "crop_bbox_valid",
        ]
    )
    return IconGapItem(
        id=gap_id,
        source=probe.source,
        sourceHintId=probe.source_hint_id,
        status="candidate",
        bbox=pick.bbox,
        confidence=confidence,
        componentId=probe.component_id,
        componentRole=probe.component_role,
        assetId=f"asset_{gap_id}",
        assetPath=str(path),
        assetUrl=storage.icon_url(task_id, filename),
        relatedTextElementIds=probe.related_text_ids,
        relatedBindingIds=probe.related_binding_ids,
        quality={"risk": "low", "reasons": unique_preserve_order(reasons)},
    )


def pick_candidate_bbox(
    *,
    pixels: PngPixels,
    image: PngMetadata,
    probe: GapProbe,
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    existing_icon_bboxes: list[list[int]],
    seen_gap_bboxes: list[list[int]],
    settings: Settings,
) -> CandidatePick | None:
    pick = raw_pick_candidate_bbox(
        pixels=pixels,
        image=image,
        probe=probe,
        search_bbox=probe.search_bbox,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        existing_icon_bboxes=existing_icon_bboxes,
        seen_gap_bboxes=seen_gap_bboxes,
        settings=settings,
    )
    if pick is None:
        return None
    if not touches_search_edge(pick.bbox, probe.search_bbox, settings.icon_gap_candidate_edge_clip_tolerance):
        return pick
    expanded = padded_bbox(probe.search_bbox, settings.icon_gap_candidate_retry_padding, image)
    retry_probe = GapProbe(
        source=probe.source,
        search_bbox=expanded,
        source_hint_id=probe.source_hint_id,
        hint_bbox=probe.hint_bbox,
        component_id=probe.component_id,
        component_role=probe.component_role,
        related_text_ids=probe.related_text_ids,
        related_binding_ids=probe.related_binding_ids,
        geometry_reason=probe.geometry_reason,
        proactive=probe.proactive,
    )
    retry = raw_pick_candidate_bbox(
        pixels=pixels,
        image=image,
        probe=retry_probe,
        search_bbox=expanded,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        existing_icon_bboxes=existing_icon_bboxes,
        seen_gap_bboxes=seen_gap_bboxes,
        settings=settings,
    )
    if retry is None or touches_search_edge(retry.bbox, expanded, settings.icon_gap_candidate_edge_clip_tolerance):
        return CandidatePick(pick.bbox, pick.contrast, pick.blob_count, unique_preserve_order(pick.reasons + ["edge_clipped_unresolved"]))
    return CandidatePick(retry.bbox, retry.contrast, retry.blob_count, unique_preserve_order(retry.reasons + ["edge_clipped_retry_applied"]))


def raw_pick_candidate_bbox(
    *,
    pixels: PngPixels,
    image: PngMetadata,
    probe: GapProbe,
    search_bbox: list[int],
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    existing_icon_bboxes: list[list[int]],
    seen_gap_bboxes: list[list[int]],
    settings: Settings,
) -> CandidatePick | None:
    background = estimate_background(pixels, search_bbox)
    raw_blobs = find_foreground_blobs(pixels, search_bbox, background, settings.icon_gap_candidate_foreground_distance)
    blobs = merge_gap_blobs(raw_blobs, distance=12)
    candidates: list[tuple[ForegroundBlob, list[int], list[str]]] = []
    for blob in blobs:
        bbox = padded_bbox(blob.bbox, 4, image)
        reasons: list[str] = []
        if len(raw_blobs) > len(blobs):
            reasons.append("multi_blob_union_applied")
        if probe.hint_bbox is not None and iou(bbox, probe.hint_bbox) <= 0.05 and not bboxes_near(bbox, probe.hint_bbox, 10):
            continue
        if any(iou(bbox, item) > 0.50 for item in existing_icon_bboxes):
            continue
        if any(iou(bbox, item) > 0.70 for item in seen_gap_bboxes):
            continue
        if any(iou(bbox, item) > 0.10 for item in text_bboxes):
            continue
        if any(iou(bbox, item) > 0.10 for item in cover_bboxes):
            continue
        if is_status_bar_bbox(bbox, probe, image):
            continue
        if not gap_size_like(bbox, probe.source, settings):
            continue
        if is_text_stroke_like(bbox, field_strict=probe.source == "field_missing_icon"):
            continue
        if probe.source == "header_right_action_icon" and looks_like_whole_capsule(bbox):
            continue
        reasons.append("foreground_contrast_ok" if blob.contrast >= settings.icon_gap_candidate_foreground_distance else "foreground_contrast_low")
        candidates.append((blob, bbox, reasons))
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            score_gap_bbox(probe, item[1], item[0].contrast, len(blobs), settings),
            item[0].area,
        ),
        reverse=True,
    )
    blob, bbox, reasons = candidates[0]
    return CandidatePick(bbox=bbox, contrast=blob.contrast, blob_count=len(blobs), reasons=reasons)


def build_gap_overlay(
    *,
    task_id: str,
    pixels: PngPixels,
    gap_icons: list[IconGapItem],
    blocked_hints: list[BlockedGapHint],
    storage: IconGapStorageAdapter,
) -> tuple[IconGapOverlay | None, IconGapWarning | None]:
    rows = [bytearray(row) for row in pixels.rows]
    for hint in blocked_hints:
        draw_rect(rows, pixels.width, pixels.height, hint.bbox, OVERLAY_COLORS["blocked"], thickness=2)
    for icon in gap_icons:
        if icon.status == "failed":
            color = OVERLAY_COLORS["failed"]
        elif "edge_clipped_retry_applied" in icon.quality.get("reasons", []):
            color = OVERLAY_COLORS["edge_retry"]
        elif icon.sourceHintId is None:
            color = OVERLAY_COLORS["region_probe"]
        else:
            color = OVERLAY_COLORS["candidate"]
        draw_rect(rows, pixels.width, pixels.height, icon.bbox, color, thickness=2)
    try:
        data = encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])
        filename = "icon_gap_overlay.png"
        path = storage.write_overlay(task_id, filename, data)
        return IconGapOverlay("asset_icon_gap_overlay", str(path), storage.overlay_url(task_id, filename)), None
    except (OSError, UnsupportedPngCropError) as error:
        return None, IconGapWarning(code="icon_gap_overlay_write_failed", message=str(error))


def apply_icon_gap_metadata(dsl: dict[str, Any], document: IconGapCandidateDocument) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m22_icon_gap_candidates" not in quality_flags:
        quality_flags.append("m22_icon_gap_candidates")
    meta["qualityFlags"] = quality_flags
    meta["iconGapCandidateCount"] = int(document.meta.get("gapIconCount", 0))
    meta["iconGapCroppedAssetCount"] = int(document.meta.get("croppedGapIconCount", 0))
    meta["iconGapBlockedCount"] = int(document.meta.get("blockedCount", 0))
    meta["iconGapFailedCropCount"] = int(document.meta.get("failedCropCount", 0))
    return next_dsl


def validate_icon_gap_candidate_document(
    *,
    document: IconGapCandidateDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    icon_candidate_document: IconCandidateDocument,
    icon_coverage_document: IconCoverageAuditDocument,
    dsl: dict[str, Any],
    image: PngMetadata,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    gap_ids = {icon.id for icon in document.gapIcons}
    if len(gap_ids) != len(document.gapIcons):
        errors.append("gap icon ids must be unique")
    blocked_ids = {hint.id for hint in document.blockedHints}
    if len(blocked_ids) != len(document.blockedHints):
        errors.append("blocked hint ids must be unique")

    m21_hint_ids = {hint.id for hint in icon_coverage_document.missedIconHints}
    component_ids = {component.id for component in structure_document.components}
    binding_ids = {binding.id for binding in binding_document.bindings}
    elements = index_dsl_elements(dsl)
    text_bboxes = unique_bboxes(bboxes_by_role(elements, {"visible_text_replacement"}) + bboxes_by_role(elements, {"candidate_text"}))
    cover_bboxes = bboxes_by_role(elements, {"text_replacement_cover"})
    m20_bboxes = [icon.bbox for icon in icon_candidate_document.icons if icon.status == "candidate"]

    for icon in document.gapIcons:
        if icon.status not in GAP_STATUSES:
            errors.append(f"invalid gap icon status: {icon.id}")
        if icon.source not in GAP_SOURCES:
            errors.append(f"invalid gap icon source: {icon.id}")
        if icon.sourceHintId is not None and icon.sourceHintId not in m21_hint_ids:
            errors.append(f"gap icon references missing M21 hint: {icon.id}")
        if icon.componentId is not None and icon.componentId not in component_ids:
            errors.append(f"gap icon references missing component: {icon.id}")
        if icon.componentId is not None:
            component = next((item for item in structure_document.components if item.id == icon.componentId), None)
            if component is not None and not bbox_inside(icon.bbox, component.bbox):
                errors.append(f"gap icon bbox must be inside component bbox: {icon.id}")
        if icon.quality.get("risk") not in RISKS:
            errors.append(f"invalid gap icon risk: {icon.id}")
        if not bbox_in_bounds(icon.bbox, image):
            errors.append(f"gap icon bbox is out of bounds: {icon.id}")
        if any(iou(icon.bbox, bbox) > 0.50 for bbox in m20_bboxes):
            errors.append(f"gap icon duplicates M20 icon: {icon.id}")
        if any(iou(icon.bbox, bbox) > 0.10 for bbox in text_bboxes):
            errors.append(f"gap icon overlaps text: {icon.id}")
        if any(iou(icon.bbox, bbox) > 0.10 for bbox in cover_bboxes):
            errors.append(f"gap icon overlaps cover: {icon.id}")
        for binding_id in icon.relatedBindingIds:
            if binding_id not in binding_ids:
                errors.append(f"gap icon references missing binding: {icon.id}")
        for element_id in icon.relatedTextElementIds:
            if element_id not in elements:
                errors.append(f"gap icon references missing DSL element: {icon.id}")
        if icon.status == "candidate":
            if not icon.assetId or not icon.assetPath or not icon.assetUrl:
                errors.append(f"candidate gap icon asset fields are required: {icon.id}")
            elif not Path(icon.assetPath).exists():
                errors.append(f"candidate gap icon asset path must exist: {icon.id}")
        elif icon.assetPath or icon.assetId or icon.assetUrl:
            errors.append(f"non-candidate gap icon must not have asset fields: {icon.id}")

    for hint in document.blockedHints:
        if hint.sourceHintId is not None and hint.sourceHintId not in m21_hint_ids:
            errors.append(f"blocked hint references missing M21 hint: {hint.id}")
        if hint.source not in GAP_SOURCES:
            errors.append(f"invalid blocked hint source: {hint.id}")
        if hint.status not in {"blocked", "skipped"}:
            errors.append(f"invalid blocked hint status: {hint.id}")
        if not bbox_in_bounds(hint.bbox, image):
            errors.append(f"blocked hint bbox is out of bounds: {hint.id}")
    if document.gapOverlay is not None and not Path(document.gapOverlay.assetPath).exists():
        errors.append("gap overlay asset path must exist")
    if document.meta.get("gapIconCount") != sum(1 for icon in document.gapIcons if icon.status == "candidate"):
        errors.append("meta gapIconCount must match candidate icons")
    if document.meta.get("croppedGapIconCount") != sum(1 for icon in document.gapIcons if icon.status == "candidate" and icon.assetPath):
        errors.append("meta croppedGapIconCount must match cropped icons")
    if document.meta.get("blockedCount") != len(document.blockedHints):
        errors.append("meta blockedCount must match blocked hints")
    if document.meta.get("failedCropCount") != sum(1 for icon in document.gapIcons if icon.status == "failed"):
        errors.append("meta failedCropCount must match failed icons")
    if document.meta.get("sourceSummary") != summarize_gap_sources(document.gapIcons):
        errors.append("meta sourceSummary must match gap icons")
    if document.meta.get("blockedReasonSummary") != summarize_blocked_reasons(document.blockedHints):
        errors.append("meta blockedReasonSummary must match blocked hints")
    return errors


def gap_icon_asset_records(document: IconGapCandidateDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for icon in document.gapIcons:
        if icon.status != "candidate" or not icon.assetId or not icon.assetPath or not icon.assetUrl:
            continue
        width, height = image_size(icon.assetPath, icon.bbox)
        records.append(
            {
                "asset_id": icon.assetId,
                "task_id": task_id,
                "role": "asset_icon_gap_candidate",
                "path": icon.assetPath,
                "url": icon.assetUrl,
                "mime_type": "image/png",
                "width": width,
                "height": height,
                "created_at": created_at,
            }
        )
    return records


def gap_overlay_asset_records(document: IconGapCandidateDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    if document.gapOverlay is None:
        return []
    width, height = image_size(document.gapOverlay.assetPath, [0, 0, document.imageSize["width"], document.imageSize["height"]])
    return [
        {
            "asset_id": document.gapOverlay.assetId,
            "task_id": task_id,
            "role": "asset_icon_gap_overlay",
            "path": document.gapOverlay.assetPath,
            "url": document.gapOverlay.assetUrl,
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "created_at": created_at,
        }
    ]


def build_skipped_icon_gap_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> IconGapCandidateDocument:
    return IconGapCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        gapIcons=[],
        blockedHints=[],
        gapOverlay=None,
        warnings=[IconGapWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_icon_gap_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[IconGapWarning] | None = None,
) -> IconGapCandidateDocument:
    return IconGapCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        gapIcons=[],
        blockedHints=[],
        gapOverlay=None,
        warnings=warnings or [IconGapWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def failed_gap_icon(index: int, probe: GapProbe, bbox: list[int], reason: str, confidence: float) -> IconGapItem:
    return IconGapItem(
        id=f"icon_gap_{index:03d}",
        source=probe.source,
        sourceHintId=probe.source_hint_id,
        status="failed",
        bbox=bbox,
        confidence=confidence,
        componentId=probe.component_id,
        componentRole=probe.component_role,
        assetId=None,
        assetPath=None,
        assetUrl=None,
        relatedTextElementIds=probe.related_text_ids,
        relatedBindingIds=probe.related_binding_ids,
        quality={"risk": "high", "reasons": [reason]},
    )


def blocked_hint(
    index: int,
    probe: GapProbe,
    reason: str,
    bbox: list[int] | None = None,
    confidence: float | None = None,
) -> BlockedGapHint:
    return BlockedGapHint(
        id=f"blocked_gap_hint_{index:03d}",
        sourceHintId=probe.source_hint_id,
        source=probe.source,
        status="blocked",
        bbox=bbox or probe.hint_bbox or probe.search_bbox,
        confidence=round(confidence if confidence is not None else 0, 3),
        reasons=[reason],
    )


def build_meta(gap_icons: list[IconGapItem], blocked_hints: list[BlockedGapHint]) -> dict[str, Any]:
    return {
        "notes": "region_guided_icon_gap_candidate_harness",
        "gapIconCount": sum(1 for icon in gap_icons if icon.status == "candidate"),
        "croppedGapIconCount": sum(1 for icon in gap_icons if icon.status == "candidate" and icon.assetPath),
        "blockedCount": len(blocked_hints),
        "failedCropCount": sum(1 for icon in gap_icons if icon.status == "failed"),
        "sourceSummary": summarize_gap_sources(gap_icons),
        "blockedReasonSummary": summarize_blocked_reasons(blocked_hints),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "region_guided_icon_gap_candidate_harness",
        "gapIconCount": 0,
        "croppedGapIconCount": 0,
        "blockedCount": 0,
        "failedCropCount": 0,
        "sourceSummary": {},
        "blockedReasonSummary": {},
    }


def merge_gap_blobs(blobs: list[ForegroundBlob], *, distance: int) -> list[ForegroundBlob]:
    remaining = list(blobs)
    merged: list[ForegroundBlob] = []
    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed:
            changed = False
            next_remaining: list[ForegroundBlob] = []
            for other in remaining:
                if bboxes_near(current.bbox, other.bbox, distance):
                    current = ForegroundBlob(
                        bbox=union_bboxes([current.bbox, other.bbox]),
                        area=current.area + other.area,
                        contrast=max(current.contrast, other.contrast),
                    )
                    changed = True
                else:
                    next_remaining.append(other)
            remaining = next_remaining
        merged.append(current)
    return merged


def dedupe_probes(probes: list[GapProbe]) -> list[GapProbe]:
    result: list[GapProbe] = []
    seen: list[list[int]] = []
    for probe in probes:
        candidate_bbox = probe.hint_bbox or probe.search_bbox
        if any(iou(candidate_bbox, item) > 0.70 for item in seen):
            continue
        result.append(probe)
        seen.append(candidate_bbox)
    return result


def gap_size_like(bbox: list[int], source: str, settings: Settings) -> bool:
    min_size = settings.icon_gap_candidate_min_size
    max_size = settings.icon_gap_candidate_max_size
    if source == "field_missing_icon":
        min_size = max(min_size, 16)
        max_size = min(max_size, 56)
    if source == "header_right_action_icon":
        max_size = min(max_size, 72)
    return min_size <= bbox[2] <= max_size and min_size <= bbox[3] <= max_size


def is_text_stroke_like(bbox: list[int], *, field_strict: bool = False) -> bool:
    ratio = bbox[2] / max(1, bbox[3])
    if bbox[2] < 8 or bbox[3] < 8:
        return True
    if field_strict and (bbox[2] < 16 or bbox[3] < 16):
        return True
    if ratio < 0.35 or ratio > 3.2:
        return True
    if field_strict and not 0.65 <= ratio <= 1.70:
        return True
    return False


def looks_like_whole_capsule(bbox: list[int]) -> bool:
    ratio = bbox[2] / max(1, bbox[3])
    return bbox[2] >= 64 and ratio > 2.2


def is_status_bar_bbox(bbox: list[int], probe: GapProbe, image: PngMetadata) -> bool:
    if probe.source not in {"header_left_nav_icon", "header_right_action_icon"}:
        return False
    top_guard = min(96, max(56, round(image.height * 0.045)))
    return bbox[1] < top_guard


def touches_search_edge(bbox: list[int], search_bbox: list[int], tolerance: int) -> bool:
    search_left = search_bbox[0]
    search_top = search_bbox[1]
    search_right = search_bbox[0] + search_bbox[2]
    search_bottom = search_bbox[1] + search_bbox[3]
    bbox_left = bbox[0]
    bbox_top = bbox[1]
    bbox_right = bbox[0] + bbox[2]
    bbox_bottom = bbox[1] + bbox[3]
    return (
        bbox_left <= search_left + tolerance
        or bbox_top <= search_top + tolerance
        or bbox_right >= search_right - tolerance
        or bbox_bottom >= search_bottom - tolerance
    )


def score_gap_candidate(probe: GapProbe, pick: CandidatePick, settings: Settings) -> float:
    return score_gap_bbox(probe, pick.bbox, pick.contrast, pick.blob_count, settings)


def score_gap_bbox(probe: GapProbe, bbox: list[int], contrast: int, blob_count: int, settings: Settings) -> float:
    score = 0.52 if probe.source_hint_id else 0.48
    if probe.source_hint_id:
        score += 0.14
    if gap_size_like(bbox, probe.source, settings):
        score += 0.05
    if contrast >= settings.icon_gap_candidate_foreground_distance:
        score += 0.08
    score += 0.10
    score += 0.10
    if blob_count > 5:
        score -= 0.12
    if probe.source == "field_missing_icon":
        score -= 0.05
    return round(max(0, min(0.99, score)), 3)


def geometry_reason_for_source(source: str) -> str:
    if source in {"header_left_nav_icon", "header_right_action_icon"}:
        return "header_action_zone"
    if source in {"row_trailing_icon", "button_trailing_icon", "card_trailing_icon"}:
        return "trailing_icon_zone"
    if source == "bottom_nav_missing_icon":
        return "bottom_nav_gap_zone"
    if source == "shortcut_missing_icon":
        return "shortcut_gap_zone"
    if source == "field_missing_icon":
        return "field_gap_zone"
    return "region_guided_probe"


def summarize_gap_sources(gap_icons: list[IconGapItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for icon in gap_icons:
        if icon.status != "candidate":
            continue
        summary[icon.source] = summary.get(icon.source, 0) + 1
    return summary


def summarize_blocked_reasons(blocked_hints: list[BlockedGapHint]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for hint in blocked_hints:
        for reason in hint.reasons:
            summary[reason] = summary.get(reason, 0) + 1
    return summary


def image_size(path: str, fallback_bbox: list[int]) -> tuple[int, int]:
    metadata = read_png_metadata(Path(path).read_bytes())
    if metadata is None:
        return fallback_bbox[2], fallback_bbox[3]
    return metadata.width, metadata.height
