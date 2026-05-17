from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .config import Settings
from .icon_candidate import (
    ForegroundBlob,
    IconCandidateDocument,
    bbox_in_bounds,
    estimate_background,
    find_foreground_blobs,
    iou,
    normalize_bbox,
    padded_bbox,
    union_bboxes,
    unique_preserve_order,
)
from .icon_coverage import draw_rect, bboxes_by_role
from .icon_gap_candidate import IconGapCandidateDocument, merge_gap_blobs, touches_search_edge
from .icon_placement_plan import IconPlacementPlanDocument
from .component_annotation import index_dsl_elements
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


IconBusinessDocumentStatus = Literal["completed", "failed", "skipped"]
IconBusinessStatus = Literal["candidate", "blocked", "failed", "skipped"]

BUSINESS_STATUSES = {"candidate", "blocked", "failed", "skipped"}
BUSINESS_SOURCES = {
    "bottom_nav_region_icon",
    "shortcut_tile_icon",
    "shortcut_leading_icon",
    "metric_card_icon",
    "primary_button_leading_icon",
    "primary_button_trailing_icon",
    "row_trailing_arrow",
    "row_trailing_check",
    "card_trailing_icon",
    "room_card_status_icon",
    "bed_status_icon",
    "tip_leading_icon",
    "info_leading_icon",
    "unknown_business_icon",
}
PLACEMENT_ROLES = {
    "nav_icon",
    "leading_icon",
    "tile_icon",
    "metric_icon",
    "button_leading_icon",
    "button_trailing_icon",
    "trailing_icon",
    "status_icon",
    "tip_leading_icon",
    "info_leading_icon",
    "unknown_icon",
}
SOURCE_TO_ROLE = {
    "bottom_nav_region_icon": "nav_icon",
    "shortcut_tile_icon": "tile_icon",
    "shortcut_leading_icon": "leading_icon",
    "metric_card_icon": "metric_icon",
    "primary_button_leading_icon": "button_leading_icon",
    "primary_button_trailing_icon": "button_trailing_icon",
    "row_trailing_arrow": "trailing_icon",
    "row_trailing_check": "trailing_icon",
    "card_trailing_icon": "trailing_icon",
    "room_card_status_icon": "status_icon",
    "bed_status_icon": "status_icon",
    "tip_leading_icon": "tip_leading_icon",
    "info_leading_icon": "info_leading_icon",
    "unknown_business_icon": "unknown_icon",
}
SOURCE_PRIORITY = {
    "bottom_nav_region_icon": 0,
    "shortcut_tile_icon": 1,
    "metric_card_icon": 2,
    "primary_button_trailing_icon": 3,
    "primary_button_leading_icon": 4,
    "room_card_status_icon": 5,
    "row_trailing_arrow": 6,
    "row_trailing_check": 6,
    "card_trailing_icon": 7,
    "tip_leading_icon": 8,
    "info_leading_icon": 8,
    "unknown_business_icon": 99,
}

OVERLAY_COLORS = {
    "candidate": (0, 200, 90),
    "blocked": (255, 205, 0),
    "failed": (235, 64, 52),
    "edge_retry": (0, 122, 255),
    "tile": (150, 80, 220),
    "duplicate": (128, 128, 128),
}


@dataclass
class IconBusinessWarning:
    code: str
    message: str
    probeId: str | None = None
    iconId: str | None = None


@dataclass
class IconBusinessItem:
    id: str
    source: str
    probeId: str
    status: IconBusinessStatus
    bbox: list[int]
    confidence: float
    componentId: str | None
    componentRole: str | None
    placementRole: str
    assetId: str | None
    assetPath: str | None
    assetUrl: str | None
    relatedTextElementIds: list[str]
    relatedBindingIds: list[str]
    quality: dict[str, Any]


@dataclass
class BlockedBusinessCandidate:
    id: str
    source: str
    probeId: str
    status: Literal["blocked", "skipped"]
    bbox: list[int]
    confidence: float
    reasons: list[str]


@dataclass
class IconBusinessOverlay:
    assetId: str
    assetPath: str
    assetUrl: str


@dataclass
class IconBusinessCandidateDocument:
    version: str
    taskId: str
    status: IconBusinessDocumentStatus
    imageSize: dict[str, int]
    businessIcons: list[IconBusinessItem]
    blockedCandidates: list[BlockedBusinessCandidate]
    businessOverlay: IconBusinessOverlay | None
    warnings: list[IconBusinessWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IconBusinessStorageAdapter:
    assets_root: Path
    public_base_url: str

    def icon_path(self, task_id: str, filename: str) -> Path:
        return self.assets_root / task_id / "icons_business" / filename

    def icon_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/icons_business/{filename}"

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
class BusinessProbe:
    id: str
    source: str
    search_bbox: list[int]
    component_role: str | None
    geometry_reason: str
    expected_color: str = "any"
    prefer_tile: bool = False


@dataclass(frozen=True)
class BusinessPick:
    bbox: list[int]
    contrast: int
    blob_count: int
    reasons: list[str]


def build_icon_business_candidate_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    icon_placement_document: IconPlacementPlanDocument | None,
    dsl: dict[str, Any],
    settings: Settings,
    storage: IconBusinessStorageAdapter,
) -> IconBusinessCandidateDocument:
    if not settings.icon_business_candidate_enabled:
        return build_skipped_icon_business_document(
            task_id=task_id,
            image=image,
            code="icon_business_candidate_disabled",
            message="Icon business candidate extraction is disabled.",
        )

    warnings: list[IconBusinessWarning] = []
    try:
        pixels = decode_png_pixels(png_data)
    except UnsupportedPngCropError as error:
        return build_skipped_icon_business_document(
            task_id=task_id,
            image=image,
            code="png_pixel_decode_unsupported",
            message=str(error),
        )

    elements = index_dsl_elements(dsl)
    text_bboxes = unique_bboxes(
        bboxes_by_role(elements, {"visible_text_replacement"})
        + bboxes_by_role(elements, {"candidate_text"})
    )
    cover_bboxes = bboxes_by_role(elements, {"text_replacement_cover"})
    existing_icon_bboxes = collect_existing_icon_bboxes(
        icon_candidate_document=icon_candidate_document,
        icon_gap_document=icon_gap_document,
        icon_placement_document=icon_placement_document,
        elements=elements,
    )
    exclusion_bboxes = exclusion_zones(image)
    probes = build_business_probes(image=image, pixels=pixels, settings=settings)

    business_icons: list[IconBusinessItem] = []
    blocked: list[BlockedBusinessCandidate] = []
    seen_bboxes: list[list[int]] = []
    for probe in probes:
        if len([icon for icon in business_icons if icon.status == "candidate"]) >= settings.icon_business_candidate_max_candidates:
            warnings.append(IconBusinessWarning(code="business_candidate_limit_reached", message="Icon business candidate limit reached."))
            break
        result = build_business_icon_for_probe(
            task_id=task_id,
            image=image,
            png_data=png_data,
            pixels=pixels,
            probe=probe,
            text_bboxes=text_bboxes,
            cover_bboxes=cover_bboxes,
            existing_icon_bboxes=existing_icon_bboxes,
            exclusion_bboxes=exclusion_bboxes,
            seen_bboxes=seen_bboxes,
            settings=settings,
            storage=storage,
            icon_index=len(business_icons) + 1,
            blocked_index=len(blocked) + 1,
        )
        if isinstance(result, IconBusinessItem):
            business_icons.append(result)
            if result.status == "candidate":
                seen_bboxes.append(result.bbox)
        elif result is not None:
            blocked.append(result)

    overlay: IconBusinessOverlay | None = None
    if settings.icon_business_candidate_overlay_enabled:
        overlay, overlay_warning = build_business_overlay(
            task_id=task_id,
            pixels=pixels,
            business_icons=business_icons,
            blocked_candidates=blocked,
            storage=storage,
        )
        if overlay_warning is not None:
            warnings.append(overlay_warning)

    document = IconBusinessCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        businessIcons=business_icons,
        blockedCandidates=blocked,
        businessOverlay=overlay,
        warnings=warnings,
        meta=build_meta(business_icons, blocked),
    )
    validation_errors = validate_icon_business_candidate_document(
        document=document,
        dsl=dsl,
        image=image,
        icon_candidate_document=icon_candidate_document,
        icon_gap_document=icon_gap_document,
        icon_placement_document=icon_placement_document,
    )
    if validation_errors:
        return build_failed_icon_business_document(
            task_id=task_id,
            image=image,
            code="ICON_BUSINESS_CANDIDATE_VALIDATION_FAILED",
            message="Icon business candidate validation failed.",
            warnings=[IconBusinessWarning(code="ICON_BUSINESS_CANDIDATE_VALIDATION_ERROR", message=error) for error in validation_errors],
        )
    return document


def build_business_probes(*, image: PngMetadata, pixels: PngPixels, settings: Settings) -> list[BusinessProbe]:
    probes: list[BusinessProbe] = []
    index = 1
    for probe in bottom_nav_probes(image, settings, index):
        probes.append(probe)
        index += 1
    for probe in primary_button_probes(image, pixels, settings, index):
        probes.append(probe)
        index += 1
    for probe in shortcut_tile_probes(image, pixels, settings, index):
        probes.append(probe)
        index += 1
    for probe in metric_card_probes(image, pixels, settings, index):
        probes.append(probe)
        index += 1
    for probe in room_card_probes(image, pixels, settings, index):
        probes.append(probe)
        index += 1
    for probe in row_trailing_probes(image, pixels, settings, index):
        probes.append(probe)
        index += 1
    for probe in tip_info_probes(image, pixels, settings, index):
        probes.append(probe)
        index += 1
    return dedupe_probes(probes)


def bottom_nav_probes(image: PngMetadata, settings: Settings, start_index: int) -> list[BusinessProbe]:
    if not settings.icon_business_bottom_nav_enabled:
        return []
    y = round(image.height * 0.88)
    height = max(1, round(image.height * 0.09))
    count = 4 if image.width >= 1200 else 3
    probes: list[BusinessProbe] = []
    for item in range(count):
        item_x = round(image.width * item / count)
        item_w = round(image.width / count)
        search = normalize_bbox([item_x + round(item_w * 0.22), y, round(item_w * 0.56), round(height * 0.62)], image)
        if search is not None:
            probes.append(
                BusinessProbe(
                    id=f"business_probe_bottom_nav_{start_index + len(probes):03d}",
                    source="bottom_nav_region_icon",
                    search_bbox=search,
                    component_role="bottom_nav_item",
                    geometry_reason="bottom_nav_zone",
                    expected_color="blue_gray",
                )
            )
    return probes


def primary_button_probes(image: PngMetadata, pixels: PngPixels, settings: Settings, start_index: int) -> list[BusinessProbe]:
    if not settings.icon_business_primary_button_enabled:
        return []
    button_bboxes = find_blue_button_bboxes(image, pixels)
    probes: list[BusinessProbe] = []
    for button in button_bboxes[:4]:
        right = normalize_bbox(
            [button[0] + round(button[2] * 0.80), button[1] + round(button[3] * 0.18), round(button[2] * 0.20), round(button[3] * 0.64)],
            image,
        )
        if right is not None:
            probes.append(
                BusinessProbe(
                    id=f"business_probe_primary_button_{start_index + len(probes):03d}",
                    source="primary_button_trailing_icon",
                    search_bbox=right,
                    component_role="primary_button",
                    geometry_reason="primary_button_zone",
                    expected_color="white",
                )
            )
    return probes


def shortcut_tile_probes(image: PngMetadata, pixels: PngPixels, settings: Settings, start_index: int) -> list[BusinessProbe]:
    if not settings.icon_business_shortcut_card_enabled:
        return []
    # Homepage shortcut cards live in the middle content band. This is intentionally geometric:
    # it must work even when OCR and component structure are weak.
    y1 = round(image.height * 0.46)
    y2 = round(image.height * 0.63)
    probes: list[BusinessProbe] = []
    for row in range(2):
        for col in range(2):
            x = round(image.width * (0.07 + col * 0.45))
            y = y1 + row * round((y2 - y1) / 2)
            search = normalize_bbox([x, y, round(image.width * 0.14), round((y2 - y1) * 0.45)], image)
            if search is not None:
                probes.append(
                    BusinessProbe(
                        id=f"business_probe_shortcut_{start_index + len(probes):03d}",
                        source="shortcut_tile_icon",
                        search_bbox=search,
                        component_role="shortcut_card",
                        geometry_reason="shortcut_card_zone",
                        expected_color="blue",
                        prefer_tile=True,
                    )
                )
    return probes


def metric_card_probes(image: PngMetadata, pixels: PngPixels, settings: Settings, start_index: int) -> list[BusinessProbe]:
    if not settings.icon_business_metric_card_enabled:
        return []
    probes: list[BusinessProbe] = []
    y = round(image.height * 0.33)
    height = round(image.height * 0.08)
    for col in range(3):
        x = round(image.width * (0.06 + col * 0.31))
        search = normalize_bbox([x, y, round(image.width * 0.14), height], image)
        if search is not None:
            probes.append(
                BusinessProbe(
                    id=f"business_probe_metric_{start_index + len(probes):03d}",
                    source="metric_card_icon",
                    search_bbox=search,
                    component_role="metric_card",
                    geometry_reason="metric_card_zone",
                    expected_color="blue_green_orange",
                )
            )
    return probes


def room_card_probes(image: PngMetadata, pixels: PngPixels, settings: Settings, start_index: int) -> list[BusinessProbe]:
    if not settings.icon_business_room_card_enabled:
        return []
    probes: list[BusinessProbe] = []
    start_y = round(image.height * 0.40)
    card_h = round(image.height * 0.13)
    for row in range(3):
        for col in range(2):
            x = round(image.width * (0.08 + col * 0.47))
            y = start_y + row * round(card_h * 1.08)
            search = normalize_bbox([x, y + round(card_h * 0.33), round(image.width * 0.12), round(card_h * 0.34)], image)
            if search is not None:
                probes.append(
                    BusinessProbe(
                        id=f"business_probe_room_card_{start_index + len(probes):03d}",
                        source="room_card_status_icon",
                        search_bbox=search,
                        component_role="room_card",
                        geometry_reason="room_card_zone",
                        expected_color="blue_gray_green",
                    )
                )
    return probes


def row_trailing_probes(image: PngMetadata, pixels: PngPixels, settings: Settings, start_index: int) -> list[BusinessProbe]:
    if not settings.icon_business_trailing_enabled:
        return []
    probes: list[BusinessProbe] = []
    for y_ratio in [0.51, 0.57, 0.64, 0.70, 0.76]:
        search = normalize_bbox([round(image.width * 0.84), round(image.height * y_ratio), round(image.width * 0.10), 42], image)
        if search is not None:
            probes.append(
                BusinessProbe(
                    id=f"business_probe_trailing_{start_index + len(probes):03d}",
                    source="row_trailing_arrow",
                    search_bbox=search,
                    component_role="row_item",
                    geometry_reason="row_trailing_zone",
                    expected_color="blue_green",
                )
            )
    return probes


def tip_info_probes(image: PngMetadata, pixels: PngPixels, settings: Settings, start_index: int) -> list[BusinessProbe]:
    if not settings.icon_business_tip_info_enabled:
        return []
    probes: list[BusinessProbe] = []
    for y_ratio in [0.76, 0.80]:
        search = normalize_bbox([round(image.width * 0.07), round(image.height * y_ratio), round(image.width * 0.09), 54], image)
        if search is not None:
            probes.append(
                BusinessProbe(
                    id=f"business_probe_info_{start_index + len(probes):03d}",
                    source="info_leading_icon",
                    search_bbox=search,
                    component_role="info_tip",
                    geometry_reason="tip_info_zone",
                    expected_color="blue_orange",
                )
            )
    return probes


def build_business_icon_for_probe(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    pixels: PngPixels,
    probe: BusinessProbe,
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    existing_icon_bboxes: list[list[int]],
    exclusion_bboxes: list[list[int]],
    seen_bboxes: list[list[int]],
    settings: Settings,
    storage: IconBusinessStorageAdapter,
    icon_index: int,
    blocked_index: int,
) -> IconBusinessItem | BlockedBusinessCandidate | None:
    if probe.source not in BUSINESS_SOURCES:
        return blocked_candidate(blocked_index, probe, "business_source_unsupported")
    pick = pick_business_bbox(
        pixels=pixels,
        image=image,
        probe=probe,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        existing_icon_bboxes=existing_icon_bboxes,
        exclusion_bboxes=exclusion_bboxes,
        seen_bboxes=seen_bboxes,
        settings=settings,
    )
    if pick is None:
        return None
    if "edge_clipped_unresolved" in pick.reasons:
        return blocked_candidate(blocked_index, probe, "edge_clipped_unresolved", pick.bbox)
    if not bbox_in_bounds(pick.bbox, image):
        return blocked_candidate(blocked_index, probe, "business_bbox_out_of_bounds", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.50 for bbox in existing_icon_bboxes):
        return blocked_candidate(blocked_index, probe, "business_bbox_duplicate_existing_icon", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.70 for bbox in seen_bboxes):
        return blocked_candidate(blocked_index, probe, "business_bbox_duplicate_existing_icon", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.10 for bbox in text_bboxes):
        return blocked_candidate(blocked_index, probe, "business_bbox_overlaps_text", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.10 for bbox in cover_bboxes):
        return blocked_candidate(blocked_index, probe, "business_bbox_overlaps_cover", pick.bbox)
    if any(iou(pick.bbox, bbox) > 0.20 for bbox in exclusion_bboxes):
        return blocked_candidate(blocked_index, probe, "business_bbox_inside_exclusion_zone", pick.bbox)
    if in_status_bar(pick.bbox, image):
        return blocked_candidate(blocked_index, probe, "business_bbox_status_bar", pick.bbox)
    if not size_like(pick.bbox, settings):
        reason = "business_bbox_too_large" if max(pick.bbox[2], pick.bbox[3]) > settings.icon_business_candidate_max_size else "business_bbox_too_small"
        return blocked_candidate(blocked_index, probe, reason, pick.bbox)
    if is_line_like(pick.bbox):
        return blocked_candidate(blocked_index, probe, "business_bbox_line_like", pick.bbox)
    if is_text_like(pick.bbox):
        return blocked_candidate(blocked_index, probe, "business_bbox_text_like", pick.bbox)

    confidence = score_business_candidate(probe, pick, settings)
    if confidence < settings.icon_business_candidate_min_confidence:
        return blocked_candidate(blocked_index, probe, "candidate_confidence_low", pick.bbox, confidence)
    icon_id = f"icon_business_{icon_index:03d}"
    filename = f"{icon_id}.png"
    try:
        cropped = crop_png(png_data, PngRegion(icon_id, pick.bbox[0], pick.bbox[1], pick.bbox[2], pick.bbox[3]))
        path = storage.write_icon(task_id, filename, cropped)
    except UnsupportedPngCropError:
        return failed_business_icon(icon_index, probe, pick.bbox, "png_crop_unsupported", confidence)
    except OSError:
        return failed_business_icon(icon_index, probe, pick.bbox, "asset_write_failed", confidence)

    reasons = unique_preserve_order(
        pick.reasons
        + [
            "region_guided_probe",
            probe.geometry_reason,
            "not_status_bar",
            "not_overlapping_text",
            "not_overlapping_cover",
            "not_overlapping_candidate_text",
            "not_duplicate_m20_icon",
            "not_duplicate_m22_icon",
            "not_duplicate_m24_visible_icon",
            "crop_bbox_valid",
        ]
    )
    return IconBusinessItem(
        id=icon_id,
        source=probe.source,
        probeId=probe.id,
        status="candidate",
        bbox=pick.bbox,
        confidence=confidence,
        componentId=None,
        componentRole=probe.component_role,
        placementRole=SOURCE_TO_ROLE[probe.source],
        assetId=f"asset_{icon_id}",
        assetPath=str(path),
        assetUrl=storage.icon_url(task_id, filename),
        relatedTextElementIds=[],
        relatedBindingIds=[],
        quality={"risk": "low" if confidence >= 0.82 else "medium", "reasons": reasons},
    )


def pick_business_bbox(
    *,
    pixels: PngPixels,
    image: PngMetadata,
    probe: BusinessProbe,
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    existing_icon_bboxes: list[list[int]],
    exclusion_bboxes: list[list[int]],
    seen_bboxes: list[list[int]],
    settings: Settings,
) -> BusinessPick | None:
    pick = raw_pick_business_bbox(
        pixels=pixels,
        image=image,
        probe=probe,
        search_bbox=probe.search_bbox,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        existing_icon_bboxes=existing_icon_bboxes,
        exclusion_bboxes=exclusion_bboxes,
        seen_bboxes=seen_bboxes,
        settings=settings,
    )
    if pick is None:
        return None
    if not touches_search_edge(pick.bbox, probe.search_bbox, settings.icon_business_candidate_edge_clip_tolerance):
        return pick
    expanded = padded_bbox(probe.search_bbox, settings.icon_business_candidate_retry_padding, image)
    retry = raw_pick_business_bbox(
        pixels=pixels,
        image=image,
        probe=probe,
        search_bbox=expanded,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        existing_icon_bboxes=existing_icon_bboxes,
        exclusion_bboxes=exclusion_bboxes,
        seen_bboxes=seen_bboxes,
        settings=settings,
    )
    if retry is None or touches_search_edge(retry.bbox, expanded, settings.icon_business_candidate_edge_clip_tolerance):
        return BusinessPick(pick.bbox, pick.contrast, pick.blob_count, unique_preserve_order(pick.reasons + ["edge_clipped_unresolved"]))
    return BusinessPick(retry.bbox, retry.contrast, retry.blob_count, unique_preserve_order(retry.reasons + ["edge_clipped_retry_applied"]))


def raw_pick_business_bbox(
    *,
    pixels: PngPixels,
    image: PngMetadata,
    probe: BusinessProbe,
    search_bbox: list[int],
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    existing_icon_bboxes: list[list[int]],
    exclusion_bboxes: list[list[int]],
    seen_bboxes: list[list[int]],
    settings: Settings,
) -> BusinessPick | None:
    if probe.expected_color == "white":
        raw_blobs = find_color_blobs(pixels, search_bbox, "white")
        blobs = raw_blobs
    else:
        background = estimate_background(pixels, search_bbox)
        raw_blobs = find_foreground_blobs(pixels, search_bbox, background, settings.icon_business_candidate_foreground_distance)
        blobs = merge_gap_blobs(raw_blobs, distance=14)
    if probe.prefer_tile:
        tile = tile_bbox_from_window(pixels, search_bbox, image)
        if tile is not None and not any(iou(tile, bbox) > 0.10 for bbox in text_bboxes + cover_bboxes):
            return BusinessPick(tile, settings.icon_business_candidate_foreground_distance, 1, ["foreground_contrast_ok"])
    candidates: list[tuple[ForegroundBlob, list[int], list[str]]] = []
    for blob in blobs:
        bbox = padded_bbox(blob.bbox, 4, image)
        reasons: list[str] = []
        if len(raw_blobs) > len(blobs):
            reasons.append("multi_blob_union_applied")
        if not size_like(bbox, settings):
            continue
        if is_line_like(bbox) or is_text_like(bbox):
            continue
        if not color_matches(pixels, blob.bbox, probe.expected_color):
            continue
        reasons.append("foreground_contrast_ok" if blob.contrast >= settings.icon_business_candidate_foreground_distance else "foreground_contrast_low")
        candidates.append((blob, bbox, reasons))
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            score_business_bbox(probe, item[1], item[0].contrast, len(blobs), settings),
            item[0].area,
        ),
        reverse=True,
    )
    blob, bbox, reasons = candidates[0]
    return BusinessPick(bbox=bbox, contrast=blob.contrast, blob_count=len(blobs), reasons=reasons)


def find_color_blobs(pixels: PngPixels, search_bbox: list[int], expected: str) -> list[ForegroundBlob]:
    x, y, width, height = search_bbox
    if width * height > 22000:
        return []
    foreground: set[tuple[int, int]] = set()
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for column in range(x, x + width):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            if color_pixel_matches(rgb, expected):
                foreground.add((column, row_index))
    blobs: list[ForegroundBlob] = []
    while foreground:
        start = foreground.pop()
        stack = [start]
        points = [start]
        while stack:
            cx, cy = stack.pop()
            for neighbor in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if neighbor in foreground:
                    foreground.remove(neighbor)
                    stack.append(neighbor)
                    points.append(neighbor)
        if len(points) < 6:
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        bbox = [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1]
        blobs.append(ForegroundBlob(bbox=bbox, area=len(points), contrast=255))
    return blobs


def tile_bbox_from_window(pixels: PngPixels, search_bbox: list[int], image: PngMetadata) -> list[int] | None:
    x, y, width, height = search_bbox
    points: list[list[int]] = []
    for row_index in range(y, min(image.height, y + height)):
        row = pixels.rows[row_index]
        for column in range(x, min(image.width, x + width)):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            if rgb[2] > 215 and rgb[1] > 220 and rgb[0] > 190 and (rgb[2] - rgb[0] >= 12 or rgb[2] - rgb[1] >= 8):
                points.append([column, row_index, 1, 1])
    if len(points) < 20:
        return None
    bbox = union_bboxes(points)
    bbox = padded_bbox(bbox, 2, image)
    if bbox[2] < 24 or bbox[3] < 24 or bbox[2] > 90 or bbox[3] > 90:
        return None
    return bbox


def find_blue_button_bboxes(image: PngMetadata, pixels: PngPixels) -> list[list[int]]:
    row_hits: list[tuple[int, int, int]] = []
    y_start = round(image.height * 0.35)
    y_end = round(image.height * 0.94)
    for row_index in range(y_start, y_end):
        row = pixels.rows[row_index]
        hit_columns = []
        for column in range(0, image.width, 3):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            if is_button_blue(rgb):
                hit_columns.append(column)
        if len(hit_columns) > (image.width / 3) * 0.35:
            row_hits.append((row_index, min(hit_columns), max(hit_columns)))
    if not row_hits:
        return []
    groups: list[list[tuple[int, int, int]]] = []
    current: list[tuple[int, int, int]] = []
    previous_y = -999
    for hit in row_hits:
        if hit[0] - previous_y > 3 and current:
            groups.append(current)
            current = []
        current.append(hit)
        previous_y = hit[0]
    if current:
        groups.append(current)
    bboxes: list[list[int]] = []
    for group in groups:
        if len(group) < 12:
            continue
        y1 = group[0][0]
        y2 = group[-1][0]
        x1 = min(item[1] for item in group)
        x2 = max(item[2] for item in group)
        bbox = normalize_bbox([x1, y1, x2 - x1 + 1, y2 - y1 + 1], image)
        if bbox is not None and bbox[2] >= image.width * 0.55 and 36 <= bbox[3] <= 120:
            bboxes.append(bbox)
    return bboxes


def build_business_overlay(
    *,
    task_id: str,
    pixels: PngPixels,
    business_icons: list[IconBusinessItem],
    blocked_candidates: list[BlockedBusinessCandidate],
    storage: IconBusinessStorageAdapter,
) -> tuple[IconBusinessOverlay | None, IconBusinessWarning | None]:
    rows = [bytearray(row) for row in pixels.rows]
    for item in blocked_candidates:
        color = OVERLAY_COLORS["duplicate"] if "business_bbox_duplicate_existing_icon" in item.reasons else OVERLAY_COLORS["blocked"]
        draw_rect(rows, pixels.width, pixels.height, item.bbox, color, thickness=2)
    for icon in business_icons:
        if icon.status == "failed":
            color = OVERLAY_COLORS["failed"]
        elif "edge_clipped_retry_applied" in icon.quality.get("reasons", []):
            color = OVERLAY_COLORS["edge_retry"]
        elif icon.source == "shortcut_tile_icon":
            color = OVERLAY_COLORS["tile"]
        else:
            color = OVERLAY_COLORS["candidate"]
        draw_rect(rows, pixels.width, pixels.height, icon.bbox, color, thickness=2)
    try:
        data = encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])
        filename = "icon_business_overlay.png"
        path = storage.write_overlay(task_id, filename, data)
        return IconBusinessOverlay("asset_icon_business_overlay", str(path), storage.overlay_url(task_id, filename)), None
    except (OSError, UnsupportedPngCropError) as error:
        return None, IconBusinessWarning(code="icon_business_overlay_write_failed", message=str(error))


def apply_icon_business_metadata(dsl: dict[str, Any], document: IconBusinessCandidateDocument) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m25_icon_business_candidates" not in quality_flags:
        quality_flags.append("m25_icon_business_candidates")
    meta["qualityFlags"] = quality_flags
    meta["iconBusinessCandidateCount"] = int(document.meta.get("businessIconCount", 0))
    meta["iconBusinessCroppedAssetCount"] = int(document.meta.get("croppedBusinessIconCount", 0))
    meta["iconBusinessBlockedCount"] = int(document.meta.get("blockedCount", 0))
    meta["iconBusinessFailedCropCount"] = int(document.meta.get("failedCropCount", 0))
    return next_dsl


def validate_icon_business_candidate_document(
    *,
    document: IconBusinessCandidateDocument,
    dsl: dict[str, Any],
    image: PngMetadata,
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    icon_placement_document: IconPlacementPlanDocument | None,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    if len({item.id for item in document.businessIcons}) != len(document.businessIcons):
        errors.append("business icon ids must be unique")
    if len({item.id for item in document.blockedCandidates}) != len(document.blockedCandidates):
        errors.append("blocked candidate ids must be unique")
    elements = index_dsl_elements(dsl)
    text_bboxes = unique_bboxes(
        bboxes_by_role(elements, {"visible_text_replacement"})
        + bboxes_by_role(elements, {"candidate_text"})
        + bboxes_by_role(elements, {"text_replacement_cover"})
    )
    existing = collect_existing_icon_bboxes(
        icon_candidate_document=icon_candidate_document,
        icon_gap_document=icon_gap_document,
        icon_placement_document=icon_placement_document,
        elements=elements,
    )
    exclusions = exclusion_zones(image)
    for item in document.businessIcons:
        if item.source not in BUSINESS_SOURCES:
            errors.append(f"invalid business icon source: {item.id}")
        if item.status not in BUSINESS_STATUSES:
            errors.append(f"invalid business icon status: {item.id}")
        if item.placementRole not in PLACEMENT_ROLES:
            errors.append(f"invalid placementRole: {item.id}")
        if not bbox_in_bounds(item.bbox, image):
            errors.append(f"business icon bbox out of bounds: {item.id}")
        if item.status == "candidate" and (item.assetPath is None or not Path(item.assetPath).exists()):
            errors.append(f"business icon asset path must exist: {item.id}")
        if any(iou(item.bbox, bbox) > 0.50 for bbox in existing):
            errors.append(f"business icon duplicates existing icon: {item.id}")
        if any(iou(item.bbox, bbox) > 0.10 for bbox in text_bboxes):
            errors.append(f"business icon overlaps text or cover: {item.id}")
        if any(iou(item.bbox, bbox) > 0.20 for bbox in exclusions):
            errors.append(f"business icon inside exclusion zone: {item.id}")
    for item in document.blockedCandidates:
        if item.source not in BUSINESS_SOURCES:
            errors.append(f"invalid blocked source: {item.id}")
        if item.status not in BUSINESS_STATUSES:
            errors.append(f"invalid blocked status: {item.id}")
    if document.meta.get("businessIconCount") != len([item for item in document.businessIcons if item.status == "candidate"]):
        errors.append("meta businessIconCount must match candidates")
    if document.meta.get("croppedBusinessIconCount") != len([item for item in document.businessIcons if item.status == "candidate" and item.assetPath]):
        errors.append("meta croppedBusinessIconCount must match candidates with assets")
    if document.meta.get("blockedCount") != len(document.blockedCandidates):
        errors.append("meta blockedCount must match blocked candidates")
    if document.meta.get("failedCropCount") != len([item for item in document.businessIcons if item.status == "failed"]):
        errors.append("meta failedCropCount must match failed icons")
    if document.meta.get("sourceSummary") != summarize_sources(document.businessIcons):
        errors.append("meta sourceSummary must match business icons")
    if document.meta.get("blockedReasonSummary") != summarize_blocked_reasons(document.blockedCandidates):
        errors.append("meta blockedReasonSummary must match blocked candidates")
    if document.businessOverlay is not None:
        if document.businessOverlay.assetId != "asset_icon_business_overlay":
            errors.append("business overlay assetId is invalid")
        if not Path(document.businessOverlay.assetPath).exists():
            errors.append("business overlay asset path must exist")
    return errors


def business_icon_asset_records(document: IconBusinessCandidateDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for icon in document.businessIcons:
        if icon.status != "candidate" or not icon.assetId or not icon.assetPath or not icon.assetUrl:
            continue
        width, height = image_size(icon.assetPath, icon.bbox)
        records.append(
            {
                "asset_id": icon.assetId,
                "task_id": task_id,
                "role": "asset_icon_business_candidate",
                "path": icon.assetPath,
                "url": icon.assetUrl,
                "mime_type": "image/png",
                "width": width,
                "height": height,
                "created_at": created_at,
            }
        )
    return records


def business_overlay_asset_records(document: IconBusinessCandidateDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    if document.businessOverlay is None:
        return []
    width, height = image_size(document.businessOverlay.assetPath, [0, 0, document.imageSize["width"], document.imageSize["height"]])
    return [
        {
            "asset_id": document.businessOverlay.assetId,
            "task_id": task_id,
            "role": "asset_icon_business_overlay",
            "path": document.businessOverlay.assetPath,
            "url": document.businessOverlay.assetUrl,
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "created_at": created_at,
        }
    ]


def build_skipped_icon_business_document(*, task_id: str, image: PngMetadata, code: str, message: str) -> IconBusinessCandidateDocument:
    return IconBusinessCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        businessIcons=[],
        blockedCandidates=[],
        businessOverlay=None,
        warnings=[IconBusinessWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_icon_business_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[IconBusinessWarning] | None = None,
) -> IconBusinessCandidateDocument:
    return IconBusinessCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        businessIcons=[],
        blockedCandidates=[],
        businessOverlay=None,
        warnings=warnings or [IconBusinessWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def failed_business_icon(index: int, probe: BusinessProbe, bbox: list[int], reason: str, confidence: float) -> IconBusinessItem:
    return IconBusinessItem(
        id=f"icon_business_{index:03d}",
        source=probe.source,
        probeId=probe.id,
        status="failed",
        bbox=bbox,
        confidence=confidence,
        componentId=None,
        componentRole=probe.component_role,
        placementRole=SOURCE_TO_ROLE[probe.source],
        assetId=None,
        assetPath=None,
        assetUrl=None,
        relatedTextElementIds=[],
        relatedBindingIds=[],
        quality={"risk": "high", "reasons": [reason]},
    )


def blocked_candidate(index: int, probe: BusinessProbe, reason: str, bbox: list[int] | None = None, confidence: float = 0) -> BlockedBusinessCandidate:
    return BlockedBusinessCandidate(
        id=f"blocked_business_icon_{index:03d}",
        source=probe.source,
        probeId=probe.id,
        status="blocked",
        bbox=bbox or probe.search_bbox,
        confidence=round(confidence, 3),
        reasons=[reason],
    )


def build_meta(business_icons: list[IconBusinessItem], blocked: list[BlockedBusinessCandidate]) -> dict[str, Any]:
    return {
        "notes": "region_guided_business_icon_candidate_harness",
        "businessIconCount": sum(1 for icon in business_icons if icon.status == "candidate"),
        "croppedBusinessIconCount": sum(1 for icon in business_icons if icon.status == "candidate" and icon.assetPath),
        "blockedCount": len(blocked),
        "failedCropCount": sum(1 for icon in business_icons if icon.status == "failed"),
        "sourceSummary": summarize_sources(business_icons),
        "blockedReasonSummary": summarize_blocked_reasons(blocked),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "region_guided_business_icon_candidate_harness",
        "businessIconCount": 0,
        "croppedBusinessIconCount": 0,
        "blockedCount": 0,
        "failedCropCount": 0,
        "sourceSummary": {},
        "blockedReasonSummary": {},
    }


def summarize_sources(business_icons: list[IconBusinessItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for icon in business_icons:
        if icon.status != "candidate":
            continue
        summary[icon.source] = summary.get(icon.source, 0) + 1
    return summary


def summarize_blocked_reasons(blocked: list[BlockedBusinessCandidate]) -> dict[str, int]:
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
    elements: dict[str, dict[str, Any]],
) -> list[list[int]]:
    bboxes: list[list[int]] = []
    if icon_candidate_document is not None:
        bboxes.extend([icon.bbox for icon in icon_candidate_document.icons if icon.status == "candidate"])
    if icon_gap_document is not None:
        bboxes.extend([icon.bbox for icon in icon_gap_document.gapIcons if icon.status == "candidate"])
    if icon_placement_document is not None:
        bboxes.extend([item.bbox for item in icon_placement_document.placements if item.status == "planned"])
    bboxes.extend(bboxes_by_role(elements, {"visible_icon_fallback"}))
    return unique_bboxes(bboxes)


def exclusion_zones(image: PngMetadata) -> list[list[int]]:
    zones = [
        [0, 0, image.width, round(image.height * 0.055)],
        [round(image.width * 0.18), round(image.height * 0.04), round(image.width * 0.64), round(image.height * 0.06)],
        [0, round(image.height * 0.10), image.width, round(image.height * 0.18)],
    ]
    return [zone for zone in zones if zone[2] > 0 and zone[3] > 0]


def score_business_candidate(probe: BusinessProbe, pick: BusinessPick, settings: Settings) -> float:
    return score_business_bbox(probe, pick.bbox, pick.contrast, pick.blob_count, settings)


def score_business_bbox(probe: BusinessProbe, bbox: list[int], contrast: int, blob_count: int, settings: Settings) -> float:
    score = 0.60
    if contrast >= settings.icon_business_candidate_foreground_distance:
        score += 0.10
    if settings.icon_business_candidate_min_size <= bbox[2] <= settings.icon_business_candidate_max_size and settings.icon_business_candidate_min_size <= bbox[3] <= settings.icon_business_candidate_max_size:
        score += 0.08
    score += 0.08
    score += 0.05
    score += 0.05
    if blob_count > 5:
        score -= 0.15
    if is_line_like(bbox):
        score -= 0.25
    if probe.source == "shortcut_tile_icon":
        score += 0.04
    return round(max(0, min(0.99, score)), 3)


def size_like(bbox: list[int], settings: Settings) -> bool:
    return settings.icon_business_candidate_min_size <= bbox[2] <= settings.icon_business_candidate_max_size and settings.icon_business_candidate_min_size <= bbox[3] <= settings.icon_business_candidate_max_size


def is_line_like(bbox: list[int]) -> bool:
    shortest = max(1, min(bbox[2], bbox[3]))
    longest = max(bbox[2], bbox[3])
    return shortest < 8 or longest / shortest > 4.5


def is_text_like(bbox: list[int]) -> bool:
    return bbox[3] > 28 and bbox[2] < 12


def in_status_bar(bbox: list[int], image: PngMetadata) -> bool:
    return bbox[1] < round(image.height * 0.055)


def color_matches(pixels: PngPixels, bbox: list[int], expected: str) -> bool:
    if expected == "any":
        return True
    color = average_color(pixels, bbox)
    r, g, b = color
    if expected == "white":
        return r > 210 and g > 210 and b > 210
    if expected == "blue":
        return b > 150 and b >= r + 20
    if expected == "blue_gray":
        return b > 110 or max(r, g, b) - min(r, g, b) < 70
    if expected == "blue_green":
        return b > 120 or g > 120
    if expected == "blue_green_orange":
        return b > 120 or g > 120 or (r > 160 and g > 80)
    if expected == "blue_gray_green":
        return b > 100 or g > 100 or max(r, g, b) - min(r, g, b) < 80
    if expected == "blue_orange":
        return b > 130 or (r > 160 and g > 80)
    return True


def color_pixel_matches(rgb: tuple[int, int, int], expected: str) -> bool:
    r, g, b = rgb
    if expected == "white":
        return r > 210 and g > 210 and b > 210
    return True


def average_color(pixels: PngPixels, bbox: list[int]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    total = [0, 0, 0]
    count = 0
    step = max(1, min(width, height) // 12)
    for row_index in range(y, min(pixels.height, y + height), step):
        row = pixels.rows[row_index]
        for column in range(x, min(pixels.width, x + width), step):
            offset = column * 3
            total[0] += row[offset]
            total[1] += row[offset + 1]
            total[2] += row[offset + 2]
            count += 1
    if count == 0:
        return (0, 0, 0)
    return (round(total[0] / count), round(total[1] / count), round(total[2] / count))


def is_button_blue(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    return b > 160 and g > 90 and r < 90 and b - r > 90


def unique_bboxes(bboxes: list[list[int]]) -> list[list[int]]:
    unique: list[list[int]] = []
    for bbox in bboxes:
        if bbox is None or len(bbox) != 4:
            continue
        if not any(iou(bbox, existing) > 0.95 for existing in unique):
            unique.append(list(bbox))
    return unique


def dedupe_probes(probes: list[BusinessProbe]) -> list[BusinessProbe]:
    deduped: list[BusinessProbe] = []
    for probe in probes:
        if any(probe.source == item.source and iou(probe.search_bbox, item.search_bbox) > 0.90 for item in deduped):
            continue
        deduped.append(probe)
    return deduped


def image_size(path: str, fallback_bbox: list[int]) -> tuple[int, int]:
    metadata = read_png_metadata(Path(path).read_bytes())
    if metadata is None:
        return fallback_bbox[2], fallback_bbox[3]
    return metadata.width, metadata.height
