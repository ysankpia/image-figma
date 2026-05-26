from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .report import build_summary
from .types import M29PerceptionFateTraceResult, REPORT_ONLY_META
from .validation import validate_m29_perception_fate_trace_report


VISIBLE_REPLAY_ACTIONS = {"text_replay", "image_replay", "icon_replay", "shape_replay"}


def extract_m29_perception_fate_trace_report(
    *,
    task_id: str,
    perception_model_report: dict[str, Any],
    perception_source_compiler_report: dict[str, Any],
    final_m295_report: dict[str, Any],
    materialization_report: dict[str, Any],
    output_dir: Path,
) -> M29PerceptionFateTraceResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    candidates = [item for item in perception_model_report.get("candidates", []) if isinstance(item, dict)]
    compiled_by_candidate = compiled_source_objects_by_candidate(perception_source_compiler_report.get("compiledSourceObjects", []))
    rejected_by_candidate = index_by_key(perception_source_compiler_report.get("rejectedCandidates", []), "candidateId")
    plan_by_source = index_by_key(final_m295_report.get("planItems", []), "sourceObjectId")
    replayed_by_source = index_by_key(materialization_report.get("replayedNodes", []), "source_id")
    skipped_by_source = index_by_key(materialization_report.get("skippedItems", []), "sourceId")

    traces = [
        build_trace(
            candidate=candidate,
            compiled_item=compiled_by_candidate.get(str(candidate.get("candidateId") or "")),
            rejected_item=rejected_by_candidate.get(str(candidate.get("candidateId") or "")),
            plan_by_source=plan_by_source,
            replayed_by_source=replayed_by_source,
            skipped_by_source=skipped_by_source,
        )
        for candidate in candidates
    ]

    report_path = output_dir / "perception_fate_trace_report.json"
    report = {
        "schemaName": "M29PerceptionFateTraceReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "perceptionSchemaName": perception_model_report.get("schemaName"),
        "perceptionSchemaVersion": perception_model_report.get("schemaVersion"),
        "compilerSchemaName": perception_source_compiler_report.get("schemaName"),
        "compilerSchemaVersion": perception_source_compiler_report.get("schemaVersion"),
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
            "truthSource": "perception_model_plus_perception_source_compiler_plus_final_m29_5_plus_materialization",
            **REPORT_ONLY_META,
        },
    }
    validate_m29_perception_fate_trace_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29PerceptionFateTraceResult(report=report, output_dir=output_dir)


def build_trace(
    *,
    candidate: dict[str, Any],
    compiled_item: dict[str, Any] | None,
    rejected_item: dict[str, Any] | None,
    plan_by_source: dict[str, dict[str, Any]],
    replayed_by_source: dict[str, dict[str, Any]],
    skipped_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidateId") or "")
    compiled_source_id = str((compiled_item or {}).get("id") or "")
    plan_item = plan_by_source.get(compiled_source_id) if compiled_source_id else None
    replayed_item = replayed_by_source.get(compiled_source_id) if compiled_source_id else None
    skipped_item = skipped_by_source.get(compiled_source_id) if compiled_source_id else None
    cleanup_target = copied_cleanup_target(plan_item)
    first_stage, first_reason = first_blocking_stage(
        compiled_item=compiled_item,
        rejected_item=rejected_item,
        plan_item=plan_item,
        replayed_item=replayed_item,
        skipped_item=skipped_item,
    )
    evidence = compiled_item.get("sourceEvidence") if isinstance((compiled_item or {}).get("sourceEvidence"), dict) else {}
    return {
        "candidateId": candidate_id,
        "bbox": candidate.get("bbox"),
        "score": candidate.get("score"),
        "sourceProvider": candidate.get("sourceProvider"),
        "compilerDecision": "compiled_source_object" if compiled_item is not None else "report_only",
        "compilerReason": str((rejected_item or {}).get("reason") or "compiled_source_object"),
        "compiledSourceObjectId": compiled_source_id or None,
        "compiledRole": str((compiled_item or {}).get("visualKind") or "not_compiled"),
        "compiledPixelOwner": (compiled_item or {}).get("pixelOwner"),
        "compiledReplayDecision": (compiled_item or {}).get("replayDecision"),
        "foregroundClaimId": evidence.get("foregroundClaimId"),
        "parentMediaSourceObjectId": evidence.get("mediaSourceObjectId"),
        "internalRole": evidence.get("internalRole"),
        "finalReplayDecision": str((plan_item or {}).get("finalReplayAction") or ("missing_final_m29_5_plan_item" if compiled_item is not None else "not_applicable")),
        "finalReplayPlanItemId": (plan_item or {}).get("id"),
        "cleanupDecision": cleanup_decision_for(plan_item, cleanup_target),
        "cleanupTarget": cleanup_target,
        "cleanupRisk": cleanup_risk_for(plan_item),
        "materializerDecision": materializer_decision_for(
            compiled_item=compiled_item,
            plan_item=plan_item,
            replayed_item=replayed_item,
            skipped_item=skipped_item,
        ),
        "materializedNodeId": (replayed_item or {}).get("id"),
        "firstBlockingStage": first_stage,
        "firstBlockingReason": first_reason,
        "traceReasons": {
            "compiler": [str((rejected_item or {}).get("reason"))] if rejected_item else list_strings((compiled_item or {}).get("reasons")),
            "finalReplay": list_strings((plan_item or {}).get("reasons")),
            "materializer": [str((skipped_item or {}).get("reason"))] if skipped_item else [],
        },
        "reportOnly": True,
    }


def first_blocking_stage(
    *,
    compiled_item: dict[str, Any] | None,
    rejected_item: dict[str, Any] | None,
    plan_item: dict[str, Any] | None,
    replayed_item: dict[str, Any] | None,
    skipped_item: dict[str, Any] | None,
) -> tuple[str, str]:
    if compiled_item is None:
        return ("m29_perception_source_compiler", str((rejected_item or {}).get("reason") or "candidate_not_compiled"))
    if plan_item is None:
        return ("m29_5_replay_plan", "missing_final_m29_5_plan_item")
    action = str(plan_item.get("finalReplayAction") or "")
    if action not in VISIBLE_REPLAY_ACTIONS:
        return ("m29_5_replay_plan", action or "not_visible_replay")
    if replayed_item is not None:
        return ("none", "visible_replay_materialized")
    return ("m29_materialization", str((skipped_item or {}).get("reason") or "missing_materialized_node"))


def materializer_decision_for(
    *,
    compiled_item: dict[str, Any] | None,
    plan_item: dict[str, Any] | None,
    replayed_item: dict[str, Any] | None,
    skipped_item: dict[str, Any] | None,
) -> str:
    if compiled_item is None:
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


def compiled_source_objects_by_candidate(items: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
        candidate_id = str(evidence.get("perceptionCandidateId") or "")
        if candidate_id:
            result[candidate_id] = item
    return result


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
