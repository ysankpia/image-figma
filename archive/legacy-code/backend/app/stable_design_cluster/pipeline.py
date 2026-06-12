from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .candidates import build_candidates
from .clusters import build_clusters
from .motifs import group_edges_by_motif
from .normalization import normalize_edges, normalize_nodes
from .report import build_summary
from .types import M294Options, M294Result
from .validation import validate_report


def extract_m294_stable_design_cluster_report(
    *,
    task_id: str,
    m2931_report: dict[str, Any],
    output_dir: Path,
    options: M294Options | None = None,
) -> M294Result:
    options = options or M294Options()
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes, skipped_nodes = normalize_nodes(m2931_report.get("nodes", []))
    node_by_id = {node["id"]: node for node in nodes}
    edges, skipped_edges = normalize_edges(m2931_report.get("edges", []), set(node_by_id))

    motif_edges = group_edges_by_motif(edges, node_by_id)
    candidates = build_candidates(motif_edges, node_by_id)
    clusters, skipped_clusters = build_clusters(candidates, node_by_id, options)

    warnings: list[str] = []
    if skipped_nodes:
        warnings.append(f"skipped_invalid_node:{len(skipped_nodes)}")
    if skipped_edges:
        warnings.append(f"skipped_invalid_edge:{len(skipped_edges)}")

    report = {
        "schemaName": "M294StableDesignClusterReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m2931_report.get("schemaName"),
        "sourceSchemaVersion": m2931_report.get("schemaVersion"),
        "outputReport": str(output_dir / "stable_design_cluster_report.json"),
        "summary": build_summary(
            source_node_count=len(nodes),
            source_edge_count=len(edges),
            structural_edge_count=sum(len(items) for items in motif_edges.values()),
            clusters=clusters,
            skipped_nodes=skipped_nodes,
            skipped_edges=skipped_edges,
            skipped_clusters=skipped_clusters,
            warnings=warnings,
        ),
        "options": options.to_dict(),
        "clusters": clusters,
        "skippedItems": skipped_nodes + skipped_edges + skipped_clusters,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_3_relation_graph_report_only",
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "componentChanged": False,
            "roleHintsAreWeakStructuralEvidence": True,
        },
    }
    validate_report(report)
    (output_dir / "stable_design_cluster_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return M294Result(report=report, output_dir=output_dir)
