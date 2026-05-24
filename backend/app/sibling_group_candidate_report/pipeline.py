from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .candidates import build_sibling_group_candidates
from .normalization import normalize_clusters, normalize_edges, normalize_hierarchy_edges, normalize_plan_items
from .report import build_summary
from .types import M29SiblingGroupCandidateResult
from .validation import validate_sibling_group_candidate_report


def extract_m29_sibling_group_candidate_report(
    *,
    task_id: str,
    m2931_report: dict[str, Any] | None,
    m294_report: dict[str, Any] | None,
    m295_report: dict[str, Any],
    hierarchy_report: dict[str, Any] | None,
    output_dir: Path,
) -> M29SiblingGroupCandidateResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    plan_items, plan_warnings = normalize_plan_items(m295_report.get("planItems", []))
    plan_source_ids = {item["sourceObjectId"] for item in plan_items}
    visible_source_ids = {item["sourceObjectId"] for item in plan_items if item["visible"]}
    edges, edge_warnings = normalize_edges((m2931_report or {}).get("edges", []), plan_source_ids)
    clusters, cluster_warnings = normalize_clusters((m294_report or {}).get("clusters", []), visible_source_ids)
    hierarchy_edges = normalize_hierarchy_edges((hierarchy_report or {}).get("selectedParentCandidates", []))

    sibling_groups = build_sibling_group_candidates(
        plan_items=plan_items,
        edges=edges,
        clusters=clusters,
        hierarchy_edges=hierarchy_edges,
    )
    warnings = plan_warnings + edge_warnings + cluster_warnings

    report_path = output_dir / "sibling_group_candidate_report.json"
    report = {
        "schemaName": "M29SiblingGroupCandidateReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "relationSchemaName": (m2931_report or {}).get("schemaName"),
        "relationSchemaVersion": (m2931_report or {}).get("schemaVersion"),
        "clusterSchemaName": (m294_report or {}).get("schemaName"),
        "clusterSchemaVersion": (m294_report or {}).get("schemaVersion"),
        "planSchemaName": m295_report.get("schemaName"),
        "planSchemaVersion": m295_report.get("schemaVersion"),
        "hierarchySchemaName": (hierarchy_report or {}).get("schemaName"),
        "hierarchySchemaVersion": (hierarchy_report or {}).get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            plan_items=plan_items,
            edges=edges,
            clusters=clusters,
            sibling_groups=sibling_groups,
            warnings=warnings,
        ),
        "siblingGroupCandidates": sibling_groups,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_3_1_plus_m29_4_plus_m29_5_plus_hierarchy_candidates",
            "reportOnly": True,
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "groupMaterializationPermission": False,
        },
    }
    validate_sibling_group_candidate_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29SiblingGroupCandidateResult(report=report, output_dir=output_dir)
