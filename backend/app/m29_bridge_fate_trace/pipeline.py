from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..transparent_asset_report.gates import visible_replay_block_reason, visible_replay_eligible
from .report import build_summary
from .types import M29BridgeFateTraceResult, REPORT_ONLY_META
from .validation import validate_m29_bridge_fate_trace_report


VISIBLE_REPLAY_ACTIONS = {"text_replay", "image_replay", "icon_replay", "shape_replay"}
ALLOW_PROMOTION_MODES = {"allow_visible_replay", "allow_foreground_claim"}
SHAPE_CANDIDATE_ROLES = {
    "selected_marker_candidate",
    "status_dot_candidate",
    "table_marker_candidate",
    "internal_shape_candidate",
    "internal_control_background",
    "internal_overlay_badge",
    "internal_pill_button",
    "internal_circle_control",
}


def extract_m29_bridge_fate_trace_report(
    *,
    task_id: str,
    media_internal_report: dict[str, Any],
    transparent_asset_report: dict[str, Any],
    evidence_contract_report: dict[str, Any],
    promotion_report: dict[str, Any],
    final_m295_report: dict[str, Any],
    materialization_report: dict[str, Any],
    output_dir: Path,
) -> M29BridgeFateTraceResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    candidates = [item for item in media_internal_report.get("internalCandidates", []) if isinstance(item, dict)]
    transparent_by_source = index_by_key(transparent_asset_report.get("items", []), "sourceObjectId")
    contract_by_candidate = index_by_key(evidence_contract_report.get("contractItems", []), "candidateId")
    rejected_promotion_by_candidate = index_by_key(promotion_report.get("rejectedCandidates", []), "candidateId")
    promoted_by_candidate = promoted_source_objects_by_candidate(promotion_report.get("promotedSourceObjects", []))
    plan_by_source = index_by_key(final_m295_report.get("planItems", []), "sourceObjectId")
    replayed_by_source = index_by_key(materialization_report.get("replayedNodes", []), "source_id")
    skipped_by_source = index_by_key(materialization_report.get("skippedItems", []), "sourceId")

    traces = [
        build_trace(
            candidate=candidate,
            transparent_item=transparent_by_source.get(str(candidate.get("candidateId") or "")),
            contract_item=contract_by_candidate.get(str(candidate.get("candidateId") or "")),
            promoted_item=promoted_by_candidate.get(str(candidate.get("candidateId") or "")),
            rejected_promotion=rejected_promotion_by_candidate.get(str(candidate.get("candidateId") or "")),
            plan_by_source=plan_by_source,
            replayed_by_source=replayed_by_source,
            skipped_by_source=skipped_by_source,
        )
        for candidate in candidates
    ]

    report_path = output_dir / "bridge_fate_trace_report.json"
    report = {
        "schemaName": "M29BridgeFateTraceReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "mediaInternalSchemaName": media_internal_report.get("schemaName"),
        "mediaInternalSchemaVersion": media_internal_report.get("schemaVersion"),
        "transparentAssetSchemaName": transparent_asset_report.get("schemaName"),
        "transparentAssetSchemaVersion": transparent_asset_report.get("schemaVersion"),
        "evidenceContractSchemaName": evidence_contract_report.get("schemaName"),
        "evidenceContractSchemaVersion": evidence_contract_report.get("schemaVersion"),
        "promotionSchemaName": promotion_report.get("schemaName"),
        "promotionSchemaVersion": promotion_report.get("schemaVersion"),
        "finalReplayPlanSchemaName": final_m295_report.get("schemaName"),
        "finalReplayPlanSchemaVersion": final_m295_report.get("schemaVersion"),
        "materializationSchemaName": materialization_report.get("schemaName"),
        "materializationSchemaVersion": materialization_report.get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(traces, warnings),
        "traces": traces,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_6_plus_transparent_asset_plus_evidence_contract_plus_promotion_plus_final_m29_5_plus_materialization",
            **REPORT_ONLY_META,
        },
    }
    validate_m29_bridge_fate_trace_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29BridgeFateTraceResult(report=report, output_dir=output_dir)


def build_trace(
    *,
    candidate: dict[str, Any],
    transparent_item: dict[str, Any] | None,
    contract_item: dict[str, Any] | None,
    promoted_item: dict[str, Any] | None,
    rejected_promotion: dict[str, Any] | None,
    plan_by_source: dict[str, dict[str, Any]],
    replayed_by_source: dict[str, dict[str, Any]],
    skipped_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidateId") or "")
    promoted_source_id = str((promoted_item or {}).get("id") or "")
    plan_item = plan_by_source.get(promoted_source_id) if promoted_source_id else None
    replayed_item = replayed_by_source.get(promoted_source_id) if promoted_source_id else None
    skipped_item = skipped_by_source.get(promoted_source_id) if promoted_source_id else None
    transparent_decision = "not_required_for_shape_replay" if shape_candidate(candidate) else decision_value(transparent_item, "decision", "missing_transparent_asset_item")
    contract_decision = nested_decision_mode(contract_item)
    promotion_decision = "promoted" if promoted_item is not None else str((rejected_promotion or {}).get("reason") or "missing_promotion_candidate")
    final_replay_decision = str((plan_item or {}).get("finalReplayAction") or ("missing_final_m29_5_plan_item" if promoted_item is not None else "not_applicable"))
    cleanup_target = copied_cleanup_target(plan_item)
    materializer_decision = materializer_decision_for(
        promoted_item=promoted_item,
        plan_item=plan_item,
        replayed_item=replayed_item,
        skipped_item=skipped_item,
    )
    first_stage, first_reason = first_blocking_stage(
        candidate=candidate,
        transparent_item=transparent_item,
        contract_item=contract_item,
        promoted_item=promoted_item,
        rejected_promotion=rejected_promotion,
        plan_item=plan_item,
        replayed_item=replayed_item,
        skipped_item=skipped_item,
    )
    return {
        "candidateId": candidate_id,
        "candidateRole": str(candidate.get("role") or "unknown"),
        "sourceObjectId": candidate_id,
        "parentMediaSourceObjectId": str(candidate.get("mediaSourceObjectId") or ""),
        "promotedSourceObjectId": promoted_source_id or None,
        "bbox": candidate.get("bbox"),
        "candidateDecision": str(candidate.get("candidateDecision") or "unknown"),
        "claimDecision": str(candidate.get("claimDecision") or "unknown"),
        "claimScore": candidate.get("claimScore"),
        "foregroundClaimId": candidate.get("foregroundClaimId") or ((promoted_item or {}).get("sourceEvidence") or {}).get("foregroundClaimId"),
        "maskKind": candidate.get("maskKind") or ((promoted_item or {}).get("sourceEvidence") or {}).get("claimMaskKind"),
        "candidateConfidence": str(candidate.get("confidence") or "unknown"),
        "candidateScore": candidate.get("score"),
        "transparentDecision": transparent_decision,
        "transparentAssetPath": (transparent_item or {}).get("assetPath"),
        "transparentVisibleReplayEligible": visible_replay_eligible(transparent_item),
        "transparentGateDecision": (transparent_item or {}).get("gateDecision"),
        "evidenceDecision": contract_decision,
        "evidenceScore": evidence_score(contract_item),
        "promotionDecision": promotion_decision,
        "finalReplayDecision": final_replay_decision,
        "finalReplayPlanItemId": (plan_item or {}).get("id"),
        "cleanupDecision": cleanup_decision_for(plan_item, cleanup_target),
        "cleanupTarget": cleanup_target,
        "cleanupRisk": cleanup_risk_for(plan_item),
        "materializerDecision": materializer_decision,
        "materializedNodeId": (replayed_item or {}).get("id"),
        "firstBlockingStage": first_stage,
        "firstBlockingReason": first_reason,
        "traceReasons": {
            "transparent": list_strings((transparent_item or {}).get("reasons")),
            "transparentRisks": list_strings((transparent_item or {}).get("risks")),
            "evidence": list_strings(((contract_item or {}).get("decision") or {}).get("reasons") if isinstance((contract_item or {}).get("decision"), dict) else []),
            "evidenceRisks": list_strings(((contract_item or {}).get("risk") or {}).get("risks") if isinstance((contract_item or {}).get("risk"), dict) else []),
            "promotion": [str((rejected_promotion or {}).get("reason"))] if rejected_promotion else list_strings((promoted_item or {}).get("reasons")),
            "finalReplay": list_strings((plan_item or {}).get("reasons")),
            "materializer": [str((skipped_item or {}).get("reason"))] if skipped_item else [],
        },
        "reportOnly": True,
    }


def first_blocking_stage(
    *,
    candidate: dict[str, Any],
    transparent_item: dict[str, Any] | None,
    contract_item: dict[str, Any] | None,
    promoted_item: dict[str, Any] | None,
    rejected_promotion: dict[str, Any] | None,
    plan_item: dict[str, Any] | None,
    replayed_item: dict[str, Any] | None,
    skipped_item: dict[str, Any] | None,
) -> tuple[str, str]:
    if candidate.get("candidateDecision") != "accepted_report_candidate":
        return ("m29_media_internal_decomposition", str(candidate.get("candidateDecision") or "internal_candidate_not_accepted"))
    if not shape_candidate(candidate):
        if transparent_item is None:
            return ("m29_transparent_assets", "missing_transparent_asset_item")
        if not visible_replay_eligible(transparent_item):
            return ("m29_transparent_assets", visible_replay_block_reason(transparent_item))
    if contract_item is None:
        return ("m29_evidence_contract", "missing_evidence_contract")
    decision = contract_item.get("decision") if isinstance(contract_item.get("decision"), dict) else {}
    if decision.get("mode") not in ALLOW_PROMOTION_MODES:
        return ("m29_evidence_contract", first_reason(decision, fallback="evidence_contract_not_allowing_foreground_claim"))
    if promoted_item is None:
        return ("m29_internal_source_promotion", str((rejected_promotion or {}).get("reason") or "missing_promoted_source_object"))
    if plan_item is None:
        return ("m29_5_replay_plan_promoted", "missing_final_m29_5_plan_item")
    action = str(plan_item.get("finalReplayAction") or "")
    if action not in VISIBLE_REPLAY_ACTIONS:
        return ("m29_5_replay_plan_promoted", action or "not_visible_replay")
    if replayed_item is not None:
        return ("none", "visible_replay_materialized")
    return ("m29_materialization", str((skipped_item or {}).get("reason") or "missing_materialized_node"))


def shape_candidate(candidate: dict[str, Any]) -> bool:
    return str(candidate.get("role") or "") in SHAPE_CANDIDATE_ROLES


def first_reason(item: dict[str, Any], *, fallback: str) -> str:
    for key in ("reasons", "risks"):
        for value in list_strings(item.get(key)):
            if value and not value.startswith("m29_"):
                return value
    return fallback


def materializer_decision_for(
    *,
    promoted_item: dict[str, Any] | None,
    plan_item: dict[str, Any] | None,
    replayed_item: dict[str, Any] | None,
    skipped_item: dict[str, Any] | None,
) -> str:
    if promoted_item is None:
        return "not_applicable"
    if plan_item is None:
        return "no_final_replay_plan_item"
    if replayed_item is not None:
        return "replayed"
    if skipped_item is not None:
        return str(skipped_item.get("reason") or "skipped")
    return "missing_materialized_node"


def copied_cleanup_target(plan_item: dict[str, Any] | None) -> dict[str, Any] | None:
    if plan_item is None:
        return None
    for target in plan_item.get("cleanupTargets", []) if isinstance(plan_item.get("cleanupTargets"), list) else []:
        if isinstance(target, dict) and target.get("target") == "copied_image_asset":
            return target
    return None


def cleanup_decision_for(plan_item: dict[str, Any] | None, cleanup_target: dict[str, Any] | None) -> str:
    if plan_item is None:
        return "not_applicable"
    if cleanup_target is not None:
        return "copied_image_cleanup_authorized"
    risks = cleanup_risk_for(plan_item)
    return "copied_image_cleanup_blocked" if risks else "not_required"


def cleanup_risk_for(plan_item: dict[str, Any] | None) -> list[str]:
    if plan_item is None:
        return []
    return [risk for risk in list_strings(plan_item.get("risks")) if risk.startswith("cleanup_rejected_")]


def promoted_source_objects_by_candidate(items: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
        candidate_id = str(evidence.get("mediaInternalCandidateId") or "")
        if candidate_id:
            result[candidate_id] = item
    return result


def nested_decision_mode(item: dict[str, Any] | None) -> str:
    if item is None:
        return "missing_evidence_contract"
    decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
    return str(decision.get("mode") or "unknown")


def evidence_score(item: dict[str, Any] | None) -> float | None:
    if item is None:
        return None
    decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
    try:
        return round(float(decision.get("evidenceScore")), 4)
    except (TypeError, ValueError):
        return None


def decision_value(item: dict[str, Any] | None, key: str, fallback: str) -> str:
    if item is None:
        return fallback
    return str(item.get(key) or "unknown")


def index_by_key(items: Any, key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        value = str(item.get(key) or "")
        if value:
            result[value] = item
    return result


def list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]
