#!/usr/bin/env python3
"""
Offline audit for Go M29 VisualTree group evidence.

This tool joins existing artifacts only:
  - visual_tree.v1.json for current tree structure and bbox-derived features
  - visual_tree_trace.v1.jsonl for create-event provenance
  - visual_tree_eval_trace.json for matched/extra labels

It deliberately does not create or require a new VisualTree runtime artifact.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict


CREATE_DECISION = "create_group"
DEFAULT_GROUP_KIND = "spatial_group"
PROJECTION_REASONS = {"xycut_x", "xycut_y", "neighbor_component"}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_trace_events(path):
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def create_events_by_node(events):
    by_node = {}
    for event in events:
        if event.get("decision") != CREATE_DECISION:
            continue
        for node_id in event.get("outputNodeIds") or []:
            by_node.setdefault(node_id, event)
    return by_node


def walk_tree(node, parent_id="", depth=0, spatial_depth=0):
    meta = node.get("meta") or {}
    current = {
        "node": node,
        "parentId": parent_id,
        "treeDepth": depth,
        "computedSpatialDepth": spatial_depth,
    }
    yield current
    child_spatial_depth = spatial_depth + 1 if meta.get("groupKind") == DEFAULT_GROUP_KIND else spatial_depth
    for child in node.get("children") or []:
        yield from walk_tree(child, node.get("id", ""), depth + 1, child_spatial_depth)


def tree_index(tree_path):
    data = load_json(tree_path)
    root = data.get("root", data)
    return {item["node"].get("id", ""): item for item in walk_tree(root) if item["node"].get("id")}


def bbox_area(bbox):
    return max(0, bbox.get("width", 0)) * max(0, bbox.get("height", 0))


def leaf_count(node):
    children = node.get("children") or []
    if not children:
        return 1
    return sum(leaf_count(child) for child in children)


def descendants(node):
    for child in node.get("children") or []:
        yield child
        yield from descendants(child)


def descendant_source_relation_count(node):
    count = len((node.get("sourceRefs") or {}).get("relationIds") or [])
    for child in node.get("children") or []:
        count += descendant_source_relation_count(child)
    return count


def child_kind(child):
    meta = child.get("meta") or {}
    return meta.get("groupKind") or child.get("type") or "?"


def bool_text(value):
    return "true" if value else "false"


def short_side_bin(value):
    if value is None:
        return "missing"
    if value <= 8:
        return "000-008"
    if value <= 20:
        return "009-020"
    if value <= 40:
        return "021-040"
    if value <= 80:
        return "041-080"
    return "081+"


def area_ratio_bin(value):
    if value is None:
        return "missing"
    if value <= 0.01:
        return "0.00-0.01"
    if value <= 0.05:
        return "0.01-0.05"
    if value <= 0.15:
        return "0.05-0.15"
    if value <= 0.40:
        return "0.15-0.40"
    return "0.40+"


def direct_child_kinds(node):
    return tuple(child_kind(child) for child in node.get("children") or [])


def has_descendant_type(node, node_type):
    if node.get("type") == node_type:
        return True
    return any(child.get("type") == node_type or has_descendant_type(child, node_type) for child in node.get("children") or [])


def has_synthetic_background(node):
    for item in descendants(node):
        meta = item.get("meta") or {}
        if meta.get("synthetic") and meta.get("groupKind") == "background_leaf":
            return True
    return False


def feature_record(go_item, tree_items, create_events, label):
    node_id = go_item.get("nodeId") or go_item.get("sourceId") or ""
    tree_item = tree_items.get(node_id)
    node = tree_item["node"] if tree_item else {}
    parent = tree_items.get(tree_item["parentId"], {}).get("node", {}) if tree_item else {}
    meta = node.get("meta") or {}
    bbox = node.get("bbox") or {}
    parent_bbox = parent.get("bbox") or {}
    create_event = create_events.get(node_id)
    event_metrics = (create_event or {}).get("metrics") or {}
    event_thresholds = (create_event or {}).get("thresholds") or {}
    children = node.get("children") or []
    short_side = min(bbox.get("width", 0), bbox.get("height", 0)) if bbox else None
    area_ratio = None
    parent_area = bbox_area(parent_bbox)
    if parent_area > 0 and bbox:
        area_ratio = round(bbox_area(bbox) / parent_area, 4)
    child_kinds = direct_child_kinds(node)
    contains_text = has_descendant_type(node, "Text")
    contains_image = has_descendant_type(node, "Image")
    contains_layer = has_descendant_type(node, "Layer")
    spatial_depth = (create_event or {}).get("spatialDepth")
    if spatial_depth is None and tree_item:
        spatial_depth = tree_item["computedSpatialDepth"]

    parent_reason = meta.get("parentReason") or (create_event or {}).get("reason") or ""
    group_kind = go_item.get("groupKind") or meta.get("groupKind") or node.get("type", "")
    source_refs = node.get("sourceRefs") or {}

    return {
        "label": label,
        "nodeId": node_id,
        "normalizedNodeId": go_item.get("normalizedNodeId", ""),
        "verdict": go_item.get("verdict", ""),
        "bestCodiaIoU": go_item.get("bestCodiaIoU", 0.0),
        "groupKind": group_kind,
        "nodeType": node.get("type", go_item.get("type", "")),
        "groupRole": meta.get("groupRole", ""),
        "parentReason": parent_reason,
        "operation": (create_event or {}).get("operation", ""),
        "decisionClass": (create_event or {}).get("decisionClass", ""),
        "createEventFound": bool(create_event),
        "parentNodeId": tree_item["parentId"] if tree_item else go_item.get("parentNodeId", ""),
        "treeJoinFound": bool(tree_item),
        "spatialDepth": spatial_depth,
        "treeDepth": tree_item["treeDepth"] if tree_item else None,
        "childCount": len(children),
        "leafCount": leaf_count(node) if node else 0,
        "containsText": contains_text,
        "containsImage": contains_image,
        "containsLayer": contains_layer,
        "containsSyntheticBackground": has_synthetic_background(node) if node else False,
        "childKinds": child_kinds,
        "childKindsKey": "|".join(child_kinds) if child_kinds else "(none)",
        "width": bbox.get("width"),
        "height": bbox.get("height"),
        "shortSide": short_side,
        "shortSideBin": short_side_bin(short_side),
        "areaRatio": area_ratio,
        "areaRatioBin": area_ratio_bin(area_ratio),
        "sourceTokenRefs": len(source_refs.get("tokenIds") or []),
        "sourceRelationRefs": len(source_refs.get("relationIds") or []),
        "descendantSourceRelationRefs": descendant_source_relation_count(node) if node else 0,
        "backgroundTokenRefs": len(source_refs.get("backgroundTokenIds") or []),
        "traceMetrics": event_metrics,
        "traceThresholds": event_thresholds,
    }


def records_for_case(tree_path, trace_path, eval_path, label):
    tree_items = tree_index(tree_path)
    create_events = create_events_by_node(load_trace_events(trace_path))
    eval_trace = load_json(eval_path)
    records = [
        feature_record(item, tree_items, create_events, label)
        for item in eval_trace.get("goContainers") or []
    ]
    return records


def parse_manifest(path):
    pairs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            label = parts[2] if len(parts) > 2 else os.path.basename(parts[1])
            pairs.append((label, parts[1]))
    return pairs


def records_for_batch(manifest_path, eval_dir):
    records = []
    for index, (label, tree_path) in enumerate(parse_manifest(manifest_path), start=1):
        trace_path = os.path.join(os.path.dirname(tree_path), "visual_tree_trace.v1.jsonl")
        eval_path = os.path.join(eval_dir, f"case_{index:03d}_visual_tree_eval_trace.json")
        records.extend(records_for_case(tree_path, trace_path, eval_path, label))
    return records


def selected_records(records, group_kind):
    if group_kind == "all":
        return list(records)
    return [record for record in records if record["groupKind"] == group_kind]


def count_by_feature(records, feature):
    counts = defaultdict(lambda: Counter({"matched": 0, "extra": 0}))
    for record in records:
        verdict = record["verdict"]
        if verdict not in {"matched", "extra"}:
            continue
        value = record.get(feature)
        if isinstance(value, bool):
            value = bool_text(value)
        if value is None or value == "":
            value = "(empty)"
        counts[str(value)][verdict] += 1
    return counts


def precision(matched, extra):
    total = matched + extra
    return matched / total if total else 0.0


def format_count_table(title, counts, limit=None):
    rows = []
    for value, counter in counts.items():
        matched = counter["matched"]
        extra = counter["extra"]
        rows.append((extra, matched, value, precision(matched, extra)))
    rows.sort(key=lambda row: (-row[0], -row[1], row[2]))
    if limit:
        rows = rows[:limit]
    lines = [title, f"{'value':<48}{'matched':>9}{'extra':>8}{'precision':>11}"]
    for extra, matched, value, prec in rows:
        lines.append(f"{value[:48]:<48}{matched:>9}{extra:>8}{prec:>11.3f}")
    return "\n".join(lines)


def signature(record):
    return (
        record["parentReason"] or "(empty)",
        bool_text(record["containsText"]),
        record["shortSideBin"],
        record["areaRatioBin"],
        record["childKindsKey"],
    )


def format_top_extra_signatures(records, limit=12):
    counts = defaultdict(lambda: Counter({"matched": 0, "extra": 0}))
    for record in records:
        verdict = record["verdict"]
        if verdict in {"matched", "extra"}:
            counts[signature(record)][verdict] += 1
    rows = []
    for sig, counter in counts.items():
        rows.append((counter["extra"], counter["matched"], sig, precision(counter["matched"], counter["extra"])))
    rows.sort(key=lambda row: (-row[0], row[1], row[2]))
    lines = [
        "Top extra signatures",
        f"{'parentReason':<22}{'text':>7}{'short':>11}{'area':>12}{'matched':>9}{'extra':>8}{'precision':>11}  childKinds",
    ]
    for extra, matched, sig, prec in rows[:limit]:
        parent_reason, contains_text, short_bin, area_bin, child_kinds = sig
        lines.append(
            f"{parent_reason[:22]:<22}{contains_text:>7}{short_bin:>11}{area_bin:>12}"
            f"{matched:>9}{extra:>8}{prec:>11.3f}  {child_kinds[:80]}"
        )
    return "\n".join(lines)


def rule_projection_no_text_short_side(limit):
    name = f"projection_no_text_shortSide<={limit}"

    def matches(record):
        return (
            record["groupKind"] == DEFAULT_GROUP_KIND
            and record["parentReason"] in PROJECTION_REASONS
            and not record["containsText"]
            and (record["shortSide"] is not None and record["shortSide"] <= limit)
        )

    return name, matches


def rule_layer_no_text_short_side(limit):
    name = f"layer_no_text_shortSide<={limit}"

    def matches(record):
        return (
            record["groupKind"] == "Layer"
            and not record["containsText"]
            and (record["shortSide"] is not None and record["shortSide"] <= limit)
        )

    return name, matches


def rule_any_no_text_short_side(limit):
    name = f"any_no_text_shortSide<={limit}"

    def matches(record):
        return (
            not record["containsText"]
            and (record["shortSide"] is not None and record["shortSide"] <= limit)
        )

    return name, matches


def backtest_rules(records):
    rules = [
        rule_projection_no_text_short_side(20),
        rule_projection_no_text_short_side(32),
        rule_layer_no_text_short_side(8),
        rule_any_no_text_short_side(8),
    ]
    lines = [
        "Rule backtest",
        f"{'rule':<42}{'wouldCollapse':>14}{'extraCollapsed':>16}{'matchedLost':>13}{'rulePrecision':>15}{'recallRisk':>12}",
    ]
    matched_total = sum(1 for record in records if record["verdict"] == "matched")
    for name, matches in rules:
        selected = [record for record in records if matches(record)]
        extra = sum(1 for record in selected if record["verdict"] == "extra")
        matched = sum(1 for record in selected if record["verdict"] == "matched")
        rule_precision = extra / len(selected) if selected else 0.0
        recall_risk = matched / matched_total if matched_total else 0.0
        lines.append(
            f"{name:<42}{len(selected):>14}{extra:>16}{matched:>13}"
            f"{rule_precision:>15.3f}{recall_risk:>12.3f}"
        )
    return "\n".join(lines)


def join_summary(records):
    total = len(records)
    tree_missing = sum(1 for record in records if not record["treeJoinFound"])
    synthetic = [record for record in records if record["groupKind"] not in {"Body", "Layer"} or record["groupRole"]]
    synthetic_create_missing = sum(1 for record in synthetic if not record["createEventFound"])
    return [
        f"records: {total}",
        f"treeJoinMissing: {tree_missing}",
        f"syntheticCreateEventMissing: {synthetic_create_missing}",
    ]


def print_report(records, group_kind):
    target = selected_records(records, group_kind)
    matched = sum(1 for record in target if record["verdict"] == "matched")
    extra = sum(1 for record in target if record["verdict"] == "extra")
    print("=" * 96)
    print(f"Group evidence audit: groupKind={group_kind}")
    print("-" * 96)
    for line in join_summary(records):
        print(line)
    print(f"selected: {len(target)} matched={matched} extra={extra} precision={precision(matched, extra):.3f}")
    print("=" * 96)
    for feature in [
        "groupKind",
        "parentReason",
        "operation",
        "spatialDepth",
        "childCount",
        "containsText",
        "shortSideBin",
        "areaRatioBin",
        "childKindsKey",
    ]:
        print(format_count_table(f"By {feature}", count_by_feature(target, feature), limit=20))
        print("-" * 96)
    print(format_top_extra_signatures(target))
    print("-" * 96)
    print(backtest_rules(target))
    print("=" * 96)


def main():
    parser = argparse.ArgumentParser(description="Audit VisualTree group evidence by joining tree, decision trace, and eval trace.")
    parser.add_argument("--tree", help="Path to visual_tree.v1.json for single-case mode")
    parser.add_argument("--trace", help="Path to visual_tree_trace.v1.jsonl for single-case mode")
    parser.add_argument("--eval", help="Path to visual_tree_eval_trace.json for single-case mode")
    parser.add_argument("--batch", help="Manifest path from eval_4img.sh")
    parser.add_argument("--eval-dir", help="Directory containing case_XXX_visual_tree_eval_trace.json")
    parser.add_argument("--group-kind", default=DEFAULT_GROUP_KIND, help="Group kind to report, or 'all'")
    args = parser.parse_args()

    if args.batch:
        if not args.eval_dir:
            raise SystemExit("--batch requires --eval-dir")
        records = records_for_batch(args.batch, args.eval_dir)
    else:
        if not args.tree or not args.trace or not args.eval:
            raise SystemExit("single-case mode requires --tree, --trace, and --eval")
        records = records_for_case(args.tree, args.trace, args.eval, os.path.basename(os.path.dirname(args.tree)))
    print_report(records, args.group_kind)


if __name__ == "__main__":
    main()
