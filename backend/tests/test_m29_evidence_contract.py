from __future__ import annotations

from pathlib import Path

from app.m29_evidence_contract import extract_m29_evidence_contract_report


def test_m29_evidence_contract_empty_is_report_only(tmp_path: Path) -> None:
    report = evidence_report(tmp_path, internal_candidates=[], transparent_items=[])

    assert report["summary"]["contractItemCount"] == 0
    assert report["summary"]["allowVisibleReplayCount"] == 0
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["assetChanged"] is False
    assert report["meta"]["reportOnly"] is True
    assert report["meta"]["sourceOwnershipChanged"] is False


def test_high_evidence_internal_icon_allows_visible_replay(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="high", text_anchor=0.82)],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="allow")],
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "allow_visible_replay"
    assert item["decision"]["promotionAllowed"] is True
    assert item["positiveEvidence"]["transparentAsset"] == 1.0
    assert item["positiveEvidence"]["textAnchor"] > 0.80
    assert item["negativeEvidence"]["textOverlapPenalty"] == 0.0
    assert item["risk"]["level"] == "low"


def test_transparent_reject_keeps_candidate_report_only(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="high", text_anchor=0.82)],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="reject")],
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "report_only"
    assert item["decision"]["promotionAllowed"] is False
    assert "transparent_asset_not_allowing_visible_replay" in item["decision"]["reasons"]
    assert "transparent_asset_not_allowing_visible_replay" in item["risk"]["risks"]


def test_analysis_only_transparent_asset_does_not_allow_visible_replay(tmp_path: Path) -> None:
    report = evidence_report(
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
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "report_only"
    assert item["decision"]["promotionAllowed"] is False
    assert item["positiveEvidence"]["transparentAsset"] == 0.0
    assert "transparent_asset_not_allowing_visible_replay" in item["decision"]["reasons"]


def test_high_text_overlap_rejects_internal_icon_contract(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[internal_icon("candidate", [20, 20, 24, 24], confidence="high", text_anchor=0.82, text_overlap=0.36)],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="allow", text_overlap=0.36)],
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "reject"
    assert "text_overlap_too_high" in item["decision"]["reasons"]


def test_medium_group_supported_internal_icon_can_allow_with_consistent_evidence(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[
            internal_icon(
                "candidate",
                [20, 20, 24, 24],
                confidence="medium",
                text_anchor=0.72,
                repetition=0.70,
                group_supported=True,
            )
        ],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 24, 24], decision="allow")],
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "allow_visible_replay"
    assert item["positiveEvidence"]["repetition"] == 0.70
    assert "execution_supported_internal_icon" in item["decision"]["reasons"]


def test_generic_non_ocr_foreground_is_not_promoted_even_with_alpha(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[
            internal_icon(
                "candidate",
                [20, 20, 80, 18],
                confidence="high",
                text_anchor=0.86,
                raw_type="pixel_component",
                raw_subtype="non_ocr_foreground",
            )
        ],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 80, 18], decision="allow")],
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "reject"
    assert item["decision"]["promotionAllowed"] is False
    assert "generic_foreground_not_visible_replay" in item["decision"]["reasons"]


def test_anchored_group_supported_non_ocr_foreground_can_pass_evidence_contract(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[
            internal_icon(
                "candidate",
                [20, 20, 52, 44],
                confidence="high",
                text_anchor=0.90,
                text_overlap=0.03,
                hero_penalty=0.12,
                group_supported=True,
                raw_type="pixel_component",
                raw_subtype="non_ocr_foreground",
            )
        ],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 52, 44], decision="allow", text_overlap=0.03)],
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "allow_visible_replay"
    assert item["decision"]["promotionAllowed"] is True
    assert "generic_foreground_not_visible_replay" not in item["decision"]["reasons"]


def test_anchored_non_ocr_foreground_without_group_support_stays_rejected(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[
            internal_icon(
                "candidate",
                [20, 20, 52, 44],
                confidence="high",
                text_anchor=0.90,
                text_overlap=0.03,
                hero_penalty=0.12,
                raw_type="pixel_component",
                raw_subtype="non_ocr_foreground",
            )
        ],
        transparent_items=[transparent_item("asset_candidate", "candidate", [20, 20, 52, 44], decision="allow", text_overlap=0.03)],
    )

    item = report["contractItems"][0]
    assert item["decision"]["mode"] == "reject"
    assert item["decision"]["promotionAllowed"] is False
    assert "generic_foreground_not_visible_replay" in item["decision"]["reasons"]


def test_label_anchored_blocked_icon_is_audit_only_not_promotion_contract(tmp_path: Path) -> None:
    report = evidence_report(
        tmp_path,
        internal_candidates=[],
        transparent_items=[],
        source_objects=[
            media_object(),
            {
                "id": "blocked_icon",
                "bbox": [20, 20, 24, 24],
                "visualKind": "raster_icon",
                "pixelOwner": "raster_icon",
                "replayDecision": "icon_replay",
                "sourceEvidence": {
                    "blockedIds": ["blocked_1", "blocked_2"],
                    "labelAnchorOcrBoxId": "ocr_label",
                    "mediaContainmentRatio": 1.0,
                    "textOverlapRatio": 0.0,
                },
                "confidence": "medium",
                "reasons": ["blocked_media_contained_label_anchored_foreground", "blocked_fragment_group"],
                "risks": [],
            },
        ],
    )

    item = report["contractItems"][0]
    assert item["sourceKind"] == "m29_2_label_anchored_blocked_icon"
    assert item["decision"]["mode"] == "report_only"
    assert item["decision"]["requiredForPromotion"] is False


def evidence_report(
    tmp_path: Path,
    *,
    internal_candidates: list[dict],
    transparent_items: list[dict],
    source_objects: list[dict] | None = None,
) -> dict:
    result = extract_m29_evidence_contract_report(
        task_id="task_evidence_contract",
        m292_document={
            "schemaName": "M292SourceUiPhysicalGraph",
            "schemaVersion": "0.1",
            "sourceObjects": source_objects if source_objects is not None else [media_object()],
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
        output_dir=tmp_path / "m29_evidence_contract",
    )
    assert (tmp_path / "m29_evidence_contract" / "evidence_contract_report.json").exists()
    return result.report


def media_object() -> dict:
    return {
        "id": "media",
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
    repetition: float = 0.0,
    text_overlap: float = 0.0,
    hero_penalty: float = 0.1,
    group_supported: bool = False,
    raw_type: str = "symbol",
    raw_subtype: str = "icon",
    anchor_relation: str = "above_text",
) -> dict:
    return {
        "candidateId": candidate_id,
        "mediaSourceObjectId": "media",
        "rawNodeId": "raw_icon",
        "rawType": raw_type,
        "rawSubtype": raw_subtype,
        "matchedOcrBoxId": "ocr_label",
        "anchorRelation": anchor_relation,
        "role": "internal_icon_candidate",
        "bbox": bbox,
        "candidateDecision": "accepted_report_candidate",
        "confidence": confidence,
        "score": 0.84 if confidence == "high" else 0.62,
        "scoreBreakdown": {
            "sizeScore": 1.0,
            "compactnessScore": 0.86,
            "textAnchorScore": text_anchor,
            "relationConsistencyScore": text_anchor * 0.9,
            "repetitionScore": repetition,
            "heroGraphicPenalty": hero_penalty,
            "textMaskOverlap": text_overlap,
        },
        **({"groupSupportedExecution": True} if group_supported else {}),
    }


def transparent_item(
    item_id: str,
    source_object_id: str,
    bbox: list[int],
    *,
    decision: str,
    text_overlap: float = 0.0,
    visible_replay_eligible: bool | None = None,
) -> dict:
    item = {
        "candidateId": item_id,
        "source": "m29_6_internal_icon_candidate",
        "sourceObjectId": source_object_id,
        "mediaSourceObjectId": "media",
        "bbox": bbox,
        "decision": decision,
        "assetPath": "assets/transparent/debug.png" if decision == "allow" else None,
        "textOverlap": text_overlap,
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
