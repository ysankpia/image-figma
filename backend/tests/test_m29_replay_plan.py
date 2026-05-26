from __future__ import annotations

import json
from pathlib import Path

from app.m29_replay_plan import M295ReplayPlanOptions, build_m295_replay_plan


def test_m295_maps_m292_replay_decisions_to_plan_actions(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_basic",
        m292_document=m292_document(
            [
                m292_object("text", [10, 10, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("image", [0, 30, 80, 40], "media_region", "preserve_raster", "image_replay"),
                m292_object("icon", [90, 10, 10, 10], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("shape", [0, 0, 100, 4], "separator", "shape_geometry", "shape_replay"),
            ]
        ),
        m2931_report=m2931_report([], []),
        m294_report=m294_report([]),
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {
        "text": "text_replay",
        "image": "image_replay",
        "icon": "icon_replay",
        "shape": "shape_replay",
    }
    assert result.report["summary"]["plannedVisibleNodeCount"] == 4
    assert result.report["summary"]["plannedTextReplayCount"] == 1
    assert (tmp_path / "m29_5" / "replay_plan.json").exists()


def test_m295_plan_items_are_sorted_for_replay_layer_order(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_layer_order",
        m292_document=m292_document(
            [
                m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("image", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
                m292_object("icon", [70, 20, 10, 10], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("shape", [0, 0, 100, 60], "control_background", "shape_geometry", "shape_replay"),
            ]
        ),
        m2931_report=m2931_report([], []),
        m294_report=m294_report([]),
        output_dir=tmp_path / "m29_5",
    )

    assert [item["finalReplayAction"] for item in result.report["planItems"]] == [
        "shape_replay",
        "image_replay",
        "icon_replay",
        "text_replay",
    ]


def test_m295_preserve_raster_text_has_no_cleanup_targets(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_preserve",
        m292_document=m292_document(
            [
                m292_object("art", [10, 10, 50, 20], "preserve_raster_text", "preserve_raster", "preserve_in_parent_raster"),
            ]
        ),
        m2931_report=None,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    item = result.report["planItems"][0]
    assert item["finalReplayAction"] == "preserve_in_parent_raster"
    assert item["targetRole"] is None
    assert item["cleanupTargets"] == []
    assert result.report["summary"]["plannedVisibleNodeCount"] == 0


def test_m295_editable_text_inside_media_declares_fallback_and_asset_cleanup(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_cleanup",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
                m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "text"],
            [edge("media_text", "media", "text", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    text_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "text")
    assert text_item["finalReplayAction"] == "text_replay"
    assert {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"} in text_item["cleanupTargets"]
    assert {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "editable_text_contained_by_media"} in text_item["cleanupTargets"]
    assert result.report["summary"]["fallbackCleanupTargetCount"] == 2
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 1


def test_m295_near_equal_duplicate_keeps_one_replay_owner(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_duplicate",
        m292_document=m292_document(
            [
                m292_object("a", [10, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("b", [11, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(["a", "b"], [edge("a_b", "a", "b", "near_equal", ["near"])]),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert sorted(actions.values()) == ["suppress_duplicate", "text_replay"]
    assert result.report["summary"]["suppressedDuplicateCount"] == 1


def test_m295_suppresses_same_icon_contained_visible_overlap(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_icon_overlap",
        m292_document=m292_document(
            [
                m292_object("icon_outer", [10, 10, 34, 22], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("icon_inner", [19, 19, 8, 13], "raster_icon", "raster_icon", "icon_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["icon_outer", "icon_inner"],
            [edge("icon_overlap", "icon_outer", "icon_inner", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"icon_outer": "icon_replay", "icon_inner": "suppress_duplicate"}
    suppressed = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "icon_inner")
    assert "visible_overlap_duplicate_suppressed" in suppressed["reasons"]
    assert "visible_overlap_duplicate" in suppressed["risks"]
    assert result.report["summary"]["visibleOverlapSuppressedCount"] == 1


def test_m295_suppresses_same_shape_high_overlap_without_suppressing_text_background(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_shape_overlap",
        m292_document=m292_document(
            [
                m292_object("shape_outer", [10, 10, 155, 55], "control_background", "shape_geometry", "shape_replay"),
                m292_object("shape_inner", [17, 10, 110, 55], "control_background", "shape_geometry", "shape_replay"),
                m292_object("label", [24, 24, 40, 12], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["shape_outer", "shape_inner", "label"],
            [
                edge("shape_overlap", "shape_outer", "shape_inner", "contains", []),
                edge("shape_label", "shape_outer", "label", "contains", []),
            ],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions["shape_outer"] == "shape_replay"
    assert actions["shape_inner"] == "suppress_duplicate"
    assert actions["label"] == "text_replay"
    assert result.report["summary"]["visibleOverlapSuppressedCount"] == 1


def test_m295_adds_copied_cleanup_for_text_overlapping_media(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_text_media_overlap",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
                m292_object("text", [80, 50, 30, 12], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "text"],
            [edge("media_text", "media", "text", "overlaps", [], metrics={"leftInRightRatio": 0.1, "rightInLeftRatio": 0.55})],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    text_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "text")
    assert {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "editable_text_contained_by_media"} in text_item[
        "cleanupTargets"
    ]
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 1


def test_m295_shape_inside_media_declares_copied_asset_cleanup(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_shape_media_cleanup",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
                m292_object("shape", [20, 20, 50, 24], "control_background", "shape_geometry", "shape_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "shape"],
            [edge("media_shape", "media", "shape", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    shape_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "shape")
    assert shape_item["finalReplayAction"] == "shape_replay"
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "shape_background_contained_by_media",
    } in shape_item["cleanupTargets"]
    assert "shape_background_cleans_containing_media_asset" in shape_item["reasons"]
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 1


def test_m295_promoted_internal_shape_marker_replays_as_shape(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_promoted_internal_shape",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_shape("marker", [24, 64, 32, 6], "media", internal_role="selected_marker_candidate", evidence_score=0.82),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "marker"],
            [edge("media_marker", "media", "marker", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    marker_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "marker")
    assert marker_item["finalReplayAction"] == "shape_replay"
    assert marker_item["targetRole"] == "m29_shape"
    assert marker_item["sourceEvidence"]["promotionSource"] == "m29_6_internal_shape_candidate"
    assert marker_item["sourceEvidence"]["internalRole"] == "selected_marker_candidate"
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "shape_background_contained_by_media",
    } in marker_item["cleanupTargets"]


def test_m295_promoted_foreground_claim_pill_creates_residual_cleanup_target(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_foreground_claim_pill_cleanup",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 160, 100], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_shape(
                    "pill",
                    [24, 36, 72, 28],
                    "media",
                    internal_role="internal_pill_button",
                    evidence_score=0.84,
                    promotion_source="m29_6_foreground_claim",
                    foreground_claim_id="pill_candidate:foreground_claim",
                    claim_mask_kind="rounded_rect",
                    shape_fill="#B94AF4",
                    shape_radius=14,
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "pill"],
            [edge("media_pill", "media", "pill", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    pill_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "pill")
    assert pill_item["finalReplayAction"] == "shape_replay"
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "foreground_claim_removed_from_residual_media",
        "foregroundClaimId": "pill_candidate:foreground_claim",
        "maskKind": "rounded_rect",
    } in pill_item["cleanupTargets"]
    assert "foreground_claim_cleans_residual_media_asset" in pill_item["reasons"]


def test_m295_low_score_styled_perception_control_creates_residual_cleanup_target(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_low_score_perception_control_cleanup",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 200, 140], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_shape(
                    "control",
                    [24, 58, 148, 36],
                    "media",
                    internal_role="internal_control_background",
                    evidence_score=0.39,
                    promotion_source="perception_model_foreground_claim",
                    foreground_claim_id="model_control:foreground_claim",
                    claim_mask_kind="rounded_rect",
                    shape_fill="#2158BE",
                    shape_radius=18,
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "control"],
            [edge("media_control", "media", "control", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    control_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "control")
    assert control_item["finalReplayAction"] == "shape_replay"
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "foreground_claim_removed_from_residual_media",
        "foregroundClaimId": "model_control:foreground_claim",
        "maskKind": "rounded_rect",
    } in control_item["cleanupTargets"]
    assert "cleanup_rejected_low_shape_evidence" not in control_item["risks"]


def test_m295_low_score_unstyled_shape_still_blocks_residual_cleanup(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_low_score_unstyled_shape_cleanup_blocked",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 200, 140], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_shape(
                    "marker",
                    [24, 58, 12, 12],
                    "media",
                    internal_role="table_marker_candidate",
                    evidence_score=0.39,
                    promotion_source="perception_model_foreground_claim",
                    foreground_claim_id="model_marker:foreground_claim",
                    claim_mask_kind="circle",
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "marker"],
            [edge("media_marker", "media", "marker", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    marker_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "marker")
    assert marker_item["finalReplayAction"] == "shape_replay"
    assert not any(target.get("target") == "copied_image_asset" for target in marker_item["cleanupTargets"])
    assert "cleanup_rejected_low_shape_evidence" in marker_item["risks"]


def test_m295_keeps_internal_shape_replay_when_cleanup_style_evidence_is_missing(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_promoted_internal_shape_cleanup_risk",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_shape("marker", [24, 64, 8, 8], "media", internal_role="table_marker_candidate", evidence_score=0.82),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "marker"],
            [edge("media_marker", "media", "marker", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    marker_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "marker")
    assert marker_item["finalReplayAction"] == "shape_replay"
    assert marker_item["targetRole"] == "m29_shape"
    assert not any(target.get("target") == "copied_image_asset" for target in marker_item["cleanupTargets"])
    assert "cleanup_rejected_missing_shape_replacement_style" in marker_item["risks"]
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 0


def test_m295_suppresses_nested_media_duplicate(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_nested_media",
        m292_document=m292_document(
            [
                m292_object("media_outer", [0, 0, 300, 180], "media_region", "preserve_raster", "image_replay"),
                m292_object("media_inner", [20, 20, 120, 100], "media_region", "preserve_raster", "image_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["media_outer", "media_inner"],
            [edge("media_nested", "media_outer", "media_inner", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"media_outer": "image_replay", "media_inner": "suppress_duplicate"}


def test_m295_keeps_promoted_internal_icon_over_parent_media(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_promoted_internal_icon",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
                m292_object(
                    "promoted_icon",
                    [30, 30, 20, 20],
                    "raster_icon",
                    "raster_icon",
                    "icon_replay",
                    source_evidence={
                        "mediaSourceObjectId": "media",
                        "promotionSource": "m29_6_internal_icon_candidate",
                        "transparentAssetPath": "assets/transparent/promoted_icon.png",
                    },
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "promoted_icon"],
            [edge("media_icon", "media", "promoted_icon", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"media": "image_replay", "promoted_icon": "icon_replay"}
    icon_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "promoted_icon")
    assert icon_item["sourceEvidence"]["promotionSource"] == "m29_6_internal_icon_candidate"
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "promoted_internal_asset_contained_by_media",
    } in icon_item["cleanupTargets"]
    assert "promoted_internal_asset_cleans_parent_media_asset" in icon_item["reasons"]
    assert result.report["summary"]["visibleOverlapSuppressedCount"] == 0
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 1


def test_m295_keeps_promoted_internal_icon_replay_when_cleanup_risk_is_high(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_promoted_internal_icon_cleanup_risk",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_icon(
                    "promoted_icon",
                    [30, 30, 20, 20],
                    "media",
                    evidence_score=0.82,
                    alpha_metrics={"transparentAssetEdgeAlphaCoverageGt32": 0.42},
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "promoted_icon"],
            [edge("media_icon", "media", "promoted_icon", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    icon_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "promoted_icon")
    assert icon_item["finalReplayAction"] == "icon_replay"
    assert icon_item["targetRole"] == "m29_symbol"
    assert {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"} in icon_item["cleanupTargets"]
    assert not any(target.get("target") == "copied_image_asset" for target in icon_item["cleanupTargets"])
    assert "cleanup_rejected_edge_alpha_risk" in icon_item["risks"]
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 0


def test_m295_allows_control_row_source_crop_promoted_icon_bbox_cleanup(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_control_row_source_crop_icon",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_icon(
                    "promoted_icon",
                    [30, 30, 20, 20],
                    "media",
                    evidence_score=0.78,
                    transparent_asset_path=None,
                    control_row_source_crop_eligible=True,
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "promoted_icon"],
            [edge("media_icon", "media", "promoted_icon", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    icon_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "promoted_icon")
    assert icon_item["finalReplayAction"] == "icon_replay"
    assert icon_item["targetRole"] == "m29_symbol"
    assert icon_item["sourceEvidence"]["controlRowSourceCropEligible"] is True
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "promoted_internal_asset_contained_by_media",
    } in icon_item["cleanupTargets"]
    assert "cleanup_rejected_missing_transparent_replacement" not in icon_item["risks"]
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 1


def test_m295_keeps_higher_evidence_promoted_internal_icon_for_near_equal_candidates(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_promoted_internal_icon_near_equal",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 160, 100], "media_region", "preserve_raster", "image_replay"),
                promoted_internal_icon("promoted_icon_lower", [30, 20, 50, 50], "media", evidence_score=0.71),
                promoted_internal_icon("promoted_icon_higher", [28, 18, 56, 54], "media", evidence_score=0.82),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "promoted_icon_lower", "promoted_icon_higher"],
            [
                edge("media_lower", "media", "promoted_icon_lower", "contains", []),
                edge("media_higher", "media", "promoted_icon_higher", "contains", []),
                edge("icons_near_equal", "promoted_icon_lower", "promoted_icon_higher", "near_equal", []),
            ],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions["promoted_icon_higher"] == "icon_replay"
    assert actions["promoted_icon_lower"] == "suppress_duplicate"


def test_m295_keeps_promoted_internal_icon_with_low_label_bbox_overlap(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_promoted_internal_icon_label_overlap",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 160, 120], "media_region", "preserve_raster", "image_replay"),
                m292_object("label", [44, 72, 32, 18], "editable_ui_text", "editable_text", "text_replay"),
                promoted_internal_icon("promoted_icon", [30, 20, 56, 68], "media", evidence_score=0.82, text_overlap_ratio=0.03),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "label", "promoted_icon"],
            [
                edge("media_icon", "media", "promoted_icon", "contains", []),
                edge("media_label", "media", "label", "contains", []),
                edge("label_icon_overlap", "label", "promoted_icon", "overlaps", []),
            ],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions["label"] == "text_replay"
    assert actions["promoted_icon"] == "icon_replay"


def test_m295_keeps_label_anchored_blocked_icon_over_parent_media(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_label_anchored_blocked_icon",
        m292_document=m292_document(
            [
                m292_object(
                    "media",
                    [0, 0, 300, 100],
                    "media_region",
                    "preserve_raster",
                    "image_replay",
                    confidence="medium",
                    source_evidence={"ocrBoxIds": ["ocr_tab"]},
                ),
                m292_object(
                    "tab_icon",
                    [42, 20, 42, 44],
                    "raster_icon",
                    "raster_icon",
                    "icon_replay",
                    confidence="medium",
                    source_evidence={
                        "blockedIds": ["blocked_001"],
                        "mediaContainmentRatio": 1.0,
                        "labelAnchorOcrBoxId": "ocr_tab",
                    },
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "tab_icon"],
            [edge("media_icon", "media", "tab_icon", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"media": "image_replay", "tab_icon": "icon_replay"}
    icon_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "tab_icon")
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "label_anchored_blocked_asset_contained_by_media",
    } in icon_item["cleanupTargets"]
    assert result.report["summary"]["visibleOverlapSuppressedCount"] == 0
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 1


def test_m295_does_not_add_copied_cleanup_for_unpromoted_icon(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_unpromoted_internal_icon",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
                m292_object("icon", [30, 30, 20, 20], "raster_icon", "raster_icon", "icon_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "icon"],
            [edge("media_icon", "media", "icon", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    icon_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "icon")
    assert not any(target.get("target") == "copied_image_asset" for target in icon_item["cleanupTargets"])


def test_m295_suppresses_overlapping_media_duplicate(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_overlapping_media",
        m292_document=m292_document(
            [
                m292_object("media_large", [0, 0, 300, 200], "media_region", "preserve_raster", "image_replay"),
                m292_object("media_overlap", [220, 120, 120, 90], "media_region", "preserve_raster", "image_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["media_large", "media_overlap"],
            [edge("media_overlap", "media_large", "media_overlap", "overlaps", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"media_large": "image_replay", "media_overlap": "suppress_duplicate"}


def test_m295_keeps_perception_control_image_crop_over_parent_media(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_perception_control_image_crop",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 320, 200], "media_region", "preserve_raster", "image_replay"),
                m292_object(
                    "control_crop",
                    [48, 118, 224, 56],
                    "media_region",
                    "preserve_raster",
                    "image_replay",
                    confidence="medium",
                    source_evidence={
                        "promotionSource": "perception_model_foreground_claim",
                        "mediaSourceObjectId": "media",
                        "foregroundClaimId": "model_button:foreground_claim",
                        "claimMaskKind": "bbox",
                        "internalRole": "internal_control_raster_background",
                    },
                ),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "control_crop"],
            [edge("media_control_crop", "media", "control_crop", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"media": "image_replay", "control_crop": "image_replay"}
    crop_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "control_crop")
    assert crop_item["targetRole"] == "m29_image"
    assert crop_item["sourceEvidence"]["internalRole"] == "internal_control_raster_background"
    assert result.report["summary"]["visibleOverlapSuppressedCount"] == 0


def test_m295_suppresses_small_overlapping_text_duplicate(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_text_overlap",
        m292_document=m292_document(
            [
                m292_object("title", [57, 88, 158, 27], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("text_fragment", [38, 96, 25, 13], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["title", "text_fragment"],
            [edge("text_overlap", "title", "text_fragment", "overlaps", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"title": "text_replay", "text_fragment": "suppress_duplicate"}


def test_m295_suppresses_icon_overlapping_text_owner(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_text_icon_overlap",
        m292_document=m292_document(
            [
                m292_object("label", [20, 20, 80, 24], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("icon", [22, 22, 60, 20], "raster_icon", "raster_icon", "icon_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["label", "icon"],
            [edge("text_icon", "label", "icon", "overlaps", [], metrics={"leftInRightRatio": 0.625, "rightInLeftRatio": 1.0})],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"label": "text_replay", "icon": "suppress_duplicate"}


def test_m295_records_cluster_support_without_semantic_role_promotion(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_cluster",
        m292_document=m292_document(
            [
                m292_object("icon", [10, 10, 12, 12], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("label", [26, 10, 40, 12], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report([], []),
        m294_report=m294_report([cluster("cluster_row", ["icon", "label"], "row_like")]),
        output_dir=tmp_path / "m29_5",
    )

    assert result.report["summary"]["clusterSupportedPlanItemCount"] == 2
    for item in result.report["planItems"]:
        assert item["clusterIds"] == ["cluster_row"]
        assert item["targetRole"] in {"m29_text", "m29_symbol"}
        assert "SearchBar" not in json.dumps(item)
        assert "Card" not in json.dumps(item)


def test_m295_keeps_recovered_raster_foreground_as_icon_replay(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_recovered_icon",
        m292_document=m292_document(
            [
                m292_object("blocked_icon", [24, 24, 36, 36], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("diagnostic", [80, 24, 20, 20], "unknown", "diagnostic_only", "skip", confidence="low"),
            ]
        ),
        m2931_report=None,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions["blocked_icon"] == "icon_replay"
    assert actions["diagnostic"] == "diagnostic_only"
    assert result.report["summary"]["plannedIconReplayCount"] == 1


def test_m295_node_budget_suppresses_low_priority_visible_items(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_budget",
        m292_document=m292_document(
            [
                m292_object("text1", [0, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("text2", [20, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("image1", [0, 20, 30, 20], "media_region", "preserve_raster", "image_replay"),
            ]
        ),
        m2931_report=None,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
        options=M295ReplayPlanOptions(max_visible_nodes=2),
    )

    assert result.report["summary"]["plannedVisibleNodeCount"] == 2
    assert result.report["summary"]["nodeBudgetSuppressedCount"] == 1
    suppressed = [item for item in result.report["planItems"] if "node_budget_suppressed" in item["reasons"]]
    assert len(suppressed) == 1
    assert suppressed[0]["finalReplayAction"] == "suppress_duplicate"


def test_m295_invalid_inputs_are_reported_and_input_is_not_mutated(tmp_path: Path) -> None:
    m292 = m292_document(
        [
            m292_object("z", [30, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
            {**m292_object("bad", [0, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"), "bbox": [0, 0, 0, 10]},
            m292_object("a", [0, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
        ]
    )
    before = json.dumps(m292, sort_keys=True)

    result = build_m295_replay_plan(
        task_id="task_invalid",
        m292_document=m292,
        m2931_report=None,
        m294_report=m294_report([{"id": "bad_cluster", "memberNodeIds": "not-list"}]),
        output_dir=tmp_path / "m29_5",
    )

    assert json.dumps(m292, sort_keys=True) == before
    assert result.report["summary"]["skippedInvalidSourceObjectCount"] == 1
    assert result.report["summary"]["warningCount"] == 2
    assert [item["sourceObjectId"] for item in result.report["planItems"]] == ["a", "z"]


def m292_document(objects: list[dict]) -> dict:
    return {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "sourceObjects": objects,
    }


def m292_object(
    object_id: str,
    bbox: list[int],
    visual_kind: str,
    pixel_owner: str,
    replay_decision: str,
    *,
    confidence: str = "high",
    source_evidence: dict | None = None,
) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": source_evidence or {},
        "confidence": confidence,
        "reasons": ["test"],
        "risks": [],
    }


def promoted_internal_icon(
    object_id: str,
    bbox: list[int],
    media_id: str,
    *,
    evidence_score: float,
    text_overlap_ratio: float = 0.0,
    alpha_metrics: dict | None = None,
    transparent_asset_path: str | None = "__default__",
    control_row_source_crop_eligible: bool = False,
) -> dict:
    resolved_asset_path = f"assets/transparent/{object_id}.png" if transparent_asset_path == "__default__" else transparent_asset_path
    return m292_object(
        object_id,
        bbox,
        "raster_icon",
        "raster_icon",
        "icon_replay",
        source_evidence={
            "mediaSourceObjectId": media_id,
            "promotionSource": "m29_6_internal_icon_candidate",
            "transparentAssetPath": resolved_asset_path,
            "controlRowSourceCropEligible": control_row_source_crop_eligible,
            "evidenceScore": evidence_score,
            "textOverlapRatio": text_overlap_ratio,
            **(alpha_metrics or {}),
        },
    )


def promoted_internal_shape(
    object_id: str,
    bbox: list[int],
    media_id: str,
    *,
    internal_role: str,
    evidence_score: float,
    promotion_source: str = "m29_6_internal_shape_candidate",
    foreground_claim_id: str | None = None,
    claim_mask_kind: str | None = None,
    shape_fill: str | None = None,
    shape_radius: int | None = None,
) -> dict:
    source_evidence = {
        "mediaSourceObjectId": media_id,
        "promotionSource": promotion_source,
        "internalRole": internal_role,
        "evidenceScore": evidence_score,
    }
    if foreground_claim_id is not None:
        source_evidence["foregroundClaimId"] = foreground_claim_id
    if claim_mask_kind is not None:
        source_evidence["claimMaskKind"] = claim_mask_kind
    if shape_fill is not None:
        source_evidence["shapeFillOverride"] = shape_fill
    if shape_radius is not None:
        source_evidence["shapeRadiusOverride"] = shape_radius
    return m292_object(
        object_id,
        bbox,
        "separator",
        "shape_geometry",
        "shape_replay",
        source_evidence=source_evidence,
    )


def m2931_report(node_ids: list[str], edges: list[dict]) -> dict:
    return {
        "schemaName": "M2931RegionRelationGraphReport",
        "schemaVersion": "0.1",
        "nodes": [{"id": node_id, "bbox": [0, 0, 10, 10]} for node_id in node_ids],
        "edges": edges,
    }


def edge(edge_id: str, left: str, right: str, primary: str, secondary: list[str], *, metrics: dict | None = None) -> dict:
    return {
        "edgeId": edge_id,
        "leftObjectId": left,
        "rightObjectId": right,
        "primarySetRelation": primary,
        "secondaryGeometryRelations": secondary,
        "metrics": metrics or {},
    }


def m294_report(clusters: list[dict]) -> dict:
    return {
        "schemaName": "M294StableDesignClusterReport",
        "schemaVersion": "0.1",
        "clusters": clusters,
    }


def cluster(cluster_id: str, member_ids: list[str], role_hint: str) -> dict:
    return {
        "id": cluster_id,
        "bbox": [0, 0, 60, 20],
        "memberNodeIds": member_ids,
        "edgeIds": [],
        "clusterPattern": "directed_row_subgraph",
        "roleHint": role_hint,
        "stabilityScore": 0.8,
        "repeatabilityScore": 0.0,
        "reasons": ["test"],
        "risks": [],
    }
