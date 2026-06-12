from __future__ import annotations

from typing import Any


def validate_hierarchy_candidate_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29HierarchyCandidateReport":
        raise ValueError("invalid hierarchy candidate schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid hierarchy candidate schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("hierarchy candidate summary must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged"]:
        if summary.get(key) is not False:
            raise ValueError(f"hierarchy candidate report must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("hierarchy candidate report must not create visible nodes")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("hierarchy candidate meta must be an object")
    for key in ["containerCandidates", "parentCandidates", "selectedParentCandidates", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"hierarchy candidate {key} must be a list")
