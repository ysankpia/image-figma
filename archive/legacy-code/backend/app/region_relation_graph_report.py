from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .region_relation_kernel import classify_region_relation, normalize_bbox


@dataclass(frozen=True)
class M2931Result:
    report: dict[str, Any]
    output_dir: Path


def extract_m2931_region_relation_graph_report(
    *,
    task_id: str,
    m292_document: dict[str, Any],
    output_dir: Path,
) -> M2931Result:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_objects = [item for item in m292_document.get("sourceObjects", []) if isinstance(item, dict)]
    nodes, skipped_items = normalize_source_nodes(source_objects)
    edges = build_edges(nodes)
    warnings = [f"skipped_invalid_bbox:{len(skipped_items)}"] if skipped_items else []
    report = {
        "schemaName": "M2931RegionRelationGraphReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "outputReport": str(output_dir / "region_relation_graph_report.json"),
        "summary": build_summary(
            source_object_count=len(source_objects),
            node_count=len(nodes),
            edge_count=len(edges),
            skipped_items=skipped_items,
            edges=edges,
            warnings=warnings,
        ),
        "nodes": nodes,
        "edges": edges,
        "skippedItems": skipped_items,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_2_source_objects_plus_m29_3_region_relation_kernel",
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "clusteringChanged": False,
            "visualKindPreservedAsRawEvidence": True,
        },
    }
    validate_report(report)
    (output_dir / "region_relation_graph_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M2931Result(report=report, output_dir=output_dir)


def normalize_source_nodes(source_objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, item in enumerate(source_objects, start=1):
        source_id = str(item.get("id") or f"m292_source_object_{index:04d}")
        try:
            bbox = normalize_bbox(item.get("bbox"), f"sourceObjects[{index - 1}].bbox")
        except ValueError as error:
            skipped.append(
                {
                    "sourceObjectId": source_id,
                    "index": index - 1,
                    "reason": "invalid_bbox",
                    "message": str(error),
                }
            )
            continue
        nodes.append(
            {
                "id": source_id,
                "bbox": bbox,
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "replayDecision": str(item.get("replayDecision") or ""),
                "confidence": str(item.get("confidence") or ""),
                "visualKind": str(item.get("visualKind") or ""),
            }
        )
    return sorted(nodes, key=lambda node: (node["id"], node["bbox"])), skipped


def build_edges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    edge_index = 1
    for left_index, left in enumerate(nodes):
        for right in nodes[left_index + 1 :]:
            relation = classify_region_relation(left["bbox"], right["bbox"]).to_dict()
            edges.append(
                {
                    "edgeId": f"m2931_edge_{edge_index:04d}",
                    "leftObjectId": left["id"],
                    "rightObjectId": right["id"],
                    "primarySetRelation": relation["primarySetRelation"],
                    "secondaryGeometryRelations": relation["secondaryGeometryRelations"],
                    "metrics": relation["metrics"],
                }
            )
            edge_index += 1
    return edges


def build_summary(
    *,
    source_object_count: int,
    node_count: int,
    edge_count: int,
    skipped_items: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    primary_counts: dict[str, int] = {}
    secondary_counts: dict[str, int] = {}
    for edge in edges:
        primary = str(edge.get("primarySetRelation") or "")
        primary_counts[primary] = primary_counts.get(primary, 0) + 1
        for relation in edge.get("secondaryGeometryRelations", []) if isinstance(edge.get("secondaryGeometryRelations"), list) else []:
            secondary = str(relation)
            secondary_counts[secondary] = secondary_counts.get(secondary, 0) + 1
    return {
        "sourceObjectCount": source_object_count,
        "nodeCount": node_count,
        "edgeCount": edge_count,
        "invalidBBoxSkippedCount": sum(1 for item in skipped_items if item.get("reason") == "invalid_bbox"),
        "warningCount": len(warnings),
        "primarySetRelationCounts": dict(sorted(primary_counts.items())),
        "secondaryGeometryRelationCounts": dict(sorted(secondary_counts.items())),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
    }


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M2931RegionRelationGraphReport":
        raise ValueError("invalid M29.3.1 schemaName")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("M29.3.1 summary must be an object")
    if summary.get("dslChanged") is not False:
        raise ValueError("M29.3.1 must not change DSL")
    if summary.get("assetChanged") is not False:
        raise ValueError("M29.3.1 must not change assets")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("M29.3.1 must not create visible nodes")
