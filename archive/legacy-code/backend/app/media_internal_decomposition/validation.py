from __future__ import annotations

from typing import Any


def validate_media_internal_decomposition_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29MediaInternalDecompositionReport":
        raise ValueError("invalid media internal decomposition schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid media internal decomposition schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("media internal decomposition summary must be an object")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("media internal decomposition meta must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "blockingUpload"]:
        if summary.get(key) is not False:
            raise ValueError(f"media internal decomposition report must not change {key}")
        if meta.get(key) is not False:
            raise ValueError(f"media internal decomposition meta must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("media internal decomposition report must not create visible nodes")
    if meta.get("reportOnly") is not True:
        raise ValueError("media internal decomposition report must be report-only")
    if meta.get("noSpecializedTextFilenameThemeOrFixedBboxRules") is not True:
        raise ValueError("media internal decomposition report must declare no specialization rules")
    for key in ["compositeMediaItems", "textMasks", "internalCandidates", "matchedInternalGroups", "rejectedFragments", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"media internal decomposition {key} must be a list")
