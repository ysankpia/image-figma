from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .onnx_box_proposer import propose_boxes_with_onnx


DEFAULT_ONNX_MODEL_PATH = Path("/Volumes/WorkDrive/Models/model_fp16.onnx")
M30_UNIT_ROLES = {
    "m30_text_member",
    "m30_shape_candidate",
    "m30_visual_asset",
    "m30_composite_media_asset",
}


@dataclass(frozen=True)
class M391Options:
    onnx_unit_proposer_enabled: bool = True
    onnx_model_path: Path = DEFAULT_ONNX_MODEL_PATH


@dataclass(frozen=True)
class M391Result:
    report: dict[str, Any]
    output_dir: Path


def audit_unit_structure_readiness(
    *,
    task_id: str,
    m30_dsl_path: str,
    m31_tree_path: str,
    m31_report_path: str,
    m37_report_path: str | None,
    m38_report_path: str | None,
    m39_report_path: str | None,
    output_dir: Path,
    source_image_path: Path | None = None,
    options: M391Options | None = None,
) -> M391Result:
    opts = options or M391Options()
    output_dir.mkdir(parents=True, exist_ok=True)

    m30_dsl_file = Path(m30_dsl_path).expanduser().resolve()
    m31_tree_file = Path(m31_tree_path).expanduser().resolve()
    m31_report_file = Path(m31_report_path).expanduser().resolve()
    m37_report_file = optional_path(m37_report_path)
    m38_report_file = optional_path(m38_report_path)
    m39_report_file = optional_path(m39_report_path)

    dsl = read_json(m30_dsl_file)
    m31_tree = read_json(m31_tree_file)
    m31_report = read_json(m31_report_file)
    m37_report = read_json(m37_report_file) if m37_report_file and m37_report_file.exists() else {}
    m38_report = read_json(m38_report_file) if m38_report_file and m38_report_file.exists() else {}
    m39_report = read_json(m39_report_file) if m39_report_file and m39_report_file.exists() else {}

    page = dsl.get("page") if isinstance(dsl.get("page"), dict) else {}
    page_width = int(page.get("width") or 0)
    page_height = int(page.get("height") or 0)
    page_area = max(1, page_width * page_height)
    visible_nodes = collect_m30_nodes(dsl.get("root", {}))
    m38_container_ids_by_unit = m38_container_map(m38_report)

    candidate_units: list[dict[str, Any]] = []
    for unit in list_dicts(m37_report.get("unitReports")):
        candidate_units.append(candidate_from_m37_unit(unit, m38_container_ids_by_unit))

    existing_keys = {candidate_key(item) for item in candidate_units}
    derived_candidates = derive_geometry_candidates(
        visible_nodes=visible_nodes,
        page_width=page_width,
        page_height=page_height,
        existing_keys=existing_keys,
    )
    candidate_units.extend(derived_candidates)
    existing_keys.update(candidate_key(item) for item in derived_candidates)

    boundary_candidates = derive_boundary_candidates(
        classified_nodes=list_dicts(m39_report.get("classifiedNodes")),
        page_width=page_width,
        page_height=page_height,
        existing_keys=existing_keys,
    )
    candidate_units.extend(boundary_candidates)
    existing_keys.update(candidate_key(item) for item in boundary_candidates)

    proposed_boxes: list[dict[str, Any]] = []
    model_skipped_reason: str | None = None
    onnx_model_loaded = False
    warnings: list[str] = []
    if opts.onnx_unit_proposer_enabled:
        proposed_boxes, model_skipped_reason, onnx_model_loaded, model_warnings = propose_boxes_with_onnx(
            source_image_path=source_image_path,
            model_path=opts.onnx_model_path,
            warning_prefix="M39.1 ONNX unit proposer",
        )
        warnings.extend(model_warnings)
        candidate_units.extend(
            derive_onnx_candidates(
                proposed_boxes=proposed_boxes,
                visible_nodes=visible_nodes,
                existing_keys=existing_keys,
            )
        )

    candidate_units = renumber_candidates(candidate_units)
    blocker_summary = reason_counts(
        reason
        for candidate in candidate_units
        for reason in candidate.get("blockerReasons", [])
        if isinstance(reason, str)
    )
    promotion_hints = build_promotion_hints(candidate_units)
    summary = {
        "m30NodeCount": len(visible_nodes),
        "m31UnitCount": int(m31_report.get("summary", {}).get("unitCount") or len(list_dicts(m31_report.get("unitSummaries")))),
        "m37SafeUnitCount": int(m37_report.get("summary", {}).get("safeContainerUnitCount") or 0),
        "m38CreatedContainerCount": int(m38_report.get("summary", {}).get("createdContainerCount") or 0),
        "candidateUnitCount": len(candidate_units),
        "readyCandidateCount": sum(1 for item in candidate_units if item.get("readiness") == "ready_for_existing_m38"),
        "blockedCandidateCount": sum(1 for item in candidate_units if item.get("readiness") == "blocked"),
        "microCandidateCount": sum(1 for item in candidate_units if "micro_unit_only" in item.get("blockerReasons", [])),
        "chromeShellCandidateCount": sum(1 for item in candidate_units if item.get("candidateKind") == "chrome_shell_candidate"),
        "contentSectionCandidateCount": sum(1 for item in candidate_units if item.get("candidateKind") == "content_section_candidate"),
        "productCardCandidateCount": sum(1 for item in candidate_units if item.get("candidateKind") == "product_card_candidate"),
        "bannerCandidateCount": sum(1 for item in candidate_units if item.get("candidateKind") == "banner_candidate"),
        "onnxModelLoaded": onnx_model_loaded,
        "onnxCandidateCount": len(proposed_boxes),
        "dslChanged": False,
        "createdVisibleNodeCount": 0,
        "assetChanged": False,
    }
    report = {
        "schemaName": "M391UnitStructureReadinessReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceM30Dsl": str(m30_dsl_file),
        "sourceM31Tree": str(m31_tree_file),
        "sourceM31Report": str(m31_report_file),
        "sourceM37Report": str(m37_report_file) if m37_report_file else None,
        "sourceM38Report": str(m38_report_file) if m38_report_file else None,
        "sourceM39Report": str(m39_report_file) if m39_report_file else None,
        "outputReport": str(output_dir / "unit_structure_readiness_report.json"),
        "summary": summary,
        "modelSkippedReason": model_skipped_reason,
        "candidateUnits": candidate_units,
        "blockerSummary": blocker_summary,
        "promotionHints": promotion_hints,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "m31Summary": m31_report.get("summary", {}),
            "m37Summary": m37_report.get("summary", {}),
            "m38Summary": m38_report.get("summary", {}),
            "m39Summary": m39_report.get("summary", {}),
        },
    }
    validate_m391_report(report)
    (output_dir / "unit_structure_readiness_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M391Result(report=report, output_dir=output_dir)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return data


def optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def collect_m30_nodes(root: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if not isinstance(node, dict):
            return
        role = str(node.get("role") or "")
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        bbox = layout_bbox(node.get("layout"))
        if meta.get("m30Materialized") is True and role in M30_UNIT_ROLES and bbox is not None:
            content = node.get("content") if isinstance(node.get("content"), dict) else {}
            nodes.append(
                {
                    "id": str(node.get("id") or ""),
                    "role": role,
                    "type": str(node.get("type") or ""),
                    "bbox": bbox,
                    "boundaryClassification": meta.get("boundaryClassification"),
                    "text": str(content.get("text") or "").strip(),
                }
            )
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            visit(child)

    visit(root)
    return nodes


def candidate_from_m37_unit(unit: dict[str, Any], m38_container_ids_by_unit: dict[str, list[str]]) -> dict[str, Any]:
    unit_id = str(unit.get("unitId") or "")
    bbox = parse_bbox(unit.get("bbox")) or [0, 0, 1, 1]
    matches = list_dicts(unit.get("matches"))
    child_ids = unique_strings([str(match.get("m30NodeId")) for match in matches if match.get("m30NodeId")])
    child_roles = unique_strings([str(match.get("role")) for match in matches if match.get("role")])
    classifications = unique_strings([str(match.get("boundaryClassification")) for match in matches if match.get("boundaryClassification")])
    unsafe_reasons = [str(reason) for reason in unit.get("unsafeReasons", []) if reason]
    is_safe = unit.get("safeContainerCandidate") is True
    blocker_reasons = blocker_reasons_from_m37(unsafe_reasons)
    if is_safe:
        readiness = "ready_for_existing_m38"
        readiness_reasons = ["m37_safe_direct_match_unit"]
        confidence = "high"
    else:
        readiness = "blocked"
        readiness_reasons = []
        confidence = "low" if "micro_unit_only" in blocker_reasons else "medium"
    return {
        "candidateId": "",
        "candidateKind": "existing_m37_safe_unit" if is_safe else "m31_unsafe_unit",
        "roleHint": role_hint_from_m37(unit),
        "sourceKind": "m37_unit",
        "bbox": bbox,
        "childM30NodeIds": child_ids,
        "childRoles": child_roles,
        "boundaryClassifications": classifications,
        "m37UnitIds": [unit_id] if unit_id else [],
        "m38ContainerIds": m38_container_ids_by_unit.get(unit_id, []),
        "matchCounts": normalized_match_counts(unit.get("matchCounts")),
        "readiness": readiness,
        "readinessReasons": readiness_reasons,
        "blockerReasons": blocker_reasons,
        "confidence": confidence,
    }


def blocker_reasons_from_m37(unsafe_reasons: list[str]) -> list[str]:
    blockers: list[str] = []
    if any(reason in unsafe_reasons for reason in ("single_primitive_unit", "micro_unit", "tiny_unit")):
        blockers.append("micro_unit_only")
    if "insufficient_mapped_children" in unsafe_reasons:
        blockers.append("insufficient_direct_matches")
    if "boundary_classification_conflict" in unsafe_reasons:
        blockers.append("boundary_classification_conflict")
    if "duplicate_unit_bbox" in unsafe_reasons:
        blockers.append("duplicate_unit_bbox")
    if "unsupported_visual_kind" in unsafe_reasons or "unsafe_visual_kind" in unsafe_reasons:
        blockers.append("unsupported_visual_kind")
    if not blockers and unsafe_reasons:
        blockers.extend(unsafe_reasons)
    return unique_strings(blockers)


def role_hint_from_m37(unit: dict[str, Any]) -> str:
    visual_kind = str(unit.get("visualKind") or "")
    if visual_kind in {"card_like", "repeated_item", "repeated_group"}:
        return "product_card"
    if visual_kind == "media_text_block":
        return "banner"
    if visual_kind in {"row", "text_block", "control_cluster"}:
        return "content_section"
    return "unknown"


def derive_geometry_candidates(
    *,
    visible_nodes: list[dict[str, Any]],
    page_width: int,
    page_height: int,
    existing_keys: set[tuple[int, int, int, int, str]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    page_area = max(1, page_width * page_height)
    image_nodes = [node for node in visible_nodes if node.get("role") in {"m30_visual_asset", "m30_composite_media_asset"}]
    for image_node in image_nodes:
        image_bbox = parse_bbox(image_node.get("bbox"))
        if image_bbox is None:
            continue
        contained = [
            node
            for node in visible_nodes
            if node.get("id") != image_node.get("id")
            and (
                bbox_containment_ratio(parse_bbox(node.get("bbox")), image_bbox) >= 0.95
                or near_image_member(parse_bbox(node.get("bbox")), image_bbox, node)
            )
        ]
        if len(contained) < 1:
            continue
        union = union_bbox([image_bbox] + [node["bbox"] for node in contained])
        if union is None:
            continue
        area_ratio = bbox_area(union) / page_area
        aspect = union[2] / max(1, union[3])
        page_width_ratio = union[2] / max(1, page_width)
        banner_like = page_width_ratio >= 0.7 and aspect >= 1.8 and area_ratio >= 0.04
        role_hint = "banner" if image_node.get("role") == "m30_composite_media_asset" or banner_like else "product_card"
        candidate_kind = "banner_candidate" if role_hint == "banner" else "product_card_candidate"
        key = (*union, candidate_kind)
        if key in existing_keys:
            continue
        child_nodes = [image_node, *contained]
        classifications = unique_strings([str(node.get("boundaryClassification")) for node in child_nodes if node.get("boundaryClassification")])
        blockers = ["boundary_classification_conflict"] if len(classifications) > 1 else []
        candidates.append(
            base_candidate(
                candidate_kind=candidate_kind,
                role_hint=role_hint,
                source_kind="m30_geometry_cluster",
                bbox=union,
                child_nodes=child_nodes,
                readiness="blocked" if blockers else "needs_unit_promotion",
                readiness_reasons=["image_text_spatial_cluster"] if not blockers else [],
                blocker_reasons=blockers,
                confidence="medium" if not blockers else "low",
            )
        )
    return candidates


def derive_boundary_candidates(
    *,
    classified_nodes: list[dict[str, Any]],
    page_width: int,
    page_height: int,
    existing_keys: set[tuple[int, int, int, int, str]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    top = []
    bottom = []
    content = []
    for item in classified_nodes:
        bbox = parse_bbox(item.get("bbox"))
        if bbox is None:
            continue
        node = {
            "id": str(item.get("nodeId") or ""),
            "role": str(item.get("role") or ""),
            "bbox": bbox,
            "boundaryClassification": item.get("classification"),
        }
        if item.get("classification") == "chrome" and bbox[1] + bbox[3] <= page_height * 0.18:
            top.append(node)
        elif item.get("classification") == "chrome" and bbox[1] >= page_height * 0.82:
            bottom.append(node)
        elif item.get("classification") == "content":
            content.append(node)

    for role_hint, nodes in (("top_chrome", top), ("bottom_chrome", bottom)):
        candidate = boundary_cluster_candidate(
            nodes=nodes,
            candidate_kind="chrome_shell_candidate",
            role_hint=role_hint,
            existing_keys=existing_keys,
        )
        if candidate is not None:
            candidates.append(candidate)
    content_nodes = [node for node in content if bbox_area(node["bbox"]) >= max(1200, page_width * page_height * 0.002)]
    candidate = boundary_cluster_candidate(
        nodes=content_nodes,
        candidate_kind="content_section_candidate",
        role_hint="content_section",
        existing_keys=existing_keys,
    )
    if candidate is not None:
        candidates.append(candidate)
    return candidates


def boundary_cluster_candidate(
    *,
    nodes: list[dict[str, Any]],
    candidate_kind: str,
    role_hint: str,
    existing_keys: set[tuple[int, int, int, int, str]],
) -> dict[str, Any] | None:
    if len(nodes) < 2:
        return None
    bbox = union_bbox([node["bbox"] for node in nodes])
    if bbox is None:
        return None
    key = (*bbox, candidate_kind)
    if key in existing_keys:
        return None
    return base_candidate(
        candidate_kind=candidate_kind,
        role_hint=role_hint,
        source_kind="m39_boundary_cluster",
        bbox=bbox,
        child_nodes=nodes,
        readiness="diagnostic_only",
        readiness_reasons=["boundary_classification_cluster"],
        blocker_reasons=[],
        confidence="medium",
    )


def derive_onnx_candidates(
    *,
    proposed_boxes: list[dict[str, Any]],
    visible_nodes: list[dict[str, Any]],
    existing_keys: set[tuple[int, int, int, int, str]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for box_info in proposed_boxes:
        bbox = parse_bbox(box_info.get("bbox"))
        if bbox is None:
            continue
        key = (*bbox, "onnx_box_candidate")
        if key in existing_keys:
            continue
        child_nodes = [
            node
            for node in visible_nodes
            if bbox_containment_ratio(parse_bbox(node.get("bbox")), bbox) >= 0.8
        ]
        candidates.append(
            base_candidate(
                candidate_kind="onnx_box_candidate",
                role_hint="unknown",
                source_kind="onnx_box",
                bbox=bbox,
                child_nodes=child_nodes,
                readiness="diagnostic_only",
                readiness_reasons=["model_candidate_requires_rule_evidence"],
                blocker_reasons=["model_only_untrusted"],
                confidence="low",
            )
        )
    return candidates


def base_candidate(
    *,
    candidate_kind: str,
    role_hint: str,
    source_kind: str,
    bbox: list[int],
    child_nodes: list[dict[str, Any]],
    readiness: str,
    readiness_reasons: list[str],
    blocker_reasons: list[str],
    confidence: str,
) -> dict[str, Any]:
    return {
        "candidateId": "",
        "candidateKind": candidate_kind,
        "roleHint": role_hint,
        "sourceKind": source_kind,
        "bbox": bbox,
        "childM30NodeIds": unique_strings([str(node.get("id")) for node in child_nodes if node.get("id")]),
        "childRoles": unique_strings([str(node.get("role")) for node in child_nodes if node.get("role")]),
        "boundaryClassifications": unique_strings([str(node.get("boundaryClassification")) for node in child_nodes if node.get("boundaryClassification")]),
        "m37UnitIds": [],
        "m38ContainerIds": [],
        "matchCounts": {"direct_match": 0, "geometry_text_match": 0, "geometry_type_match": 0},
        "readiness": readiness,
        "readinessReasons": readiness_reasons,
        "blockerReasons": blocker_reasons,
        "confidence": confidence,
    }


def m38_container_map(report: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for item in list_dicts(report.get("containers")):
        unit_id = str(item.get("unitId") or "")
        container_id = str(item.get("containerId") or "")
        if unit_id and container_id:
            mapping.setdefault(unit_id, []).append(container_id)
    return mapping


def build_promotion_hints(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hints = []
    for candidate in candidates:
        if candidate.get("readiness") != "needs_unit_promotion":
            continue
        hints.append(
            {
                "candidateId": candidate.get("candidateId"),
                "roleHint": candidate.get("roleHint"),
                "bbox": candidate.get("bbox"),
                "childM30NodeIds": candidate.get("childM30NodeIds", []),
                "reason": "Candidate has coherent geometry but is not yet represented as an M37 safe unit.",
            }
        )
    return hints[:40]


def renumber_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, candidate in enumerate(candidates, start=1):
        candidate["candidateId"] = f"m391_candidate_{index:04d}"
    return candidates


def validate_m391_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if summary.get("dslChanged") is not False:
        raise ValueError("M39.1 must not change DSL.")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("M39.1 must not create visible nodes.")
    if summary.get("assetChanged") is not False:
        raise ValueError("M39.1 must not change assets.")


def layout_bbox(layout: Any) -> list[int] | None:
    if not isinstance(layout, dict):
        return None
    try:
        bbox = [round(float(layout["x"])), round(float(layout["y"])), round(float(layout["width"])), round(float(layout["height"]))]
    except (KeyError, TypeError, ValueError):
        return None
    return bbox if bbox[2] > 0 and bbox[3] > 0 else None


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
    return max(0, min(left_x2, right_x2) - max(left[0], right[0])) * max(0, min(left_y2, right_y2) - max(left[1], right[1]))


def bbox_containment_ratio(inner: list[int] | None, outer: list[int]) -> float:
    if inner is None:
        return 0.0
    area = bbox_area(inner)
    if area == 0:
        return 0.0
    return bbox_intersection_area(inner, outer) / area


def near_image_member(member_bbox: list[int] | None, image_bbox: list[int], node: dict[str, Any]) -> bool:
    if member_bbox is None:
        return False
    if node.get("role") not in {"m30_text_member", "m30_shape_candidate"}:
        return False
    image_bottom = image_bbox[1] + image_bbox[3]
    member_top = member_bbox[1]
    vertical_gap = member_top - image_bottom
    if vertical_gap < 0 or vertical_gap > max(80, image_bbox[3] * 0.35):
        return False
    member_center_x = member_bbox[0] + member_bbox[2] / 2.0
    horizontal_margin = max(16, image_bbox[2] * 0.12)
    if not (image_bbox[0] - horizontal_margin <= member_center_x <= image_bbox[0] + image_bbox[2] + horizontal_margin):
        return False
    horizontal_overlap = max(
        0,
        min(image_bbox[0] + image_bbox[2], member_bbox[0] + member_bbox[2]) - max(image_bbox[0], member_bbox[0]),
    )
    return horizontal_overlap / max(1, min(image_bbox[2], member_bbox[2])) >= 0.25


def union_bbox(boxes: list[list[int]]) -> list[int] | None:
    boxes = [box for box in boxes if parse_bbox(box) is not None]
    if not boxes:
        return None
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[0] + box[2] for box in boxes)
    y1 = max(box[1] + box[3] for box in boxes)
    return [x0, y0, max(1, x1 - x0), max(1, y1 - y0)]


def normalized_match_counts(value: Any) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    return {
        "direct_match": int(source.get("direct_match") or 0),
        "geometry_text_match": int(source.get("geometry_text_match") or 0),
        "geometry_type_match": int(source.get("geometry_type_match") or 0),
    }


def candidate_key(candidate: dict[str, Any]) -> tuple[int, int, int, int, str]:
    bbox = parse_bbox(candidate.get("bbox")) or [0, 0, 0, 0]
    return (bbox[0], bbox[1], bbox[2], bbox[3], str(candidate.get("candidateKind") or ""))


def list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def reason_counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value:
            counts[str(value)] = counts.get(str(value), 0) + 1
    return counts
