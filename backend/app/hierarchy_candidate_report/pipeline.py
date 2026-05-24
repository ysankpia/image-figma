from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .candidates import build_hierarchy_candidates, select_best_parent_candidates
from .normalization import normalize_edges, normalize_plan_items, normalize_source_objects
from .relations import build_edge_lookup
from .report import build_summary
from .types import M29HierarchyCandidateResult
from .validation import validate_hierarchy_candidate_report


def extract_m29_hierarchy_candidate_report(
    *,
    task_id: str,
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any] | None,
    m295_report: dict[str, Any],
    output_dir: Path,
) -> M29HierarchyCandidateResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_objects, source_warnings = normalize_source_objects(m292_document.get("sourceObjects", []))
    valid_source_ids = {item["sourceObjectId"] for item in source_objects}
    plan_items, plan_warnings = normalize_plan_items(m295_report.get("planItems", []))
    edges, edge_warnings = normalize_edges((m2931_report or {}).get("edges", []), valid_source_ids)
    edge_lookup = build_edge_lookup(edges)

    container_candidates, parent_candidates = build_hierarchy_candidates(
        source_objects=source_objects,
        plan_items=plan_items,
        edge_lookup=edge_lookup,
    )
    selected_parent_candidates = select_best_parent_candidates(parent_candidates)
    warnings = source_warnings + plan_warnings + edge_warnings
    report_path = output_dir / "hierarchy_candidate_report.json"
    report = {
        "schemaName": "M29HierarchyCandidateReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "relationSchemaName": (m2931_report or {}).get("schemaName"),
        "relationSchemaVersion": (m2931_report or {}).get("schemaVersion"),
        "planSchemaName": m295_report.get("schemaName"),
        "planSchemaVersion": m295_report.get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            source_objects=source_objects,
            plan_items=plan_items,
            container_candidates=container_candidates,
            parent_candidates=parent_candidates,
            selected_parent_candidates=selected_parent_candidates,
            warnings=warnings,
        ),
        "containerCandidates": container_candidates,
        "parentCandidates": parent_candidates,
        "selectedParentCandidates": selected_parent_candidates,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_2_plus_m29_3_1_plus_m29_5",
            "reportOnly": True,
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "groupFrameAutoLayoutPermission": False,
        },
    }
    validate_hierarchy_candidate_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29HierarchyCandidateResult(report=report, output_dir=output_dir)
