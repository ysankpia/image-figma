from __future__ import annotations

from typing import Any


def validate_sibling_group_candidate_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29SiblingGroupCandidateReport":
        raise ValueError("invalid sibling group candidate schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid sibling group candidate schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("sibling group candidate summary must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "groupMaterializationPermission"]:
        if summary.get(key) is not False:
            raise ValueError(f"sibling group candidate report must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("sibling group candidate report must not create visible nodes")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("sibling group candidate meta must be an object")
    for key in ["siblingGroupCandidates", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"sibling group candidate {key} must be a list")
