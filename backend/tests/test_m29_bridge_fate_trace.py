from __future__ import annotations

from pathlib import Path

from app.m29_bridge_fate_trace import extract_m29_bridge_fate_trace_report


def test_bridge_fate_trace_reports_transparent_asset_blocker(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        internal_candidates=[internal_candidate("candidate", [20, 20, 24, 24])],
        transparent_items=[
            {
                "candidateId": "transparent_candidate",
                "source": "m29_6_internal_icon_candidate",
                "sourceObjectId": "candidate",
                "bbox": [20, 20, 24, 24],
                "decision": "reject",
                "assetPath": None,
                "reasons": ["m29_6_internal_icon_candidate", "internal_candidate_not_execution_supported"],
                "risks": ["transparent_asset_rejected"],
            }
        ],
        evidence_contract_items=[],
        promoted_source_objects=[],
        rejected_candidates=[
            {
                "candidateId": "candidate",
                "reason": "missing_transparent_asset_path",
                "bbox": [20, 20, 24, 24],
            }
        ],
        final_plan_items=[],
        replayed_nodes=[],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["firstBlockingStage"] == "m29_transparent_assets"
    assert trace["firstBlockingReason"] == "internal_candidate_not_execution_supported"
    assert trace["transparentDecision"] == "reject"
    assert trace["promotionDecision"] == "missing_transparent_asset_path"
    assert trace["finalReplayDecision"] == "not_applicable"
    assert trace["materializerDecision"] == "not_applicable"
    assert result.report["summary"]["firstBlockingReasonCounts"]["internal_candidate_not_execution_supported"] == 1
    assert (tmp_path / "m29_bridge_fate_trace" / "bridge_fate_trace_report.json").exists()


def test_bridge_fate_trace_reports_materialized_visible_replay(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        internal_candidates=[internal_candidate("candidate", [20, 20, 24, 24])],
        transparent_items=[
            {
                "candidateId": "transparent_candidate",
                "source": "m29_6_internal_icon_candidate",
                "sourceObjectId": "candidate",
                "bbox": [20, 20, 24, 24],
                "decision": "allow",
                "assetPath": "assets/transparent/icon.png",
                "reasons": ["m29_6_internal_icon_candidate", "transparent_asset_allow"],
                "risks": [],
            }
        ],
        evidence_contract_items=[
            {
                "contractId": "contract",
                "candidateId": "candidate",
                "sourceKind": "m29_6_internal_icon_candidate",
                "decision": {
                    "mode": "allow_visible_replay",
                    "evidenceScore": 0.82,
                    "reasons": ["allow_visible_replay_contract"],
                },
            }
        ],
        promoted_source_objects=[
            {
                "id": "m292_promoted_internal_icon_0001",
                "bbox": [20, 20, 24, 24],
                "sourceEvidence": {"mediaInternalCandidateId": "candidate"},
                "reasons": ["internal_source_promotion"],
            }
        ],
        rejected_candidates=[],
        final_plan_items=[
            {
                "id": "m295_plan_0001",
                "sourceObjectId": "m292_promoted_internal_icon_0001",
                "finalReplayAction": "icon_replay",
                "reasons": ["m29_5_action_icon_replay"],
            }
        ],
        replayed_nodes=[
            {
                "id": "m29_symbol_0001",
                "kind": "symbol",
                "source_id": "m292_promoted_internal_icon_0001",
            }
        ],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["firstBlockingStage"] == "none"
    assert trace["firstBlockingReason"] == "visible_replay_materialized"
    assert trace["promotionDecision"] == "promoted"
    assert trace["finalReplayDecision"] == "icon_replay"
    assert trace["materializerDecision"] == "replayed"
    assert trace["evidenceScore"] == 0.82
    assert result.report["summary"]["promotedCount"] == 1
    assert result.report["summary"]["materializedCount"] == 1


def test_bridge_fate_trace_reports_analysis_only_transparent_gate_blocker(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        internal_candidates=[internal_candidate("candidate", [20, 20, 24, 24])],
        transparent_items=[
            {
                "candidateId": "transparent_candidate",
                "source": "m29_6_internal_icon_candidate",
                "sourceObjectId": "candidate",
                "bbox": [20, 20, 24, 24],
                "decision": "allow",
                "assetPath": "assets/transparent/icon.png",
                "visibleReplayEligible": False,
                "gateDecision": {
                    "analysisAllowed": True,
                    "assetGenerated": True,
                    "visibleReplayEligible": False,
                    "cleanupEligible": False,
                    "visibleReplayReason": "analysis_only_without_visible_replay_support",
                },
                "reasons": ["strong_independent_evidence_alpha_analysis"],
                "risks": [],
            }
        ],
        evidence_contract_items=[
            {
                "contractId": "contract",
                "candidateId": "candidate",
                "sourceKind": "m29_6_internal_icon_candidate",
                "decision": {
                    "mode": "report_only",
                    "evidenceScore": 0.62,
                    "reasons": ["transparent_asset_not_allowing_visible_replay"],
                },
            }
        ],
        promoted_source_objects=[],
        rejected_candidates=[
            {
                "candidateId": "candidate",
                "reason": "analysis_only_without_visible_replay_support",
                "bbox": [20, 20, 24, 24],
            }
        ],
        final_plan_items=[],
        replayed_nodes=[],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["firstBlockingStage"] == "m29_transparent_assets"
    assert trace["firstBlockingReason"] == "analysis_only_without_visible_replay_support"
    assert trace["transparentDecision"] == "allow"
    assert trace["transparentAssetPath"] == "assets/transparent/icon.png"
    assert trace["transparentVisibleReplayEligible"] is False
    assert trace["promotionDecision"] == "analysis_only_without_visible_replay_support"


def test_bridge_fate_trace_does_not_require_transparent_asset_for_shape_candidate(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        internal_candidates=[internal_candidate("selected_marker", [20, 40, 32, 6], role="selected_marker_candidate")],
        transparent_items=[],
        evidence_contract_items=[
            {
                "contractId": "contract",
                "candidateId": "selected_marker",
                "sourceKind": "m29_6_internal_shape_candidate",
                "decision": {
                    "mode": "allow_visible_replay",
                    "evidenceScore": 0.82,
                    "reasons": ["allow_visible_replay_contract"],
                },
            }
        ],
        promoted_source_objects=[
            {
                "id": "m292_promoted_internal_shape_0001",
                "bbox": [20, 40, 32, 6],
                "sourceEvidence": {"mediaInternalCandidateId": "selected_marker"},
                "reasons": ["internal_source_promotion"],
            }
        ],
        rejected_candidates=[],
        final_plan_items=[
            {
                "id": "m295_plan_0001",
                "sourceObjectId": "m292_promoted_internal_shape_0001",
                "finalReplayAction": "shape_replay",
                "reasons": ["m29_5_action_shape_replay"],
            }
        ],
        replayed_nodes=[
            {
                "id": "m29_shape_0001",
                "kind": "shape",
                "source_id": "m292_promoted_internal_shape_0001",
            }
        ],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["firstBlockingStage"] == "none"
    assert trace["firstBlockingReason"] == "visible_replay_materialized"
    assert trace["transparentDecision"] == "not_required_for_shape_replay"
    assert trace["transparentAssetPath"] is None
    assert trace["promotionDecision"] == "promoted"
    assert trace["finalReplayDecision"] == "shape_replay"


def test_bridge_fate_trace_reports_foreground_claim_cleanup_authorization(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        internal_candidates=[
            internal_candidate(
                "pill",
                [20, 40, 72, 28],
                role="internal_pill_button",
                claim_decision="propose_foreground_claim",
                claim_score=0.74,
                foreground_claim_id="pill:foreground_claim",
                mask_kind="rounded_rect",
            )
        ],
        transparent_items=[],
        evidence_contract_items=[
            {
                "contractId": "contract",
                "candidateId": "pill",
                "sourceKind": "m29_6_internal_shape_candidate",
                "decision": {
                    "mode": "allow_foreground_claim",
                    "evidenceScore": 0.84,
                    "reasons": ["allow_foreground_claim_contract"],
                },
            }
        ],
        promoted_source_objects=[
            {
                "id": "m292_promoted_internal_shape_0001",
                "bbox": [20, 40, 72, 28],
                "sourceEvidence": {
                    "mediaInternalCandidateId": "pill",
                    "foregroundClaimId": "pill:foreground_claim",
                    "claimMaskKind": "rounded_rect",
                },
                "reasons": ["internal_source_promotion"],
            }
        ],
        rejected_candidates=[],
        final_plan_items=[
            {
                "id": "m295_plan_0001",
                "sourceObjectId": "m292_promoted_internal_shape_0001",
                "finalReplayAction": "shape_replay",
                "cleanupTargets": [
                    {
                        "target": "copied_image_asset",
                        "targetSourceObjectId": "media",
                        "reason": "foreground_claim_removed_from_residual_media",
                        "foregroundClaimId": "pill:foreground_claim",
                        "maskKind": "rounded_rect",
                    }
                ],
                "reasons": ["m29_5_action_shape_replay", "foreground_claim_cleans_residual_media_asset"],
            }
        ],
        replayed_nodes=[
            {
                "id": "m29_shape_0001",
                "kind": "shape",
                "source_id": "m292_promoted_internal_shape_0001",
            }
        ],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["firstBlockingStage"] == "none"
    assert trace["evidenceDecision"] == "allow_foreground_claim"
    assert trace["claimDecision"] == "propose_foreground_claim"
    assert trace["foregroundClaimId"] == "pill:foreground_claim"
    assert trace["maskKind"] == "rounded_rect"
    assert trace["cleanupDecision"] == "copied_image_cleanup_authorized"
    assert trace["cleanupTarget"]["reason"] == "foreground_claim_removed_from_residual_media"
    assert trace["materializerDecision"] == "replayed"


def test_bridge_fate_trace_reports_cleanup_risk_without_blocking_visible_replay(tmp_path: Path) -> None:
    result = trace_report(
        tmp_path,
        internal_candidates=[
            internal_candidate(
                "pill",
                [20, 40, 72, 28],
                role="internal_pill_button",
                claim_decision="propose_foreground_claim",
                claim_score=0.74,
                foreground_claim_id="pill:foreground_claim",
                mask_kind="rounded_rect",
            )
        ],
        transparent_items=[],
        evidence_contract_items=[
            {
                "contractId": "contract",
                "candidateId": "pill",
                "sourceKind": "m29_6_internal_shape_candidate",
                "decision": {
                    "mode": "allow_foreground_claim",
                    "evidenceScore": 0.84,
                    "reasons": ["allow_foreground_claim_contract"],
                },
            }
        ],
        promoted_source_objects=[
            {
                "id": "m292_promoted_internal_shape_0001",
                "bbox": [20, 40, 72, 28],
                "sourceEvidence": {
                    "mediaInternalCandidateId": "pill",
                    "foregroundClaimId": "pill:foreground_claim",
                    "claimMaskKind": "rounded_rect",
                },
                "reasons": ["internal_source_promotion"],
            }
        ],
        rejected_candidates=[],
        final_plan_items=[
            {
                "id": "m295_plan_0001",
                "sourceObjectId": "m292_promoted_internal_shape_0001",
                "finalReplayAction": "shape_replay",
                "cleanupTargets": [{"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"}],
                "risks": ["cleanup_rejected_missing_shape_replacement_style"],
                "reasons": ["m29_5_action_shape_replay"],
            }
        ],
        replayed_nodes=[
            {
                "id": "m29_shape_0001",
                "kind": "shape",
                "source_id": "m292_promoted_internal_shape_0001",
            }
        ],
        skipped_items=[],
    )

    trace = result.report["traces"][0]
    assert trace["firstBlockingStage"] == "none"
    assert trace["firstBlockingReason"] == "visible_replay_materialized"
    assert trace["cleanupDecision"] == "copied_image_cleanup_blocked"
    assert trace["cleanupRisk"] == ["cleanup_rejected_missing_shape_replacement_style"]
    assert trace["materializerDecision"] == "replayed"


def trace_report(
    tmp_path: Path,
    *,
    internal_candidates: list[dict],
    transparent_items: list[dict],
    evidence_contract_items: list[dict],
    promoted_source_objects: list[dict],
    rejected_candidates: list[dict],
    final_plan_items: list[dict],
    replayed_nodes: list[dict],
    skipped_items: list[dict],
):
    return extract_m29_bridge_fate_trace_report(
        task_id="task_trace",
        media_internal_report={
            "schemaName": "M29MediaInternalDecompositionReport",
            "schemaVersion": "0.1",
            "internalCandidates": internal_candidates,
        },
        transparent_asset_report={
            "schemaName": "M29TransparentAssetReport",
            "schemaVersion": "0.1",
            "items": transparent_items,
        },
        evidence_contract_report={
            "schemaName": "M29EvidenceContractReport",
            "schemaVersion": "0.1",
            "contractItems": evidence_contract_items,
        },
        promotion_report={
            "schemaName": "M29InternalSourcePromotionReport",
            "schemaVersion": "0.1",
            "promotedSourceObjects": promoted_source_objects,
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
        output_dir=tmp_path / "m29_bridge_fate_trace",
    )


def internal_candidate(
    candidate_id: str,
    bbox: list[int],
    *,
    role: str = "internal_icon_candidate",
    claim_decision: str | None = None,
    claim_score: float | None = None,
    foreground_claim_id: str | None = None,
    mask_kind: str | None = None,
) -> dict:
    candidate = {
        "candidateId": candidate_id,
        "mediaSourceObjectId": "media",
        "role": role,
        "bbox": bbox,
        "candidateDecision": "accepted_report_candidate",
        "confidence": "medium",
        "score": 0.64,
        "scoreBreakdown": {"textAnchorScore": 0.82, "heroGraphicPenalty": 0.0},
    }
    if claim_decision is not None:
        candidate["claimDecision"] = claim_decision
    if claim_score is not None:
        candidate["claimScore"] = claim_score
    if foreground_claim_id is not None:
        candidate["foregroundClaimId"] = foreground_claim_id
    if mask_kind is not None:
        candidate["maskKind"] = mask_kind
    return candidate
