from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, PngRegion, UnsupportedPngCropError, crop_pixels_to_png, decode_png_pixels, encode_rgb_png, read_png_metadata
from .small_overlay_text_proposal import (
    M292Options,
    parse_ocr_boxes,
    propose_candidates_in_image,
)
from .visual_primitive_graph import bbox_clamp, bbox_x2, bbox_y2, draw_rect


M293Decision = Literal["proposal_only", "covered_by_existing_ocr", "rejected_geometry", "rejected_texture_like"]
M293OverlayKind = Literal["text_like_overlay_candidate", "symbol_like_overlay_candidate", "unknown_overlay_candidate"]
M293Anchor = Literal["top_left", "top_right", "bottom_left", "bottom_right", "top_edge", "bottom_edge", "left_edge", "right_edge"]


@dataclass(frozen=True)
class M293Options:
    enabled: bool = True
    max_overlays: int = 12
    max_overlays_per_image: int = 4
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

    def to_m292_options(self) -> M292Options:
        return M292Options(
            max_candidates=self.max_overlays,
            max_candidates_per_image=self.max_overlays_per_image,
            crop_padding=self.crop_padding,
            min_width=self.min_width,
            max_width=self.max_width,
            min_height=self.min_height,
            max_height=self.max_height,
            min_area=self.min_area,
            max_area=self.max_area,
            min_aspect_ratio=self.min_aspect_ratio,
            max_aspect_ratio=self.max_aspect_ratio,
            foreground_distance_threshold=self.foreground_distance_threshold,
            min_ink_density=self.min_ink_density,
            max_ink_density=self.max_ink_density,
            min_component_count=self.min_component_count,
            max_component_count=self.max_component_count,
            max_ocr_iou=self.max_ocr_iou,
            max_ocr_coverage=self.max_ocr_coverage,
            edge_distance_ratio=self.edge_distance_ratio,
            min_edge_distance=self.min_edge_distance,
        )


@dataclass(frozen=True)
class M293DebugArtifacts:
    overlay: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {key: value for key, value in {"overlay": self.overlay}.items() if value is not None}


@dataclass(frozen=True)
class M293Overlay:
    id: str
    source_image_node_id: str
    source_m29_node_id: str | None
    source_image_bbox: list[int]
    bbox: list[int]
    anchor: M293Anchor
    overlay_kind: M293OverlayKind
    decision: M293Decision
    base_image_handling: str
    materialization_eligible: bool
    overlaps_existing_ocr: bool
    matched_ocr_box_id: str | None
    asset_path: str | None
    reasons: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceImageNodeId": self.source_image_node_id,
            "sourceM29NodeId": self.source_m29_node_id,
            "sourceImageBBox": self.source_image_bbox,
            "bbox": self.bbox,
            "anchor": self.anchor,
            "overlayKind": self.overlay_kind,
            "decision": self.decision,
            "baseImageHandling": self.base_image_handling,
            "materializationEligible": self.materialization_eligible,
            "overlapsExistingOcr": self.overlaps_existing_ocr,
            "matchedOcrBoxId": self.matched_ocr_box_id,
            "assetPath": self.asset_path,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class M293Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_ocr_json: str | None
    source_m29_nodes_json: str | None
    source_m2902_audit_json: str | None
    options: M293Options
    summary: dict[str, Any]
    overlays: list[M293Overlay]
    warnings: list[str]
    debug: M293DebugArtifacts = field(default_factory=M293DebugArtifacts)

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
            "overlays": [overlay.to_dict() for overlay in self.overlays],
            "warnings": self.warnings,
            "debug": self.debug.to_dict(),
        }


def extract_image_internal_overlays(
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
    options: M293Options | None = None,
    emit_debug_artifacts: bool = True,
) -> M293Document:
    options = options or M293Options()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_boxes = parse_ocr_boxes(ocr_document)
    images = accepted_overlay_images(m2902_document, m29_document)
    selected_proposals, warnings = select_fair_overlay_proposals(pixels, images, ocr_boxes, options)

    overlays: list[M293Overlay] = []
    for selected in selected_proposals:
        overlay = build_overlay(
            overlay_index=len(overlays) + 1,
            proposal=selected["proposal"],
            image=selected["image"],
            pixels=pixels,
            output_dir=output_dir,
            options=options,
            emit_debug_artifacts=emit_debug_artifacts,
        )
        overlays.append(overlay)

    debug = M293DebugArtifacts()
    if emit_debug_artifacts:
        overlay_dir = output_dir / "overlays"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = overlay_dir / "image_internal_overlays.png"
        overlay_path.write_bytes(overlay_image_internal_overlays(pixels, overlays))
        debug = M293DebugArtifacts(overlay=str(overlay_path.relative_to(output_dir)))

    document = M293Document(
        schema_name="M293ImageInternalOverlayDocument",
        schema_version="0.1",
        source_image=source_image,
        source_ocr_json=ocr_json_path,
        source_m29_nodes_json=m29_nodes_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        options=options,
        summary=build_summary(images, overlays),
        overlays=overlays,
        warnings=warnings,
        debug=debug,
    )
    validate_document(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document


def accepted_overlay_images(m2902_document: dict[str, Any], m29_document: dict[str, Any]) -> list[dict[str, Any]]:
    m29_image_nodes = [
        node
        for node in m29_document.get("nodes", [])
        if isinstance(node, dict) and node.get("type") == "image" and parse_bbox(node.get("bbox")) is not None
    ]
    by_id = {str(node.get("id") or ""): node for node in m29_image_nodes}
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
        source_node = resolve_source_m29_image_node(source_id, bbox, m29_image_nodes, by_id)
        images.append(
            {
                "id": source_id,
                "bbox": bbox,
                "sourceM29NodeId": str(source_node.get("id")) if isinstance(source_node, dict) else None,
            }
        )
    return images


def resolve_source_m29_image_node(
    source_id: str,
    bbox: list[int],
    m29_image_nodes: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for node in m29_image_nodes:
        if parse_bbox(node.get("bbox")) == bbox:
            return node
    if source_id.startswith("m29_image_"):
        suffix = source_id.removeprefix("m29_image_")
        node = by_id.get(f"image_{suffix}")
        if node is not None:
            return node
    return by_id.get(source_id)


def select_fair_overlay_proposals(
    pixels: PngPixels,
    images: list[dict[str, Any]],
    ocr_boxes: list[dict[str, Any]],
    options: M293Options,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    per_image: list[dict[str, Any]] = []
    m292_options = options.to_m292_options()
    for image in images:
        proposals = propose_candidates_in_image(pixels, image, ocr_boxes, m292_options)
        kept = proposals[: max(0, options.max_overlays_per_image)]
        if len(proposals) > len(kept):
            warnings.append(f"M29.3 per-image overlay limit reached for {image.get('id') or 'unknown_image'}.")
        per_image.append({"image": image, "proposals": kept})

    selected: list[dict[str, Any]] = []
    max_rounds = max((len(item["proposals"]) for item in per_image), default=0)
    for selection_round in range(max_rounds):
        for item in per_image:
            proposals = item["proposals"]
            if selection_round >= len(proposals):
                continue
            if len(selected) >= options.max_overlays:
                warnings.append("M29.3 global overlay limit reached after fair per-image selection.")
                return selected, warnings
            proposal = dict(proposals[selection_round])
            proposal["metrics"] = dict(proposal["metrics"])
            proposal["metrics"]["selectionRound"] = selection_round + 1
            selected.append({"image": item["image"], "proposal": proposal})
    return selected, warnings


def build_overlay(
    *,
    overlay_index: int,
    proposal: dict[str, Any],
    image: dict[str, Any],
    pixels: PngPixels,
    output_dir: Path,
    options: M293Options,
    emit_debug_artifacts: bool,
) -> M293Overlay:
    asset_path = None
    if emit_debug_artifacts:
        asset_path = write_overlay_asset(pixels, output_dir, proposal["bbox"], overlay_index, options.crop_padding)
    metrics = dict(proposal["metrics"])
    matched = metrics.pop("matchedOcrBoxId", None)
    decision = normalize_decision(str(proposal["decision"]))
    overlaps = decision == "covered_by_existing_ocr"
    reasons = normalize_reasons(proposal["reasons"], decision)
    return M293Overlay(
        id=f"m293_overlay_{overlay_index:03d}",
        source_image_node_id=str(image.get("id") or ""),
        source_m29_node_id=str(image.get("sourceM29NodeId")) if image.get("sourceM29NodeId") else None,
        source_image_bbox=image["bbox"],
        bbox=proposal["bbox"],
        anchor=classify_anchor(proposal["bbox"], image["bbox"], options),
        overlay_kind=classify_overlay_kind(metrics, decision),
        decision=decision,
        base_image_handling="preserve_underlay",
        materialization_eligible=False,
        overlaps_existing_ocr=overlaps,
        matched_ocr_box_id=matched if overlaps else None,
        asset_path=asset_path,
        reasons=reasons,
        metrics=metrics,
    )


def normalize_decision(decision: str) -> M293Decision:
    if decision in {"proposal_only", "covered_by_existing_ocr", "rejected_geometry", "rejected_texture_like"}:
        return decision  # type: ignore[return-value]
    return "rejected_geometry"


def normalize_reasons(reasons: list[str], decision: M293Decision) -> list[str]:
    mapped: list[str] = []
    for reason in reasons:
        if reason == "near_image_edge":
            mapped.append("edge_or_corner_anchored")
        elif reason == "small_high_contrast_components":
            mapped.append("small_high_contrast_foreground")
        else:
            mapped.append(reason)
    if decision in {"proposal_only", "covered_by_existing_ocr"}:
        mapped.append("parent_image_ownership_bound")
        if "text_like_component_group" not in mapped:
            mapped.append("text_like_component_group")
    return dedupe(mapped)


def classify_overlay_kind(metrics: dict[str, Any], decision: M293Decision) -> M293OverlayKind:
    if decision in {"proposal_only", "covered_by_existing_ocr"} and int(metrics.get("componentCount") or 0) >= 2:
        return "text_like_overlay_candidate"
    if float(metrics.get("lineLikeComponentRatio") or 0.0) <= 0.35:
        return "symbol_like_overlay_candidate"
    return "unknown_overlay_candidate"


def classify_anchor(bbox: list[int], image_bbox: list[int], options: M293Options) -> M293Anchor:
    left = bbox[0] - image_bbox[0]
    top = bbox[1] - image_bbox[1]
    right = bbox_x2(image_bbox) - bbox_x2(bbox)
    bottom = bbox_y2(image_bbox) - bbox_y2(bbox)
    edge_limit = max(options.min_edge_distance, round(min(image_bbox[2], image_bbox[3]) * options.edge_distance_ratio))
    x_center = bbox[0] + bbox[2] / 2
    y_center = bbox[1] + bbox[3] / 2
    left_zone = x_center <= image_bbox[0] + image_bbox[2] * 0.35
    right_zone = x_center >= image_bbox[0] + image_bbox[2] * 0.65
    top_zone = y_center <= image_bbox[1] + image_bbox[3] * 0.35
    bottom_zone = y_center >= image_bbox[1] + image_bbox[3] * 0.65
    if top <= edge_limit and left <= edge_limit and left_zone:
        return "top_left"
    if top <= edge_limit and right <= edge_limit and right_zone:
        return "top_right"
    if bottom <= edge_limit and left <= edge_limit and left_zone:
        return "bottom_left"
    if bottom <= edge_limit and right <= edge_limit and right_zone:
        return "bottom_right"
    edge_distances = {"top_edge": top, "bottom_edge": bottom, "left_edge": left, "right_edge": right}
    return min(edge_distances.items(), key=lambda item: item[1])[0]  # type: ignore[return-value]


def write_overlay_asset(pixels: PngPixels, output_dir: Path, bbox: list[int], index: int, padding: int) -> str:
    padded = bbox_clamp([bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2], pixels.width, pixels.height)
    if padded is None:
        raise UnsupportedPngCropError("M29.3 overlay bbox is outside image bounds.")
    png = crop_pixels_to_png(pixels, PngRegion("overlay", padded[0], padded[1], padded[2], padded[3]))
    target_dir = output_dir / "assets" / "overlays"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"m293_overlay_{index:03d}.png"
    path.write_bytes(png)
    return str(path.relative_to(output_dir))


def overlay_image_internal_overlays(pixels: PngPixels, overlays: list[M293Overlay]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "proposal_only": (255, 149, 0),
        "covered_by_existing_ocr": (120, 120, 120),
        "rejected_geometry": (190, 190, 190),
        "rejected_texture_like": (235, 64, 52),
    }
    for overlay in overlays:
        draw_rect(rows, pixels.width, pixels.height, overlay.source_image_bbox, (0, 180, 210), 1)
        draw_rect(rows, pixels.width, pixels.height, overlay.bbox, colors[overlay.decision], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def write_outputs(document: M293Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "image_internal_overlays.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "image_internal_overlays.md").write_text(build_markdown(document), encoding="utf-8")


def build_markdown(document: M293Document) -> str:
    lines = [
        "# M29.3 Image Internal Overlay Ownership Audit",
        "",
        f"- Accepted images: {document.summary['acceptedImageCount']}",
        f"- Overlays: {document.summary['overlayCount']}",
        f"- OCR-covered: {document.summary['ocrCoveredOverlayCount']}",
        f"- DSL changed: `{document.summary['dslChanged']}`",
        "",
        "## Overlays",
        "",
    ]
    for overlay in document.overlays[:80]:
        lines.append(
            f"- `{overlay.id}` `{overlay.decision}` `{overlay.overlay_kind}` "
            f"parent=`{overlay.source_image_node_id}` bbox={overlay.bbox} anchor=`{overlay.anchor}` reasons={overlay.reasons}"
        )
    return "\n".join(lines).rstrip() + "\n"


def build_summary(images: list[dict[str, Any]], overlays: list[M293Overlay]) -> dict[str, Any]:
    return {
        "acceptedImageCount": len(images),
        "overlayCount": len(overlays),
        "ocrCoveredOverlayCount": sum(1 for item in overlays if item.decision == "covered_by_existing_ocr"),
        "materializedTextCount": 0,
        "createdNewBBoxCount": 0,
        "dslChanged": False,
    }


def validate_document(document: M293Document, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M293ImageInternalOverlayDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.3 document schema")
    seen: set[str] = set()
    for overlay in document.overlays:
        if overlay.id in seen:
            raise ValueError(f"duplicate M29.3 overlay id: {overlay.id}")
        seen.add(overlay.id)
        if bbox_clamp(overlay.bbox, width, height) != overlay.bbox:
            raise ValueError(f"M29.3 overlay bbox out of bounds: {overlay.id}")
        if not overlay.source_image_node_id:
            raise ValueError(f"M29.3 overlay missing parent image id: {overlay.id}")
        if overlay.materialization_eligible:
            raise ValueError(f"M29.3 overlay must remain audit-only: {overlay.id}")
        if overlay.asset_path:
            assert_readable_relative_png(output_dir, overlay.asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.3 PNG output missing or unreadable: {path}")


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


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
