from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Literal

from .png_tools import (
    PngPixels,
    PngRegion,
    UnsupportedPngCropError,
    crop_pixels_to_png,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
    upscale_pixels_nearest,
)
from .visual_primitive_graph import bbox_area, bbox_clamp, bbox_iou, bbox_x2, bbox_y2, draw_rect


M292Decision = Literal[
    "proposal_only",
    "covered_by_existing_ocr",
    "rejected_geometry",
    "rejected_texture_like",
    "reprobe_recognized",
    "reprobe_unrecognized",
    "reprobe_failed",
]
M292ReprobeFn = Callable[[bytes, list[int]], dict[str, Any]]
COUNTER_TEXT_RE = re.compile(r"^[0-9]{1,2}/[0-9]{1,2}$")


@dataclass(frozen=True)
class M292Options:
    enabled: bool = True
    reprobe_enabled: bool = False
    max_candidates: int = 12
    upscale_factor: int = 3
    crop_padding: int = 4
    min_width: int = 12
    max_width: int = 96
    min_height: int = 8
    max_height: int = 42
    min_area: int = 80
    max_area: int = 2600
    min_aspect_ratio: float = 0.8
    max_aspect_ratio: float = 8.0
    foreground_distance_threshold: int = 64
    min_ink_density: float = 0.04
    max_ink_density: float = 0.45
    min_component_count: int = 2
    max_component_count: int = 8
    max_ocr_iou: float = 0.10
    max_ocr_coverage: float = 0.35
    edge_distance_ratio: float = 0.12
    min_edge_distance: int = 24

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M292DebugArtifacts:
    overlay: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {key: value for key, value in {"overlay": self.overlay}.items() if value is not None}


@dataclass(frozen=True)
class M292Candidate:
    candidate_id: str
    candidate_kind: str
    bbox: list[int]
    source_image_evidence_id: str
    source_image_bbox: list[int]
    decision: M292Decision
    recognized_text: str | None
    recognition_source: str | None
    recognition_confidence: float | None
    materialization_eligible: bool
    overlaps_existing_ocr: bool
    matched_ocr_box_id: str | None
    asset_path: str | None
    upscaled_asset_path: str | None
    reasons: list[str]
    metrics: dict[str, Any]
    reprobe_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "candidateId": self.candidate_id,
            "candidateKind": self.candidate_kind,
            "bbox": self.bbox,
            "sourceImageEvidenceId": self.source_image_evidence_id,
            "sourceImageBBox": self.source_image_bbox,
            "decision": self.decision,
            "recognizedText": self.recognized_text,
            "recognitionSource": self.recognition_source,
            "recognitionConfidence": self.recognition_confidence,
            "materializationEligible": self.materialization_eligible,
            "overlapsExistingOcr": self.overlaps_existing_ocr,
            "matchedOcrBoxId": self.matched_ocr_box_id,
            "assetPath": self.asset_path,
            "upscaledAssetPath": self.upscaled_asset_path,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }
        if self.reprobe_error:
            data["reprobeError"] = self.reprobe_error
        return data


@dataclass(frozen=True)
class M292Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_ocr_json: str | None
    source_m29_nodes_json: str | None
    source_m2902_audit_json: str | None
    options: M292Options
    summary: dict[str, Any]
    candidates: list[M292Candidate]
    warnings: list[str]
    debug: M292DebugArtifacts = field(default_factory=M292DebugArtifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceOcrJson": self.source_ocr_json,
            "sourceM29NodesJson": self.source_m29_nodes_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "options": self.options.to_dict(),
            "summary": self.summary,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": self.warnings,
            "debug": self.debug.to_dict(),
        }


def extract_small_overlay_text_proposals(
    *,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    ocr_document: dict[str, Any],
    ocr_json_path: str | None,
    m29_document: dict[str, Any],
    m29_nodes_json_path: str | None,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str | None,
    options: M292Options | None = None,
    emit_debug_artifacts: bool = True,
    reprobe_fn: M292ReprobeFn | None = None,
) -> M292Document:
    options = options or M292Options()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_boxes = parse_ocr_boxes(ocr_document)
    images = accepted_images(m2902_document, m29_document)
    warnings: list[str] = []
    candidates: list[M292Candidate] = []

    for image in images:
        if len(candidates) >= options.max_candidates:
            warnings.append("M29.2 candidate limit reached; remaining accepted images were not scanned.")
            break
        proposals = propose_candidates_in_image(pixels, image, ocr_boxes, options)
        for proposal in proposals:
            if len(candidates) >= options.max_candidates:
                warnings.append("M29.2 candidate limit reached; remaining proposals were dropped.")
                break
            candidate = build_candidate(
                candidate_index=len(candidates) + 1,
                proposal=proposal,
                image=image,
                pixels=pixels,
                output_dir=output_dir,
                options=options,
                emit_debug_artifacts=emit_debug_artifacts,
            )
            if options.reprobe_enabled and candidate.decision == "proposal_only":
                candidate = run_reprobe(candidate, pixels, output_dir, options, reprobe_fn, emit_debug_artifacts)
            candidates.append(candidate)

    debug = M292DebugArtifacts()
    if emit_debug_artifacts:
        overlay_dir = output_dir / "overlays"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = overlay_dir / "small_overlay_text_candidates.png"
        overlay_path.write_bytes(overlay_candidates(pixels, candidates))
        debug = M292DebugArtifacts(overlay=str(overlay_path.relative_to(output_dir)))

    document = M292Document(
        schema_name="M292SmallOverlayTextProposalDocument",
        schema_version="0.1",
        source_image=source_image,
        source_ocr_json=ocr_json_path,
        source_m29_nodes_json=m29_nodes_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        options=options,
        summary=build_summary(images, candidates),
        candidates=candidates,
        warnings=warnings,
        debug=debug,
    )
    validate_document(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document


def parse_ocr_boxes(ocr_document: dict[str, Any]) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for block in ocr_document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        bbox = parse_bbox(block.get("bbox"))
        if bbox is None:
            continue
        boxes.append({"id": str(block.get("id") or ""), "bbox": bbox, "text": str(block.get("text") or "")})
    return boxes


def accepted_images(m2902_document: dict[str, Any], m29_document: dict[str, Any]) -> list[dict[str, Any]]:
    m29_images = {
        str(node.get("id")): node
        for node in m29_document.get("nodes", [])
        if isinstance(node, dict) and node.get("type") == "image"
    }
    images: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for item in m2902_document.get("mediaEvidence", []):
        if not isinstance(item, dict):
            continue
        if item.get("decision") != "accepted_image":
            continue
        if item.get("source") != "m29_image":
            continue
        if item.get("suggestedNextAction") != "keep_accepted_image":
            continue
        bbox = parse_bbox(item.get("bbox"))
        if bbox is None:
            continue
        key = tuple(bbox)
        if key in seen:
            continue
        seen.add(key)
        source_id = str(item.get("id") or "")
        source_node = m29_images.get(source_id)
        images.append(
            {
                "id": source_id,
                "bbox": bbox,
                "sourceNodeId": source_node.get("id") if isinstance(source_node, dict) else None,
            }
        )
    return images


def propose_candidates_in_image(
    pixels: PngPixels,
    image: dict[str, Any],
    ocr_boxes: list[dict[str, Any]],
    options: M292Options,
) -> list[dict[str, Any]]:
    image_bbox = parse_bbox(image.get("bbox"))
    if image_bbox is None:
        return []
    clamped_image = bbox_clamp(image_bbox, pixels.width, pixels.height)
    if clamped_image is None:
        return []
    components = foreground_components_for_image(pixels, clamped_image, options)
    groups = group_components(components, clamped_image, options)
    proposals: list[dict[str, Any]] = []
    for group in groups:
        candidate_bbox = union_bbox([component["bbox"] for component in group])
        proposal = evaluate_group(candidate_bbox, group, clamped_image, ocr_boxes, options)
        proposals.append(proposal)
    proposals.sort(key=lambda item: (0 if item["decision"] == "proposal_only" else 1, item["bbox"][1], item["bbox"][0]))
    return proposals


def foreground_components_for_image(pixels: PngPixels, image_bbox: list[int], options: M292Options) -> list[dict[str, Any]]:
    x, y, width, height = image_bbox
    visited: set[tuple[int, int]] = set()
    components: list[dict[str, Any]] = []
    for row_index in range(y, y + height):
        for column in range(x, x + width):
            point = (column, row_index)
            if point in visited:
                continue
            if not within_image_edge_scan([column, row_index, 1, 1], image_bbox, options):
                continue
            if not is_text_ink_pixel(pixels, image_bbox, column, row_index, options):
                continue
            component = flood_component(pixels, image_bbox, point, visited, options)
            if component is None:
                continue
            components.append(component)
    return components


def flood_component(
    pixels: PngPixels,
    image_bbox: list[int],
    start: tuple[int, int],
    visited: set[tuple[int, int]],
    options: M292Options,
) -> dict[str, Any] | None:
    x, y, width, height = image_bbox
    x2 = x + width
    y2 = y + height
    stack = [start]
    visited.add(start)
    points: list[tuple[int, int]] = []
    while stack:
        px, py = stack.pop()
        points.append((px, py))
        for ny in range(max(y, py - 1), min(y2, py + 2)):
            for nx in range(max(x, px - 1), min(x2, px + 2)):
                point = (nx, ny)
                if point in visited:
                    continue
                if not within_image_edge_scan([nx, ny, 1, 1], image_bbox, options):
                    continue
                if not is_text_ink_pixel(pixels, image_bbox, nx, ny, options):
                    continue
                visited.add(point)
                stack.append(point)
    if len(points) < 4:
        return None
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    bbox = [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]
    area = len(points)
    box_area = bbox_area(bbox)
    if area < 4 or box_area <= 0:
        return None
    aspect = bbox[2] / max(1, bbox[3])
    if bbox[2] > options.max_width or bbox[3] > options.max_height:
        return None
    if aspect > 8.0 or aspect < 0.12:
        return None
    return {
        "bbox": bbox,
        "area": area,
        "fillRatio": round(area / max(1, box_area), 4),
        "centroid": (
            round(sum(point[0] for point in points) / area, 3),
            round(sum(point[1] for point in points) / area, 3),
        ),
    }


def group_components(components: list[dict[str, Any]], image_bbox: list[int], options: M292Options) -> list[list[dict[str, Any]]]:
    usable = [component for component in components if is_small_text_component(component, image_bbox, options)]
    usable.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    groups: list[list[dict[str, Any]]] = []
    for component in usable:
        placed = False
        for group in groups:
            if component_fits_group(component, group, options):
                group.append(component)
                group.sort(key=lambda item: item["bbox"][0])
                placed = True
                break
        if not placed:
            groups.append([component])
    return [group for group in groups if len(group) >= options.min_component_count]


def is_small_text_component(component: dict[str, Any], image_bbox: list[int], options: M292Options) -> bool:
    bbox = component["bbox"]
    if not near_image_edge(bbox, image_bbox, options):
        return False
    if bbox[2] < 1 or bbox[3] < 4:
        return False
    if bbox[2] > 40 or bbox[3] > options.max_height:
        return False
    if bbox[2] / max(1, bbox[3]) > 5.0:
        return False
    return True


def component_fits_group(component: dict[str, Any], group: list[dict[str, Any]], options: M292Options) -> bool:
    bbox = component["bbox"]
    group_bbox = union_bbox([item["bbox"] for item in group])
    median_height = sorted(item["bbox"][3] for item in group)[len(group) // 2]
    center_y = bbox[1] + bbox[3] / 2
    group_center_y = group_bbox[1] + group_bbox[3] / 2
    if abs(center_y - group_center_y) > max(5, median_height * 0.65):
        return False
    if abs(bbox[3] - median_height) > max(6, median_height * 0.75):
        return False
    horizontal_gap = max(0, bbox[0] - bbox_x2(group_bbox), group_bbox[0] - bbox_x2(bbox))
    return horizontal_gap <= max(14, round(median_height * 1.4))


def evaluate_group(
    candidate_bbox: list[int],
    group: list[dict[str, Any]],
    image_bbox: list[int],
    ocr_boxes: list[dict[str, Any]],
    options: M292Options,
) -> dict[str, Any]:
    metrics = candidate_metrics(candidate_bbox, group, image_bbox, ocr_boxes, options)
    reasons = ["inside_accepted_image", "near_image_edge", "small_high_contrast_components"]
    decision: M292Decision = "proposal_only"
    if not bbox_geometry_ok(candidate_bbox, options):
        decision = "rejected_geometry"
        reasons.append("geometry_outside_small_overlay_bounds")
    elif metrics["componentCount"] < options.min_component_count or metrics["componentCount"] > options.max_component_count:
        decision = "rejected_geometry"
        reasons.append("component_count_out_of_range")
    elif metrics["inkDensity"] < options.min_ink_density or metrics["inkDensity"] > options.max_ink_density:
        decision = "rejected_texture_like"
        reasons.append("ink_density_out_of_range")
    elif metrics["baselineSpread"] > max(4, round(candidate_bbox[3] * 0.35)):
        decision = "rejected_geometry"
        reasons.append("baseline_spread_too_high")
    elif metrics["maxComponentAspectRatio"] > 5.0 or metrics["lineLikeComponentRatio"] > 0.35:
        decision = "rejected_texture_like"
        reasons.append("line_like_texture")
    elif metrics["ocrIoUMax"] > options.max_ocr_iou or metrics["ocrCoverageMax"] > options.max_ocr_coverage:
        decision = "covered_by_existing_ocr"
        reasons.append("covered_by_existing_ocr")
    else:
        reasons.append("ocr_missing")
    return {"bbox": candidate_bbox, "group": group, "decision": decision, "reasons": reasons, "metrics": metrics}


def candidate_metrics(
    candidate_bbox: list[int],
    group: list[dict[str, Any]],
    image_bbox: list[int],
    ocr_boxes: list[dict[str, Any]],
    options: M292Options,
) -> dict[str, Any]:
    area = bbox_area(candidate_bbox)
    ink_area = sum(int(item["area"]) for item in group)
    centers = [item["bbox"][1] + item["bbox"][3] / 2 for item in group]
    heights = [item["bbox"][3] for item in group]
    max_aspect = max((item["bbox"][2] / max(1, item["bbox"][3]) for item in group), default=0.0)
    line_like_count = sum(1 for item in group if item["bbox"][2] / max(1, item["bbox"][3]) > 4.0)
    ocr_iou_max = 0.0
    ocr_coverage_max = 0.0
    matched_id: str | None = None
    for box in ocr_boxes:
        bbox = box["bbox"]
        iou = bbox_iou(candidate_bbox, bbox)
        coverage = intersection_area(candidate_bbox, bbox) / max(1, bbox_area(candidate_bbox))
        if iou > ocr_iou_max or coverage > ocr_coverage_max:
            matched_id = str(box.get("id") or "")
        ocr_iou_max = max(ocr_iou_max, iou)
        ocr_coverage_max = max(ocr_coverage_max, coverage)
    contrast = min(1.0, max(0.0, sum(item["fillRatio"] for item in group) / max(1, len(group))))
    return {
        "componentCount": len(group),
        "inkDensity": round(ink_area / max(1, area), 4),
        "baselineSpread": round(max(centers) - min(centers), 3) if centers else 0.0,
        "medianComponentHeight": median(heights),
        "maxComponentAspectRatio": round(max_aspect, 4),
        "lineLikeComponentRatio": round(line_like_count / max(1, len(group)), 4),
        "contrastScore": round(contrast, 4),
        "ocrIoUMax": round(ocr_iou_max, 4),
        "ocrCoverageMax": round(ocr_coverage_max, 4),
        "matchedOcrBoxId": matched_id,
        "upscaleFactor": options.upscale_factor,
        "edgeDistance": edge_distance(candidate_bbox, image_bbox),
    }


def bbox_geometry_ok(bbox: list[int], options: M292Options) -> bool:
    area = bbox_area(bbox)
    aspect = bbox[2] / max(1, bbox[3])
    return (
        options.min_width <= bbox[2] <= options.max_width
        and options.min_height <= bbox[3] <= options.max_height
        and options.min_area <= area <= options.max_area
        and options.min_aspect_ratio <= aspect <= options.max_aspect_ratio
    )


def build_candidate(
    *,
    candidate_index: int,
    proposal: dict[str, Any],
    image: dict[str, Any],
    pixels: PngPixels,
    output_dir: Path,
    options: M292Options,
    emit_debug_artifacts: bool,
) -> M292Candidate:
    asset_path = None
    if emit_debug_artifacts:
        asset_path = write_candidate_asset(pixels, output_dir, proposal["bbox"], candidate_index, "candidates", options.crop_padding, 1)
    metrics = dict(proposal["metrics"])
    matched = metrics.pop("matchedOcrBoxId", None)
    decision = proposal["decision"]
    overlaps = decision == "covered_by_existing_ocr"
    return M292Candidate(
        candidate_id=f"m292_overlay_text_{candidate_index:03d}",
        candidate_kind="small_overlay_counter_candidate",
        bbox=proposal["bbox"],
        source_image_evidence_id=str(image.get("id") or ""),
        source_image_bbox=image["bbox"],
        decision=decision,
        recognized_text=None,
        recognition_source=None,
        recognition_confidence=None,
        materialization_eligible=False,
        overlaps_existing_ocr=overlaps,
        matched_ocr_box_id=matched if overlaps else None,
        asset_path=asset_path,
        upscaled_asset_path=None,
        reasons=proposal["reasons"],
        metrics=metrics,
    )


def run_reprobe(
    candidate: M292Candidate,
    pixels: PngPixels,
    output_dir: Path,
    options: M292Options,
    reprobe_fn: M292ReprobeFn | None,
    emit_debug_artifacts: bool,
) -> M292Candidate:
    index = int(candidate.candidate_id.rsplit("_", 1)[-1])
    crop_bytes = candidate_crop_png_bytes(pixels, candidate.bbox, options.crop_padding, options.upscale_factor)
    upscaled_asset = None
    if emit_debug_artifacts:
        upscaled_asset = write_candidate_asset(pixels, output_dir, candidate.bbox, index, "upscaled", options.crop_padding, options.upscale_factor)
    if reprobe_fn is None:
        return replace(
            candidate,
            decision="reprobe_failed",
            upscaled_asset_path=upscaled_asset,
            reasons=[*candidate.reasons, "reprobe_unavailable"],
            reprobe_error="Local OCR reprobe is not configured.",
        )
    try:
        result = reprobe_fn(crop_bytes, candidate.bbox)
    except Exception as error:  # noqa: BLE001 - diagnostic reprobe must not block the pipeline.
        return replace(
            candidate,
            decision="reprobe_failed",
            upscaled_asset_path=upscaled_asset,
            reasons=[*candidate.reasons, "reprobe_error"],
            reprobe_error=str(error),
        )
    text = str(result.get("text") or "").strip()
    confidence = parse_float(result.get("confidence"))
    if COUNTER_TEXT_RE.match(text):
        return replace(
            candidate,
            decision="reprobe_recognized",
            recognized_text=text,
            recognition_source="local_crop_ocr",
            recognition_confidence=confidence,
            upscaled_asset_path=upscaled_asset,
            reasons=[*candidate.reasons, "recognized_counter_pattern"],
        )
    return replace(
        candidate,
        decision="reprobe_unrecognized",
        recognized_text=text or None,
        recognition_source="local_crop_ocr",
        recognition_confidence=confidence,
        upscaled_asset_path=upscaled_asset,
        reasons=[*candidate.reasons, "recognition_pattern_rejected"],
    )


def write_candidate_asset(
    pixels: PngPixels,
    output_dir: Path,
    bbox: list[int],
    index: int,
    folder: str,
    padding: int,
    upscale_factor: int,
) -> str:
    crop_png = candidate_crop_png_bytes(pixels, bbox, padding, upscale_factor)
    target_dir = output_dir / "assets" / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"m292_overlay_text_{index:03d}.png"
    path.write_bytes(crop_png)
    return str(path.relative_to(output_dir))


def candidate_crop_png_bytes(pixels: PngPixels, bbox: list[int], padding: int, upscale_factor: int) -> bytes:
    padded = bbox_clamp([bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2], pixels.width, pixels.height)
    if padded is None:
        raise UnsupportedPngCropError("M29.2 candidate bbox is outside image bounds.")
    crop_png = crop_pixels_to_png(pixels, PngRegion("candidate", padded[0], padded[1], padded[2], padded[3]))
    if upscale_factor > 1:
        crop_pixels = decode_png_pixels(crop_png)
        scaled = upscale_pixels_nearest(crop_pixels, upscale_factor)
        crop_png = encode_rgb_png(scaled.width, scaled.height, scaled.rows)
    return crop_png


def overlay_candidates(pixels: PngPixels, candidates: list[M292Candidate]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "proposal_only": (255, 149, 0),
        "covered_by_existing_ocr": (120, 120, 120),
        "rejected_geometry": (190, 190, 190),
        "rejected_texture_like": (235, 64, 52),
        "reprobe_recognized": (0, 200, 90),
        "reprobe_unrecognized": (238, 190, 40),
        "reprobe_failed": (235, 64, 52),
    }
    for candidate in candidates:
        draw_rect(rows, pixels.width, pixels.height, candidate.bbox, colors[candidate.decision], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def is_text_ink_pixel(pixels: PngPixels, image_bbox: list[int], column: int, row_index: int, options: M292Options) -> bool:
    row = pixels.rows[row_index]
    offset = column * 3
    rgb = (row[offset], row[offset + 1], row[offset + 2])
    luma = relative_luma(rgb)
    if luma < 170:
        return False
    for ny in range(max(image_bbox[1], row_index - 2), min(bbox_y2(image_bbox), row_index + 3)):
        neighbor_row = pixels.rows[ny]
        for nx in range(max(image_bbox[0], column - 2), min(bbox_x2(image_bbox), column + 3)):
            if nx == column and ny == row_index:
                continue
            neighbor_offset = nx * 3
            neighbor_rgb = (
                neighbor_row[neighbor_offset],
                neighbor_row[neighbor_offset + 1],
                neighbor_row[neighbor_offset + 2],
            )
            neighbor_luma = relative_luma(neighbor_rgb)
            if color_distance(rgb, neighbor_rgb) <= options.foreground_distance_threshold:
                continue
            if neighbor_luma <= luma - 70:
                return True
    return False


def write_outputs(document: M292Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "small_overlay_text_candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "small_overlay_text_candidates.md").write_text(build_markdown(document), encoding="utf-8")


def build_markdown(document: M292Document) -> str:
    lines = [
        "# M29.2 Small Overlay Text Proposal Audit",
        "",
        f"- Candidates: {document.summary['candidateCount']}",
        f"- OCR-covered: {document.summary['ocrCoveredCandidateCount']}",
        f"- Reprobe attempts: {document.summary['reprobeAttemptCount']}",
        f"- Reprobe recognized: {document.summary['reprobeRecognizedCount']}",
        f"- DSL changed: `{document.summary['dslChanged']}`",
        "",
        "## Candidates",
        "",
    ]
    for candidate in document.candidates[:80]:
        lines.append(
            f"- `{candidate.candidate_id}` `{candidate.decision}` bbox={candidate.bbox} "
            f"recognized=`{candidate.recognized_text}` reasons={candidate.reasons}"
        )
    return "\n".join(lines).rstrip() + "\n"


def build_summary(images: list[dict[str, Any]], candidates: list[M292Candidate]) -> dict[str, Any]:
    return {
        "acceptedImageCount": len(images),
        "candidateCount": len(candidates),
        "ocrCoveredCandidateCount": sum(1 for item in candidates if item.decision == "covered_by_existing_ocr"),
        "reprobeAttemptCount": sum(1 for item in candidates if item.decision.startswith("reprobe_")),
        "reprobeRecognizedCount": sum(1 for item in candidates if item.decision == "reprobe_recognized"),
        "materializedTextCount": 0,
        "createdNewBBoxCount": 0,
        "dslChanged": False,
    }


def validate_document(document: M292Document, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M292SmallOverlayTextProposalDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.2 document schema")
    seen: set[str] = set()
    for candidate in document.candidates:
        if candidate.candidate_id in seen:
            raise ValueError(f"duplicate M29.2 candidate id: {candidate.candidate_id}")
        seen.add(candidate.candidate_id)
        if bbox_clamp(candidate.bbox, width, height) != candidate.bbox:
            raise ValueError(f"M29.2 candidate bbox out of bounds: {candidate.candidate_id}")
        for path in [candidate.asset_path, candidate.upscaled_asset_path]:
            if path:
                assert_readable_relative_png(output_dir, path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.2 PNG output missing or unreadable: {path}")


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1]) + abs(left[2] - right[2])


def relative_luma(rgb: tuple[int, int, int]) -> float:
    return rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114


def near_image_edge(bbox: list[int], image_bbox: list[int], options: M292Options) -> bool:
    return edge_distance(bbox, image_bbox) <= max(options.min_edge_distance, round(min(image_bbox[2], image_bbox[3]) * options.edge_distance_ratio))


def within_image_edge_scan(bbox: list[int], image_bbox: list[int], options: M292Options) -> bool:
    return near_image_edge(bbox, image_bbox, options)


def edge_distance(bbox: list[int], image_bbox: list[int]) -> int:
    distances = [
        bbox[0] - image_bbox[0],
        bbox[1] - image_bbox[1],
        bbox_x2(image_bbox) - bbox_x2(bbox),
        bbox_y2(image_bbox) - bbox_y2(bbox),
    ]
    return max(0, min(distances))


def union_bbox(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def intersection_area(left: list[int], right: list[int]) -> int:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(bbox_x2(left), bbox_x2(right))
    y2 = min(bbox_y2(left), bbox_y2(right))
    return max(0, x2 - x1) * max(0, y2 - y1)


def median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [round(float(item)) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def parse_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(1.0, parsed)), 4)


def extract_ocr_from_png_bytes_for_reprobe(_png_data: bytes, _source_bbox: list[int]) -> dict[str, Any]:
    raise RuntimeError("Local OCR reprobe is not configured for this runtime.")
