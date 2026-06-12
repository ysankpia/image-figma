from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .quality import build_quality_summary
from .report import build_summary
from .types import M29BStageQualityResult
from .validation import validate_b_stage_quality_report


def extract_m29_b_stage_quality_report(
    *,
    task_id: str,
    ownership_report: dict[str, Any] | None,
    hierarchy_report: dict[str, Any] | None,
    sibling_group_report: dict[str, Any] | None,
    layout_energy_report: dict[str, Any] | None,
    auto_layout_permission_report: dict[str, Any] | None,
    design_token_report: dict[str, Any] | None,
    materialization_report: dict[str, Any] | None,
    output_dir: Path,
) -> M29BStageQualityResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    quality = build_quality_summary(
        ownership_report=ownership_report,
        hierarchy_report=hierarchy_report,
        sibling_group_report=sibling_group_report,
        layout_energy_report=layout_energy_report,
        auto_layout_permission_report=auto_layout_permission_report,
        design_token_report=design_token_report,
        materialization_report=materialization_report,
    )
    report_path = output_dir / "b_stage_quality_report.json"
    report = {
        "schemaName": "M29BStageQualityReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "outputReport": str(report_path),
        "summary": build_summary(quality["qualitySummary"], quality["riskSummary"], quality["repairCost"], warnings),
        "qualitySummary": quality["qualitySummary"],
        "riskSummary": quality["riskSummary"],
        "repairCost": quality["repairCost"],
        "capabilityMaturity": quality["capabilityMaturity"],
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_b_stage_reports_plus_materialization_report",
            "reportOnly": True,
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "blockingUpload": False,
        },
    }
    validate_b_stage_quality_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29BStageQualityResult(report=report, output_dir=output_dir)

