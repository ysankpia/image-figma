from __future__ import annotations

from typing import Any


def validate_m29_evidence_contract_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29EvidenceContractReport":
        raise ValueError("invalid evidence contract schemaName")
    if report.get("schemaVersion") != "0.1":
        raise ValueError("invalid evidence contract schemaVersion")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("evidence contract summary must be an object")
    meta = report.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("evidence contract meta must be an object")
    for key in ["dslChanged", "assetChanged", "materializationChanged", "sourceOwnershipChanged", "materializerConsumesContracts", "blockingUpload"]:
        if summary.get(key) is not False:
            raise ValueError(f"evidence contract report must not change {key}")
        if meta.get(key) is not False:
            raise ValueError(f"evidence contract meta must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("evidence contract report must not create visible nodes")
    if meta.get("reportOnly") is not True:
        raise ValueError("evidence contract report must be report-only")
    if meta.get("noSpecializedTextFilenameThemeOrFixedBboxRules") is not True:
        raise ValueError("evidence contract report must declare no specialization rules")
    for key in ["contractItems", "warnings"]:
        if not isinstance(report.get(key), list):
            raise ValueError(f"evidence contract {key} must be a list")
    for item in report["contractItems"]:
        validate_contract_item(item)


def validate_contract_item(item: dict[str, Any]) -> None:
    if not str(item.get("contractId") or ""):
        raise ValueError("evidence contract item requires contractId")
    decision = item.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("evidence contract item decision must be an object")
    if decision.get("mode") not in {"allow_visible_replay", "report_only", "reject"}:
        raise ValueError("invalid evidence contract decision mode")
    if item.get("reportOnly") is not True:
        raise ValueError("evidence contract item must be report-only")
    for key in ["sourceTruth", "positiveEvidence", "negativeEvidence", "risk"]:
        if not isinstance(item.get(key), dict):
            raise ValueError(f"evidence contract item {key} must be an object")
