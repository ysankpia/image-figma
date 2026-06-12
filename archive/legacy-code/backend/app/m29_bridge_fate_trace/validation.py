from __future__ import annotations

from typing import Any


def validate_m29_bridge_fate_trace_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29BridgeFateTraceReport":
        raise ValueError("invalid bridge fate trace schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid bridge fate trace schemaVersion")
    summary = report.get("summary")
    meta = report.get("meta")
    traces = report.get("traces")
    if not isinstance(summary, dict) or not isinstance(meta, dict) or not isinstance(traces, list):
        raise ValueError("bridge fate trace report requires summary/meta/traces")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "sourceOwnershipChanged"]:
        if summary.get(key) is not False or meta.get(key) is not False:
            raise ValueError(f"bridge fate trace must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("bridge fate trace must not create visible nodes")
    if meta.get("reportOnly") is not True:
        raise ValueError("bridge fate trace must be report-only")
    for trace in traces:
        if not isinstance(trace, dict):
            raise ValueError("bridge fate trace items must be objects")
        if not trace.get("candidateId"):
            raise ValueError("bridge fate trace item missing candidateId")
