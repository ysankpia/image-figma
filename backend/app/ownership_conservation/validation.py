from __future__ import annotations

from typing import Any


def validate_ownership_conservation_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29OwnershipConservationReport":
        raise ValueError("invalid ownership conservation schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid ownership conservation schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("ownership conservation summary must be an object")
    if summary.get("dslChanged") is not False:
        raise ValueError("ownership conservation report must not change DSL")
    if summary.get("assetChanged") is not False:
        raise ValueError("ownership conservation report must not change assets")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("ownership conservation report must not create visible nodes")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("ownership conservation meta must be an object")
    if meta.get("dslChanged") is not False or meta.get("assetChanged") is not False:
        raise ValueError("ownership conservation meta must be report-only")
    for key in ["sourceObjectClaims", "visibleReplayClaims", "cleanupClaims", "conflicts", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"ownership conservation {key} must be a list")

