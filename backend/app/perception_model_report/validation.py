from __future__ import annotations

from typing import Any


def validate_perception_model_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29PerceptionModelReport":
        raise ValueError("invalid perception model schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid perception model schemaVersion")
    summary = report.get("summary")
    meta = report.get("meta")
    candidates = report.get("candidates")
    if not isinstance(summary, dict) or not isinstance(meta, dict) or not isinstance(candidates, list):
        raise ValueError("perception model report requires summary/meta/candidates")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "sourceOwnershipChanged", "cleanupAuthorized", "blockingUpload"]:
        if summary.get(key) is not False or meta.get(key) is not False:
            raise ValueError(f"perception model report must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("perception model report must not create visible nodes")
    if summary.get("reportOnly") is not True or meta.get("reportOnly") is not True:
        raise ValueError("perception model report must be report-only")
    for candidate in candidates:
        validate_candidate(candidate)


def validate_candidate(candidate: dict[str, Any]) -> None:
    if not candidate.get("candidateId"):
        raise ValueError("perception candidate missing candidateId")
    bbox = candidate.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("perception candidate bbox must be [x1,y1,x2,y2]")
    x1, y1, x2, y2 = [float(value) for value in bbox]
    if x2 <= x1 or y2 <= y1:
        raise ValueError("perception candidate bbox must have positive area")
    if candidate.get("decision") != "report_only":
        raise ValueError("perception candidate must remain report_only")
    if candidate.get("replayAuthorized") is not False or candidate.get("cleanupAuthorized") is not False:
        raise ValueError("perception candidate must not authorize replay or cleanup")
