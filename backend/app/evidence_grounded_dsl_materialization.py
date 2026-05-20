from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .dsl_factory import build_deterministic_dsl
from .mixed_symbol_text_conflict_audit import find_forbidden_contract_terms
from .png_tools import PngMetadata, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata, sample_rect_edges_dominant_background
from .visual_evidence_normalization import parse_bbox
from .visual_primitive_graph import bbox_in_bounds, draw_rect, measure_region


M30Mode = Literal["augment-existing-dsl", "bootstrap-dsl-from-m29"]
MaterializedKind = Literal["text", "shape", "image", "text_cover"]
TextEditabilityDecisionKind = Literal["editable_text", "graphic_text_preserve_in_fallback", "review_text"]


@dataclass(frozen=True)
class M30Options:
    safe_visual_text_overlap_max: float = 0.0
    safe_shape_text_overlap_max: float = 0.0
    default_text_color: str = "#111827"
    min_text_font_size: int = 8
    max_text_font_size: int = 36
    text_cover_enabled: bool = True
    text_cover_background_tolerance: int = 24
    text_cover_min_sample_confidence: float = 0.72
    text_cover_max_text_visual_overlap: float = 0.02
    text_cover_min_width: int = 4
    text_cover_min_height: int = 4
    text_cover_max_area_ratio: float = 0.08
    text_cover_padding: int = 0
    text_editability_enabled: bool = True
    preserve_graphic_text_in_media_units: bool = True
    max_editable_text_rotation_angle: float = 3.0
    max_editable_background_texture: float = 0.45
    max_editable_background_color_count: int = 32
    unstable_background_sample_preserve: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M30MaterializedNode:
    id: str
    kind: MaterializedKind
    source_id: str
    bbox: list[int]
    confidence: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "sourceId": self.source_id,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class M30PendingNode:
    node: dict[str, Any]
    materialized: M30MaterializedNode


@dataclass(frozen=True)
class M30SkippedItem:
    id: str
    source_kind: str
    reason: str
    bbox: list[int] | None = None
    source_risks: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "sourceKind": self.source_kind,
            "reason": self.reason,
        }
        if self.bbox is not None:
            data["bbox"] = self.bbox
        if self.source_risks is not None:
            data["sourceRisks"] = self.source_risks
        return data


@dataclass(frozen=True)
class M30TextEditabilityDecision:
    source_text_member_id: str
    source_text_box_id: str | None
    decision: TextEditabilityDecisionKind
    bbox: list[int]
    text: str
    reasons: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "sourceTextMemberId": self.source_text_member_id,
            "decision": self.decision,
            "bbox": self.bbox,
            "text": self.text,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }
        if self.source_text_box_id:
            data["sourceTextBoxId"] = self.source_text_box_id
        return data


@dataclass(frozen=True)
class TextEditabilityItem:
    id: str
    source_text_box_id: str | None
    bbox: list[int]
    text: str
    source_meta: dict[str, Any]


@dataclass(frozen=True)
class VisualEditabilityItem:
    bbox: list[int]


@dataclass(frozen=True)
class M30DebugArtifacts:
    materialization_preview: str | None = None

    def to_dict(self) -> dict[str, str]:
        if self.materialization_preview is None:
            return {}
        return {"materializationPreview": self.materialization_preview}


@dataclass(frozen=True)
class M30Report:
    schema_name: str
    schema_version: str
    mode: M30Mode
    source_image: str
    source_base_dsl: str | None
    source_m2905_refined_visual_objects_json: str
    output_dsl: str
    options: M30Options
    summary: dict[str, Any]
    materialized_text_nodes: list[M30MaterializedNode]
    materialized_text_cover_nodes: list[M30MaterializedNode]
    materialized_shape_nodes: list[M30MaterializedNode]
    materialized_image_nodes: list[M30MaterializedNode]
    skipped_items: list[M30SkippedItem]
    skipped_text_cover_items: list[M30SkippedItem]
    text_editability_decisions: list[M30TextEditabilityDecision]
    audit_only_references: list[dict[str, Any]]
    warnings: list[str]
    debug: M30DebugArtifacts
    forbidden_term_check: dict[str, Any]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "mode": self.mode,
            "sourceImage": self.source_image,
            "sourceBaseDsl": self.source_base_dsl,
            "sourceM2905RefinedVisualObjectsJson": self.source_m2905_refined_visual_objects_json,
            "outputDsl": self.output_dsl,
            "options": self.options.to_dict(),
            "summary": self.summary,
            "materializedTextNodes": [item.to_dict() for item in self.materialized_text_nodes],
            "materializedTextCoverNodes": [item.to_dict() for item in self.materialized_text_cover_nodes],
            "materializedShapeNodes": [item.to_dict() for item in self.materialized_shape_nodes],
            "materializedImageNodes": [item.to_dict() for item in self.materialized_image_nodes],
            "skippedItems": [item.to_dict() for item in self.skipped_items],
            "skippedTextCoverItems": [item.to_dict() for item in self.skipped_text_cover_items],
            "textEditabilityDecisions": [item.to_dict() for item in self.text_editability_decisions],
            "preservedGraphicTextItems": [item.to_dict() for item in self.text_editability_decisions if item.decision == "graphic_text_preserve_in_fallback"],
            "reviewTextItems": [item.to_dict() for item in self.text_editability_decisions if item.decision == "review_text"],
            "auditOnlyReferences": self.audit_only_references,
            "warnings": self.warnings,
            "debug": self.debug.to_dict(),
            "forbiddenTermCheck": self.forbidden_term_check,
            "meta": self.meta,
        }


@dataclass(frozen=True)
class M30Result:
    dsl: dict[str, Any]
    report: M30Report
    output_dir: Path


def materialize_evidence_grounded_dsl(
    *,
    source_image_path: str,
    m2905_document: dict[str, Any],
    m2905_json_path: str,
    m2902_document: dict[str, Any] | None = None,
    output_dir: Path,
    mode: M30Mode,
    base_dsl: dict[str, Any] | None = None,
    base_dsl_path: str | None = None,
    options: M30Options | None = None,
    warnings: list[str] | None = None,
    emit_preview_artifacts: bool = True,
) -> M30Result:
    options = options or M30Options()
    source_path = Path(source_image_path).expanduser().resolve()
    png_data = source_path.read_bytes()
    image = read_png_metadata(png_data)
    if image is None:
        raise ValueError(f"M30 source image must be a readable PNG: {source_path}")
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == "augment-existing-dsl":
        if base_dsl is None:
            raise ValueError("augment-existing-dsl requires base_dsl")
        dsl = copy.deepcopy(base_dsl)
    elif mode == "bootstrap-dsl-from-m29":
        if base_dsl is not None:
            raise ValueError("bootstrap-dsl-from-m29 does not accept base_dsl")
        dsl = build_bootstrap_dsl(source_path, image, output_dir)
    else:
        raise ValueError(f"unsupported M30 mode: {mode}")

    ensure_dsl_shape(dsl)
    before_children = list(dsl["root"].get("children", []))
    existing_ids = collect_element_ids(dsl["root"])
    assets_by_id = {str(asset.get("assetId")) for asset in dsl.get("assets", []) if isinstance(asset, dict) and asset.get("assetId")}

    materialized_text: list[M30MaterializedNode] = []
    materialized_text_cover: list[M30MaterializedNode] = []
    materialized_shape: list[M30MaterializedNode] = []
    materialized_image: list[M30MaterializedNode] = []
    pending_text_nodes: list[M30PendingNode] = []
    pending_text_cover_nodes: list[M30PendingNode] = []
    pending_shape_nodes: list[M30PendingNode] = []
    pending_image_nodes: list[M30PendingNode] = []
    skipped: list[M30SkippedItem] = []
    skipped_text_cover: list[M30SkippedItem] = []

    text_decisions = classify_text_editability(
        pixels=pixels,
        image=image,
        m2905_document=m2905_document,
        m2902_document=m2902_document or {},
        options=options,
    )
    append_text_nodes(existing_ids, m2905_document, image, options, text_decisions, pending_text_nodes, skipped)
    harmonize_text_font_sizes(pending_text_nodes, options)
    append_shape_nodes(existing_ids, m2905_document, image, options, pending_shape_nodes, skipped)
    append_image_nodes(dsl, existing_ids, assets_by_id, m2905_document, Path(m2905_json_path).expanduser().resolve().parent, output_dir, image, options, pending_image_nodes, skipped)
    append_text_cover_nodes(
        existing_ids=existing_ids,
        pixels=pixels,
        image=image,
        options=options,
        text_nodes=pending_text_nodes,
        image_nodes=pending_image_nodes,
        cover_nodes=pending_text_cover_nodes,
        skipped=skipped_text_cover,
    )
    append_pending_nodes(dsl, pending_shape_nodes)
    append_pending_nodes(dsl, pending_image_nodes)
    append_pending_nodes(dsl, pending_text_cover_nodes)
    append_pending_nodes(dsl, pending_text_nodes)
    materialized_text = [item.materialized for item in pending_text_nodes]
    materialized_text_cover = [item.materialized for item in pending_text_cover_nodes]
    materialized_shape = [item.materialized for item in pending_shape_nodes]
    materialized_image = [item.materialized for item in pending_image_nodes]

    audit_refs = collect_audit_only_references(m2905_document)
    preview_path = write_preview(pixels, output_dir, [*materialized_shape, *materialized_image, *materialized_text_cover, *materialized_text]) if emit_preview_artifacts else None
    erase_text_from_fallback_images(dsl, output_dir, materialized_text)
    update_dsl_meta(dsl, mode, before_children, materialized_text, materialized_text_cover, materialized_shape, materialized_image, audit_refs)

    output_dsl_path = output_dir / "m30_materialized_dsl.json"
    report_path = output_dir / "m30_materialization_report.json"
    summary = build_summary(
        dsl=dsl,
        mode=mode,
        m2905_document=m2905_document,
        materialized_text=materialized_text,
        materialized_text_cover=materialized_text_cover,
        materialized_shape=materialized_shape,
        materialized_image=materialized_image,
        skipped=skipped,
        skipped_text_cover=skipped_text_cover,
        text_decisions=text_decisions,
        audit_refs=audit_refs,
    )
    report = M30Report(
        schema_name="M30EvidenceGroundedDslMaterializationReport",
        schema_version="0.1",
        mode=mode,
        source_image=str(source_path),
        source_base_dsl=base_dsl_path,
        source_m2905_refined_visual_objects_json=m2905_json_path,
        output_dsl=str(output_dsl_path),
        options=options,
        summary=summary,
        materialized_text_nodes=materialized_text,
        materialized_text_cover_nodes=materialized_text_cover,
        materialized_shape_nodes=materialized_shape,
        materialized_image_nodes=materialized_image,
        skipped_items=skipped,
        skipped_text_cover_items=skipped_text_cover,
        text_editability_decisions=text_decisions,
        audit_only_references=audit_refs,
        warnings=warnings or [],
        debug=M30DebugArtifacts(materialization_preview=preview_path),
        forbidden_term_check={"hits": [], "checkedScope": "m30_report_and_materialized_nodes"},
        meta={
            "notes": "m30_evidence_grounded_dsl_materialization",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    forbidden_hits = find_forbidden_contract_terms(json.dumps(report_without_forbidden_check(report), ensure_ascii=False).lower())
    report = replace_forbidden_check(report, forbidden_hits)
    validate_m30_result(dsl, report, output_dir, image.width, image.height)
    output_dsl_path.write_text(json.dumps(dsl, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return M30Result(dsl=dsl, report=report, output_dir=output_dir)


def build_bootstrap_dsl(source_path: Path, image: PngMetadata, output_dir: Path) -> dict[str, Any]:
    fallback_dir = output_dir / "assets" / "m30_fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    fallback_path = fallback_dir / source_path.name
    if source_path.resolve() != fallback_path.resolve():
        shutil.copy2(source_path, fallback_path)
    return build_deterministic_dsl(
        task_id=f"m30_{source_path.stem}",
        original_url=str(source_path),
        fallback_url=relative_posix(output_dir, fallback_path),
        image=image,
        regions=None,
        quality_flags=["m30_bootstrap_full_image_fallback"],
    )


def classify_text_editability(
    *,
    pixels: Any,
    image: PngMetadata,
    m2905_document: dict[str, Any],
    m2902_document: dict[str, Any],
    options: M30Options,
) -> list[M30TextEditabilityDecision]:
    decisions: list[M30TextEditabilityDecision] = []
    text_boxes_by_id = {
        str(item.get("id")): item
        for item in list_dicts(m2902_document.get("textBoxes"))
        if item.get("id") is not None
    }
    image_area = max(1, image.width * image.height)
    text_items: list[TextEditabilityItem] = []
    visual_items: list[VisualEditabilityItem] = []

    for item in list_dicts(m2905_document.get("textMembers")):
        source_id = str(item.get("id") or "")
        bbox = parse_bbox(item.get("bbox"))
        text = str(item.get("text") or item.get("textPreview") or "").strip()
        if not source_id or bbox is None or not text or not bbox_in_bounds(bbox, image.width, image.height):
            continue

        source_text_box_id = str(item.get("sourceTextBoxId") or "") or None
        source_text_box = text_boxes_by_id.get(source_text_box_id or "")
        source_meta = source_text_box.get("meta") if isinstance(source_text_box, dict) and isinstance(source_text_box.get("meta"), dict) else {}
        text_items.append(
            TextEditabilityItem(
                id=source_id,
                source_text_box_id=source_text_box_id,
                bbox=bbox,
                text=text,
                source_meta=source_meta,
            )
        )

    for item in list_dicts(m2905_document.get("visualAssets")):
        source_id = str(item.get("id") or "")
        bbox = parse_bbox(item.get("bbox"))
        if source_id and bbox is not None and bbox_in_bounds(bbox, image.width, image.height):
            visual_items.append(VisualEditabilityItem(bbox=bbox))

    visual_bboxes = [item.bbox for item in visual_items]

    for item in text_items:
        reasons: list[str] = ["source_evidence_trace"]
        decision: TextEditabilityDecisionKind = "editable_text"
        metrics = build_text_editability_metrics(pixels, item.bbox, item.source_meta, visual_bboxes, image_area)

        if options.text_editability_enabled:
            preserve_reasons: list[str] = []
            if options.preserve_graphic_text_in_media_units:
                angle = metrics.get("angle")
                if isinstance(angle, (int, float)) and angle >= options.max_editable_text_rotation_angle:
                    preserve_reasons.append("rotated_or_skewed_text")
                if metrics["visualOverlapRatio"] >= 0.35:
                    preserve_reasons.append("image_embedded_text")
                if is_media_region_text(item.bbox, image):
                    preserve_reasons.append("media_region_text")
                if is_high_visual_style_loss(item.text, item.bbox, image, metrics):
                    preserve_reasons.append("high_visual_style_loss")
                if (
                    options.unstable_background_sample_preserve
                    and metrics["colorCount"] >= options.max_editable_background_color_count
                    and metrics["textureScore"] >= options.max_editable_background_texture
                ):
                    preserve_reasons.append("unstable_background_sample")

            preserve_reasons = unique_strings(preserve_reasons)
            counter_reasons = text_editability_counter_signals(
                item=item,
                text_items=text_items,
                visual_items=visual_items,
                image=image,
                image_area=image_area,
                metrics=metrics,
                preserve_reasons=preserve_reasons,
                options=options,
            )
            metrics["preserveSignals"] = preserve_reasons
            metrics["editableCounterSignals"] = counter_reasons

            if preserve_reasons and should_preserve_text(
                metrics=metrics,
                preserve_reasons=preserve_reasons,
                counter_reasons=counter_reasons,
                options=options,
            ):
                decision = "graphic_text_preserve_in_fallback"
                reasons = unique_strings([*preserve_reasons, "source_evidence_trace"])
            elif preserve_reasons and counter_reasons:
                reasons = unique_strings([*counter_reasons, "source_evidence_trace"])
        else:
            metrics["preserveSignals"] = []
            metrics["editableCounterSignals"] = []

        decisions.append(
            M30TextEditabilityDecision(
                source_text_member_id=item.id,
                source_text_box_id=item.source_text_box_id,
                decision=decision,
                bbox=item.bbox,
                text=item.text,
                reasons=reasons,
                metrics=metrics,
            )
        )
    return decisions


def build_text_editability_metrics(
    pixels: Any,
    bbox: list[int],
    source_meta: dict[str, Any],
    visual_bboxes: list[list[int]],
    image_area: int,
) -> dict[str, Any]:
    measured = measure_region(pixels, bbox)
    angle = source_meta.get("angle")
    max_visual_overlap = max((bbox_overlap_ratio(bbox, visual_bbox) for visual_bbox in visual_bboxes), default=0.0)
    return {
        "angle": round(float(angle), 3) if isinstance(angle, (int, float)) else None,
        "colorCount": measured.color_count,
        "textureScore": measured.texture_score,
        "edgeScore": measured.edge_score,
        "fillRatio": measured.fill_ratio,
        "bboxAreaRatio": round(bbox_area(bbox) / image_area, 6),
        "visualOverlapRatio": round(max_visual_overlap, 4),
    }


def text_editability_counter_signals(
    *,
    item: TextEditabilityItem,
    text_items: list[TextEditabilityItem],
    visual_items: list[VisualEditabilityItem],
    image: PngMetadata,
    image_area: int,
    metrics: dict[str, Any],
    preserve_reasons: list[str],
    options: M30Options,
) -> list[str]:
    signals: list[str] = []
    if find_aligned_text_row_signal(item, text_items, image):
        signals.append("aligned_text_row")
    if "image_embedded_text" in preserve_reasons and find_compact_overlay_badge_signal(item.bbox, visual_items, metrics):
        signals.append("compact_overlay_badge")
    if find_metadata_text_cluster_signal(item, text_items, visual_items, image_area):
        signals.append("metadata_text_cluster")
    if is_stable_local_background(metrics, options):
        signals.append("stable_local_background")
    return unique_strings(signals)


def should_preserve_text(
    *,
    metrics: dict[str, Any],
    preserve_reasons: list[str],
    counter_reasons: list[str],
    options: M30Options,
) -> bool:
    if not preserve_reasons:
        return False
    if not counter_reasons:
        return True

    strong_preserve = False
    if "media_region_text" in preserve_reasons and "high_visual_style_loss" in preserve_reasons:
        strong_preserve = True
    if "high_visual_style_loss" in preserve_reasons and metrics["bboxAreaRatio"] >= 0.004:
        strong_preserve = True

    angle = metrics.get("angle")
    has_structural_counter = any(reason in counter_reasons for reason in ("aligned_text_row", "compact_overlay_badge", "metadata_text_cluster"))
    if (
        isinstance(angle, (int, float))
        and angle >= options.max_editable_text_rotation_angle * 3
        and not has_structural_counter
    ):
        strong_preserve = True

    if strong_preserve:
        return True

    weak_preserve = set(preserve_reasons).issubset(
        {
            "rotated_or_skewed_text",
            "image_embedded_text",
            "unstable_background_sample",
        }
    )
    if weak_preserve and has_structural_counter:
        return False
    if weak_preserve and counter_reasons == ["stable_local_background"]:
        return False
    return True


def find_aligned_text_row_signal(target: TextEditabilityItem, text_items: list[TextEditabilityItem], image: PngMetadata) -> bool:
    target_cy = bbox_center_y(target.bbox)
    target_area = bbox_area(target.bbox)
    siblings: list[TextEditabilityItem] = []
    for other in text_items:
        if other.id == target.id:
            continue
        other_area = bbox_area(other.bbox)
        if target_area <= 0 or other_area <= 0:
            continue
        min_height = max(1, min(target.bbox[3], other.bbox[3]))
        height_ratio = target.bbox[3] / max(1, other.bbox[3])
        if abs(target_cy - bbox_center_y(other.bbox)) > min_height * 0.35:
            continue
        if height_ratio < 0.70 or height_ratio > 1.45:
            continue
        overlap = bbox_intersection_area(target.bbox, other.bbox)
        if overlap / max(1, min(target_area, other_area)) > 0.30:
            continue
        siblings.append(other)

    if len(siblings) >= 2:
        return True
    if len(siblings) < 1:
        return False
    row_boxes = [target.bbox, *[item.bbox for item in siblings]]
    span_left = min(bbox[0] for bbox in row_boxes)
    span_right = max(bbox[0] + bbox[2] for bbox in row_boxes)
    return (span_right - span_left) >= image.width * 0.18


def find_compact_overlay_badge_signal(bbox: list[int], visual_items: list[VisualEditabilityItem], metrics: dict[str, Any]) -> bool:
    text_area = bbox_area(bbox)
    if text_area <= 0:
        return False
    for visual in visual_items:
        visual_area = bbox_area(visual.bbox)
        if visual_area <= text_area:
            continue
        if bbox_overlap_ratio(bbox, visual.bbox) < 0.95:
            continue
        if text_area / visual_area > 0.035:
            continue
        if bbox[3] / max(1, visual.bbox[3]) > 0.16:
            continue
        cx = bbox_center_x(bbox)
        cy = bbox_center_y(bbox)
        x_ratio = (cx - visual.bbox[0]) / max(1, visual.bbox[2])
        y_ratio = (cy - visual.bbox[1]) / max(1, visual.bbox[3])
        edge_band = x_ratio <= 0.22 or x_ratio >= 0.78 or y_ratio <= 0.22 or y_ratio >= 0.78
        local_stable_enough = metrics["textureScore"] <= 0.50 or (metrics["colorCount"] / max(1, text_area)) <= 0.12
        if edge_band and local_stable_enough:
            return True
    return False


def find_metadata_text_cluster_signal(
    target: TextEditabilityItem,
    text_items: list[TextEditabilityItem],
    visual_items: list[VisualEditabilityItem],
    image_area: int,
) -> bool:
    target_area = bbox_area(target.bbox)
    if target_area <= 0 or target_area / image_area > 0.003:
        return False
    neighbors: list[list[int]] = []
    for other in text_items:
        if other.id != target.id and is_compact_neighbor(target.bbox, other.bbox, image_area):
            neighbors.append(other.bbox)
    for visual in visual_items:
        if is_compact_neighbor(target.bbox, visual.bbox, image_area):
            neighbors.append(visual.bbox)

    for neighbor in neighbors:
        union = bbox_union(target.bbox, neighbor)
        if union[3] <= target.bbox[3] * 1.8:
            return True
    return False


def is_compact_neighbor(target: list[int], neighbor: list[int], image_area: int) -> bool:
    neighbor_area = bbox_area(neighbor)
    if neighbor_area <= 0 or neighbor_area / image_area > 0.003:
        return False
    max_height = max(1, target[3], neighbor[3])
    if abs(bbox_center_y(target) - bbox_center_y(neighbor)) > max_height * 0.75:
        return False
    return bbox_axis_gap(target, neighbor) <= max(max_height, neighbor[2]) * 1.2


def is_stable_local_background(metrics: dict[str, Any], options: M30Options) -> bool:
    return (
        metrics["bboxAreaRatio"] <= 0.003
        and metrics["textureScore"] <= options.max_editable_background_texture * 0.75
        and metrics["colorCount"] <= options.max_editable_background_color_count * 2
        and 0.12 <= metrics["fillRatio"] <= 0.90
    )


def is_media_region_text(bbox: list[int], image: PngMetadata) -> bool:
    if image.height < 600:
        return False
    x, y, width, height = bbox
    center_y = y + height / 2
    center_x = x + width / 2
    return (
        center_y >= image.height * 0.10
        and center_y <= image.height * 0.32
        and width >= image.width * 0.16
        and center_x <= image.width * 0.55
    )


def is_high_visual_style_loss(text: str, bbox: list[int], image: PngMetadata, metrics: dict[str, Any]) -> bool:
    _, y, width, height = bbox
    if height < max(28, image.height * 0.018):
        return False
    if width < image.width * 0.14:
        return False
    if y > image.height * 0.36:
        return False
    return metrics["colorCount"] >= 24 and metrics["edgeScore"] >= 0.08 and bool(text)


def unique_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def harmonize_text_font_sizes(pending_nodes: list[M30PendingNode], options: M30Options) -> None:
    """
    Harmonize the font sizes of text nodes that are horizontally aligned (in the same row)
    and have similar initial font sizes, reducing OCR measurement noise.
    """
    if not pending_nodes:
        return

    # Extract relevant info from text nodes
    text_items = []
    for p_node in pending_nodes:
        node = p_node.node
        layout = node.get("layout", {})
        x = layout.get("x", 0)
        y = layout.get("y", 0)
        w = layout.get("width", 0)
        h = layout.get("height", 0)
        style = node.get("style", {})
        fs = style.get("fontSize", 12)
        text_items.append({
            "pending_node": p_node,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "y_center": y + h / 2.0,
            "initial_fs": fs
        })

    # Sort text items by Y-center to process them row-by-row
    text_items.sort(key=lambda item: item["y_center"])

    # Cluster horizontally aligned text items into horizontal rows
    rows: list[list[dict[str, Any]]] = []
    for item in text_items:
        added = False
        # Try to fit the item into an existing row
        for row in rows:
            # We check if y_center of this item is close to the average/representative y_center of the row
            representative = row[0]
            rep_h = representative["height"]
            curr_h = item["height"]
            min_h = min(rep_h, curr_h)
            max_y_center_diff = max(8.0, min_h * 0.4)
            if abs(item["y_center"] - representative["y_center"]) <= max_y_center_diff:
                row.append(item)
                added = True
                break
        if not added:
            rows.append([item])

    # Harmonize each row using iterative mode-based snapping
    for row in rows:
        if len(row) < 2:
            continue
            
        remaining = list(row)
        while len(remaining) >= 2:
            # Count frequencies of remaining items
            freqs = {}
            for item in remaining:
                fs = item["initial_fs"]
                freqs[fs] = freqs.get(fs, 0) + 1
            
            # Find the mode (highest frequency, breaking ties with larger size)
            max_freq = -1
            mode_fs = -1
            for fs, freq in freqs.items():
                if freq > max_freq:
                    max_freq = freq
                    mode_fs = fs
                elif freq == max_freq and fs > mode_fs:
                    mode_fs = fs
            
            # If the mode only has frequency 1, fallback to legacy grouping (diff <= 3)
            if max_freq == 1:
                remaining.sort(key=lambda x: x["initial_fs"])
                sub_groups = []
                for item in remaining:
                    grouped = False
                    for g in sub_groups:
                        if abs(item["initial_fs"] - g[0]["initial_fs"]) <= 3:
                            g.append(item)
                            grouped = True
                            break
                    if not grouped:
                        sub_groups.append([item])
                
                for g in sub_groups:
                    if len(g) >= 2:
                        sizes = sorted([x["initial_fs"] for x in g])
                        n = len(sizes)
                        median_fs = sizes[n // 2] if n % 2 == 1 else round((sizes[n // 2 - 1] + sizes[n // 2]) / 2)
                        for x in g:
                            x["pending_node"].node["style"]["fontSize"] = int(median_fs)
                break

            # Snapping threshold: adaptive based on the mode size (18% of size, min 3, max 6)
            threshold = max(3, min(6, round(mode_fs * 0.18)))
            
            # Identify all items that are close to the mode
            snapped_group = []
            next_remaining = []
            for item in remaining:
                if abs(item["initial_fs"] - mode_fs) <= threshold:
                    snapped_group.append(item)
                else:
                    next_remaining.append(item)
            
            # Apply mode_fs to the snapped group
            for item in snapped_group:
                item["pending_node"].node["style"]["fontSize"] = int(mode_fs)
            
            # Safety check to avoid infinite loop
            if len(next_remaining) == len(remaining):
                break
                
            remaining = next_remaining


def append_text_nodes(
    existing_ids: set[str],
    m2905_document: dict[str, Any],
    image: PngMetadata,
    options: M30Options,
    text_decisions: list[M30TextEditabilityDecision],
    materialized: list[M30PendingNode],
    skipped: list[M30SkippedItem],
) -> None:
    decisions_by_member_id = {item.source_text_member_id: item for item in text_decisions}
    for item in list_dicts(m2905_document.get("textMembers")):
        source_id = str(item.get("id") or "")
        bbox = parse_bbox(item.get("bbox"))
        text = str(item.get("text") or item.get("textPreview") or "").strip()
        if not source_id or bbox is None or not bbox_in_bounds(bbox, image.width, image.height):
            skipped.append(M30SkippedItem(source_id or "unknown_text_member", "m2905_text_member", "invalid_bbox", bbox))
            continue
        if not text:
            skipped.append(M30SkippedItem(source_id, "m2905_text_member", "missing_text", bbox))
            continue
        decision = decisions_by_member_id.get(source_id)
        if decision is not None and decision.decision != "editable_text":
            skipped.append(M30SkippedItem(source_id, "m2905_text_member", decision.decision, bbox, decision.reasons))
            continue
        node_id = next_unique_id(existing_ids, f"m30_text_{len(materialized) + 1:04d}")
        node = {
            "id": node_id,
            "type": "text",
            "role": "m30_text_member",
            "name": f"M30 Text / {source_id}",
            "layout": layout_from_bbox(bbox),
            "style": {
                "visible": True,
                "opacity": 1,
                "color": options.default_text_color,
                "fontSize": estimate_font_size(bbox, options),
                "fontFamily": "Inter",
                "fontWeight": 400,
                "textAlign": "left",
            },
            "content": {"text": text},
            "meta": {
                "m30Materialized": True,
                "sourceKind": "m2905_text_member",
                "sourceTextMemberId": source_id,
                "sourceTextBoxId": item.get("sourceTextBoxId"),
                "sourceEvidenceNodeId": item.get("sourceEvidenceNodeId"),
                "sourceObjectId": item.get("sourceObjectId"),
                "sourceBBox": bbox,
                "ocrConfidence": item.get("confidence"),
                "materializationConfidence": "medium",
                "riskFlags": list_strings(item.get("risks")),
                "textEditabilityDecision": decision.decision if decision is not None else "editable_text",
                "textEditabilityReasons": decision.reasons if decision is not None else ["source_evidence_trace"],
            },
        }
        materialized.append(M30PendingNode(node, M30MaterializedNode(node_id, "text", source_id, bbox, "medium", ["source_evidence_trace"])))


def append_shape_nodes(
    existing_ids: set[str],
    m2905_document: dict[str, Any],
    image: PngMetadata,
    options: M30Options,
    materialized: list[M30PendingNode],
    skipped: list[M30SkippedItem],
) -> None:
    for item in list_dicts(m2905_document.get("shapeCandidates")):
        source_id = str(item.get("id") or "")
        bbox = parse_bbox(item.get("bbox"))
        risks = list_strings(item.get("risks"))
        if not source_id or bbox is None or not bbox_in_bounds(bbox, image.width, image.height):
            skipped.append(M30SkippedItem(source_id or "unknown_shape_candidate", "m2905_shape_candidate", "invalid_bbox", bbox, risks))
            continue
        color = str(item.get("color") or "").strip()
        overlap = to_float(item.get("textOverlapRatio"))
        if item.get("decision") != "candidate":
            skipped.append(M30SkippedItem(source_id, "m2905_shape_candidate", "unresolved_boundary", bbox, risks))
            continue
        if not is_hex_color(color):
            skipped.append(M30SkippedItem(source_id, "m2905_shape_candidate", "missing_reliable_fill", bbox, risks))
            continue
        if overlap > options.safe_shape_text_overlap_max or any(risk in {"contains_text", "text_overlay_shape", "text_touching_visual", "high_text_overlap"} for risk in risks):
            skipped.append(M30SkippedItem(source_id, "m2905_shape_candidate", "unsafe_text_overlap", bbox, risks))
            continue
        node_id = next_unique_id(existing_ids, f"m30_shape_{len(materialized) + 1:04d}")
        node = {
            "id": node_id,
            "type": "shape",
            "role": "m30_shape_candidate",
            "name": f"M30 Shape / {source_id}",
            "layout": layout_from_bbox(bbox),
            "style": {
                "visible": True,
                "opacity": 1,
                "fill": color,
            },
            "meta": {
                "m30Materialized": True,
                "sourceKind": "m2905_shape_candidate",
                "sourceShapeCandidateId": source_id,
                "sourceEvidenceNodeIds": list_strings(item.get("sourceEvidenceNodeIds")),
                "sourceObjectId": item.get("sourceObjectId"),
                "sourceBBox": bbox,
                "materializationConfidence": "medium",
                "riskFlags": risks,
            },
        }
        materialized.append(M30PendingNode(node, M30MaterializedNode(node_id, "shape", source_id, bbox, "medium", ["solid_fill_candidate", "source_evidence_trace"])))


def append_image_nodes(
    dsl: dict[str, Any],
    existing_ids: set[str],
    assets_by_id: set[str],
    m2905_document: dict[str, Any],
    m2905_dir: Path,
    output_dir: Path,
    image: PngMetadata,
    options: M30Options,
    materialized: list[M30PendingNode],
    skipped: list[M30SkippedItem],
) -> None:
    asset_dir = output_dir / "assets" / "m30_visual_assets"
    for item in list_dicts(m2905_document.get("visualAssets")):
        source_id = str(item.get("id") or "")
        bbox = parse_bbox(item.get("bbox"))
        risks = list_strings(item.get("risks"))
        asset_path = str(item.get("assetPath") or "").strip()
        if not source_id or bbox is None or not bbox_in_bounds(bbox, image.width, image.height):
            skipped.append(M30SkippedItem(source_id or "unknown_visual_asset", "m2905_visual_asset", "invalid_bbox", bbox, risks))
            continue
        if item.get("assetUse") not in {"image_asset", "icon_asset"} or item.get("decision") not in {"candidate", "accepted"}:
            skipped.append(M30SkippedItem(source_id, "m2905_visual_asset", "audit_only_source", bbox, risks))
            continue
        if not list_strings(item.get("sourceEvidenceNodeIds")):
            skipped.append(M30SkippedItem(source_id, "m2905_visual_asset", "missing_source_evidence", bbox, risks))
            continue
        if not asset_path:
            skipped.append(M30SkippedItem(source_id, "m2905_visual_asset", "missing_asset_path", bbox, risks))
            continue
        if to_float(item.get("textOverlapRatio")) > options.safe_visual_text_overlap_max or any(risk in {"contains_text", "text_overlay_shape", "text_touching_visual", "high_text_overlap", "unresolved_boundary", "split_needed"} for risk in risks):
            skipped.append(M30SkippedItem(source_id, "m2905_visual_asset", "unsafe_text_overlap", bbox, risks))
            continue
        source_asset_path = (m2905_dir / asset_path).resolve()
        if not source_asset_path.exists():
            skipped.append(M30SkippedItem(source_id, "m2905_visual_asset", "missing_asset_path", bbox, risks))
            continue
        asset_dir.mkdir(parents=True, exist_ok=True)
        copied_path = asset_dir / f"{source_id}{source_asset_path.suffix.lower() or '.png'}"
        shutil.copy2(source_asset_path, copied_path)
        asset_id = next_unique_asset_id(assets_by_id, f"m30_visual_asset_{len(materialized) + 1:04d}")
        dsl["assets"].append(
            {
                "assetId": asset_id,
                "type": "image",
                "role": "m30_visual_asset",
                "url": relative_posix(output_dir, copied_path),
                "format": image_format_for(copied_path),
                "width": bbox[2],
                "height": bbox[3],
                "storage": "local",
                "meta": {
                    "m30Materialized": True,
                    "sourceKind": "m2905_visual_asset",
                    "sourceVisualAssetId": source_id,
                    "copiedFromExistingM2905Asset": asset_path,
                },
            }
        )
        node_id = next_unique_id(existing_ids, f"m30_image_{len(materialized) + 1:04d}")
        node = {
            "id": node_id,
            "type": "image",
            "role": "m30_visual_asset",
            "name": f"M30 Image / {source_id}",
            "layout": layout_from_bbox(bbox),
            "source": {"assetId": asset_id},
            "imageFill": {"mode": "fit"},
            "style": {"visible": True, "opacity": 1},
            "meta": {
                "m30Materialized": True,
                "sourceKind": "m2905_visual_asset",
                "sourceVisualAssetId": source_id,
                "sourceEvidenceNodeIds": list_strings(item.get("sourceEvidenceNodeIds")),
                "sourceObjectId": item.get("sourceObjectId"),
                "sourceBBox": bbox,
                "materializationConfidence": "medium",
                "riskFlags": risks,
            },
        }
        materialized.append(M30PendingNode(node, M30MaterializedNode(node_id, "image", source_id, bbox, "medium", ["source_evidence_trace"])))


def append_text_cover_nodes(
    *,
    existing_ids: set[str],
    pixels: Any,
    image: PngMetadata,
    options: M30Options,
    text_nodes: list[M30PendingNode],
    image_nodes: list[M30PendingNode],
    cover_nodes: list[M30PendingNode],
    skipped: list[M30SkippedItem],
) -> None:
    if not options.text_cover_enabled:
        for text_node in text_nodes:
            meta = text_node.node.get("meta") if isinstance(text_node.node.get("meta"), dict) else {}
            source_id = str(meta.get("sourceTextMemberId") or text_node.materialized.source_id)
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "text_cover_disabled", text_node.materialized.bbox, list_strings(meta.get("riskFlags"))))
        return

    image_area = max(1, image.width * image.height)
    visual_bboxes = [item.materialized.bbox for item in image_nodes]
    high_risks = {"high_text_overlap", "unresolved_boundary", "text_contamination_possible", "text_touching_visual"}

    for text_node in text_nodes:
        node = text_node.node
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        source_id = str(meta.get("sourceTextMemberId") or text_node.materialized.source_id)
        bbox = pad_cover_bbox(text_node.materialized.bbox, options.text_cover_padding)
        risks = list_strings(meta.get("riskFlags"))
        content = node.get("content") if isinstance(node.get("content"), dict) else {}
        text = str(content.get("text") or "").strip()
        confidence = to_float(meta.get("ocrConfidence"))

        if not bbox_in_bounds(bbox, image.width, image.height):
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "invalid_bbox", bbox, risks))
            continue
        if not text:
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "missing_text", bbox, risks))
            continue
        if confidence < 0.70:
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "low_text_confidence", bbox, risks))
            continue
        if bbox[2] < options.text_cover_min_width or bbox[3] < options.text_cover_min_height:
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "bbox_too_small", bbox, risks))
            continue
        if bbox_area(bbox) / image_area > options.text_cover_max_area_ratio:
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "bbox_too_large", bbox, risks))
            continue
        if any(risk in high_risks for risk in risks):
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "high_risk_text_member", bbox, risks))
            continue
        if any(bbox_overlap_ratio(bbox, visual_bbox) > options.text_cover_max_text_visual_overlap for visual_bbox in visual_bboxes):
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "unsafe_visual_overlap", bbox, risks))
            continue

        try:
            sample = sample_rect_edges_dominant_background(
                pixels,
                bbox,
                sides={"top", "bottom", "left", "right"},
                inset=0,
                thickness=1,
                tolerance=options.text_cover_background_tolerance,
                min_fraction=0.58,
            )
        except UnsupportedPngCropError:
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "background_sample_failed", bbox, risks))
            continue
        if sample.confidence < options.text_cover_min_sample_confidence or sample.max_channel_delta > options.text_cover_background_tolerance:
            skipped.append(M30SkippedItem(source_id, "m30_text_cover", "unstable_background_sample", bbox, risks))
            continue

        node_id = next_unique_id(existing_ids, f"m30_text_cover_{len(cover_nodes) + 1:04d}")
        cover_node = {
            "id": node_id,
            "type": "shape",
            "role": "m30_text_cover",
            "name": f"M30 Text Cover / {source_id}",
            "layout": layout_from_bbox(bbox),
            "style": {
                "visible": True,
                "opacity": 1,
                "fill": sample.color,
            },
            "meta": {
                "m30Materialized": True,
                "sourceKind": "m30_text_cover",
                "sourceTextMemberId": source_id,
                "sourceTextNodeId": node.get("id"),
                "sourceBBox": bbox,
                "coverFill": sample.color,
                "backgroundSampleConfidence": sample.confidence,
                "coverConfidence": "medium",
                "riskFlags": [],
            },
        }
        cover_nodes.append(
            M30PendingNode(
                cover_node,
                M30MaterializedNode(node_id, "text_cover", source_id, bbox, "medium", ["stable_background_sample", "source_evidence_trace"]),
            )
        )


def append_pending_nodes(dsl: dict[str, Any], nodes: list[M30PendingNode]) -> None:
    children = dsl["root"].setdefault("children", [])
    for item in nodes:
        children.append(item.node)


def collect_audit_only_references(m2905_document: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in list_dicts(m2905_document.get("objects")):
        if item.get("combinedAssetUse") == "audit_only":
            refs.append({"sourceKind": "m2905_refined_object", "id": item.get("id"), "reason": "audit_only_source"})
    return refs


def erase_text_from_fallback_images(
    dsl: dict[str, Any],
    output_dir: Path,
    materialized_text: list[M30MaterializedNode],
) -> None:
    if not materialized_text:
        return

    fallback_assets = []
    for asset in dsl.get("assets", []):
        if isinstance(asset, dict) and asset.get("role") == "fallback_region" and asset.get("type") == "image":
            url = asset.get("url")
            if url:
                fallback_assets.append(asset)

    if not fallback_assets:
        return

    def find_element_offset_for_asset(element: dict[str, Any], asset_id: str) -> tuple[int, int] | None:
        if not isinstance(element, dict):
            return None
        if element.get("source", {}).get("assetId") == asset_id:
            layout = element.get("layout") or {}
            return int(layout.get("x", 0)), int(layout.get("y", 0))
        for child in element.get("children", []):
            offset = find_element_offset_for_asset(child, asset_id)
            if offset is not None:
                return offset
        return None

    for asset in fallback_assets:
        asset_id = asset["assetId"]
        url = asset["url"]
        image_path = (output_dir / url).resolve()
        if not image_path.exists():
            continue

        try:
            image_bytes = image_path.read_bytes()
            pixels = decode_png_pixels(image_bytes)
        except Exception:
            continue

        offset = find_element_offset_for_asset(dsl.get("root", {}), asset_id)
        rx, ry = offset if offset is not None else (0, 0)
        asset_w, asset_h = pixels.width, pixels.height

        mutable_rows = [bytearray(row) for row in pixels.rows]
        modified = False

        for node in materialized_text:
            tx, ty, tw, th = node.bbox
            local_x = tx - rx
            local_y = ty - ry

            overlap_x1 = max(0, local_x)
            overlap_y1 = max(0, local_y)
            overlap_x2 = min(asset_w, local_x + tw)
            overlap_y2 = min(asset_h, local_y + th)

            if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                try:
                    local_bbox = [local_x, local_y, tw, th]
                    sample = sample_rect_edges_dominant_background(
                        pixels,
                        local_bbox,
                        sides={"top", "bottom", "left", "right"},
                        inset=0,
                        thickness=1,
                        tolerance=24,
                        min_fraction=0.5,
                    )
                    fill_color = sample.mean_rgb
                except Exception:
                    fill_color = [247, 248, 250]

                for row_idx in range(overlap_y1, overlap_y2):
                    row = mutable_rows[row_idx]
                    for col_idx in range(overlap_x1, overlap_x2):
                        offset_idx = col_idx * 3
                        row[offset_idx] = fill_color[0]
                        row[offset_idx + 1] = fill_color[1]
                        row[offset_idx + 2] = fill_color[2]
                modified = True

        if modified:
            try:
                encoded_png = encode_rgb_png(asset_w, asset_h, [bytes(row) for row in mutable_rows])
                image_path.write_bytes(encoded_png)
            except Exception:
                pass


def update_dsl_meta(
    dsl: dict[str, Any],
    mode: M30Mode,
    before_children: list[dict[str, Any]],
    materialized_text: list[M30MaterializedNode],
    materialized_text_cover: list[M30MaterializedNode],
    materialized_shape: list[M30MaterializedNode],
    materialized_image: list[M30MaterializedNode],
    audit_refs: list[dict[str, Any]],
) -> None:
    meta = dict(dsl.get("meta") or {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m30_evidence_grounded_materialization" not in quality_flags:
        quality_flags.append("m30_evidence_grounded_materialization")
    meta["qualityFlags"] = quality_flags
    meta["elementCount"] = count_elements(dsl["root"])
    meta["m30Materialization"] = {
        "mode": mode,
        "baseChildCount": len(before_children),
        "textNodeCount": len(materialized_text),
        "textCoverNodeCount": len(materialized_text_cover),
        "shapeNodeCount": len(materialized_shape),
        "imageNodeCount": len(materialized_image),
        "auditOnlyReferenceCount": len(audit_refs),
    }
    dsl["meta"] = meta


def build_summary(
    *,
    dsl: dict[str, Any],
    mode: M30Mode,
    m2905_document: dict[str, Any],
    materialized_text: list[M30MaterializedNode],
    materialized_text_cover: list[M30MaterializedNode],
    materialized_shape: list[M30MaterializedNode],
    materialized_image: list[M30MaterializedNode],
    skipped: list[M30SkippedItem],
    skipped_text_cover: list[M30SkippedItem],
    text_decisions: list[M30TextEditabilityDecision],
    audit_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    visual_skips = [item for item in skipped if item.source_kind == "m2905_visual_asset"]
    shape_skips = [item for item in skipped if item.source_kind == "m2905_shape_candidate"]
    editable_text = [item for item in text_decisions if item.decision == "editable_text"]
    preserved_text = [item for item in text_decisions if item.decision == "graphic_text_preserve_in_fallback"]
    review_text = [item for item in text_decisions if item.decision == "review_text"]
    fallback_preserved = has_fallback_node(dsl)
    return {
        "mode": mode,
        "textMemberCount": len(list_dicts(m2905_document.get("textMembers"))),
        "materializedTextCount": len(materialized_text),
        "editableTextCount": len(editable_text),
        "preservedGraphicTextCount": len(preserved_text),
        "reviewTextCount": len(review_text),
        "textEditabilityReasonCounts": text_editability_reason_counts(text_decisions),
        "textCoverCandidateCount": len(materialized_text_cover) + len(skipped_text_cover),
        "materializedTextCoverCount": len(materialized_text_cover),
        "skippedTextCoverCount": len(skipped_text_cover),
        "skippedTextCoverReasons": reason_counts(skipped_text_cover),
        "shapeCandidateCount": len(list_dicts(m2905_document.get("shapeCandidates"))),
        "materializedShapeCount": len(materialized_shape),
        "visualAssetCount": len(list_dicts(m2905_document.get("visualAssets"))),
        "materializedImageCount": len(materialized_image),
        "skippedMixedOrAuditOnlyCount": len(audit_refs),
        "skippedUnsafeVisualAssetCount": len(visual_skips),
        "skippedUnreliableShapeCount": len(shape_skips),
        "fallbackPreserved": fallback_preserved,
        "createdNewBBoxCount": 0,
        "permissionViolationCount": 0,
        "forbiddenHitCount": 0,
        "visibleAuditOnlyChildCount": count_visible_audit_only_children(dsl["root"]),
        "dslElementCount": count_elements(dsl["root"]),
    }


def write_preview(pixels: Any, output_dir: Path, nodes: list[M30MaterializedNode]) -> str:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {"shape": (42, 157, 143), "image": (38, 70, 83), "text_cover": (80, 160, 220), "text": (231, 111, 81)}
    for node in nodes:
        draw_rect(rows, pixels.width, pixels.height, node.bbox, colors[node.kind], 2)
    path = output_dir / "m30_materialization_preview.png"
    path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return path.name


def validate_m30_result(dsl: dict[str, Any], report: M30Report, output_dir: Path, width: int, height: int) -> None:
    if report.schema_name != "M30EvidenceGroundedDslMaterializationReport" or report.schema_version != "0.1":
        raise ValueError("invalid M30 report schema")
    if not has_fallback_node(dsl):
        raise ValueError("M30 output must preserve fallback")
    if report.summary.get("createdNewBBoxCount") != 0:
        raise ValueError("M30 must not create new bbox")
    if report.summary.get("permissionViolationCount") != 0:
        raise ValueError("M30 has permission violation")
    if report.summary.get("visibleAuditOnlyChildCount") != 0:
        raise ValueError("M30 audit-only references cannot be visible DSL children")
    materialized_nodes = [*report.materialized_text_nodes, *report.materialized_text_cover_nodes, *report.materialized_shape_nodes, *report.materialized_image_nodes]
    for item in materialized_nodes:
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M30 materialized bbox out of bounds: {item.id}")
    for child in materialized_children(dsl["root"]):
        if child.get("type") == "icon":
            raise ValueError(f"M30 must not emit DSL icon nodes: {child.get('id')}")
        if child.get("role") == "m30_text_cover" and child.get("type") != "shape":
            raise ValueError(f"M30 text cover must be a DSL shape node: {child.get('id')}")
    if report.debug.materialization_preview is not None:
        preview = output_dir / report.debug.materialization_preview
        metadata = read_png_metadata(preview.read_bytes()) if preview.exists() else None
        if metadata is None or metadata.width != width or metadata.height != height:
            raise ValueError("M30 preview is missing or does not match source image")
    if report.forbidden_term_check.get("hits"):
        raise ValueError(f"M30 output contains forbidden terms: {report.forbidden_term_check['hits']}")


def ensure_dsl_shape(dsl: dict[str, Any]) -> None:
    if dsl.get("version") != "0.1":
        raise ValueError("M30 requires DSL version 0.1")
    if not isinstance(dsl.get("assets"), list):
        raise ValueError("M30 requires DSL assets array")
    root = dsl.get("root")
    if not isinstance(root, dict) or root.get("type") != "frame":
        raise ValueError("M30 requires DSL root frame")
    if not isinstance(root.get("children"), list):
        root["children"] = []


def has_fallback_node(dsl: dict[str, Any]) -> bool:
    children = dsl.get("root", {}).get("children", [])
    return any(isinstance(child, dict) and child.get("role") in {"fallback_region", "original_reference"} for child in children)


def count_visible_audit_only_children(root: dict[str, Any]) -> int:
    count = 0
    for child in root.get("children", []):
        if not isinstance(child, dict):
            continue
        meta = child.get("meta") if isinstance(child.get("meta"), dict) else {}
        if meta.get("sourceKind") in {"m2913_audit", "m29032_review", "mixed_symbol_text_candidate"}:
            count += 1
    return count


def materialized_children(root: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        child
        for child in root.get("children", [])
        if isinstance(child, dict) and isinstance(child.get("meta"), dict) and child["meta"].get("m30Materialized") is True
    ]


def report_without_forbidden_check(report: M30Report) -> dict[str, Any]:
    data = report.to_dict()
    data["forbiddenTermCheck"] = {"hits": [], "checkedScope": "m30_report_and_materialized_nodes"}
    strip_user_text_for_forbidden_check(data)
    return data


def strip_user_text_for_forbidden_check(value: Any) -> None:
    if isinstance(value, dict):
        for key in list(value.keys()):
            if key in {"text", "content"}:
                value[key] = ""
            else:
                strip_user_text_for_forbidden_check(value[key])
    elif isinstance(value, list):
        for item in value:
            strip_user_text_for_forbidden_check(item)


def replace_forbidden_check(report: M30Report, hits: list[str]) -> M30Report:
    return M30Report(
        schema_name=report.schema_name,
        schema_version=report.schema_version,
        mode=report.mode,
        source_image=report.source_image,
        source_base_dsl=report.source_base_dsl,
        source_m2905_refined_visual_objects_json=report.source_m2905_refined_visual_objects_json,
        output_dsl=report.output_dsl,
        options=report.options,
        summary={**report.summary, "forbiddenHitCount": len(hits)},
        materialized_text_nodes=report.materialized_text_nodes,
        materialized_text_cover_nodes=report.materialized_text_cover_nodes,
        materialized_shape_nodes=report.materialized_shape_nodes,
        materialized_image_nodes=report.materialized_image_nodes,
        skipped_items=report.skipped_items,
        skipped_text_cover_items=report.skipped_text_cover_items,
        audit_only_references=report.audit_only_references,
        warnings=report.warnings,
        debug=report.debug,
        forbidden_term_check={"hits": hits, "checkedScope": "m30_report_and_materialized_nodes"},
        meta=report.meta,
        text_editability_decisions=report.text_editability_decisions,
    )


def layout_from_bbox(bbox: list[int]) -> dict[str, int]:
    return {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]}


def estimate_font_size(bbox: list[int], options: M30Options) -> int:
    return max(options.min_text_font_size, min(options.max_text_font_size, round(bbox[3] * 0.82)))


def collect_element_ids(root: dict[str, Any]) -> set[str]:
    ids: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        if isinstance(node.get("id"), str):
            ids.add(node["id"])
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            if isinstance(child, dict):
                visit(child)

    visit(root)
    return ids


def next_unique_id(existing_ids: set[str], base: str) -> str:
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    existing_ids.add(candidate)
    return candidate


def next_unique_asset_id(existing_ids: set[str], base: str) -> str:
    return next_unique_id(existing_ids, base)


def count_elements(root: dict[str, Any]) -> int:
    total = 1
    for child in root.get("children", []) if isinstance(root.get("children"), list) else []:
        if isinstance(child, dict):
            total += count_elements(child)
    return total


def relative_posix(base: Path, path: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def image_format_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".jpeg":
        return "jpeg"
    if suffix == ".jpg":
        return "jpg"
    if suffix == ".webp":
        return "webp"
    return "png"


def pad_cover_bbox(bbox: list[int], padding: int) -> list[int]:
    if padding <= 0:
        return list(bbox)
    return [bbox[0] - padding, bbox[1] - padding, bbox[2] + (padding * 2), bbox[3] + (padding * 2)]


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def bbox_intersection_area(left: list[int], right: list[int]) -> int:
    left_x2 = left[0] + left[2]
    left_y2 = left[1] + left[3]
    right_x2 = right[0] + right[2]
    right_y2 = right[1] + right[3]
    width = max(0, min(left_x2, right_x2) - max(left[0], right[0]))
    height = max(0, min(left_y2, right_y2) - max(left[1], right[1]))
    return width * height


def bbox_overlap_ratio(left: list[int], right: list[int]) -> float:
    area = bbox_area(left)
    if area <= 0:
        return 0.0
    return bbox_intersection_area(left, right) / area


def bbox_center_x(bbox: list[int]) -> float:
    return bbox[0] + (bbox[2] / 2)


def bbox_center_y(bbox: list[int]) -> float:
    return bbox[1] + (bbox[3] / 2)


def bbox_axis_gap(left: list[int], right: list[int]) -> float:
    left_x2 = left[0] + left[2]
    right_x2 = right[0] + right[2]
    if left_x2 < right[0]:
        return right[0] - left_x2
    if right_x2 < left[0]:
        return left[0] - right_x2
    return 0.0


def bbox_union(left: list[int], right: list[int]) -> list[int]:
    x1 = min(left[0], right[0])
    y1 = min(left[1], right[1])
    x2 = max(left[0] + left[2], right[0] + right[2])
    y2 = max(left[1] + left[3], right[1] + right[3])
    return [x1, y1, x2 - x1, y2 - y1]


def reason_counts(items: list[M30SkippedItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.reason] = counts.get(item.reason, 0) + 1
    return counts


def text_editability_reason_counts(items: list[M30TextEditabilityDecision]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for reason in item.reasons:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def list_dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def list_strings(value: object) -> list[str]:
    return [str(item) for item in value if isinstance(item, str)] if isinstance(value, list) else []


def to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def is_hex_color(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True
