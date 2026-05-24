from __future__ import annotations

from typing import Any


def build_summary(quality_summary: dict[str, Any], risk_summary: dict[str, Any], repair_cost: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "qualityScore": quality_summary["score"],
        "qualityGrade": quality_summary["grade"],
        "repairCost": repair_cost["totalCost"],
        "ownershipErrorCount": risk_summary["ownershipErrorCount"],
        "ownershipConflictCount": risk_summary["ownershipConflictCount"],
        "warningCount": len(warnings) + risk_summary["warningCount"],
        "autoLayoutAllowCandidateCount": quality_summary["autoLayoutAllowCandidateCount"],
        "designTokenCandidateCount": quality_summary["designTokenCandidateCount"],
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "blockingUpload": False,
        "reportOnly": True,
    }

