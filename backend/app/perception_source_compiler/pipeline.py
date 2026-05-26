from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..ocr import text_boxes_from_ocr_document
from ..png_tools import UnsupportedPngCropError, decode_png_pixels, read_png_metadata
from ..source_ui_physical_graph import local_background_confidence
from ..source_ui_physical_graph.controls import source_fill_excluding_text
from ..visual_primitive_graph import measure_region
from .geometry import bbox_area, bbox_iou, containment_ratio, overlap_ratio, parse_xywh_bbox, parse_xyxy_bbox
from .types import PerceptionSourceCompilerOptions, PerceptionSourceCompilerResult
from .validation import validate_perception_source_compiler_report


def extract_perception_source_compiler_report(
    *,
    task_id: str,
    source_png: bytes,
    ocr_document: dict[str, Any] | None,
    perception_model_report: dict[str, Any],
    m292_document: dict[str, Any],
    output_dir: Path,
    options: PerceptionSourceCompilerOptions | None = None,
) -> PerceptionSourceCompilerResult:
    options = options or PerceptionSourceCompilerOptions()
    image = read_png_metadata(source_png)
    if image is None:
        raise UnsupportedPngCropError("M29 perception source compiler requires a readable PNG.")
    pixels = decode_png_pixels(source_png)
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_boxes, ocr_warnings = text_boxes_from_ocr_document(ocr_document or {"blocks": []})
    base_objects = [deepcopy(item) for item in m292_document.get("sourceObjects", []) if isinstance(item, dict)]
    compiled_objects: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []

    for candidate in normalized_candidates(perception_model_report, image.width, image.height):
        decision = classify_candidate(
            candidate=candidate,
            base_objects=base_objects,
            compiled_objects=compiled_objects,
            ocr_boxes=ocr_boxes,
            pixels=pixels,
            image_width=image.width,
            image_height=image.height,
            options=options,
        )
        if decision["mode"] == "compile_source_object":
            compiled_objects.append(decision["sourceObject"])
        else:
            rejected_candidates.append(decision["candidateDecision"])

    enhanced_document = build_enhanced_document(m292_document, base_objects + compiled_objects, len(compiled_objects))
    document_path = output_dir / "source_ui_physical_graph.perception.json"
    report_path = output_dir / "perception_source_compiler_report.json"
    report = {
        "schemaName": "M29PerceptionSourceCompilerReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "perceptionSchemaName": perception_model_report.get("schemaName"),
        "perceptionSchemaVersion": perception_model_report.get("schemaVersion"),
        "outputReport": str(report_path),
        "outputM292": str(document_path),
        "image": {"width": image.width, "height": image.height},
        "options": options.to_dict(),
        "summary": {
            "baseSourceObjectCount": len(base_objects),
            "perceptionCandidateCount": len(normalized_candidates(perception_model_report, image.width, image.height)),
            "compiledSourceObjectCount": len(compiled_objects),
            "finalSourceObjectCount": len(base_objects) + len(compiled_objects),
            "rejectedCandidateCount": len(rejected_candidates),
            "compiledControlBackgroundCount": sum(1 for item in compiled_objects if item.get("visualKind") == "control_background"),
            "compiledRasterIconCount": sum(1 for item in compiled_objects if item.get("visualKind") == "raster_icon"),
            "warningCount": len(ocr_warnings),
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "sourceOwnershipChanged": bool(compiled_objects),
        },
        "compiledSourceObjects": compiled_objects,
        "rejectedCandidates": rejected_candidates,
        "warnings": ocr_warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "source_png_plus_ocr_plus_perception_model_candidates_plus_m29_2",
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "sourceOwnershipChanged": bool(compiled_objects),
            "noSpecializedTextFilenameThemeOrFixedBboxRules": True,
        },
    }
    validate_perception_source_compiler_report(report)
    document_path.write_text(json.dumps(enhanced_document, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return PerceptionSourceCompilerResult(report=report, m292_document=enhanced_document, output_dir=output_dir)


def normalized_candidates(report: dict[str, Any], image_width: int, image_height: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(report.get("candidates", []) if isinstance(report.get("candidates"), list) else [], start=1):
        if not isinstance(item, dict):
            continue
        bbox = parse_xyxy_bbox(item.get("bbox"), image_width=image_width, image_height=image_height)
        if bbox is None:
            continue
        result.append(
            {
                "candidateId": str(item.get("candidateId") or f"perception_candidate_{index:04d}"),
                "bbox": bbox,
                "rawBbox": item.get("bbox"),
                "score": safe_float(item.get("score")),
                "areaRatio": bbox_area(bbox) / max(1, image_width * image_height),
                "sourceProvider": str(item.get("sourceProvider") or "perception_model"),
            }
        )
    return sorted(result, key=lambda item: (-item["score"], item["bbox"][1], item["bbox"][0], bbox_area(item["bbox"])))


def classify_candidate(
    *,
    candidate: dict[str, Any],
    base_objects: list[dict[str, Any]],
    compiled_objects: list[dict[str, Any]],
    ocr_boxes: list[Any],
    pixels: Any,
    image_width: int,
    image_height: int,
    options: PerceptionSourceCompilerOptions,
) -> dict[str, Any]:
    bbox = candidate["bbox"]
    score = candidate["score"]
    area_ratio = candidate["areaRatio"]
    if area_ratio >= options.max_report_only_area_ratio:
        return rejected(candidate, "large_perception_candidate_preserved_as_media_residual", bbox=bbox)

    contained_text = contained_ocr_boxes(bbox, ocr_boxes, options)
    text_area_ratio = sum(overlap_area_for_box(bbox, box) for box in contained_text) / max(1, bbox_area(bbox))
    media_parent = best_parent_media(bbox, base_objects)
    media_source_id = str(media_parent.get("id") or "") if media_parent else ""
    text_overlap = max((overlap_ratio(bbox, getattr(box, "bbox", [])) for box in ocr_boxes), default=0.0)
    metrics = measure_region(pixels, bbox)

    if overlaps_existing_replay_owner(bbox, [*base_objects, *compiled_objects], options):
        return rejected(candidate, "duplicate_or_near_equal_existing_source_object", bbox=bbox)

    if contained_text and score >= options.min_control_score and area_ratio <= options.max_control_area_ratio:
        if text_area_ratio < options.min_control_text_area_ratio or text_area_ratio > options.max_control_text_area_ratio:
            return rejected(candidate, "contained_text_area_ratio_outside_control_range", bbox=bbox)
        return {
            "mode": "compile_source_object",
            "sourceObject": build_control_background_object(
                index=len([item for item in compiled_objects if item.get("visualKind") == "control_background"]) + 1,
                candidate=candidate,
                bbox=bbox,
                ocr_boxes=contained_text,
                pixels=pixels,
                media_source_id=media_source_id,
                text_area_ratio=text_area_ratio,
                inference_reasons=["perception_candidate_contains_ocr_text"],
            ),
        }

    if score >= options.min_geometry_control_score and geometry_supports_control_background(
        bbox=bbox,
        metrics=metrics,
        image_width=image_width,
        image_height=image_height,
        options=options,
    ):
        return {
            "mode": "compile_source_object",
            "sourceObject": build_control_background_object(
                index=len([item for item in compiled_objects if item.get("visualKind") == "control_background"]) + 1,
                candidate=candidate,
                bbox=bbox,
                ocr_boxes=contained_text,
                pixels=pixels,
                media_source_id=media_source_id,
                text_area_ratio=text_area_ratio,
                inference_reasons=["perception_candidate_control_geometry"],
            ),
        }

    if score >= options.min_icon_score and area_ratio <= options.max_icon_area_ratio and text_overlap <= options.max_icon_text_overlap:
        if is_simple_indicator_shape(metrics, bbox):
            return {
                "mode": "compile_source_object",
                "sourceObject": build_indicator_shape_object(
                    index=len([item for item in compiled_objects if item.get("visualKind") == "control_background"]) + 1,
                    candidate=candidate,
                    bbox=bbox,
                    pixels=pixels,
                    media_source_id=media_source_id,
                ),
            }
        return {
            "mode": "compile_source_object",
            "sourceObject": build_raster_icon_object(
                index=len([item for item in compiled_objects if item.get("visualKind") == "raster_icon"]) + 1,
                candidate=candidate,
                bbox=bbox,
                pixels=pixels,
                media_source_id=media_source_id,
                text_overlap=text_overlap,
                inference_reasons=["perception_candidate_compact_foreground"],
                parent_control_id=None,
            ),
        }

    parent_control = parent_control_for_candidate(bbox, compiled_objects, options)
    if (
        parent_control is not None
        and score >= options.min_control_child_icon_score
        and area_ratio <= options.max_icon_area_ratio
    ):
        if text_overlap > options.max_control_child_icon_text_overlap:
            return rejected(candidate, "control_child_icon_text_overlap_risk", bbox=bbox)
        return {
            "mode": "compile_source_object",
            "sourceObject": build_raster_icon_object(
                index=len([item for item in compiled_objects if item.get("visualKind") == "raster_icon"]) + 1,
                candidate=candidate,
                bbox=bbox,
                pixels=pixels,
                media_source_id=media_source_id,
                text_overlap=text_overlap,
                inference_reasons=["perception_candidate_inside_compiled_control"],
                parent_control_id=str(parent_control.get("id") or ""),
            ),
        }

    if near_equal_media_region(bbox, base_objects, options):
        return rejected(candidate, "near_equal_parent_media_candidate", bbox=bbox)

    return rejected(candidate, "insufficient_ownership_evidence", bbox=bbox)


def build_control_background_object(
    *,
    index: int,
    candidate: dict[str, Any],
    bbox: list[int],
    ocr_boxes: list[Any],
    pixels: Any,
    media_source_id: str,
    text_area_ratio: float,
    inference_reasons: list[str],
) -> dict[str, Any]:
    fill = source_fill_excluding_text(pixels, bbox, ocr_boxes)
    radius = inferred_radius(bbox, role="control")
    return source_object(
        object_id=f"m292_perception_control_{index:04d}",
        bbox=bbox,
        visual_kind="control_background",
        pixel_owner="shape_geometry",
        replay_decision="shape_replay",
        confidence="high",
        reasons=[*inference_reasons, "compiled_before_m29_replay"],
        risks=["model_single_class_role_inferred_from_geometry_and_text"],
        evidence={
            **common_evidence(candidate, bbox, pixels, media_source_id),
            "ocrBoxIds": [str(box.id) for box in ocr_boxes if getattr(box, "id", None)],
            "promotionSource": "perception_model_foreground_claim",
            "foregroundClaimId": f"{candidate['candidateId']}:foreground_claim",
            "claimMaskKind": "rounded_rect",
            "internalRole": "internal_control_background",
            "shapeFillOverride": fill,
            "shapeRadiusOverride": radius,
            "controlTextAreaRatio": round(text_area_ratio, 4),
            "controlInferenceReasons": inference_reasons,
        },
    )


def build_indicator_shape_object(*, index: int, candidate: dict[str, Any], bbox: list[int], pixels: Any, media_source_id: str) -> dict[str, Any]:
    radius = inferred_radius(bbox, role="indicator")
    return source_object(
        object_id=f"m292_perception_shape_{index:04d}",
        bbox=bbox,
        visual_kind="control_background",
        pixel_owner="shape_geometry",
        replay_decision="shape_replay",
        confidence="medium",
        reasons=["perception_candidate_simple_indicator_shape", "compiled_before_m29_replay"],
        risks=["model_single_class_role_inferred_from_pixel_stability"],
        evidence={
            **common_evidence(candidate, bbox, pixels, media_source_id),
            "promotionSource": "perception_model_foreground_claim",
            "foregroundClaimId": f"{candidate['candidateId']}:foreground_claim",
            "claimMaskKind": "circle" if abs(bbox[2] - bbox[3]) <= max(2, round(min(bbox[2], bbox[3]) * 0.18)) else "rounded_rect",
            "internalRole": "internal_circle_control" if abs(bbox[2] - bbox[3]) <= max(2, round(min(bbox[2], bbox[3]) * 0.18)) else "selected_marker_candidate",
            "shapeFillOverride": source_fill_excluding_text(pixels, bbox, []),
            **({"shapeRadiusOverride": radius} if radius is not None else {}),
        },
    )


def build_raster_icon_object(
    *,
    index: int,
    candidate: dict[str, Any],
    bbox: list[int],
    pixels: Any,
    media_source_id: str,
    text_overlap: float,
    inference_reasons: list[str],
    parent_control_id: str | None,
) -> dict[str, Any]:
    return source_object(
        object_id=f"m292_perception_icon_{index:04d}",
        bbox=bbox,
        visual_kind="raster_icon",
        pixel_owner="raster_icon",
        replay_decision="icon_replay",
        confidence="medium",
        reasons=[*inference_reasons, "compiled_before_m29_replay"],
        risks=["source_crop_icon_without_transparent_asset"],
        evidence={
            **common_evidence(candidate, bbox, pixels, media_source_id),
            "promotionSource": "perception_model_foreground_claim",
            "foregroundClaimId": f"{candidate['candidateId']}:foreground_claim",
            "claimMaskKind": "bbox",
            "internalRole": "internal_icon_candidate",
            "textOverlapRatio": round(text_overlap, 4),
            "controlRowSourceCropEligible": True,
            "iconInferenceReasons": inference_reasons,
            **({"parentControlSourceObjectId": parent_control_id} if parent_control_id else {}),
        },
    )


def source_object(
    *,
    object_id: str,
    bbox: list[int],
    visual_kind: str,
    pixel_owner: str,
    replay_decision: str,
    confidence: str,
    reasons: list[str],
    risks: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": evidence,
        "confidence": confidence,
        "reasons": reasons,
        "risks": risks,
    }


def common_evidence(candidate: dict[str, Any], bbox: list[int], pixels: Any, media_source_id: str) -> dict[str, Any]:
    return {
        "ocrBoxIds": [],
        "m29NodeIds": [],
        "blockedIds": [],
        "perceptionCandidateId": candidate["candidateId"],
        "perceptionProvider": candidate["sourceProvider"],
        "candidateBbox": bbox,
        "modelScore": round(candidate["score"], 6),
        "evidenceScore": round(candidate["score"], 6),
        "areaRatio": round(candidate["areaRatio"], 6),
        "localBackgroundConfidence": round(local_background_confidence(pixels, bbox), 4),
        "mediaSourceObjectId": media_source_id,
    }


def contained_ocr_boxes(bbox: list[int], ocr_boxes: list[Any], options: PerceptionSourceCompilerOptions) -> list[Any]:
    result = []
    for box in ocr_boxes:
        text_bbox = parse_xywh_bbox(getattr(box, "bbox", None))
        if text_bbox is None:
            continue
        text = str(getattr(box, "text", "") or "").strip()
        if not text:
            continue
        if containment_ratio(text_bbox, bbox) >= options.min_text_containment:
            result.append(box)
    return result


def overlap_area_for_box(bbox: list[int], box: Any) -> int:
    text_bbox = parse_xywh_bbox(getattr(box, "bbox", None))
    if text_bbox is None:
        return 0
    from .geometry import intersection_area

    return intersection_area(bbox, text_bbox)


def best_parent_media(bbox: list[int], objects: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = []
    for item in objects:
        if item.get("visualKind") != "media_region" or item.get("pixelOwner") != "preserve_raster":
            continue
        media_bbox = parse_xywh_bbox(item.get("bbox"))
        if media_bbox is None:
            continue
        ratio = containment_ratio(bbox, media_bbox)
        if ratio >= 0.85:
            matches.append((ratio, bbox_area(media_bbox), item))
    if not matches:
        return None
    return sorted(matches, key=lambda value: (-value[0], value[1]))[0][2]


def overlaps_existing_replay_owner(bbox: list[int], objects: list[dict[str, Any]], options: PerceptionSourceCompilerOptions) -> bool:
    for item in objects:
        if item.get("replayDecision") in {"preserve_in_parent_raster", "skip"}:
            continue
        if item.get("visualKind") == "media_region" and item.get("pixelOwner") == "preserve_raster":
            continue
        existing_bbox = parse_xywh_bbox(item.get("bbox"))
        if existing_bbox is None:
            continue
        if bbox_iou(bbox, existing_bbox) >= options.duplicate_iou_threshold:
            return True
    return False


def near_equal_media_region(bbox: list[int], objects: list[dict[str, Any]], options: PerceptionSourceCompilerOptions) -> bool:
    for item in objects:
        if item.get("visualKind") != "media_region":
            continue
        media_bbox = parse_xywh_bbox(item.get("bbox"))
        if media_bbox is not None and bbox_iou(bbox, media_bbox) >= options.media_near_equal_iou_threshold:
            return True
    return False


def parent_control_for_candidate(bbox: list[int], objects: list[dict[str, Any]], options: PerceptionSourceCompilerOptions) -> dict[str, Any] | None:
    matches: list[tuple[float, int, dict[str, Any]]] = []
    for item in objects:
        if item.get("visualKind") != "control_background" or item.get("pixelOwner") != "shape_geometry":
            continue
        control_bbox = parse_xywh_bbox(item.get("bbox"))
        if control_bbox is None:
            continue
        ratio = containment_ratio(bbox, control_bbox)
        if ratio < options.min_control_child_containment:
            continue
        matches.append((ratio, bbox_area(control_bbox), item))
    if not matches:
        return None
    return sorted(matches, key=lambda value: (-value[0], value[1]))[0][2]


def geometry_supports_control_background(
    *,
    bbox: list[int],
    metrics: Any,
    image_width: int,
    image_height: int,
    options: PerceptionSourceCompilerOptions,
) -> bool:
    area_ratio = bbox_area(bbox) / max(1, image_width * image_height)
    if area_ratio < options.min_geometry_control_area_ratio or area_ratio > options.max_control_area_ratio:
        return False
    aspect = bbox[2] / max(1, bbox[3])
    if aspect < options.min_control_aspect_ratio or aspect > options.max_control_aspect_ratio:
        return False
    if bbox[2] < round(image_width * options.min_control_width_ratio):
        return False
    if bbox[3] < round(image_height * options.min_control_height_ratio):
        return False
    if bbox[3] > round(image_height * options.max_control_height_ratio):
        return False
    fill_ratio = float(getattr(metrics, "fill_ratio", 0.0))
    texture_score = float(getattr(metrics, "texture_score", 1.0))
    edge_score = float(getattr(metrics, "edge_score", 1.0))
    return (
        fill_ratio >= options.min_geometry_control_fill_ratio
        and texture_score <= options.max_geometry_control_texture_score
        and edge_score <= options.max_geometry_control_edge_score
    )


def is_simple_indicator_shape(metrics: Any, bbox: list[int]) -> bool:
    color_count = int(getattr(metrics, "color_count", 999))
    texture_score = float(getattr(metrics, "texture_score", 1.0))
    edge_score = float(getattr(metrics, "edge_score", 1.0))
    aspect = bbox[2] / max(1, bbox[3])
    long_marker = aspect >= 3.0 or aspect <= 0.34
    tiny_dot = max(bbox[2], bbox[3]) <= 14 and 0.55 <= aspect <= 1.82
    stable_fill = color_count <= 16 and texture_score <= 0.18
    return stable_fill and (long_marker or tiny_dot)


def inferred_radius(bbox: list[int], *, role: str) -> int | None:
    if role == "indicator" and abs(bbox[2] - bbox[3]) <= max(2, round(min(bbox[2], bbox[3]) * 0.18)):
        return min(bbox[2], bbox[3]) // 2
    if role == "control" and bbox[2] / max(1, bbox[3]) >= 1.6:
        return min(bbox[2], bbox[3]) // 2
    return None


def rejected(candidate: dict[str, Any], reason: str, *, bbox: list[int]) -> dict[str, Any]:
    return {
        "mode": "report_only",
        "candidateDecision": {
            "candidateId": candidate["candidateId"],
            "bbox": bbox,
            "score": round(candidate["score"], 6),
            "reason": reason,
        },
    }


def build_enhanced_document(source_document: dict[str, Any], objects: list[dict[str, Any]], compiled_count: int) -> dict[str, Any]:
    document = deepcopy(source_document)
    document["sourceObjects"] = objects
    summary = dict(document.get("summary") if isinstance(document.get("summary"), dict) else {})
    summary["sourceObjectCount"] = len(objects)
    summary["perceptionCompiledSourceObjectCount"] = compiled_count
    document["summary"] = summary
    meta = dict(document.get("meta") if isinstance(document.get("meta"), dict) else {})
    meta["perceptionSourceCompilerApplied"] = compiled_count > 0
    meta["sourceOwnershipChangedByPerceptionCompiler"] = compiled_count > 0
    document["meta"] = meta
    return document


def safe_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
