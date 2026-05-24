from __future__ import annotations

from typing import Any


def validate_layout_energy_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29LayoutEnergyReport":
        raise ValueError("invalid layout energy schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid layout energy schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("layout energy summary must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "autoLayoutPermission"]:
        if summary.get(key) is not False:
            raise ValueError(f"layout energy report must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("layout energy report must not create visible nodes")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("layout energy meta must be an object")
    for key in ["layoutSubjects", "layoutEnergyCandidates", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"layout energy {key} must be a list")
