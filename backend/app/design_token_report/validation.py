from __future__ import annotations

from typing import Any


def validate_design_token_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29DesignTokenReport":
        raise ValueError("invalid design token schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid design token schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("design token summary must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "figmaVariablesBound", "designSystemChanged"]:
        if summary.get(key) is not False:
            raise ValueError(f"design token report must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("design token report must not create visible nodes")
    if summary.get("singlePageOnly") is not True:
        raise ValueError("design token report must be single-page only")
    for key in ["colorTokens", "textStyleTokens", "radiusTokens", "spacingTokens", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"design token {key} must be a list")

