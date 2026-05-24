from __future__ import annotations

from typing import Any


def validate_auto_layout_permission_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29AutoLayoutPermissionReport":
        raise ValueError("invalid auto layout permission schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid auto layout permission schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("auto layout permission summary must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "autoLayoutCreated"]:
        if summary.get(key) is not False:
            raise ValueError(f"auto layout permission report must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("auto layout permission report must not create visible nodes")
    if summary.get("permissionOnly") is not True:
        raise ValueError("auto layout permission report must be permission-only")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("auto layout permission meta must be an object")
    for key in ["permissionItems", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"auto layout permission {key} must be a list")
    for item in report.get("permissionItems", []):
        if item.get("materializationPermission") is not False or item.get("autoLayoutCreated") is not False:
            raise ValueError("auto layout permission item must not grant materialization")
