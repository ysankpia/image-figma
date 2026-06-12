from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .energy import build_layout_energy_candidates
from .normalization import normalize_plan_items, normalize_selected_parents, normalize_sibling_groups
from .report import build_summary, strip_internal_subject_fields
from .subjects import build_layout_subjects
from .types import M29LayoutEnergyResult
from .validation import validate_layout_energy_report


def extract_m29_layout_energy_report(
    *,
    task_id: str,
    m295_report: dict[str, Any],
    hierarchy_report: dict[str, Any] | None,
    sibling_group_report: dict[str, Any] | None,
    output_dir: Path,
) -> M29LayoutEnergyResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    plan_items, plan_warnings = normalize_plan_items(m295_report.get("planItems", []))
    visible_source_ids = {item["sourceObjectId"] for item in plan_items if item["visible"]}
    sibling_groups, sibling_warnings = normalize_sibling_groups((sibling_group_report or {}).get("siblingGroupCandidates", []), visible_source_ids)
    selected_parents, parent_warnings = normalize_selected_parents((hierarchy_report or {}).get("selectedParentCandidates", []), visible_source_ids)
    layout_subjects = build_layout_subjects(plan_items=plan_items, sibling_groups=sibling_groups, selected_parents=selected_parents)
    layout_candidates = build_layout_energy_candidates(layout_subjects)
    warnings = plan_warnings + sibling_warnings + parent_warnings

    report_path = output_dir / "layout_energy_report.json"
    report = {
        "schemaName": "M29LayoutEnergyReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "planSchemaName": m295_report.get("schemaName"),
        "planSchemaVersion": m295_report.get("schemaVersion"),
        "hierarchySchemaName": (hierarchy_report or {}).get("schemaName"),
        "hierarchySchemaVersion": (hierarchy_report or {}).get("schemaVersion"),
        "siblingGroupSchemaName": (sibling_group_report or {}).get("schemaName"),
        "siblingGroupSchemaVersion": (sibling_group_report or {}).get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            plan_items=plan_items,
            layout_subjects=layout_subjects,
            layout_candidates=layout_candidates,
            warnings=warnings,
        ),
        "layoutSubjects": strip_internal_subject_fields(layout_subjects),
        "layoutEnergyCandidates": layout_candidates,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_5_plus_hierarchy_candidates_plus_sibling_group_candidates",
            "reportOnly": True,
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "autoLayoutPermission": False,
        },
    }
    validate_layout_energy_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29LayoutEnergyResult(report=report, output_dir=output_dir)
