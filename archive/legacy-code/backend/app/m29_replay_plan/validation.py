from __future__ import annotations

from typing import Any


def validate_replay_plan(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M295ReplayPlan":
        raise ValueError("invalid M29.5 schemaName")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("M29.5 summary must be an object")
    if summary.get("dslChanged") is not False:
        raise ValueError("M29.5 must not change DSL")
    if summary.get("assetChanged") is not False:
        raise ValueError("M29.5 must not change assets")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("M29.5 must not create visible nodes")
