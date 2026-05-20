from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .visual_evidence_normalization import parse_bbox


M38_MOVABLE_ROLES = {"m30_text_member", "m30_shape_candidate", "m30_visual_asset"}
M38_FORBIDDEN_ROLES = {"fallback_region", "original_reference"}


@dataclass(frozen=True)
class M38Options:
    max_containers: int = 8


@dataclass(frozen=True)
class M38Result:
    dsl: dict[str, Any]
    report: dict[str, Any]
    output_dir: Path


def materialize_m38_hierarchy(
    *,
    m30_dsl_path: str,
    m37_report_path: str,
    output_dir: Path,
    flat_dsl_output_path: str | None = None,
    final_dsl_output_path: str | None = None,
    options: M38Options | None = None,
) -> M38Result:
    opts = options or M38Options()
    m30_dsl_file = Path(m30_dsl_path).expanduser().resolve()
    m37_report_file = Path(m37_report_path).expanduser().resolve()
    dsl = read_json(m30_dsl_file)
    flat_dsl = copy.deepcopy(dsl)
    report = read_json(m37_report_file)
    output_dir.mkdir(parents=True, exist_ok=True)

    root = dsl.get("root") if isinstance(dsl.get("root"), dict) else {}
    children = root.get("children") if isinstance(root.get("children"), list) else []
    if not isinstance(root, dict) or not isinstance(children, list):
        raise ValueError("M38 requires DSL root.children.")

    child_entries = collect_root_child_entries(children)
    children_by_id = {entry["id"]: entry for entry in child_entries}
    claimed: set[str] = set()
    containers: list[dict[str, Any]] = []
    selected_units: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    ignored_geometry_match_count = 0
    source_safe_count = 0

    for unit in list_dicts(report.get("unitReports")):
        if unit.get("safeContainerCandidate") is not True:
            continue
        source_safe_count += 1
        unit_id = str(unit.get("unitId") or "")
        bbox = parse_bbox(unit.get("bbox"))
        if not unit_id or bbox is None:
            skipped.append(skip(unit_id, "invalid_unit"))
            continue
        if unit.get("unsafeReasons"):
            skipped.append(skip(unit_id, "unsafe_reasons_present"))
            continue

        matches = list_dicts(unit.get("matches"))
        geometry_matches = [match for match in matches if str(match.get("matchKind") or "") in {"geometry_text_match", "geometry_type_match"}]
        ignored_geometry_match_count += len(geometry_matches)
        direct_matches = [match for match in matches if str(match.get("matchKind") or "") == "direct_match"]
        movable_ids, reasons = movable_direct_match_ids(direct_matches, children_by_id, claimed)
        if len(movable_ids) < 2:
            skipped.append(skip(unit_id, "insufficient_direct_movable_children", reasons))
            continue
        if z_order_interleaving_risk(movable_ids, children_by_id, bbox):
            skipped.append(skip(unit_id, "interleaved_z_order_risk"))
            continue
        if len(containers) >= opts.max_containers:
            skipped.append(skip(unit_id, "skipped_max_containers"))
            continue

        container = build_container(unit_id, bbox, unit, movable_ids)
        moved_children: list[dict[str, Any]] = []
        for child_id in movable_ids:
            entry = children_by_id[child_id]
            child = copy.deepcopy(entry["node"])
            original_layout = copy.deepcopy(child.get("layout"))
            original_bbox = layout_bbox(original_layout)
            if original_bbox is None:
                continue
            child["rawLayout"] = original_layout
            child["layout"] = {
                "x": original_bbox[0] - bbox[0],
                "y": original_bbox[1] - bbox[1],
                "width": original_bbox[2],
                "height": original_bbox[3],
            }
            meta = dict(child.get("meta") or {})
            meta["m38ParentContainerId"] = container["id"]
            meta["m38OriginalPageBBox"] = original_bbox
            child["meta"] = meta
            moved_children.append(child)
            claimed.add(child_id)
        container["children"] = moved_children
        containers.append(container)
        selected_units.append({"unitId": unit_id, "containerId": container["id"], "movedChildIds": movable_ids})

    if containers:
        moved_ids = {child.get("id") for container in containers for child in container.get("children", []) if isinstance(child, dict)}
        next_children: list[dict[str, Any]] = []
        inserted_containers: set[str] = set()
        container_by_first_index = {
            min(children_by_id[str(child.get("id"))]["index"] for child in container["children"] if isinstance(child, dict) and str(child.get("id")) in children_by_id): container
            for container in containers
        }
        for index, child in enumerate(children):
            child_id = child.get("id") if isinstance(child, dict) else None
            if index in container_by_first_index:
                container = container_by_first_index[index]
                next_children.append(container)
                inserted_containers.add(str(container["id"]))
            if child_id in moved_ids:
                continue
            next_children.append(child)
        for container in containers:
            if str(container["id"]) not in inserted_containers:
                next_children.append(container)
        root["children"] = next_children
        update_m38_meta(dsl, len(containers), sum(len(container.get("children", [])) for container in containers))

    violations = absolute_position_violations(dsl.get("root", {}))
    fallback_moved = moved_role_count(dsl.get("root", {}), "fallback_region")
    original_moved = moved_role_count(dsl.get("root", {}), "original_reference")
    report_payload = {
        "schemaName": "M38HierarchyMaterializationReport",
        "schemaVersion": "0.1",
        "sourceM30Dsl": str(m30_dsl_file),
        "sourceM37Report": str(m37_report_file),
        "outputReport": str(output_dir / "hierarchy_materialization_report.json"),
        "flatDslOutput": str(Path(flat_dsl_output_path).expanduser().resolve()) if flat_dsl_output_path else None,
        "finalDslOutput": str(Path(final_dsl_output_path).expanduser().resolve()) if final_dsl_output_path else None,
        "options": {"maxContainers": opts.max_containers},
        "summary": {
            "sourceSafeContainerCount": source_safe_count,
            "selectedContainerCount": len(selected_units),
            "createdContainerCount": len(containers),
            "movedChildCount": sum(len(container.get("children", [])) for container in containers),
            "ignoredGeometryMatchCount": ignored_geometry_match_count,
            "skippedContainerCount": len(skipped),
            "skipReasonCounts": reason_counts(skipped),
            "absolutePositionViolationCount": len(violations),
            "fallbackMovedCount": fallback_moved,
            "originalReferenceMovedCount": original_moved,
            "assetChanged": dsl.get("assets") != flat_dsl.get("assets"),
            "dslChanged": bool(containers),
            "maxContainers": opts.max_containers,
        },
        "containers": selected_units,
        "skippedContainers": skipped,
        "absolutePositionViolations": violations,
        "warnings": [],
        "meta": {"createdAt": datetime.now(timezone.utc).isoformat()},
    }
    validate_m38_report(report_payload)

    (output_dir / "hierarchy_materialization_report.json").write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if flat_dsl_output_path and bool(containers):
        Path(flat_dsl_output_path).write_text(json.dumps(flat_dsl, ensure_ascii=False, indent=2), encoding="utf-8")
    if final_dsl_output_path:
        Path(final_dsl_output_path).write_text(json.dumps(dsl, ensure_ascii=False, indent=2), encoding="utf-8")

    return M38Result(dsl=dsl, report=report_payload, output_dir=output_dir)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return data


def list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def collect_root_child_entries(children: list[Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, child in enumerate(children):
        if isinstance(child, dict) and isinstance(child.get("id"), str):
            entries.append({"id": child["id"], "index": index, "node": child})
    return entries


def movable_direct_match_ids(matches: list[dict[str, Any]], children_by_id: dict[str, dict[str, Any]], claimed: set[str]) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    reasons: list[str] = []
    for match in matches:
        node_id = str(match.get("m30NodeId") or "")
        entry = children_by_id.get(node_id)
        if entry is None:
            reasons.append("not_root_child")
            continue
        if node_id in claimed:
            reasons.append("already_claimed_child")
            continue
        node = entry["node"]
        role = str(node.get("role") or "")
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        if role in M38_FORBIDDEN_ROLES:
            reasons.append("forbidden_role")
            continue
        if role not in M38_MOVABLE_ROLES:
            reasons.append("unsupported_role")
            continue
        if meta.get("m30Materialized") is not True:
            reasons.append("not_m30_materialized")
            continue
        if layout_bbox(node.get("layout")) is None:
            reasons.append("invalid_child_layout")
            continue
        if node_id not in ids:
            ids.append(node_id)
    ids.sort(key=lambda item: children_by_id[item]["index"])
    return ids, unique_strings(reasons)


def z_order_interleaving_risk(movable_ids: list[str], children_by_id: dict[str, dict[str, Any]], container_bbox: list[int]) -> bool:
    indexes = [children_by_id[item]["index"] for item in movable_ids]
    if not indexes:
        return True
    movable = set(movable_ids)
    min_index = min(indexes)
    max_index = max(indexes)
    for entry in children_by_id.values():
        index = entry["index"]
        if index <= min_index or index >= max_index or entry["id"] in movable:
            continue
        node = entry["node"]
        node_bbox = layout_bbox(node.get("layout"))
        if node_bbox is None or not bbox_intersects(node_bbox, container_bbox):
            continue
        role = str(node.get("role") or "")
        if role in M38_FORBIDDEN_ROLES:
            continue
        style = node.get("style") if isinstance(node.get("style"), dict) else {}
        if style.get("visible") is False:
            continue
        return True
    return False


def bbox_intersects(left: list[int], right: list[int]) -> bool:
    return left[0] < right[0] + right[2] and left[0] + left[2] > right[0] and left[1] < right[1] + right[3] and left[1] + left[3] > right[1]


def build_container(unit_id: str, bbox: list[int], unit: dict[str, Any], child_ids: list[str]) -> dict[str, Any]:
    return {
        "id": f"m38_container_{unit_id}",
        "type": "group",
        "role": "m38_container",
        "name": f"M38 Container / {unit_id}",
        "layout": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
        "style": {"fill": None, "clipContent": False},
        "children": [],
        "meta": {
            "m38Materialized": True,
            "sourceKind": "m37_safe_container",
            "sourceM37UnitId": unit_id,
            "sourceM37VisualKind": unit.get("visualKind"),
            "sourceM37UnitKind": unit.get("unitKind"),
            "matchPolicy": "direct_match_only",
            "sourceM30ChildIds": child_ids,
        },
    }


def layout_bbox(layout: Any) -> list[int] | None:
    if not isinstance(layout, dict):
        return None
    try:
        return [round(float(layout["x"])), round(float(layout["y"])), round(float(layout["width"])), round(float(layout["height"]))]
    except (KeyError, TypeError, ValueError):
        return None


def absolute_position_violations(root: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    def visit(node: Any, offset_x: float, offset_y: float) -> None:
        if not isinstance(node, dict):
            return
        layout = node.get("layout") if isinstance(node.get("layout"), dict) else {}
        x = float(layout.get("x", 0) or 0)
        y = float(layout.get("y", 0) or 0)
        next_offset_x = offset_x + x
        next_offset_y = offset_y + y
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        original_bbox = parse_bbox(meta.get("m38OriginalPageBBox"))
        bbox = layout_bbox(layout)
        if original_bbox is not None and bbox is not None:
            actual = [round(next_offset_x), round(next_offset_y), bbox[2], bbox[3]]
            if actual != original_bbox:
                violations.append({"nodeId": node.get("id"), "expected": original_bbox, "actual": actual})
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            visit(child, next_offset_x, next_offset_y)

    for child in root.get("children", []) if isinstance(root.get("children"), list) else []:
        visit(child, 0, 0)
    return violations


def moved_role_count(root: dict[str, Any], role: str) -> int:
    count = 0

    def visit(node: Any, inside_m38: bool) -> None:
        nonlocal count
        if not isinstance(node, dict):
            return
        next_inside = inside_m38 or node.get("role") == "m38_container"
        if inside_m38 and node.get("role") == role:
            count += 1
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            visit(child, next_inside)

    visit(root, False)
    return count


def update_m38_meta(dsl: dict[str, Any], container_count: int, moved_child_count: int) -> None:
    meta = dict(dsl.get("meta") or {})
    flags = list(meta.get("qualityFlags") or [])
    if "m38_controlled_hierarchy_materialization" not in flags:
        flags.append("m38_controlled_hierarchy_materialization")
    meta["qualityFlags"] = flags
    meta["m38HierarchyMaterialization"] = {
        "containerCount": container_count,
        "movedChildCount": moved_child_count,
        "mode": "direct_match_only",
    }
    meta["elementCount"] = count_elements(dsl.get("root", {}))
    dsl["meta"] = meta


def count_elements(node: Any) -> int:
    if not isinstance(node, dict):
        return 0
    return 1 + sum(count_elements(child) for child in node.get("children", []) if isinstance(node.get("children"), list))


def skip(unit_id: str, reason: str, details: list[str] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"unitId": unit_id, "reason": reason}
    if details:
        item["details"] = details
    return item


def reason_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(item.get("reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def validate_m38_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if summary.get("absolutePositionViolationCount") != 0:
        raise ValueError("M38 absolute position drift detected.")
    if summary.get("fallbackMovedCount") != 0:
        raise ValueError("M38 must not move fallback_region nodes.")
    if summary.get("originalReferenceMovedCount") != 0:
        raise ValueError("M38 must not move original_reference nodes.")
    if summary.get("assetChanged") is not False:
        raise ValueError("M38 must not change DSL assets.")
