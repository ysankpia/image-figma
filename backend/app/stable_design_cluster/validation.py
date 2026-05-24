from __future__ import annotations

from typing import Any


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M294StableDesignClusterReport":
        raise ValueError("invalid M29.4 schemaName")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("M29.4 summary must be an object")
    if summary.get("dslChanged") is not False:
        raise ValueError("M29.4 must not change DSL")
    if summary.get("assetChanged") is not False:
        raise ValueError("M29.4 must not change assets")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("M29.4 must not create visible nodes")
    if summary.get("componentChanged") is not False:
        raise ValueError("M29.4 must not create components")
    for cluster in report.get("clusters", []):
        role_hint = cluster.get("roleHint")
        if role_hint is not None and role_hint not in {"row_like", "column_like", "repeated_item_like", "background_anchor_like", "media_text_group_like"}:
            raise ValueError(f"M29.4 roleHint is not structural: {role_hint}")
