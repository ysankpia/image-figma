from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..ocr import text_boxes_from_ocr_document
from ..png_tools import UnsupportedPngCropError, decode_png_pixels, read_png_metadata
from ..source_ui_physical_graph import local_background_confidence
from ..source_ui_physical_graph.controls import radius_from_control_pixels, source_fill_excluding_text
from ..visual_primitive_graph import measure_region
from .geometry import bbox_area, bbox_iou, containment_ratio, intersection_area, overlap_ratio, parse_xywh_bbox, parse_xyxy_bbox, x2, y2
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

    candidates = normalized_candidates(perception_model_report, image.width, image.height)
    for candidate in candidates:
        decision = classify_candidate(
            candidate=candidate,
            all_candidates=candidates,
            base_objects=base_objects,
            compiled_objects=compiled_objects,
            ocr_boxes=ocr_boxes,
            pixels=pixels,
            image_width=image.width,
            image_height=image.height,
            options=options,
        )
        if decision["mode"] == "compile_source_object":
            compiled_objects.extend(source_objects_from_decision(decision))
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
            "perceptionCandidateCount": len(candidates),
            "compiledSourceObjectCount": len(compiled_objects),
            "finalSourceObjectCount": len(base_objects) + len(compiled_objects),
            "rejectedCandidateCount": len(rejected_candidates),
            "compiledControlBackgroundCount": sum(1 for item in compiled_objects if item.get("visualKind") == "control_background"),
            "compiledControlImageCount": sum(
                1
                for item in compiled_objects
                if item.get("visualKind") == "media_region"
                and (item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}).get("internalRole")
                == "internal_control_raster_background"
            ),
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


def source_objects_from_decision(decision: dict[str, Any]) -> list[dict[str, Any]]:
    items = decision.get("sourceObjects")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    item = decision.get("sourceObject")
    return [item] if isinstance(item, dict) else []


def classify_candidate(
    *,
    candidate: dict[str, Any],
    all_candidates: list[dict[str, Any]],
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
        if content_region_too_large_for_text_control(
            bbox=bbox,
            text_count=len(contained_text),
            area_ratio=area_ratio,
            contained_text=contained_text,
            image_height=image_height,
            options=options,
        ):
            vertical_icon = build_inferred_vertical_label_icon_object(
                index=len([item for item in compiled_objects if item.get("visualKind") == "raster_icon"]) + 1,
                candidate=candidate,
                tile_bbox=bbox,
                ocr_boxes=contained_text,
                pixels=pixels,
                media_source_id=media_source_id,
                options=options,
            )
            if vertical_icon is not None:
                return {
                    "mode": "compile_source_object",
                    "sourceObject": vertical_icon,
                }
            if geometry_supports_control_background(
                bbox=bbox,
                metrics=metrics,
                image_width=image_width,
                image_height=image_height,
                options=options,
            ):
                return {
                    "mode": "compile_source_object",
                    "sourceObject": build_control_image_object(
                        index=len([item for item in compiled_objects if item.get("visualKind") == "media_region"]) + 1,
                        candidate=candidate,
                        bbox=bbox,
                        ocr_boxes=contained_text,
                        pixels=pixels,
                        media_source_id=media_source_id,
                        text_area_ratio=text_area_ratio,
                        inference_reasons=["perception_candidate_complex_text_control_raster_crop"],
                    ),
                }
            return rejected(candidate, "content_region_too_large_for_control_background", bbox=bbox)
        if text_area_ratio < options.min_control_text_area_ratio or text_area_ratio > options.max_control_text_area_ratio:
            return rejected(candidate, "contained_text_area_ratio_outside_control_range", bbox=bbox)
        object_index = len([item for item in compiled_objects if item.get("visualKind") == "control_background"]) + 1
        control = build_control_background_object(
            index=object_index,
            candidate=candidate,
            bbox=bbox,
            ocr_boxes=contained_text,
            pixels=pixels,
            media_source_id=media_source_id,
            text_area_ratio=text_area_ratio,
            inference_reasons=["perception_candidate_contains_ocr_text"],
        )
        derived = build_inferred_leading_icon_object(
            index=len([item for item in compiled_objects if item.get("visualKind") == "raster_icon"]) + 1,
            candidate=candidate,
            all_candidates=all_candidates,
            control_bbox=bbox,
            control_object_id=str(control.get("id") or ""),
            ocr_boxes=contained_text,
            pixels=pixels,
            media_source_id=media_source_id,
            options=options,
        )
        return {
            "mode": "compile_source_object",
            "sourceObjects": [control, *([derived] if derived is not None else [])],
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
        if not control_child_icon_has_safe_geometry(bbox, parent_control, ocr_boxes, text_overlap, options):
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

    vertical_icon = build_inferred_vertical_label_icon_object(
        index=len([item for item in compiled_objects if item.get("visualKind") == "raster_icon"]) + 1,
        candidate=candidate,
        tile_bbox=bbox,
        ocr_boxes=contained_text,
        pixels=pixels,
        media_source_id=media_source_id,
        options=options,
    )
    if vertical_icon is not None:
        return {
            "mode": "compile_source_object",
            "sourceObject": vertical_icon,
        }

    if supports_selectable_raster_crop_fallback(
        candidate=candidate,
        bbox=bbox,
        score=score,
        area_ratio=area_ratio,
        text_overlap=text_overlap,
        contained_text=contained_text,
        metrics=metrics,
        existing_objects=[*base_objects, *compiled_objects],
        options=options,
    ):
        return {
            "mode": "compile_source_object",
            "sourceObject": build_selectable_raster_crop_object(
                index=len(
                    [
                        item
                        for item in compiled_objects
                        if item.get("visualKind") == "media_region"
                        and (item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}).get("internalRole")
                        == "internal_selectable_raster_crop"
                    ]
                )
                + 1,
                candidate=candidate,
                bbox=bbox,
                pixels=pixels,
                media_source_id=media_source_id,
                contained_text=contained_text,
                text_overlap=text_overlap,
                inference_reasons=["perception_candidate_selectable_raster_crop_fallback"],
            ),
        }

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
    radius = radius_from_control_pixels(pixels, bbox, ocr_boxes)
    claim_mask_kind = "rounded_rect" if radius is not None else "bbox"
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
            "claimMaskKind": claim_mask_kind,
            "internalRole": "internal_control_background",
            "shapeFillOverride": fill,
            "shapeGeometryKind": control_geometry_kind(bbox, radius),
            "shapeGeometryConfidence": "high" if radius is not None else "medium",
            **({"shapeRadiusOverride": radius} if radius is not None else {}),
            "controlTextAreaRatio": round(text_area_ratio, 4),
            "controlInferenceReasons": inference_reasons,
        },
    )


def build_control_image_object(
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
    return source_object(
        object_id=f"m292_perception_control_image_{index:04d}",
        bbox=bbox,
        visual_kind="media_region",
        pixel_owner="preserve_raster",
        replay_decision="image_replay",
        confidence="medium",
        reasons=[*inference_reasons, "compiled_before_m29_replay"],
        risks=["model_single_class_complex_control_kept_as_selectable_raster"],
        evidence={
            **common_evidence(candidate, bbox, pixels, media_source_id),
            "ocrBoxIds": [str(box.id) for box in ocr_boxes if getattr(box, "id", None)],
            "promotionSource": "perception_model_foreground_claim",
            "foregroundClaimId": f"{candidate['candidateId']}:foreground_claim",
            "claimMaskKind": "bbox",
            "internalRole": "internal_control_raster_background",
            "controlTextAreaRatio": round(text_area_ratio, 4),
            "controlInferenceReasons": inference_reasons,
        },
    )


def build_selectable_raster_crop_object(
    *,
    index: int,
    candidate: dict[str, Any],
    bbox: list[int],
    pixels: Any,
    media_source_id: str,
    contained_text: list[Any],
    text_overlap: float,
    inference_reasons: list[str],
) -> dict[str, Any]:
    return source_object(
        object_id=f"m292_perception_selectable_crop_{index:04d}",
        bbox=bbox,
        visual_kind="media_region",
        pixel_owner="preserve_raster",
        replay_decision="image_replay",
        confidence="medium",
        reasons=[*inference_reasons, "compiled_before_m29_replay"],
        risks=[
            "model_single_class_low_risk_candidate_kept_as_selectable_raster",
            "not_vectorized_yet",
        ],
        evidence={
            **common_evidence(candidate, bbox, pixels, media_source_id),
            "ocrBoxIds": [str(box.id) for box in contained_text if getattr(box, "id", None)],
            "promotionSource": "perception_model_foreground_claim",
            "foregroundClaimId": f"{candidate['candidateId']}:foreground_claim",
            "claimMaskKind": "bbox",
            "internalRole": "internal_selectable_raster_crop",
            "textOverlapRatio": round(text_overlap, 4),
            "cleanupEligible": False,
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
    extra_evidence: dict[str, Any] | None = None,
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
            **(extra_evidence or {}),
        },
    )


def build_inferred_leading_icon_object(
    *,
    index: int,
    candidate: dict[str, Any],
    all_candidates: list[dict[str, Any]],
    control_bbox: list[int],
    control_object_id: str,
    ocr_boxes: list[Any],
    pixels: Any,
    media_source_id: str,
    options: PerceptionSourceCompilerOptions,
) -> dict[str, Any] | None:
    if not ocr_boxes:
        return None
    leftmost_text = min(
        (parse_xywh_bbox(getattr(box, "bbox", None)) for box in ocr_boxes),
        key=lambda bbox: bbox[0] if bbox is not None else 10**9,
        default=None,
    )
    if leftmost_text is None:
        return None
    if candidate_contains_real_child_icon(candidate, all_candidates, leftmost_text, options):
        return None
    roi = leading_icon_search_bbox(control_bbox, leftmost_text)
    if roi is None:
        return None
    icon_bbox = foreground_component_bbox_in_roi(
        pixels=pixels,
        roi=roi,
        control_bbox=control_bbox,
        text_bbox=leftmost_text,
        options=options,
    )
    if icon_bbox is None:
        return None
    return build_raster_icon_object(
        index=index,
        candidate={
            **candidate,
            "candidateId": f"{candidate['candidateId']}:leading_icon",
            "bbox": icon_bbox,
            "areaRatio": bbox_area(icon_bbox) / max(1, pixels.width * pixels.height),
        },
        bbox=icon_bbox,
        pixels=pixels,
        media_source_id=media_source_id,
        text_overlap=0.0,
        inference_reasons=["inferred_leading_icon_inside_compiled_control"],
        parent_control_id=control_object_id,
        extra_evidence={
            "derivedFromPerceptionCandidateId": candidate["candidateId"],
            "leadingIconSource": "control_pixels_left_of_ocr_text",
        },
    )


def build_inferred_vertical_label_icon_object(
    *,
    index: int,
    candidate: dict[str, Any],
    tile_bbox: list[int],
    ocr_boxes: list[Any],
    pixels: Any,
    media_source_id: str,
    options: PerceptionSourceCompilerOptions,
) -> dict[str, Any] | None:
    if len(ocr_boxes) != options.max_vertical_label_tile_ocr_count:
        return None
    text_bbox = parse_xywh_bbox(getattr(ocr_boxes[0], "bbox", None))
    if text_bbox is None:
        return None
    text_top_gap = text_bbox[1] - tile_bbox[1]
    if text_top_gap < round(tile_bbox[3] * options.min_vertical_label_gap_ratio):
        return None
    side_pad = max(4, round(text_bbox[3] * 0.45))
    vertical_gap = max(3, round(text_bbox[3] * 0.18))
    roi_left = max(tile_bbox[0], text_bbox[0] - max(text_bbox[2], text_bbox[3]) - side_pad)
    roi_right = min(x2(tile_bbox), x2(text_bbox) + max(text_bbox[2], text_bbox[3]) + side_pad)
    roi_top = tile_bbox[1] + max(2, round(tile_bbox[3] * 0.08))
    roi_bottom = text_bbox[1] - vertical_gap
    if roi_right <= roi_left or roi_bottom <= roi_top:
        return None
    roi = [roi_left, roi_top, roi_right - roi_left, roi_bottom - roi_top]
    icon_bbox = foreground_component_bbox_in_roi(
        pixels=pixels,
        roi=roi,
        control_bbox=tile_bbox,
        text_bbox=text_bbox,
        options=options,
        axis="vertical",
    )
    if icon_bbox is None:
        return None
    width_ratio = icon_bbox[2] / max(1, text_bbox[2])
    if width_ratio < options.min_vertical_icon_text_width_ratio or width_ratio > options.max_vertical_icon_text_width_ratio:
        return None
    icon_center_x = icon_bbox[0] + icon_bbox[2] / 2
    text_center_x = text_bbox[0] + text_bbox[2] / 2
    if abs(icon_center_x - text_center_x) > max(text_bbox[2], icon_bbox[2]) * 0.75:
        return None
    return build_raster_icon_object(
        index=index,
        candidate={
            **candidate,
            "candidateId": f"{candidate['candidateId']}:vertical_label_icon",
            "bbox": icon_bbox,
            "areaRatio": bbox_area(icon_bbox) / max(1, pixels.width * pixels.height),
        },
        bbox=icon_bbox,
        pixels=pixels,
        media_source_id=media_source_id,
        text_overlap=0.0,
        inference_reasons=["inferred_icon_above_ocr_label_inside_model_tile"],
        parent_control_id=None,
        extra_evidence={
            "derivedFromPerceptionCandidateId": candidate["candidateId"],
            "labelAnchorOcrBoxId": str(getattr(ocr_boxes[0], "id", "") or ""),
            "verticalIconSource": "tile_pixels_above_ocr_label",
        },
    )


def candidate_contains_real_child_icon(
    candidate: dict[str, Any],
    all_candidates: list[dict[str, Any]],
    text_bbox: list[int],
    options: PerceptionSourceCompilerOptions,
) -> bool:
    parent_bbox = candidate["bbox"]
    parent_id = candidate["candidateId"]
    for item in all_candidates:
        if item["candidateId"] == parent_id:
            continue
        bbox = item["bbox"]
        is_left_of_text = x2(bbox) <= text_bbox[0] + max(3, round(text_bbox[3] * 0.45))
        if (
            is_left_of_text
            and child_icon_text_overlap_is_safe(bbox, [text_bbox], options)
            and containment_ratio(bbox, parent_bbox) >= 0.82
            and bbox_area(bbox) <= bbox_area(parent_bbox) * 0.32
        ):
            return True
    return False


def child_icon_text_overlap_is_safe(bbox: list[int], text_bboxes: list[list[int]], options: PerceptionSourceCompilerOptions) -> bool:
    text_overlap = max((overlap_ratio(bbox, text_bbox) for text_bbox in text_bboxes), default=0.0)
    if text_overlap <= options.max_control_child_icon_text_overlap:
        return True
    if text_overlap > options.max_control_child_icon_edge_text_overlap:
        return False
    shrink_x = max(1, round(bbox[2] * 0.18))
    shrink_y = max(1, round(bbox[3] * 0.18))
    center_bbox = [bbox[0] + shrink_x, bbox[1] + shrink_y, max(1, bbox[2] - shrink_x * 2), max(1, bbox[3] - shrink_y * 2)]
    center_overlap = max((overlap_ratio(center_bbox, text_bbox) for text_bbox in text_bboxes), default=0.0)
    return center_overlap <= options.max_control_child_icon_center_text_overlap


def leading_icon_search_bbox(control_bbox: list[int], text_bbox: list[int]) -> list[int] | None:
    gap = text_bbox[0] - control_bbox[0]
    if gap <= max(8, round(text_bbox[3] * 0.75)):
        return None
    pad_y = max(3, round(text_bbox[3] * 0.85))
    inner_pad_x = max(4, round(control_bbox[3] * 0.28))
    inner_pad_y = max(3, round(control_bbox[3] * 0.12))
    left = control_bbox[0] + inner_pad_x
    right = text_bbox[0] - max(3, round(text_bbox[3] * 0.22))
    top = max(control_bbox[1] + inner_pad_y, text_bbox[1] - pad_y)
    bottom = min(y2(control_bbox) - inner_pad_y, y2(text_bbox) + pad_y)
    if right <= left or bottom <= top:
        return None
    return [left, top, right - left, bottom - top]


def foreground_component_bbox_in_roi(
    *,
    pixels: Any,
    roi: list[int],
    control_bbox: list[int],
    text_bbox: list[int],
    options: PerceptionSourceCompilerOptions,
    axis: str = "leading",
) -> list[int] | None:
    bg = dominant_border_rgb(pixels, control_bbox)
    components = contrast_components(
        pixels=pixels,
        roi=roi,
        bg=bg,
        threshold=options.min_inferred_leading_icon_contrast,
        min_area=options.min_inferred_leading_icon_area,
    )
    if not components:
        return None
    max_edge = max(6, round(text_bbox[3] * options.max_inferred_leading_icon_text_height_ratio))
    scored: list[tuple[float, list[int]]] = []
    text_center_x = text_bbox[0] + text_bbox[2] / 2
    text_center_y = text_bbox[1] + text_bbox[3] / 2
    for component in components:
        bbox = component["bbox"]
        if bbox[2] > max_edge or bbox[3] > max_edge:
            continue
        aspect_ratio = bbox[2] / max(1, bbox[3])
        if (
            aspect_ratio < options.min_inferred_leading_icon_aspect_ratio
            or aspect_ratio > options.max_inferred_leading_icon_aspect_ratio
        ):
            continue
        if bbox[2] < 3 or bbox[3] < 3:
            continue
        fill_ratio = component["area"] / max(1, bbox_area(bbox))
        if fill_ratio < options.min_inferred_leading_icon_fill_ratio:
            continue
        if intersection_area(bbox, text_bbox) > 0:
            continue
        center_x = bbox[0] + bbox[2] / 2
        center_y = bbox[1] + bbox[3] / 2
        if axis == "vertical":
            align_score = 1.0 / (1.0 + abs(center_x - text_center_x) / max(1, text_bbox[2]))
            position_bonus = 1.0 if center_y < text_bbox[1] else 0.0
        else:
            align_score = 1.0 / (1.0 + abs(center_y - text_center_y) / max(1, text_bbox[3]))
            position_bonus = 0.0
        size_score = min(1.0, (bbox[2] * bbox[3]) / max(1, text_bbox[3] * text_bbox[3]))
        scored.append((align_score + size_score + fill_ratio + position_bonus, bbox))
    if not scored:
        return None
    return sorted(scored, key=lambda item: (-item[0], item[1][0]))[0][1]


def dominant_border_rgb(pixels: Any, bbox: list[int]) -> tuple[int, int, int]:
    samples: list[tuple[int, int, int]] = []
    x, y, width, height = bbox
    for row_idx in {max(0, y), max(0, min(pixels.height - 1, y + height - 1))}:
        row = pixels.rows[row_idx]
        for col in range(max(0, x), min(pixels.width, x + width), max(1, width // 24)):
            offset = col * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    for col in {max(0, x), max(0, min(pixels.width - 1, x + width - 1))}:
        for row_idx in range(max(0, y), min(pixels.height, y + height), max(1, height // 12)):
            row = pixels.rows[row_idx]
            offset = col * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    if not samples:
        return (255, 255, 255)
    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for rgb in samples:
        buckets.setdefault((rgb[0] // 16, rgb[1] // 16, rgb[2] // 16), []).append(rgb)
    best = max(buckets.values(), key=len)
    return (
        round(sum(item[0] for item in best) / len(best)),
        round(sum(item[1] for item in best) / len(best)),
        round(sum(item[2] for item in best) / len(best)),
    )


def contrast_components(
    *,
    pixels: Any,
    roi: list[int],
    bg: tuple[int, int, int],
    threshold: int,
    min_area: int,
) -> list[dict[str, Any]]:
    x, y, width, height = roi
    visited: set[tuple[int, int]] = set()
    components: list[dict[str, Any]] = []
    for row_idx in range(y, y + height):
        for col in range(x, x + width):
            point = (col, row_idx)
            if point in visited or not is_foreground_pixel(pixels, col, row_idx, bg, threshold):
                continue
            stack = [point]
            visited.add(point)
            points: list[tuple[int, int]] = []
            while stack:
                current_x, current_y = stack.pop()
                points.append((current_x, current_y))
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    next_point = (next_x, next_y)
                    if (
                        next_x < x
                        or next_x >= x + width
                        or next_y < y
                        or next_y >= y + height
                        or next_point in visited
                        or not is_foreground_pixel(pixels, next_x, next_y, bg, threshold)
                    ):
                        continue
                    visited.add(next_point)
                    stack.append(next_point)
            if len(points) < min_area:
                continue
            left = min(item[0] for item in points)
            top = min(item[1] for item in points)
            right = max(item[0] for item in points) + 1
            bottom = max(item[1] for item in points) + 1
            components.append({"bbox": [left, top, right - left, bottom - top], "area": len(points)})
    return components


def is_foreground_pixel(pixels: Any, x: int, y: int, bg: tuple[int, int, int], threshold: int) -> bool:
    row = pixels.rows[y]
    offset = x * 3
    rgb = (row[offset], row[offset + 1], row[offset + 2])
    return abs(rgb[0] - bg[0]) + abs(rgb[1] - bg[1]) + abs(rgb[2] - bg[2]) >= threshold


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
        if not is_compiled_control_parent(item):
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


def control_child_icon_has_safe_geometry(
    bbox: list[int],
    parent_control: dict[str, Any],
    ocr_boxes: list[Any],
    text_overlap: float,
    options: PerceptionSourceCompilerOptions,
) -> bool:
    control_bbox = parse_xywh_bbox(parent_control.get("bbox"))
    if control_bbox is None:
        return False
    if bbox[2] > round(control_bbox[2] * options.max_control_child_icon_width_ratio):
        return False
    if bbox[3] > round(control_bbox[3] * options.max_control_child_icon_height_ratio):
        return False
    if text_overlap <= options.max_control_child_icon_text_overlap:
        return True
    if text_overlap > options.max_control_child_icon_edge_text_overlap:
        return False
    shrink_x = max(1, round(bbox[2] * 0.18))
    shrink_y = max(1, round(bbox[3] * 0.18))
    center_bbox = [bbox[0] + shrink_x, bbox[1] + shrink_y, max(1, bbox[2] - shrink_x * 2), max(1, bbox[3] - shrink_y * 2)]
    center_overlap = max((overlap_ratio(center_bbox, getattr(box, "bbox", [])) for box in ocr_boxes), default=0.0)
    return center_overlap <= options.max_control_child_icon_center_text_overlap


def is_compiled_control_parent(item: dict[str, Any]) -> bool:
    if item.get("visualKind") == "control_background" and item.get("pixelOwner") == "shape_geometry":
        return True
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    return (
        item.get("visualKind") == "media_region"
        and item.get("pixelOwner") == "preserve_raster"
        and item.get("replayDecision") == "image_replay"
        and evidence.get("promotionSource") == "perception_model_foreground_claim"
        and evidence.get("internalRole") == "internal_control_raster_background"
    )


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


def content_region_too_large_for_text_control(
    *,
    bbox: list[int],
    text_count: int,
    area_ratio: float,
    contained_text: list[Any],
    image_height: int,
    options: PerceptionSourceCompilerOptions,
) -> bool:
    if text_count > options.max_text_control_ocr_count:
        return True
    text_heights = []
    for box in contained_text:
        text_bbox = parse_xywh_bbox(getattr(box, "bbox", None))
        if text_bbox is not None:
            text_heights.append(text_bbox[3])
    median_text_height = sorted(text_heights)[len(text_heights) // 2] if text_heights else 0
    if median_text_height > 0 and bbox[3] > round(median_text_height * options.max_text_control_height_to_text_height):
        return True
    return False


def is_simple_indicator_shape(metrics: Any, bbox: list[int]) -> bool:
    color_count = int(getattr(metrics, "color_count", 999))
    texture_score = float(getattr(metrics, "texture_score", 1.0))
    edge_score = float(getattr(metrics, "edge_score", 1.0))
    aspect = bbox[2] / max(1, bbox[3])
    long_marker = aspect >= 3.0 or aspect <= 0.34
    tiny_dot = max(bbox[2], bbox[3]) <= 14 and 0.55 <= aspect <= 1.82
    stable_fill = color_count <= 16 and texture_score <= 0.18
    return stable_fill and (long_marker or tiny_dot)


def supports_selectable_raster_crop_fallback(
    *,
    candidate: dict[str, Any],
    bbox: list[int],
    score: float,
    area_ratio: float,
    text_overlap: float,
    contained_text: list[Any],
    metrics: Any,
    existing_objects: list[dict[str, Any]],
    options: PerceptionSourceCompilerOptions,
) -> bool:
    if area_ratio < options.min_selectable_raster_crop_area_ratio:
        return False
    if area_ratio > options.max_selectable_raster_crop_area_ratio:
        return False
    if overlaps_specific_replay_owner(bbox, existing_objects, options):
        return False
    if len(contained_text) > options.max_selectable_raster_crop_ocr_count:
        return False
    if text_overlap > options.max_selectable_raster_crop_text_overlap and not contained_text:
        return False
    if contained_text:
        if score < options.min_selectable_text_raster_crop_score:
            return False
        if not candidate_expands_beyond_text(bbox, contained_text, options):
            return False
    elif score < options.min_selectable_raster_crop_score:
        return False
    if bbox[2] < 3 or bbox[3] < 3:
        return False
    return has_nontrivial_visual_signal(metrics)


def overlaps_specific_replay_owner(bbox: list[int], objects: list[dict[str, Any]], options: PerceptionSourceCompilerOptions) -> bool:
    for item in objects:
        if item.get("replayDecision") not in {"shape_replay", "icon_replay"}:
            continue
        existing_bbox = parse_xywh_bbox(item.get("bbox"))
        if existing_bbox is None:
            continue
        if overlap_ratio(existing_bbox, bbox) > options.max_selectable_raster_crop_specific_owner_overlap:
            return True
    return False


def candidate_expands_beyond_text(bbox: list[int], contained_text: list[Any], options: PerceptionSourceCompilerOptions) -> bool:
    text_boxes = [parse_xywh_bbox(getattr(box, "bbox", None)) for box in contained_text]
    valid_boxes = [box for box in text_boxes if box is not None]
    if not valid_boxes:
        return True
    text_union = union_bbox(valid_boxes)
    if bbox_area(bbox) < bbox_area(text_union) * options.min_selectable_text_crop_area_expansion:
        return False
    vertical_padding = (bbox[3] - text_union[3]) / max(1, text_union[3])
    horizontal_padding = (bbox[2] - text_union[2]) / max(1, text_union[2])
    return vertical_padding >= 0.18 or horizontal_padding >= 0.18


def union_bbox(boxes: list[list[int]]) -> list[int]:
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(x2(box) for box in boxes)
    bottom = max(y2(box) for box in boxes)
    return [left, top, right - left, bottom - top]


def has_nontrivial_visual_signal(metrics: Any) -> bool:
    color_count = int(getattr(metrics, "color_count", 0))
    texture_score = float(getattr(metrics, "texture_score", 0.0))
    edge_score = float(getattr(metrics, "edge_score", 0.0))
    fill_ratio = float(getattr(metrics, "fill_ratio", 0.0))
    return color_count >= 2 or texture_score >= 0.015 or edge_score >= 0.015 or fill_ratio < 0.96


def inferred_radius(bbox: list[int], *, role: str) -> int | None:
    if role == "indicator" and abs(bbox[2] - bbox[3]) <= max(2, round(min(bbox[2], bbox[3]) * 0.18)):
        return min(bbox[2], bbox[3]) // 2
    return None


def control_geometry_kind(bbox: list[int], radius: int | None) -> str:
    if radius is None:
        return "rect"
    half_short_edge = max(1, min(bbox[2], bbox[3]) // 2)
    return "pill" if radius >= round(half_short_edge * 0.75) else "rounded_rect"


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
