from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .onnx_box_proposer import (
    UnexpectedOnnxOutputShape,
    import_optional_module,
    nms,
    preprocess_image,
    propose_boxes_with_onnx,
    run_model_inference,
)


DEFAULT_ONNX_MODEL_PATH = Path("/Volumes/WorkDrive/Models/model_fp16.onnx")
CLASSIFIABLE_M30_ROLES = {
    "m30_text_member",
    "m30_shape_candidate",
    "m30_visual_asset",
    "m30_composite_media_asset",
}


@dataclass(frozen=True)
class M39Options:
    onnx_proposer_enabled: bool = True
    onnx_model_path: Path = DEFAULT_ONNX_MODEL_PATH


def classify_content_chrome(
    dsl: dict[str, Any],
    task_id: str,
    output_dir: Path,
    source_image_path: Path | None = None,
    options: M39Options | None = None,
) -> dict[str, Any]:
    opts = options or M39Options()
    output_dir.mkdir(parents=True, exist_ok=True)

    page = dsl.get("page") if isinstance(dsl.get("page"), dict) else {}
    page_width = int(page.get("width") or 0)
    page_height = int(page.get("height") or 0)

    warnings: list[str] = []
    proposed_chrome_boxes: list[dict[str, Any]] = []
    model_skipped_reason: str | None = None
    onnx_model_loaded = False

    if opts.onnx_proposer_enabled:
        proposed_chrome_boxes, model_skipped_reason, onnx_model_loaded, model_warnings = propose_chrome_boxes_with_onnx(
            source_image_path=source_image_path,
            model_path=opts.onnx_model_path,
        )
        warnings.extend(model_warnings)

    classified_nodes: list[dict[str, Any]] = []

    def classify_node(node: dict[str, Any]) -> None:
        role = str(node.get("role") or "")
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        is_m30_node = meta.get("m30Materialized") is True and role in CLASSIFIABLE_M30_ROLES
        if is_m30_node:
            mutable_meta = node.setdefault("meta", {})
            node_bbox = layout_bbox(node.get("layout"))
            if node_bbox is None or page_width <= 0 or page_height <= 0:
                mutable_meta["boundaryClassification"] = "content"
                classified_nodes.append(
                    {
                        "nodeId": node.get("id"),
                        "role": role,
                        "bbox": node_bbox,
                        "classification": "content",
                        "matchedRules": ["invalid_or_missing_geometry"],
                        "modelAssisted": False,
                        "onnxOverlap": None,
                    }
                )
            else:
                classification, matched_rules, model_assisted, onnx_overlap = classify_bbox(
                    node_bbox,
                    page_width=page_width,
                    page_height=page_height,
                    proposed_chrome_boxes=proposed_chrome_boxes,
                )
                mutable_meta["boundaryClassification"] = classification
                classified_nodes.append(
                    {
                        "nodeId": node.get("id"),
                        "role": role,
                        "bbox": node_bbox,
                        "classification": classification,
                        "matchedRules": matched_rules,
                        "modelAssisted": model_assisted,
                        "onnxOverlap": onnx_overlap,
                    }
                )

        children = node.get("children") if isinstance(node.get("children"), list) else []
        for child in children:
            if isinstance(child, dict):
                classify_node(child)

    root = dsl.get("root") if isinstance(dsl.get("root"), dict) else {}
    if isinstance(root, dict):
        classify_node(root)

    model_assisted_count = sum(1 for item in classified_nodes if item.get("modelAssisted") is True)
    report = {
        "schemaName": "M39BoundaryClassificationReport",
        "schemaVersion": "0.2",
        "taskId": task_id,
        "pageWidth": page_width,
        "pageHeight": page_height,
        "summary": {
            "totalClassifiedNodeCount": len(classified_nodes),
            "chromeNodeCount": sum(1 for item in classified_nodes if item.get("classification") == "chrome"),
            "contentNodeCount": sum(1 for item in classified_nodes if item.get("classification") == "content"),
            "onnxProposerEnabled": opts.onnx_proposer_enabled,
            "onnxModelLoaded": onnx_model_loaded,
            "onnxCandidateCount": len(proposed_chrome_boxes),
            "ruleOnlyClassificationCount": len(classified_nodes) - model_assisted_count,
            "modelAssistedClassificationCount": model_assisted_count,
        },
        "modelSkippedReason": model_skipped_reason,
        "warnings": warnings,
        "proposedChromeBoxes": proposed_chrome_boxes,
        "classifiedNodes": classified_nodes,
    }

    report_file = output_dir / "m39_boundary_classification_report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def classify_bbox(
    node_bbox: list[int],
    *,
    page_width: int,
    page_height: int,
    proposed_chrome_boxes: list[dict[str, Any]],
) -> tuple[str, list[str], bool, dict[str, Any] | None]:
    classification = "content"
    matched_rules: list[str] = []
    matched_model_box: list[int] | None = None
    overlap_ratio = 0.0

    if (node_bbox[1] + node_bbox[3]) <= 0.12 * page_height and node_bbox[2] >= 0.6 * page_width:
        classification = "chrome"
        matched_rules.append("top_12_percent_full_width")

    if node_bbox[1] >= 0.88 * page_height and node_bbox[2] >= 0.6 * page_width:
        classification = "chrome"
        matched_rules.append("bottom_12_percent_full_width")

    if (
        node_bbox[0] > 0.8 * page_width
        and node_bbox[1] > 0.12 * page_height
        and (node_bbox[1] + node_bbox[3]) < 0.88 * page_height
        and node_bbox[2] < 0.2 * page_width
        and node_bbox[3] < 0.2 * page_height
    ):
        classification = "chrome"
        matched_rules.append("right_edge_floating_item")

    model_proposed = False
    for box_info in proposed_chrome_boxes:
        chrome_bbox = parse_bbox(box_info.get("bbox"))
        if chrome_bbox is None:
            continue
        ratio = compute_overlap_ratio(node_bbox, chrome_bbox)
        if ratio > 0.8:
            model_proposed = True
            matched_model_box = chrome_bbox
            overlap_ratio = ratio
            if classification != "chrome":
                classification = "chrome"
                matched_rules.append("onnx_model_proposal")
            break

    if classification == "chrome" and is_center_protected(node_bbox, page_width=page_width, page_height=page_height):
        classification = "content"
        matched_rules.append("override_safety_center_60_percent")

    onnx_overlap = (
        {
            "proposedBox": matched_model_box,
            "ratio": overlap_ratio,
        }
        if matched_model_box is not None
        else None
    )
    model_assisted = model_proposed and classification == "chrome" and "override_safety_center_60_percent" not in matched_rules
    return classification, matched_rules, model_assisted, onnx_overlap


def propose_chrome_boxes_with_onnx(
    *,
    source_image_path: Path | None,
    model_path: Path,
) -> tuple[list[dict[str, Any]], str | None, bool, list[str]]:
    return propose_boxes_with_onnx(
        source_image_path=source_image_path,
        model_path=model_path,
        warning_prefix="M39 ONNX proposer",
    )


def layout_bbox(layout: Any) -> list[int] | None:
    if not isinstance(layout, dict):
        return None
    try:
        return [
            round(float(layout["x"])),
            round(float(layout["y"])),
            round(float(layout["width"])),
            round(float(layout["height"])),
        ]
    except (KeyError, TypeError, ValueError):
        return None


def parse_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [round(float(item)) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


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


def compute_overlap_ratio(node_bbox: list[int], chrome_bbox: list[int]) -> float:
    node_area = bbox_area(node_bbox)
    if node_area == 0:
        return 0.0
    return bbox_intersection_area(node_bbox, chrome_bbox) / node_area


def is_center_protected(node_bbox: list[int], *, page_width: int, page_height: int) -> bool:
    cx = node_bbox[0] + node_bbox[2] / 2.0
    cy = node_bbox[1] + node_bbox[3] / 2.0
    in_center_horiz = (0.2 * page_width) <= cx <= (0.8 * page_width)
    in_center_vert = (0.2 * page_height) <= cy <= (0.8 * page_height)
    return in_center_horiz and in_center_vert
