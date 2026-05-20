from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .visual_evidence_normalization import parse_bbox


MatchKind = Literal["direct_match", "geometry_text_match", "geometry_type_match", "unmapped"]


SAFE_VISUAL_KINDS = {
    "text_block",
    "control_cluster",
    "media_text_block",
    "row",
    "column",
    "card_like",
    "tabular_like",
    "repeated_item",
    "repeated_group",
}


UNSAFE_UNIT_KINDS = {"single_primitive_unit"}
UNSAFE_VISUAL_KINDS = {"unknown", "fallback_region"}


@dataclass(frozen=True)
class M37Result:
    report: dict[str, Any]
    output_dir: Path


@dataclass(frozen=True)
class VisibleNode:
    id: str
    role: str
    element_type: str
    bbox: list[int]
    text: str | None
    source_ids: set[str]


def extract_m37_hierarchy_readiness(
    *,
    m31_tree_path: str,
    m31_report_path: str,
    m30_dsl_path: str,
    m30_report_path: str,
    output_dir: Path,
) -> M37Result:
    m31_tree_file = Path(m31_tree_path).expanduser().resolve()
    m31_report_file = Path(m31_report_path).expanduser().resolve()
    m30_dsl_file = Path(m30_dsl_path).expanduser().resolve()
    m30_report_file = Path(m30_report_path).expanduser().resolve()
    tree = read_json(m31_tree_file)
    m31_report = read_json(m31_report_file)
    dsl = read_json(m30_dsl_file)
    m30_report = read_json(m30_report_file)

    output_dir.mkdir(parents=True, exist_ok=True)

    image_size = tree.get("imageSize") if isinstance(tree.get("imageSize"), dict) else {}
    image_width = int(image_size.get("width") or dsl.get("page", {}).get("width") or 0)
    image_height = int(image_size.get("height") or dsl.get("page", {}).get("height") or 0)
    page_area = max(1, image_width * image_height)

    primitive_refs = [item for item in tree.get("primitiveRefs", []) if isinstance(item, dict)]
    primitive_by_id = {str(item.get("id")): item for item in primitive_refs if item.get("id")}
    node_by_id = {str(item.get("id")): item for item in tree.get("nodes", []) if isinstance(item, dict) and item.get("id")}
    primitive_by_unit: dict[str, list[dict[str, Any]]] = {}
    for ref in primitive_refs:
        owner_id = str(ref.get("ownerUnitId") or "")
        if owner_id:
            primitive_by_unit.setdefault(owner_id, []).append(ref)

    visible_nodes = visible_m30_nodes(dsl.get("root", {}))
    duplicate_bboxes = duplicate_unit_bboxes(tree.get("nodes", []))
    unit_reports: list[dict[str, Any]] = []
    safe_candidates: list[dict[str, Any]] = []
    unsafe_candidates: list[dict[str, Any]] = []
    mappable_node_ids: set[str] = set()
    relative_coordinate_violation_count = 0
    fallback_conflict_risk_count = 0
    micro_unit_count = 0

    for unit in [item for item in tree.get("nodes", []) if isinstance(item, dict) and item.get("kind") in {"reconstruction_unit", "repeated_item", "repeated_group"}]:
        unit_id = str(unit.get("id") or "")
        bbox = parse_bbox(unit.get("bbox"))
        if not unit_id or bbox is None:
            continue
        children_refs = unit_child_primitives(unit, primitive_by_id, primitive_by_unit, node_by_id)
        matches = match_visible_nodes(unit, children_refs, visible_nodes)
        mapped_nodes = [match for match in matches if match["matchKind"] != "unmapped"]
        for match in mapped_nodes:
            mappable_node_ids.add(str(match["m30NodeId"]))

        relative_violations = sum(1 for match in mapped_nodes if not child_inside_parent(match["bbox"], bbox))
        relative_coordinate_violation_count += relative_violations
        duplicate_bbox = tuple(bbox) in duplicate_bboxes
        micro_unit = is_micro_unit(unit, bbox, page_area, len(children_refs), len(mapped_nodes))
        if micro_unit:
            micro_unit_count += 1
        fallback_risk = bool(unit.get("fallback")) and len(mapped_nodes) > 0
        if fallback_risk:
            fallback_conflict_risk_count += 1

        unsafe_reasons = unsafe_unit_reasons(
            unit=unit,
            bbox=bbox,
            page_area=page_area,
            primitive_ref_count=len(children_refs),
            mapped_count=len(mapped_nodes),
            duplicate_bbox=duplicate_bbox,
            micro_unit=micro_unit,
            relative_violations=relative_violations,
        )
        unit_report = {
            "unitId": unit_id,
            "kind": unit.get("kind"),
            "unitKind": unit.get("unitKind"),
            "visualKind": unit.get("visualKind"),
            "bbox": bbox,
            "primitiveRefCount": len(children_refs),
            "mappedM30ChildCount": len(mapped_nodes),
            "matchCounts": match_counts(matches),
            "relativeCoordinateViolationCount": relative_violations,
            "fallbackConflictRisk": fallback_risk,
            "safeContainerCandidate": not unsafe_reasons,
            "unsafeReasons": unsafe_reasons,
            "matches": matches,
        }
        unit_reports.append(unit_report)
        if unsafe_reasons:
            unsafe_candidates.append(unit_report)
        else:
            safe_candidates.append(unit_report)

    report = {
        "schemaName": "M37HierarchyReadinessReport",
        "schemaVersion": "0.1",
        "sourceM31Tree": str(m31_tree_file),
        "sourceM31Report": str(m31_report_file),
        "sourceM30Dsl": str(m30_dsl_file),
        "sourceM30Report": str(m30_report_file),
        "outputReport": str(output_dir / "m37_hierarchy_readiness_report.json"),
        "summary": {
            "m30NodeCount": len(visible_nodes),
            "m31UnitCount": len(unit_reports),
            "mappableM30NodeCount": len(mappable_node_ids),
            "unmappedM30NodeCount": max(0, len(visible_nodes) - len(mappable_node_ids)),
            "safeContainerUnitCount": len(safe_candidates),
            "unsafeContainerUnitCount": len(unsafe_candidates),
            "microUnitCount": micro_unit_count,
            "duplicateUnitBBoxCount": len(duplicate_bboxes),
            "unitChildCoverage": round(len(mappable_node_ids) / len(visible_nodes), 4) if visible_nodes else 1.0,
            "relativeCoordinateViolationCount": relative_coordinate_violation_count,
            "fallbackConflictRiskCount": fallback_conflict_risk_count,
            "createdVisibleFrameCount": 0,
            "dslChanged": False,
        },
        "safeContainerCandidates": compact_units(safe_candidates),
        "unsafeContainerCandidates": compact_units(unsafe_candidates),
        "unitReports": unit_reports,
        "warnings": [],
        "meta": {
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "m31Summary": m31_report.get("summary", {}),
            "m30Summary": m30_report.get("summary", {}),
        },
    }
    validate_m37_report(report)
    (output_dir / "m37_hierarchy_readiness_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M37Result(report=report, output_dir=output_dir)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return data


def visible_m30_nodes(root: dict[str, Any]) -> list[VisibleNode]:
    nodes: list[VisibleNode] = []

    def visit(node: Any) -> None:
        if not isinstance(node, dict):
            return
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        role = str(node.get("role") or "")
        if meta.get("m30Materialized") is True and role in {"m30_text_member", "m30_shape_candidate", "m30_visual_asset"}:
            bbox = layout_bbox(node.get("layout"))
            if bbox is not None:
                content = node.get("content") if isinstance(node.get("content"), dict) else {}
                nodes.append(
                    VisibleNode(
                        id=str(node.get("id") or ""),
                        role=role,
                        element_type=str(node.get("type") or ""),
                        bbox=bbox,
                        text=str(content.get("text")).strip() if content.get("text") is not None else None,
                        source_ids=node_source_ids(meta),
                    )
                )
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            visit(child)

    visit(root)
    return nodes


def layout_bbox(layout: Any) -> list[int] | None:
    if not isinstance(layout, dict):
        return None
    try:
        return [round(float(layout["x"])), round(float(layout["y"])), round(float(layout["width"])), round(float(layout["height"]))]
    except (KeyError, TypeError, ValueError):
        return None


def node_source_ids(meta: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("sourceTextMemberId", "sourceTextBoxId", "sourceEvidenceNodeId", "sourceVisualAssetId", "sourceShapeCandidateId", "sourceObjectId"):
        value = meta.get(key)
        if value is not None:
            ids.add(str(value))
    for value in meta.get("sourceEvidenceNodeIds", []) if isinstance(meta.get("sourceEvidenceNodeIds"), list) else []:
        ids.add(str(value))
    return ids


def duplicate_unit_bboxes(nodes: Any) -> set[tuple[int, int, int, int]]:
    counts: dict[tuple[int, int, int, int], int] = {}
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict) or node.get("kind") != "reconstruction_unit":
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is not None:
            key = tuple(bbox)
            counts[key] = counts.get(key, 0) + 1
    return {bbox for bbox, count in counts.items() if count > 1}


def unit_child_primitives(
    unit: dict[str, Any],
    primitive_by_id: dict[str, dict[str, Any]],
    primitive_by_unit: dict[str, list[dict[str, Any]]],
    node_by_id: dict[str, dict[str, Any]],
    seen_nodes: set[str] | None = None,
) -> list[dict[str, Any]]:
    unit_id = str(unit.get("id") or "")
    seen = seen_nodes or set()
    if unit_id in seen:
        return []
    seen.add(unit_id)
    refs = list(primitive_by_unit.get(unit_id, []))
    for child_id in unit.get("children", []) if isinstance(unit.get("children"), list) else []:
        primitive = primitive_by_id.get(str(child_id))
        if primitive is not None and primitive not in refs:
            refs.append(primitive)
            continue
        child_node = node_by_id.get(str(child_id))
        if child_node is not None:
            for child_ref in unit_child_primitives(child_node, primitive_by_id, primitive_by_unit, node_by_id, seen):
                if child_ref not in refs:
                    refs.append(child_ref)
    return refs


def match_visible_nodes(unit: dict[str, Any], primitives: list[dict[str, Any]], visible_nodes: list[VisibleNode]) -> list[dict[str, Any]]:
    unit_bbox = parse_bbox(unit.get("bbox")) or [0, 0, 0, 0]
    primitive_sources = primitive_source_ids(primitives)
    primitive_texts = {normalize_text(str(item.get("text") or "")) for item in primitives if item.get("text")}
    primitive_types = {str(item.get("primitiveType") or "") for item in primitives}
    matches: list[dict[str, Any]] = []
    for node in visible_nodes:
        if bbox_iou(node.bbox, unit_bbox) <= 0 and bbox_overlap_ratio(node.bbox, unit_bbox) < 0.75:
            continue
        match_kind: MatchKind = "unmapped"
        if primitive_sources & node.source_ids:
            match_kind = "direct_match"
        elif node.text and normalize_text(node.text) in primitive_texts and bbox_best_iou(node.bbox, [parse_bbox(item.get("bbox")) for item in primitives]) >= 0.5:
            match_kind = "geometry_text_match"
        elif role_matches_primitive_type(node, primitive_types) and bbox_best_iou(node.bbox, [parse_bbox(item.get("bbox")) for item in primitives]) >= 0.5:
            match_kind = "geometry_type_match"
        if match_kind != "unmapped":
            matches.append(
                {
                    "m30NodeId": node.id,
                    "role": node.role,
                    "matchKind": match_kind,
                    "bbox": node.bbox,
                    "relativeBBox": [node.bbox[0] - unit_bbox[0], node.bbox[1] - unit_bbox[1], node.bbox[2], node.bbox[3]],
                }
            )
    return matches


def primitive_source_ids(primitives: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for item in primitives:
        for value in (item.get("id"), item.get("sourceId")):
            if value is not None:
                ids.add(str(value))
        source_refs = item.get("sourceRefs") if isinstance(item.get("sourceRefs"), dict) else {}
        for value in source_refs.values():
            if isinstance(value, list):
                ids.update(str(inner) for inner in value)
            elif value is not None:
                ids.add(str(value))
    return ids


def normalize_text(text: str) -> str:
    return "".join(text.split()).lower()


def bbox_best_iou(bbox: list[int], candidates: list[list[int] | None]) -> float:
    return max((bbox_iou(bbox, candidate) for candidate in candidates if candidate is not None), default=0.0)


def role_matches_primitive_type(node: VisibleNode, primitive_types: set[str]) -> bool:
    if node.role == "m30_text_member":
        return "text" in primitive_types
    if node.role == "m30_visual_asset":
        return bool({"image", "symbol"} & primitive_types)
    if node.role == "m30_shape_candidate":
        return "shape" in primitive_types
    return False


def child_inside_parent(child: list[int], parent: list[int]) -> bool:
    return child[0] >= parent[0] and child[1] >= parent[1] and child[0] + child[2] <= parent[0] + parent[2] and child[1] + child[3] <= parent[1] + parent[3]


def is_micro_unit(unit: dict[str, Any], bbox: list[int], page_area: int, primitive_count: int, mapped_count: int) -> bool:
    if unit.get("unitKind") == "single_primitive_unit" or primitive_count <= 1:
        return True
    if mapped_count <= 1:
        return True
    return bbox_area(bbox) / page_area < 0.0005


def unsafe_unit_reasons(
    *,
    unit: dict[str, Any],
    bbox: list[int],
    page_area: int,
    primitive_ref_count: int,
    mapped_count: int,
    duplicate_bbox: bool,
    micro_unit: bool,
    relative_violations: int,
) -> list[str]:
    reasons: list[str] = []
    kind = str(unit.get("kind") or "")
    unit_kind = str(unit.get("unitKind") or "")
    visual_kind = str(unit.get("visualKind") or "")
    area_ratio = bbox_area(bbox) / page_area
    if kind == "review_bucket":
        reasons.append("review_bucket")
    if unit_kind in UNSAFE_UNIT_KINDS:
        reasons.append("single_primitive_unit")
    if visual_kind in UNSAFE_VISUAL_KINDS:
        reasons.append("unsafe_visual_kind")
    if visual_kind not in SAFE_VISUAL_KINDS:
        reasons.append("unsupported_visual_kind")
    if primitive_ref_count < 2:
        reasons.append("insufficient_primitives")
    if mapped_count < 2:
        reasons.append("insufficient_mapped_children")
    if duplicate_bbox:
        reasons.append("duplicate_unit_bbox")
    if micro_unit:
        reasons.append("micro_unit")
    if area_ratio > 0.9:
        reasons.append("full_page_like_unit")
    if area_ratio < 0.0005:
        reasons.append("tiny_unit")
    if relative_violations:
        reasons.append("relative_coordinate_violation")
    return unique_strings(reasons)


def match_counts(matches: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"direct_match": 0, "geometry_text_match": 0, "geometry_type_match": 0, "unmapped": 0}
    for match in matches:
        kind = str(match.get("matchKind") or "unmapped")
        if kind in counts:
            counts[kind] += 1
    return counts


def compact_units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "unitId": item["unitId"],
            "kind": item.get("kind"),
            "unitKind": item.get("unitKind"),
            "visualKind": item.get("visualKind"),
            "bbox": item.get("bbox"),
            "primitiveRefCount": item.get("primitiveRefCount"),
            "mappedM30ChildCount": item.get("mappedM30ChildCount"),
            "unsafeReasons": item.get("unsafeReasons"),
        }
        for item in units
    ]


def validate_m37_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if summary.get("createdVisibleFrameCount") != 0:
        raise ValueError("M37 must not create visible frames.")
    if summary.get("dslChanged") is not False:
        raise ValueError("M37 must not change DSL.")


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def bbox_intersection_area(left: list[int], right: list[int]) -> int:
    left_x2 = left[0] + left[2]
    left_y2 = left[1] + left[3]
    right_x2 = right[0] + right[2]
    right_y2 = right[1] + right[3]
    return max(0, min(left_x2, right_x2) - max(left[0], right[0])) * max(0, min(left_y2, right_y2) - max(left[1], right[1]))


def bbox_iou(left: list[int] | None, right: list[int] | None) -> float:
    if left is None or right is None:
        return 0.0
    intersection = bbox_intersection_area(left, right)
    union = bbox_area(left) + bbox_area(right) - intersection
    return intersection / union if union > 0 else 0.0


def bbox_overlap_ratio(left: list[int], right: list[int]) -> float:
    area = bbox_area(left)
    return bbox_intersection_area(left, right) / area if area > 0 else 0.0


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
