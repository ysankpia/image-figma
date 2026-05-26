from __future__ import annotations

from typing import Any


def validate_perception_source_compiler_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29PerceptionSourceCompilerReport":
        raise ValueError("invalid perception source compiler schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid perception source compiler schemaVersion")
    summary = report.get("summary")
    meta = report.get("meta")
    if not isinstance(summary, dict) or not isinstance(meta, dict):
        raise ValueError("perception source compiler requires summary and meta")
    for key in ["dslChanged", "assetChanged", "materializationChanged"]:
        if summary.get(key) is not False or meta.get(key) is not False:
            raise ValueError(f"perception source compiler must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("perception source compiler must not create visible nodes")
    if not isinstance(report.get("compiledSourceObjects"), list):
        raise ValueError("perception source compiler compiledSourceObjects must be a list")
    if not isinstance(report.get("rejectedCandidates"), list):
        raise ValueError("perception source compiler rejectedCandidates must be a list")

