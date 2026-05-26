from __future__ import annotations

from typing import Any


def validate_m29_perception_fate_trace_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29PerceptionFateTraceReport":
        raise ValueError("invalid perception fate trace schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid perception fate trace schemaVersion")
    summary = report.get("summary")
    meta = report.get("meta")
    traces = report.get("traces")
    if not isinstance(summary, dict) or not isinstance(meta, dict) or not isinstance(traces, list):
        raise ValueError("perception fate trace report requires summary/meta/traces")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "sourceOwnershipChanged"]:
        if summary.get(key) is not False or meta.get(key) is not False:
            raise ValueError(f"perception fate trace must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("perception fate trace must not create visible nodes")
    if meta.get("reportOnly") is not True:
        raise ValueError("perception fate trace must be report-only")
    if meta.get("materializerConsumesTrace") is not False:
        raise ValueError("materializer must not consume perception fate trace")
    for trace in traces:
        if not isinstance(trace, dict):
            raise ValueError("perception fate trace items must be objects")
        if not trace.get("candidateId"):
            raise ValueError("perception fate trace item missing candidateId")
        if "firstBlockingStage" not in trace or "firstBlockingReason" not in trace:
            raise ValueError("perception fate trace item missing first blocking fields")
