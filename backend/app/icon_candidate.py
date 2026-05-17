from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .asset_slice import AssetSliceCandidateDocument
from .component_annotation import ComponentAnnotationDocument, ComponentAnnotationItem, index_dsl_elements
from .component_structure import ComponentStructureDocument, ComponentStructureItem
from .config import Settings
from .layer_separation import LayerSeparationDocument
from .png_tools import (
    PngMetadata,
    PngPixels,
    PngRegion,
    UnsupportedPngCropError,
    crop_png,
    decode_png_pixels,
    read_png_metadata,
)
from .text_binding import TextPrimitiveBindingDocument


IconCandidateDocumentStatus = Literal["completed", "failed", "skipped"]
IconCandidateStatus = Literal["candidate", "blocked", "failed", "skipped"]

ICON_STATUSES = {"candidate", "blocked", "failed", "skipped"}
ICON_SOURCES = {
    "bottom_nav_label_above",
    "shortcut_card_leading_icon",
    "tip_title_leading_icon",
    "field_label_leading_icon",
    "component_local_visual_blob",
}
RISKS = {"low", "medium", "high"}


@dataclass
class IconCandidateWarning:
    code: str
    message: str
    componentId: str | None = None
    iconId: str | None = None


@dataclass
class IconCandidateItem:
    id: str
    componentId: str
    componentRole: str
    source: str
    status: IconCandidateStatus
    bbox: list[int]
    confidence: float
    assetId: str | None
    assetPath: str | None
    assetUrl: str | None
    relatedTextElementIds: list[str]
    relatedBindingIds: list[str]
    quality: dict[str, Any]


@dataclass
class IconCandidateDocument:
    version: str
    taskId: str
    status: IconCandidateDocumentStatus
    imageSize: dict[str, int]
    icons: list[IconCandidateItem]
    blockedComponentIds: list[str]
    warnings: list[IconCandidateWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IconCandidateStorageAdapter:
    assets_root: Path
    public_base_url: str

    def icon_path(self, task_id: str, filename: str) -> Path:
        return self.assets_root / task_id / "icons" / filename

    def icon_url(self, task_id: str, filename: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/icons/{filename}"

    def write_icon(self, task_id: str, filename: str, data: bytes) -> Path:
        path = self.icon_path(task_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


@dataclass(frozen=True)
class TextFact:
    element_id: str
    binding_id: str
    bbox: list[int]


@dataclass(frozen=True)
class CandidateProbe:
    source: str
    search_bbox: list[int]
    related_text_ids: list[str]
    related_binding_ids: list[str]
    geometry_reason: str


@dataclass(frozen=True)
class ForegroundBlob:
    bbox: list[int]
    area: int
    contrast: int


def build_icon_candidate_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    annotation_document: ComponentAnnotationDocument | None,
    layer_separation_document: LayerSeparationDocument | None,
    asset_slice_document: AssetSliceCandidateDocument | None,
    dsl: dict[str, Any],
    settings: Settings,
    storage: IconCandidateStorageAdapter,
) -> IconCandidateDocument:
    del layer_separation_document, asset_slice_document
    if not settings.icon_candidate_enabled:
        return build_skipped_icon_candidate_document(
            task_id=task_id,
            image=image,
            code="icon_candidate_disabled",
            message="Icon candidate extraction is disabled.",
        )
    if binding_document.status != "completed":
        return build_skipped_icon_candidate_document(
            task_id=task_id,
            image=image,
            code="text_binding_not_completed",
            message="Icon candidate extraction skipped because text binding did not complete.",
        )
    if structure_document.status != "completed":
        return build_skipped_icon_candidate_document(
            task_id=task_id,
            image=image,
            code="component_structure_not_completed",
            message="Icon candidate extraction skipped because component structure did not complete.",
        )
    if annotation_document is None or annotation_document.status != "completed":
        return build_skipped_icon_candidate_document(
            task_id=task_id,
            image=image,
            code="component_annotation_not_completed",
            message="Icon candidate extraction skipped because component annotation did not complete.",
        )

    elements = index_dsl_elements(dsl)
    annotations_by_component = group_annotations_by_component(annotation_document.annotations)
    binding_ids = {binding.id for binding in binding_document.bindings}
    pixels, pixel_warning = try_decode_pixels(png_data)
    warnings: list[IconCandidateWarning] = []
    if pixel_warning is not None:
        warnings.append(pixel_warning)

    icons: list[IconCandidateItem] = []
    blocked_ids: list[str] = []
    seen_bboxes: list[tuple[str, list[int]]] = []
    if pixels is not None:
        for component in structure_document.components:
            cropped_count = sum(1 for icon in icons if icon.status == "candidate")
            if cropped_count >= settings.icon_candidate_max_candidates:
                blocked_ids.append(component.id)
                warnings.append(
                    IconCandidateWarning(
                        code="icon_candidate_limit_reached",
                        message="Icon candidate limit reached.",
                        componentId=component.id,
                    )
                )
                break
            block_reason = component_block_reason(component, image, settings)
            if block_reason is not None:
                blocked_ids.append(component.id)
                warnings.append(
                    IconCandidateWarning(
                        code=block_reason,
                        message="Component is not eligible for icon candidate extraction.",
                        componentId=component.id,
                    )
                )
                continue
            component_annotations = annotations_by_component.get(component.id, [])
            items = build_icons_for_component(
                task_id=task_id,
                image=image,
                png_data=png_data,
                pixels=pixels,
                component=component,
                annotations=component_annotations,
                elements=elements,
                binding_ids=binding_ids,
                storage=storage,
                settings=settings,
                index=len(icons) + 1,
                remaining_candidates=settings.icon_candidate_max_candidates - cropped_count,
                seen_bboxes=seen_bboxes,
            )
            for item in items:
                icons.append(item)
                if item.status == "blocked":
                    blocked_ids.append(component.id)
                if item.status == "candidate":
                    seen_bboxes.append((component.id, item.bbox))

    document = IconCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        icons=icons,
        blockedComponentIds=sorted(set(blocked_ids)),
        warnings=warnings,
        meta=build_meta(icons),
    )
    validation_errors = validate_icon_candidate_document(
        document=document,
        binding_document=binding_document,
        structure_document=structure_document,
        dsl=dsl,
        image=image,
    )
    if validation_errors:
        return build_failed_icon_candidate_document(
            task_id=task_id,
            image=image,
            code="ICON_CANDIDATE_VALIDATION_FAILED",
            message="Icon candidate validation failed.",
            warnings=[IconCandidateWarning(code="ICON_CANDIDATE_VALIDATION_ERROR", message=error) for error in validation_errors],
        )
    return document


def build_icons_for_component(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    pixels: PngPixels,
    component: ComponentStructureItem,
    annotations: list[ComponentAnnotationItem],
    elements: dict[str, dict[str, Any]],
    binding_ids: set[str],
    storage: IconCandidateStorageAdapter,
    settings: Settings,
    index: int,
    remaining_candidates: int,
    seen_bboxes: list[tuple[str, list[int]]],
) -> list[IconCandidateItem]:
    text_facts = text_facts_for_component(annotations, elements, binding_ids)
    if not text_facts:
        return []
    cover_bboxes = cover_bboxes_for_component(annotations, elements)
    probes = probes_for_component(component, text_facts, image)
    items: list[IconCandidateItem] = []
    local_seen = list(seen_bboxes)
    for probe in probes:
        if sum(1 for item in items if item.status == "candidate") >= remaining_candidates:
            break
        blob = best_blob_for_probe(pixels, probe, [fact.bbox for fact in text_facts], cover_bboxes, image, settings)
        if blob is None:
            continue
        bbox = padded_bbox_within(blob.bbox, 3, image, component.bbox)
        if not final_bbox_is_valid_for_source(probe.source, bbox, settings):
            continue
        if duplicate_bbox(component.id, bbox, local_seen):
            continue
        confidence, reasons = score_candidate(component, probe, blob, bbox, [fact.bbox for fact in text_facts], cover_bboxes, image, settings)
        if confidence < settings.icon_candidate_min_confidence:
            continue
        icon_id = f"icon_candidate_{index + len(items):03d}"
        filename = f"{icon_id}.png"
        try:
            cropped = crop_png(png_data, PngRegion(icon_id, bbox[0], bbox[1], bbox[2], bbox[3]))
            path = storage.write_icon(task_id, filename, cropped)
        except UnsupportedPngCropError:
            items.append(failed_icon(index + len(items), component, probe, bbox, "png_crop_unsupported", text_facts))
            continue
        except OSError:
            items.append(failed_icon(index + len(items), component, probe, bbox, "asset_write_failed", text_facts))
            continue
        items.append(
            IconCandidateItem(
                id=icon_id,
                componentId=component.id,
                componentRole=component.role,
                source=probe.source,
                status="candidate",
                bbox=bbox,
                confidence=confidence,
                assetId=f"asset_{icon_id}",
                assetPath=str(path),
                assetUrl=storage.icon_url(task_id, filename),
                relatedTextElementIds=probe.related_text_ids,
                relatedBindingIds=probe.related_binding_ids,
                quality={"risk": "low", "reasons": reasons},
            )
        )
        local_seen.append((component.id, bbox))
    return items


def component_block_reason(component: ComponentStructureItem, image: PngMetadata, settings: Settings) -> str | None:
    if component.confidence < settings.icon_candidate_min_confidence:
        return "component_confidence_low"
    if not bbox_in_bounds(component.bbox, image):
        return "crop_bbox_out_of_bounds"
    if component.bbox[2] * component.bbox[3] < settings.icon_candidate_min_size * settings.icon_candidate_min_size:
        return "crop_bbox_too_small"
    if component.bbox[2] * component.bbox[3] / max(1, image.width * image.height) > settings.icon_candidate_max_component_area_ratio:
        return "crop_bbox_too_large"
    return None


def text_facts_for_component(
    annotations: list[ComponentAnnotationItem],
    elements: dict[str, dict[str, Any]],
    binding_ids: set[str],
) -> list[TextFact]:
    facts: list[TextFact] = []
    for annotation in annotations:
        if annotation.elementRole != "visible_text_replacement" or annotation.bindingId not in binding_ids:
            continue
        element = elements.get(annotation.dslElementId)
        bbox = bbox_from_element(element)
        if bbox is None:
            continue
        facts.append(TextFact(annotation.dslElementId, annotation.bindingId, bbox))
    return sorted(facts, key=lambda fact: (fact.bbox[1], fact.bbox[0]))


def cover_bboxes_for_component(
    annotations: list[ComponentAnnotationItem],
    elements: dict[str, dict[str, Any]],
) -> list[list[int]]:
    bboxes: list[list[int]] = []
    for annotation in annotations:
        if annotation.elementRole != "text_replacement_cover":
            continue
        bbox = bbox_from_element(elements.get(annotation.dslElementId))
        if bbox is not None:
            bboxes.append(bbox)
    return bboxes


def probes_for_component(component: ComponentStructureItem, text_facts: list[TextFact], image: PngMetadata) -> list[CandidateProbe]:
    if component.role == "bottom_nav_item":
        return bottom_nav_probes(component, text_facts, image)
    if component.role == "shortcut_card":
        return leading_icon_probes(component, text_facts, "shortcut_card_leading_icon", "left_of_text_cluster", image)
    if component.role == "tip_card":
        return leading_icon_probes(component, text_facts[:1], "tip_title_leading_icon", "left_of_title", image)
    if component.role in {"legend_group", "summary_stat_card", "activity_card", "page_header", "badge", "status_badge"}:
        return []
    return field_label_probes(component, text_facts, image)


def bottom_nav_probes(component: ComponentStructureItem, text_facts: list[TextFact], image: PngMetadata) -> list[CandidateProbe]:
    if component.role != "bottom_nav_item" or not text_facts:
        return []
    label = max(text_facts, key=lambda fact: fact.bbox[1])
    x, y, width, _height = component.bbox
    search = normalize_bbox([x, y, width, label.bbox[1] - y], image)
    if search is None:
        return []
    return [
        CandidateProbe(
            source="bottom_nav_label_above",
            search_bbox=search,
            related_text_ids=[label.element_id],
            related_binding_ids=[label.binding_id],
            geometry_reason="above_text_label",
        )
    ]


def leading_icon_probes(
    component: ComponentStructureItem,
    text_facts: list[TextFact],
    source: str,
    geometry_reason: str,
    image: PngMetadata,
) -> list[CandidateProbe]:
    if not text_facts:
        return []
    cluster = union_bboxes([fact.bbox for fact in text_facts])
    x, y, width, height = component.bbox
    max_search_width = 140 if source == "tip_title_leading_icon" else width
    search_left = max(x, cluster[0] - max_search_width)
    search_right = max(search_left, cluster[0] - 4)
    vertical_pad = max(12, round(cluster[3] * 0.55))
    search = normalize_bbox(
        [
            search_left,
            max(y, cluster[1] - vertical_pad),
            search_right - search_left,
            min(y + height, cluster[1] + cluster[3] + vertical_pad) - max(y, cluster[1] - vertical_pad),
        ],
        image,
    )
    if search is None:
        return []
    return [
        CandidateProbe(
            source=source,
            search_bbox=search,
            related_text_ids=[fact.element_id for fact in text_facts],
            related_binding_ids=[fact.binding_id for fact in text_facts],
            geometry_reason=geometry_reason,
        )
    ]


def field_label_probes(component: ComponentStructureItem, text_facts: list[TextFact], image: PngMetadata) -> list[CandidateProbe]:
    rows = paired_text_rows(text_facts)
    if len(rows) < 2:
        return []
    probes: list[CandidateProbe] = []
    x, y, width, height = component.bbox
    for row in rows:
        fact = min(row, key=lambda item: item.bbox[0])
        search_width = min(max(40, round(fact.bbox[3] * 2.4)), 96)
        search_left = max(x, fact.bbox[0] - search_width)
        search_right = max(search_left, fact.bbox[0] - 4)
        vertical_pad = max(8, round(fact.bbox[3] * 0.45))
        search = normalize_bbox(
            [
                search_left,
                max(y, fact.bbox[1] - vertical_pad),
                search_right - search_left,
                min(y + height, fact.bbox[1] + fact.bbox[3] + vertical_pad) - max(y, fact.bbox[1] - vertical_pad),
            ],
            image,
        )
        if search is None:
            continue
        probes.append(
            CandidateProbe(
                source="field_label_leading_icon",
                search_bbox=search,
                related_text_ids=[fact.element_id],
                related_binding_ids=[fact.binding_id],
                geometry_reason="field_leading_visual",
            )
        )
    return probes


def paired_text_rows(text_facts: list[TextFact]) -> list[list[TextFact]]:
    rows: list[list[TextFact]] = []
    for fact in sorted(text_facts, key=lambda item: (bbox_center_y(item.bbox), item.bbox[0])):
        for row in rows:
            row_center = average([bbox_center_y(item.bbox) for item in row])
            row_height = average([item.bbox[3] for item in row])
            if abs(bbox_center_y(fact.bbox) - row_center) <= max(10, row_height * 0.55):
                row.append(fact)
                break
        else:
            rows.append([fact])
    return [sorted(row, key=lambda item: item.bbox[0]) for row in rows if len(row) >= 2]


def best_blob_for_probe(
    pixels: PngPixels,
    probe: CandidateProbe,
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    image: PngMetadata,
    settings: Settings,
) -> ForegroundBlob | None:
    background = estimate_background(pixels, probe.search_bbox)
    blobs = merge_nearby_blobs(find_foreground_blobs(pixels, probe.search_bbox, background, settings.icon_candidate_foreground_distance))
    candidates = [
        blob
        for blob in blobs
        if blob_is_valid(blob, probe, text_bboxes, cover_bboxes, image, settings)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda blob: (blob.contrast, blob.area), reverse=True)
    return candidates[0]


def find_foreground_blobs(
    pixels: PngPixels,
    search_bbox: list[int],
    background: tuple[int, int, int],
    distance: int,
) -> list[ForegroundBlob]:
    x, y, width, height = search_bbox
    foreground: set[tuple[int, int]] = set()
    max_points = width * height
    if max_points > 22000:
        return []
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for column in range(x, x + width):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            if rgb_distance(rgb, background) >= distance:
                foreground.add((column, row_index))
    blobs: list[ForegroundBlob] = []
    while foreground:
        start = foreground.pop()
        stack = [start]
        points = [start]
        contrast = 0
        while stack:
            cx, cy = stack.pop()
            offset = cx * 3
            row = pixels.rows[cy]
            contrast = max(contrast, rgb_distance((row[offset], row[offset + 1], row[offset + 2]), background))
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
        blobs.append(ForegroundBlob(bbox=bbox, area=len(points), contrast=contrast))
    return blobs


def blob_is_valid(
    blob: ForegroundBlob,
    probe: CandidateProbe,
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    image: PngMetadata,
    settings: Settings,
) -> bool:
    bbox = padded_bbox(blob.bbox, 3, image)
    if not bbox_in_bounds(bbox, image):
        return False
    min_size = 16 if probe.source == "field_label_leading_icon" else settings.icon_candidate_min_size
    max_size = min(settings.icon_candidate_max_size, 56) if probe.source == "field_label_leading_icon" else settings.icon_candidate_max_size
    if bbox[2] < min_size or bbox[3] < min_size:
        return False
    if bbox[2] > max_size or bbox[3] > max_size:
        return False
    ratio = bbox[2] / max(1, bbox[3])
    if ratio < 0.25 or ratio > 4:
        return False
    if any(iou(bbox, text_bbox) > 0.10 for text_bbox in text_bboxes):
        return False
    if any(iou(bbox, cover_bbox) > 0.10 for cover_bbox in cover_bboxes):
        return False
    return True


def final_bbox_is_valid_for_source(source: str, bbox: list[int], settings: Settings) -> bool:
    if not icon_size_like(bbox, settings):
        return False
    if source not in {"field_label_leading_icon", "tip_title_leading_icon"}:
        return True
    if bbox[2] < 18 or bbox[3] < 18:
        return False
    ratio = bbox[2] / max(1, bbox[3])
    return 0.70 <= ratio <= 1.60


def merge_nearby_blobs(blobs: list[ForegroundBlob]) -> list[ForegroundBlob]:
    remaining = list(blobs)
    merged: list[ForegroundBlob] = []
    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed:
            changed = False
            next_remaining: list[ForegroundBlob] = []
            for other in remaining:
                if bboxes_near(current.bbox, other.bbox, 8):
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


def score_candidate(
    component: ComponentStructureItem,
    probe: CandidateProbe,
    blob: ForegroundBlob,
    bbox: list[int],
    text_bboxes: list[list[int]],
    cover_bboxes: list[list[int]],
    image: PngMetadata,
    settings: Settings,
) -> tuple[float, list[str]]:
    component_area = max(1, component.bbox[2] * component.bbox[3])
    score = 0.55
    reasons = ["inside_component_bbox"]
    if bbox_inside(bbox, component.bbox):
        score += 0.12
    if not any(iou(bbox, item) > 0.10 for item in text_bboxes) and not any(iou(bbox, item) > 0.10 for item in cover_bboxes):
        score += 0.10
        reasons.extend(["not_overlapping_text", "not_overlapping_cover"])
    score += 0.10
    reasons.append(probe.geometry_reason)
    if blob.contrast >= settings.icon_candidate_foreground_distance:
        score += 0.08
        reasons.append("foreground_contrast_ok")
    if icon_size_like(bbox, settings):
        score += 0.05
        reasons.append("small_visual_region")
    if bbox[2] * bbox[3] / component_area > settings.icon_candidate_max_component_area_ratio:
        score -= 0.30
        reasons.append("crop_bbox_too_large")
    if not bbox_in_bounds(bbox, image):
        score -= 0.50
        reasons.append("crop_bbox_out_of_bounds")
    reasons.append("crop_bbox_valid")
    return round(max(0, min(0.99, score)), 3), unique_preserve_order(reasons)


def apply_icon_candidate_metadata(dsl: dict[str, Any], document: IconCandidateDocument) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m20_icon_candidate_extraction" not in quality_flags:
        quality_flags.append("m20_icon_candidate_extraction")
    meta["qualityFlags"] = quality_flags
    meta["iconCandidateCount"] = int(document.meta.get("iconCount", 0))
    meta["iconCroppedAssetCount"] = int(document.meta.get("croppedIconCount", 0))
    meta["iconBlockedCount"] = int(document.meta.get("blockedCount", 0))
    meta["iconFailedCropCount"] = int(document.meta.get("failedCropCount", 0))
    return next_dsl


def validate_icon_candidate_document(
    *,
    document: IconCandidateDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    dsl: dict[str, Any],
    image: PngMetadata,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    ids = {icon.id for icon in document.icons}
    if len(ids) != len(document.icons):
        errors.append("icon ids must be unique")
    components = {component.id: component for component in structure_document.components}
    binding_ids = {binding.id for binding in binding_document.bindings}
    elements = index_dsl_elements(dsl)
    for icon in document.icons:
        component = components.get(icon.componentId)
        if component is None:
            errors.append(f"icon references missing component: {icon.id}")
        elif not bbox_inside(icon.bbox, component.bbox):
            errors.append(f"icon bbox must be inside component bbox: {icon.id}")
        if icon.status not in ICON_STATUSES:
            errors.append(f"invalid icon status: {icon.id}")
        if icon.source not in ICON_SOURCES:
            errors.append(f"invalid icon source: {icon.id}")
        if icon.quality.get("risk") not in RISKS:
            errors.append(f"invalid icon risk: {icon.id}")
        if not bbox_in_bounds(icon.bbox, image):
            errors.append(f"icon bbox is out of bounds: {icon.id}")
        for binding_id in icon.relatedBindingIds:
            if binding_id not in binding_ids:
                errors.append(f"icon references missing binding: {icon.id}")
        for element_id in icon.relatedTextElementIds:
            if element_id not in elements:
                errors.append(f"icon references missing DSL element: {icon.id}")
        if icon.status == "candidate":
            if not icon.assetId or not icon.assetPath or not icon.assetUrl:
                errors.append(f"candidate icon asset fields are required: {icon.id}")
            elif not Path(icon.assetPath).exists():
                errors.append(f"candidate icon asset path must exist: {icon.id}")
        elif icon.assetPath or icon.assetId or icon.assetUrl:
            errors.append(f"non-candidate icon must not have asset fields: {icon.id}")
    for component_id in document.blockedComponentIds:
        if component_id not in components:
            errors.append(f"blocked component id is missing: {component_id}")
    if document.meta.get("iconCount") != sum(1 for icon in document.icons if icon.status == "candidate"):
        errors.append("meta iconCount must match candidate icons")
    if document.meta.get("croppedIconCount") != sum(1 for icon in document.icons if icon.status == "candidate" and icon.assetPath):
        errors.append("meta croppedIconCount must match cropped icons")
    if document.meta.get("blockedCount") != sum(1 for icon in document.icons if icon.status == "blocked"):
        errors.append("meta blockedCount must match blocked icons")
    if document.meta.get("failedCropCount") != sum(1 for icon in document.icons if icon.status == "failed"):
        errors.append("meta failedCropCount must match failed icons")
    if document.meta.get("sourceSummary") != summarize_sources(document.icons):
        errors.append("meta sourceSummary must match icons")
    if document.meta.get("roleSummary") != summarize_roles(document.icons):
        errors.append("meta roleSummary must match icons")
    return errors


def icon_asset_records(document: IconCandidateDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for icon in document.icons:
        if icon.status != "candidate" or not icon.assetId or not icon.assetPath or not icon.assetUrl:
            continue
        width, height = image_size(icon.assetPath, icon.bbox)
        records.append(
            {
                "asset_id": icon.assetId,
                "task_id": task_id,
                "role": "asset_icon_candidate",
                "path": icon.assetPath,
                "url": icon.assetUrl,
                "mime_type": "image/png",
                "width": width,
                "height": height,
                "created_at": created_at,
            }
        )
    return records


def build_skipped_icon_candidate_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> IconCandidateDocument:
    return IconCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        icons=[],
        blockedComponentIds=[],
        warnings=[IconCandidateWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_icon_candidate_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[IconCandidateWarning] | None = None,
) -> IconCandidateDocument:
    return IconCandidateDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        icons=[],
        blockedComponentIds=[],
        warnings=warnings or [IconCandidateWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def failed_icon(
    index: int,
    component: ComponentStructureItem,
    probe: CandidateProbe,
    bbox: list[int],
    reason: str,
    text_facts: list[TextFact],
) -> IconCandidateItem:
    return IconCandidateItem(
        id=f"icon_candidate_{index:03d}",
        componentId=component.id,
        componentRole=component.role,
        source=probe.source,
        status="failed",
        bbox=bbox,
        confidence=0,
        assetId=None,
        assetPath=None,
        assetUrl=None,
        relatedTextElementIds=probe.related_text_ids,
        relatedBindingIds=probe.related_binding_ids or [fact.binding_id for fact in text_facts],
        quality={"risk": "high", "reasons": [reason]},
    )


def build_meta(icons: list[IconCandidateItem]) -> dict[str, Any]:
    return {
        "notes": "icon_candidate_extraction_harness",
        "iconCount": sum(1 for icon in icons if icon.status == "candidate"),
        "croppedIconCount": sum(1 for icon in icons if icon.status == "candidate" and icon.assetPath),
        "blockedCount": sum(1 for icon in icons if icon.status == "blocked"),
        "failedCropCount": sum(1 for icon in icons if icon.status == "failed"),
        "sourceSummary": summarize_sources(icons),
        "roleSummary": summarize_roles(icons),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "icon_candidate_extraction_harness",
        "iconCount": 0,
        "croppedIconCount": 0,
        "blockedCount": 0,
        "failedCropCount": 0,
        "sourceSummary": {},
        "roleSummary": {},
    }


def try_decode_pixels(png_data: bytes) -> tuple[PngPixels | None, IconCandidateWarning | None]:
    try:
        return decode_png_pixels(png_data), None
    except UnsupportedPngCropError as error:
        return None, IconCandidateWarning(code="png_pixel_decode_unsupported", message=str(error))


def group_annotations_by_component(
    annotations: list[ComponentAnnotationItem],
) -> dict[str, list[ComponentAnnotationItem]]:
    grouped: dict[str, list[ComponentAnnotationItem]] = {}
    for annotation in annotations:
        grouped.setdefault(annotation.componentId, []).append(annotation)
    return grouped


def bbox_from_element(element: dict[str, Any] | None) -> list[int] | None:
    if element is None:
        return None
    layout = element.get("layout")
    if not isinstance(layout, dict):
        return None
    return normalize_bbox([layout.get("x"), layout.get("y"), layout.get("width"), layout.get("height")])


def normalize_bbox(bbox: list[Any] | tuple[Any, ...] | None, image: PngMetadata | None = None) -> list[int] | None:
    if bbox is None or len(bbox) != 4:
        return None
    try:
        x, y, width, height = [round(float(value)) for value in bbox]
    except (TypeError, ValueError):
        return None
    if image is not None:
        x1 = max(0, min(image.width, x))
        y1 = max(0, min(image.height, y))
        x2 = max(0, min(image.width, x + width))
        y2 = max(0, min(image.height, y + height))
        if x2 <= x1 or y2 <= y1:
            return None
        return [x1, y1, x2 - x1, y2 - y1]
    if width <= 0 or height <= 0:
        return None
    return [x, y, width, height]


def estimate_background(pixels: PngPixels, bbox: list[int]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    samples: list[tuple[int, int, int]] = []
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for column in range(x, x + width):
            if row_index not in {y, y + height - 1} and column not in {x, x + width - 1}:
                continue
            offset = column * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    if not samples:
        return (255, 255, 255)
    return tuple(round(sum(sample[index] for sample in samples) / len(samples)) for index in range(3))  # type: ignore[return-value]


def padded_bbox(bbox: list[int], padding: int, image: PngMetadata) -> list[int]:
    x, y, width, height = bbox
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(image.width, x + width + padding)
    y2 = min(image.height, y + height + padding)
    return [x1, y1, max(1, x2 - x1), max(1, y2 - y1)]


def padded_bbox_within(bbox: list[int], padding: int, image: PngMetadata, outer: list[int]) -> list[int]:
    padded = padded_bbox(bbox, padding, image)
    x1 = max(padded[0], outer[0])
    y1 = max(padded[1], outer[1])
    x2 = min(padded[0] + padded[2], outer[0] + outer[2], image.width)
    y2 = min(padded[1] + padded[3], outer[1] + outer[3], image.height)
    return [x1, y1, max(1, x2 - x1), max(1, y2 - y1)]


def bbox_in_bounds(bbox: list[int], image: PngMetadata) -> bool:
    return len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0 and bbox[0] >= 0 and bbox[1] >= 0 and bbox[0] + bbox[2] <= image.width and bbox[1] + bbox[3] <= image.height


def bbox_inside(inner: list[int], outer: list[int]) -> bool:
    return inner[0] >= outer[0] and inner[1] >= outer[1] and inner[0] + inner[2] <= outer[0] + outer[2] and inner[1] + inner[3] <= outer[1] + outer[3]


def union_bboxes(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox[0] + bbox[2] for bbox in bboxes)
    y2 = max(bbox[1] + bbox[3] for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def bbox_center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2


def average(values: list[float] | list[int]) -> float:
    return sum(values) / len(values) if values else 0


def iou(left: list[int], right: list[int]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    if x2 <= x1 or y2 <= y1:
        return 0
    intersection = (x2 - x1) * (y2 - y1)
    union = left[2] * left[3] + right[2] * right[3] - intersection
    return intersection / max(1, union)


def icon_size_like(bbox: list[int], settings: Settings) -> bool:
    return settings.icon_candidate_min_size <= bbox[2] <= settings.icon_candidate_max_size and settings.icon_candidate_min_size <= bbox[3] <= settings.icon_candidate_max_size


def duplicate_bbox(component_id: str, bbox: list[int], seen: list[tuple[str, list[int]]]) -> bool:
    return any(component_id == seen_component and iou(bbox, seen_bbox) > 0.70 for seen_component, seen_bbox in seen)


def bboxes_near(left: list[int], right: list[int], distance: int) -> bool:
    expanded = [left[0] - distance, left[1] - distance, left[2] + distance * 2, left[3] + distance * 2]
    return iou(expanded, right) > 0 or bbox_intersects(expanded, right)


def bbox_intersects(left: list[int], right: list[int]) -> bool:
    return not (
        left[0] + left[2] <= right[0]
        or right[0] + right[2] <= left[0]
        or left[1] + left[3] <= right[1]
        or right[1] + right[3] <= left[1]
    )


def rgb_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return max(abs(left[index] - right[index]) for index in range(3))


def summarize_sources(icons: list[IconCandidateItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for icon in icons:
        if icon.status != "candidate":
            continue
        summary[icon.source] = summary.get(icon.source, 0) + 1
    return summary


def summarize_roles(icons: list[IconCandidateItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for icon in icons:
        if icon.status != "candidate":
            continue
        summary[icon.componentRole] = summary.get(icon.componentRole, 0) + 1
    return summary


def image_size(path: str, fallback_bbox: list[int]) -> tuple[int, int]:
    metadata = read_png_metadata(Path(path).read_bytes())
    if metadata is None:
        return fallback_bbox[2], fallback_bbox[3]
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
