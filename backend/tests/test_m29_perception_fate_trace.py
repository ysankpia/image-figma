from __future__ import annotations

from pathlib import Path

from app.m29_perception_fate_trace import extract_m29_perception_fate_trace_report


def test_perception_fate_trace_reports_materialized_compiled_candidate(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        perception_candidates=[candidate("model_button", [20, 30, 180, 48])],
        compiled_source_objects=[compiled_source("m292_perception_control_0001", "model_button", [20, 30, 180, 48])],
        rejected_candidates=[],
        final_plan_items=[
            {
                "id": "m295_plan_0001",
                "sourceObjectId": "m292_perception_control_0001",
                "finalReplayAction": "shape_replay",
                "cleanupTargets": [],
                "reasons": ["m29_5_action_shape_replay"],
            }
        ],
        replayed_nodes=[
            {
                "id": "m29_shape_0001",
                "kind": "shape",
                "source_id": "m292_perception_control_0001",
            }
        ],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["compilerDecision"] == "compiled_source_object"
    assert trace["compiledSourceObjectId"] == "m292_perception_control_0001"
    assert trace["finalReplayDecision"] == "shape_replay"
    assert trace["materializerDecision"] == "replayed"
    assert trace["firstBlockingStage"] == "none"
    assert trace["firstBlockingReason"] == "visible_replay_materialized"
    assert result.report["summary"]["traceCount"] == 1
    assert result.report["summary"]["materializedCount"] == 1
    assert result.report["meta"]["materializerConsumesTrace"] is False
    assert (tmp_path / "m29_perception_fate_trace" / "perception_fate_trace_report.json").exists()


def test_perception_fate_trace_reports_derived_compiled_source_object(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        perception_candidates=[candidate("model_button", [20, 30, 180, 48])],
        compiled_source_objects=[
            compiled_source("m292_perception_control_0001", "model_button", [20, 30, 180, 48]),
            compiled_source(
                "m292_perception_icon_0001",
                "model_button:leading_icon",
                [42, 42, 18, 18],
                visual_kind="raster_icon",
                pixel_owner="raster_icon",
                replay_decision="icon_replay",
                internal_role="internal_icon_candidate",
                source_evidence={
                    "derivedFromPerceptionCandidateId": "model_button",
                    "parentControlSourceObjectId": "m292_perception_control_0001",
                },
            ),
        ],
        rejected_candidates=[],
        final_plan_items=[
            {
                "id": "m295_plan_0001",
                "sourceObjectId": "m292_perception_control_0001",
                "finalReplayAction": "shape_replay",
                "cleanupTargets": [],
                "reasons": ["m29_5_action_shape_replay"],
            },
            {
                "id": "m295_plan_0002",
                "sourceObjectId": "m292_perception_icon_0001",
                "finalReplayAction": "icon_replay",
                "cleanupTargets": [],
                "reasons": ["m29_5_action_icon_replay"],
            },
        ],
        replayed_nodes=[
            {
                "id": "m29_shape_0001",
                "kind": "shape",
                "source_id": "m292_perception_control_0001",
            },
            {
                "id": "m29_image_0001",
                "kind": "image",
                "source_id": "m292_perception_icon_0001",
            },
        ],
        skipped_items=[],
    )

    assert result.report["summary"]["traceCount"] == 2
    assert result.report["summary"]["compiledCount"] == 2
    assert result.report["summary"]["materializedCount"] == 2
    assert result.report["summary"]["compiledRoleCounts"]["raster_icon"] == 1
    derived_trace = next(item for item in result.report["traces"] if item["candidateId"] == "model_button:leading_icon")
    assert derived_trace["traceKind"] == "derived_compiled_source_object"
    assert derived_trace["derivedFromPerceptionCandidateId"] == "model_button"
    assert derived_trace["compiledSourceObjectId"] == "m292_perception_icon_0001"
    assert derived_trace["finalReplayDecision"] == "icon_replay"
    assert derived_trace["materializerDecision"] == "replayed"
    assert derived_trace["firstBlockingStage"] == "none"


def test_perception_fate_trace_reports_compiler_blocker(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        perception_candidates=[candidate("model_banner", [20, 30, 420, 220])],
        compiled_source_objects=[],
        rejected_candidates=[
            {
                "candidateId": "model_banner",
                "reason": "content_region_too_large_for_control_background",
                "bbox": [20, 30, 420, 220],
            }
        ],
        final_plan_items=[],
        replayed_nodes=[],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["compilerDecision"] == "report_only"
    assert trace["firstBlockingStage"] == "m29_perception_source_compiler"
    assert trace["firstBlockingReason"] == "content_region_too_large_for_control_background"
    assert result.report["summary"]["blockedCount"] == 1
    assert result.report["summary"]["firstBlockingReasonCounts"]["content_region_too_large_for_control_background"] == 1


def test_perception_fate_trace_reports_cleanup_authorization(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        perception_candidates=[candidate("model_pill", [12, 14, 96, 28])],
        compiled_source_objects=[compiled_source("m292_perception_control_0001", "model_pill", [12, 14, 96, 28])],
        rejected_candidates=[],
        final_plan_items=[
            {
                "id": "m295_plan_0001",
                "sourceObjectId": "m292_perception_control_0001",
                "finalReplayAction": "shape_replay",
                "cleanupTargets": [
                    {
                        "target": "copied_image_asset",
                        "targetSourceObjectId": "media",
                        "reason": "foreground_claim_removed_from_residual_media",
                    }
                ],
                "reasons": ["m29_5_action_shape_replay"],
            }
        ],
        replayed_nodes=[
            {
                "id": "m29_shape_0001",
                "kind": "shape",
                "source_id": "m292_perception_control_0001",
            }
        ],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["cleanupDecision"] == "copied_image_cleanup_authorized"
    assert trace["cleanupTarget"]["targetSourceObjectId"] == "media"
    assert result.report["summary"]["cleanupAuthorizedCount"] == 1


def test_perception_fate_trace_report_only_invariants(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        perception_candidates=[candidate("model_icon", [10, 10, 18, 18])],
        compiled_source_objects=[],
        rejected_candidates=[],
        final_plan_items=[],
        replayed_nodes=[],
        skipped_items=[],
    )

    assert result.report["summary"]["dslChanged"] is False
    assert result.report["summary"]["materializationChanged"] is False
    assert result.report["summary"]["sourceOwnershipChanged"] is False
    assert result.report["meta"]["dslChanged"] is False
    assert result.report["meta"]["materializationChanged"] is False
    assert result.report["meta"]["sourceOwnershipChanged"] is False
    assert result.report["meta"]["materializerConsumesTrace"] is False


def trace_report(
    tmp_path: Path,
    *,
    perception_candidates: list[dict],
    compiled_source_objects: list[dict],
    rejected_candidates: list[dict],
    final_plan_items: list[dict],
    replayed_nodes: list[dict],
    skipped_items: list[dict],
):
    return extract_m29_perception_fate_trace_report(
        task_id="task_trace",
        perception_model_report={
            "schemaName": "M29PerceptionModelReport",
            "schemaVersion": "0.1",
            "candidates": perception_candidates,
        },
        perception_source_compiler_report={
            "schemaName": "M29PerceptionSourceCompilerReport",
            "schemaVersion": "0.1",
            "compiledSourceObjects": compiled_source_objects,
            "rejectedCandidates": rejected_candidates,
        },
        final_m295_report={
            "schemaName": "M295ReplayPlan",
            "schemaVersion": "0.1",
            "planItems": final_plan_items,
        },
        materialization_report={
            "schemaName": "M29PlanMaterializationReport",
            "schemaVersion": "0.1",
            "replayedNodes": replayed_nodes,
            "skippedItems": skipped_items,
        },
        output_dir=tmp_path / "m29_perception_fate_trace",
    )


def candidate(candidate_id: str, bbox: list[int], score: float = 0.8) -> dict:
    return {
        "candidateId": candidate_id,
        "sourceProvider": "fake_perception_model",
        "bbox": bbox,
        "score": score,
    }


def compiled_source(
    source_id: str,
    candidate_id: str,
    bbox: list[int],
    *,
    visual_kind: str = "control_background",
    pixel_owner: str = "shape_geometry",
    replay_decision: str = "shape_replay",
    internal_role: str = "internal_control_background",
    source_evidence: dict | None = None,
) -> dict:
    return {
        "id": source_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": {
            "perceptionCandidateId": candidate_id,
            "foregroundClaimId": f"{candidate_id}:foreground_claim",
            "mediaSourceObjectId": "media",
            "internalRole": internal_role,
            **(source_evidence or {}),
        },
        "reasons": ["perception_candidate_control_geometry"],
        "risks": [],
    }
