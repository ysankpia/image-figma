from __future__ import annotations

from typing import Any


def validate_b_stage_quality_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29BStageQualityReport":
        raise ValueError("invalid B-stage quality schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid B-stage quality schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("B-stage quality summary must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "blockingUpload"]:
        if summary.get(key) is not False:
            raise ValueError(f"B-stage quality report must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("B-stage quality report must not create visible nodes")
    if summary.get("reportOnly") is not True:
        raise ValueError("B-stage quality report must be report-only")
    for key in ["qualitySummary", "riskSummary", "repairCost", "capabilityMaturity", "warnings"]:
        if key not in report:
            raise ValueError(f"B-stage quality report missing {key}")

