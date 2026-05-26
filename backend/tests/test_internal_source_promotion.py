from __future__ import annotations

from pathlib import Path

from app.internal_source_promotion import extract_m29_internal_source_promotion_report


def test_internal_source_promotion_promotes_high_confidence_allowed_internal_icon(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="high", text_anchor=0.82)],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="allow")],
        evidence_contract_items=[evidence_contract_item("contract", "candidate", decision="allow_visible_replay", evidence_score=0.82)],
    )

    assert result.report["summary"]["promotedSourceObjectCount"] == 1
    promoted = result.report["promotedSourceObjects"][0]
    assert promoted["pixelOwner"] == "raster_icon"
    assert promoted["replayDecision"] == "icon_replay"
    assert promoted["sourceEvidence"]["mediaSourceObjectId"] == "media"
    assert promoted["sourceEvidence"]["promotionSource"] == "m29_6_internal_icon_candidate"
    assert promoted["sourceEvidence"]["evidenceContractId"] == "contract"
    assert promoted["sourceEvidence"]["evidenceContractDecision"] == "allow_visible_replay"
    assert result.m292_document["summary"]["promotedInternalSourceObjectCount"] == 1
    assert (tmp_path / "m29_internal_source_promotion" / "source_ui_physical_graph.promoted.json").exists()


def test_internal_source_promotion_rejects_medium_without_group_support_internal_icon(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="medium", text_anchor=0.30)],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="allow")],
        evidence_contract_items=[evidence_contract_item("contract", "candidate", decision="report_only", evidence_score=0.52)],
    )

    assert result.report["summary"]["promotedSourceObjectCount"] == 0
    assert result.report["rejectedCandidates"][0]["reason"] == "evidence_contract_not_allowing_visible_replay"


def test_internal_source_promotion_promotes_group_supported_medium_internal_icon(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="medium", text_anchor=0.72, group_supported=True)],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="allow")],
        evidence_contract_items=[evidence_contract_item("contract", "candidate", decision="allow_visible_replay", evidence_score=0.74)],
    )

    assert result.report["summary"]["promotedSourceObjectCount"] == 1
    promoted = result.report["promotedSourceObjects"][0]
    assert promoted["confidence"] == "medium"
    assert "m29_6_group_supported_internal_icon_candidate" in promoted["reasons"]
    assert "evidence_contract_allow_visible_replay" in promoted["reasons"]


def test_internal_source_promotion_uses_transparent_asset_analysis_bbox(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="high", text_anchor=0.82)],
        transparent_items=[
            transparent_item(
                "asset_candidate",
                "candidate",
                [20, 20, 24, 24],
                decision="allow",
                analysis_bbox=[16, 16, 32, 32],
            )
        ],
        evidence_contract_items=[evidence_contract_item("contract", "candidate", decision="allow_visible_replay", evidence_score=0.82)],
    )

    promoted = result.report["promotedSourceObjects"][0]
    assert promoted["bbox"] == [16, 16, 32, 32]
    assert promoted["sourceEvidence"]["candidateBbox"] == [20, 20, 24, 24]
    assert promoted["sourceEvidence"]["transparentAssetBbox"] == [16, 16, 32, 32]


def test_internal_source_promotion_requires_evidence_contract_even_when_alpha_allows(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="high", text_anchor=0.82)],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="allow")],
        evidence_contract_items=[],
    )

    assert result.report["summary"]["promotedSourceObjectCount"] == 0
    assert result.report["rejectedCandidates"][0]["reason"] == "missing_evidence_contract"


def test_internal_source_promotion_rejects_analysis_only_transparent_asset(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="high", text_anchor=0.82)],
        transparent_items=[
            transparent_item(
                "asset_candidate",
                "candidate",
                [20, 20, 24, 24],
                decision="allow",
                visible_replay_eligible=False,
            )
        ],
        evidence_contract_items=[evidence_contract_item("contract", "candidate", decision="allow_visible_replay", evidence_score=0.82)],
    )

    assert result.report["summary"]["promotedSourceObjectCount"] == 0
    assert result.report["rejectedCandidates"][0]["reason"] == "analysis_only_without_visible_replay_support"


def test_internal_source_promotion_dedupes_same_promoted_bbox_by_evidence_score(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        source_objects=[media_object("media_a"), media_object("media_b")],
        internal_candidates=[
            internal_icon("candidate_a", [20, 20, 24, 24], confidence="high", text_anchor=0.82, media_source_object_id="media_a"),
            internal_icon("candidate_b", [20, 20, 24, 24], confidence="high", text_anchor=0.86, media_source_object_id="media_b"),
        ],
        transparent_items=[
            transparent_item("asset_candidate_a", "candidate_a", [20, 20, 24, 24], decision="allow"),
            transparent_item("asset_candidate_b", "candidate_b", [20, 20, 24, 24], decision="allow"),
        ],
        evidence_contract_items=[
            evidence_contract_item("contract_a", "candidate_a", decision="allow_visible_replay", evidence_score=0.72),
            evidence_contract_item("contract_b", "candidate_b", decision="allow_visible_replay", evidence_score=0.86),
        ],
    )

    assert result.report["summary"]["promotedSourceObjectCount"] == 1
    promoted = result.report["promotedSourceObjects"][0]
    assert promoted["id"] == "m292_promoted_internal_icon_0001"
    assert promoted["sourceEvidence"]["mediaInternalCandidateId"] == "candidate_b"
    assert result.report["rejectedCandidates"] == [
        {
            "candidateId": "candidate_a",
            "reason": "duplicate_promoted_internal_bbox",
            "bbox": [20, 20, 24, 24],
            "keptBy": "highest_evidence_score",
        }
    ]


def test_internal_source_promotion_promotes_selected_marker_as_shape(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[
            internal_shape_candidate(
                "selected_marker",
                [24, 72, 36, 6],
                role="selected_marker_candidate",
                text_anchor=0.82,
                relation="below_text",
            )
        ],
        transparent_items=[],
        evidence_contract_items=[
            evidence_contract_item(
                "contract",
                "selected_marker",
                decision="allow_visible_replay",
                evidence_score=0.80,
                source_kind="m29_6_internal_shape_candidate",
            )
        ],
    )

    assert result.report["summary"]["promotedSourceObjectCount"] == 1
    promoted = result.report["promotedSourceObjects"][0]
    assert promoted["id"] == "m292_promoted_internal_shape_0001"
    assert promoted["visualKind"] == "separator"
    assert promoted["pixelOwner"] == "shape_geometry"
    assert promoted["replayDecision"] == "shape_replay"
    assert promoted["sourceEvidence"]["promotionSource"] == "m29_6_internal_shape_candidate"
    assert promoted["sourceEvidence"]["internalRole"] == "selected_marker_candidate"


def test_internal_source_promotion_promotes_table_marker_as_rounded_shape(tmp_path: Path) -> None:
    result = promotion_report(
        tmp_path,
        internal_candidates=[
            internal_shape_candidate(
                "table_marker",
                [32, 44, 8, 8],
                role="table_marker_candidate",
                text_anchor=0.0,
                relation="non_ocr_foreground",
                repetition=0.72,
            )
        ],
        transparent_items=[],
        evidence_contract_items=[
            evidence_contract_item(
                "contract",
                "table_marker",
                decision="allow_visible_replay",
                evidence_score=0.78,
                source_kind="m29_6_internal_shape_candidate",
            )
        ],
    )

    promoted = result.report["promotedSourceObjects"][0]
    assert promoted["visualKind"] == "control_background"
    assert promoted["pixelOwner"] == "shape_geometry"
    assert promoted["sourceEvidence"]["internalRole"] == "table_marker_candidate"
    assert promoted["sourceEvidence"]["shapeRadiusOverride"] == 4
    assert promoted["sourceEvidence"]["shapeFillOverride"] == "#2D73EB"


def promotion_report(
    tmp_path: Path,
    *,
    internal_candidates: list[dict],
    transparent_items: list[dict],
    evidence_contract_items: list[dict],
    source_objects: list[dict] | None = None,
):
    return extract_m29_internal_source_promotion_report(
        task_id="task_promotion",
        m292_document={
            "schemaName": "M292SourceUiPhysicalGraph",
            "schemaVersion": "0.1",
            "summary": {"sourceObjectCount": 1, "rasterIconCount": 0, "dslChanged": False, "assetChanged": False},
            "sourceObjects": source_objects or [media_object()],
        },
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
        output_dir=tmp_path / "m29_internal_source_promotion",
    )


def media_object(object_id: str = "media") -> dict:
    return {
        "id": object_id,
        "bbox": [0, 0, 100, 100],
        "visualKind": "media_region",
        "pixelOwner": "preserve_raster",
        "replayDecision": "image_replay",
        "sourceEvidence": {},
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
    }


def internal_icon(
    candidate_id: str,
    bbox: list[int],
    *,
    confidence: str,
    text_anchor: float,
    group_supported: bool = False,
    media_source_object_id: str = "media",
) -> dict:
    return {
        "candidateId": candidate_id,
        "mediaSourceObjectId": media_source_object_id,
        "rawNodeId": "raw_icon",
        "role": "internal_icon_candidate",
        "bbox": bbox,
        "candidateDecision": "accepted_report_candidate",
        "confidence": confidence,
        "score": 0.84,
        "scoreBreakdown": {"heroGraphicPenalty": 0.1, "textMaskOverlap": 0.0, "textAnchorScore": text_anchor},
        **({"groupSupportedExecution": True} if group_supported else {}),
    }


def internal_shape_candidate(
    candidate_id: str,
    bbox: list[int],
    *,
    role: str,
    text_anchor: float,
    relation: str,
    repetition: float = 0.0,
    confidence: str = "high",
    media_source_object_id: str = "media",
) -> dict:
    return {
        "candidateId": candidate_id,
        "mediaSourceObjectId": media_source_object_id,
        "rawNodeId": "raw_shape",
        "role": role,
        "bbox": bbox,
        "candidateDecision": "accepted_report_candidate",
        "confidence": confidence,
        "score": 0.84 if confidence == "high" else 0.62,
        "scoreBreakdown": {
            "heroGraphicPenalty": 0.1,
            "textMaskOverlap": 0.0,
            "textAnchorScore": text_anchor,
            "repetitionScore": repetition,
        },
        "matchedOcrBoxId": "ocr_label" if text_anchor > 0 else None,
        "anchorRelation": relation,
        "metrics": {
            "meanRgb": [45, 115, 235],
        },
    }


def transparent_item(
    item_id: str,
    source_object_id: str,
    bbox: list[int],
    *,
    decision: str,
    analysis_bbox: list[int] | None = None,
    media_source_object_id: str = "media",
    visible_replay_eligible: bool | None = None,
) -> dict:
    item = {
        "candidateId": item_id,
        "source": "m29_6_internal_icon_candidate",
        "sourceObjectId": source_object_id,
        "mediaSourceObjectId": media_source_object_id,
        "bbox": bbox,
        "analysisBbox": analysis_bbox,
        "decision": decision,
        "assetPath": "assets/transparent/debug.png" if decision == "allow" else None,
        "textOverlap": 0.0,
    }
    if visible_replay_eligible is not None:
        item["visibleReplayEligible"] = visible_replay_eligible
        item["gateDecision"] = {
            "visibleReplayEligible": visible_replay_eligible,
            "visibleReplayReason": "asset_generated_and_alpha_quality_passed"
            if visible_replay_eligible
            else "analysis_only_without_visible_replay_support",
        }
    return item


def evidence_contract_item(
    item_id: str,
    candidate_id: str,
    *,
    decision: str,
    evidence_score: float,
    source_kind: str = "m29_6_internal_icon_candidate",
) -> dict:
    return {
        "contractId": item_id,
        "candidateId": candidate_id,
        "sourceKind": source_kind,
        "decision": {
            "mode": decision,
            "evidenceScore": evidence_score,
            "promotionAllowed": decision == "allow_visible_replay",
        },
    }
