from __future__ import annotations

from typing import Any


def validate_transparent_asset_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29TransparentAssetReport":
        raise ValueError("invalid transparent asset report schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid transparent asset report schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("transparent asset summary must be an object")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("transparent asset meta must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "materializerConsumesAssets", "blockingUpload"]:
        if summary.get(key) is not False:
            raise ValueError(f"transparent asset report must not change {key}")
        if meta.get(key) is not False:
            raise ValueError(f"transparent asset meta must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("transparent asset report must not create visible nodes")
    if meta.get("reportOnly") is not True:
        raise ValueError("transparent asset report must be report-only")
    if meta.get("noSpecializedTextFilenameThemeOrFixedBboxRules") is not True:
        raise ValueError("transparent asset report must declare no specialization rules")
    for key in ["items", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"transparent asset {key} must be a list")
    for item in report["items"]:
        if item.get("decision") not in {"allow", "reject"}:
            raise ValueError("transparent asset item decision must be allow or reject")
