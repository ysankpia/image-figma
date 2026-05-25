from __future__ import annotations

from pathlib import Path

from app.ownership_conservation import extract_m29_ownership_conservation_report


def test_ownership_conservation_records_basic_visible_claims(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("text", [10, 10, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
            m292_object("image", [0, 30, 80, 40], "media_region", "preserve_raster", "image_replay"),
            m292_object("icon", [90, 10, 10, 10], "raster_icon", "raster_icon", "icon_replay"),
            m292_object("shape", [0, 0, 100, 4], "separator", "shape_geometry", "shape_replay"),
        ],
        plan_items=[
            plan_item("plan_shape", "shape", [0, 0, 100, 4], "shape_replay", "m29_shape"),
            plan_item("plan_image", "image", [0, 30, 80, 40], "image_replay", "m29_image"),
            plan_item("plan_icon", "icon", [90, 10, 10, 10], "icon_replay", "m29_symbol"),
            plan_item("plan_text", "text", [10, 10, 30, 10], "text_replay", "m29_text"),
        ],
    )

    assert report["summary"]["visibleReplayClaimCount"] == 4
    assert report["summary"]["conflictCount"] == 0
    assert {claim["finalReplayAction"] for claim in report["visibleReplayClaims"]} == {
        "text_replay",
        "image_replay",
        "icon_replay",
        "shape_replay",
    }
    assert report["meta"]["dslChanged"] is False
    assert report["meta"]["createdVisibleNodeCount"] == 0


def test_preserve_raster_text_has_no_visible_or_cleanup_claim(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[m292_object("caption", [10, 10, 40, 16], "preserve_raster_text", "preserve_raster", "preserve_in_parent_raster")],
        plan_items=[plan_item("plan_caption", "caption", [10, 10, 40, 16], "preserve_in_parent_raster", None)],
    )

    assert report["visibleReplayClaims"] == []
    assert report["cleanupClaims"] == []
    assert report["summary"]["conflictCount"] == 0


def test_diagnostic_fallback_and_suppressed_items_do_not_claim_visible_ownership(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("diagnostic", [0, 0, 10, 10], "unknown", "diagnostic_only", "skip"),
            m292_object("fallback", [20, 0, 10, 10], "unknown", "fallback_only", "skip"),
            m292_object("duplicate", [40, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
        ],
        plan_items=[
            plan_item("plan_diagnostic", "diagnostic", [0, 0, 10, 10], "diagnostic_only", None),
            plan_item("plan_fallback", "fallback", [20, 0, 10, 10], "fallback_only", None),
            plan_item("plan_duplicate", "duplicate", [40, 0, 10, 10], "suppress_duplicate", None),
        ],
    )

    assert report["visibleReplayClaims"] == []
    assert report["summary"]["conflictCount"] == 0


def test_fallback_cleanup_claim_is_recorded_as_plan_authorized(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[m292_object("text", [10, 10, 30, 10], "editable_ui_text", "editable_text", "text_replay")],
        plan_items=[
            plan_item(
                "plan_text",
                "text",
                [10, 10, 30, 10],
                "text_replay",
                "m29_text",
                cleanup_targets=[{"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"}],
            )
        ],
    )

    assert report["summary"]["cleanupTargetCounts"] == {"fallback": 1}
    assert report["cleanupClaims"][0]["authorizedBy"] == "m29_5_cleanupTargets"
    assert report["summary"]["conflictCount"] == 0


def test_copied_image_cleanup_is_explainable_for_text_contained_by_media(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
            m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
        ],
        edges=[edge("edge_media_text", "media", "text", "contains")],
        plan_items=[
            plan_item("plan_media", "media", [0, 0, 100, 60], "image_replay", "m29_image"),
            plan_item(
                "plan_text",
                "text",
                [20, 20, 30, 10],
                "text_replay",
                "m29_text",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "editable_text_contained_by_media"},
                ],
            ),
        ],
    )

    assert report["summary"]["cleanupTargetCounts"] == {"copied_image_asset": 1, "fallback": 1}
    assert report["summary"]["conflictCount"] == 0


def test_copied_image_cleanup_is_explainable_for_text_overlapping_media(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
            m292_object("text", [80, 50, 30, 12], "editable_ui_text", "editable_text", "text_replay"),
        ],
        edges=[edge("edge_media_text", "media", "text", "overlaps", metrics={"leftInRightRatio": 0.1, "rightInLeftRatio": 0.55})],
        plan_items=[
            plan_item("plan_media", "media", [0, 0, 100, 60], "image_replay", "m29_image"),
            plan_item(
                "plan_text",
                "text",
                [80, 50, 30, 12],
                "text_replay",
                "m29_text",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "editable_text_contained_by_media"},
                ],
            ),
        ],
    )

    assert report["summary"]["cleanupTargetCounts"] == {"copied_image_asset": 1, "fallback": 1}
    assert report["summary"]["conflictCount"] == 0


def test_copied_image_cleanup_is_explainable_for_promoted_internal_icon(tmp_path: Path) -> None:
    source_evidence = {
        "promotionSource": "m29_6_internal_icon_candidate",
        "mediaSourceObjectId": "media",
        "transparentAssetPath": "assets/transparent/promoted_icon.png",
    }
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
            m292_object(
                "promoted_icon",
                [30, 30, 20, 20],
                "raster_icon",
                "raster_icon",
                "icon_replay",
                source_evidence=source_evidence,
            ),
        ],
        edges=[edge("edge_media_icon", "media", "promoted_icon", "contains")],
        plan_items=[
            plan_item("plan_media", "media", [0, 0, 100, 80], "image_replay", "m29_image"),
            plan_item(
                "plan_icon",
                "promoted_icon",
                [30, 30, 20, 20],
                "icon_replay",
                "m29_symbol",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {
                        "target": "copied_image_asset",
                        "targetSourceObjectId": "media",
                        "reason": "promoted_internal_asset_contained_by_media",
                    },
                ],
                source_evidence=source_evidence,
            ),
        ],
    )

    assert report["summary"]["cleanupTargetCounts"] == {"copied_image_asset": 1, "fallback": 1}
    assert report["summary"]["conflictCount"] == 0


def test_unpromoted_icon_copied_image_cleanup_is_rejected(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("media", [0, 0, 100, 80], "media_region", "preserve_raster", "image_replay"),
            m292_object("icon", [30, 30, 20, 20], "raster_icon", "raster_icon", "icon_replay"),
        ],
        edges=[edge("edge_media_icon", "media", "icon", "contains")],
        plan_items=[
            plan_item("plan_media", "media", [0, 0, 100, 80], "image_replay", "m29_image"),
            plan_item(
                "plan_icon",
                "icon",
                [30, 30, 20, 20],
                "icon_replay",
                "m29_symbol",
                cleanup_targets=[
                    {
                        "target": "copied_image_asset",
                        "targetSourceObjectId": "media",
                        "reason": "promoted_internal_asset_contained_by_media",
                    },
                ],
            ),
        ],
    )

    assert any(item["type"] == "invalid_copied_image_asset_cleanup" for item in report["conflicts"])
    assert report["summary"]["errorCount"] == 1


def test_missing_copied_image_cleanup_is_reported_without_changing_plan(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
            m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
        ],
        edges=[edge("edge_media_text", "media", "text", "contains")],
        plan_items=[
            plan_item("plan_media", "media", [0, 0, 100, 60], "image_replay", "m29_image"),
            plan_item("plan_text", "text", [20, 20, 30, 10], "text_replay", "m29_text"),
        ],
    )

    conflict_types = {item["type"] for item in report["conflicts"]}
    assert "missing_copied_image_asset_cleanup" in conflict_types
    assert "visible_ownership_overlap" in conflict_types
    assert report["summary"]["warningConflictCount"] == 2


def test_invalid_copied_cleanup_target_is_reported(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("shape", [0, 0, 100, 60], "control_background", "shape_geometry", "shape_replay"),
            m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
        ],
        edges=[edge("edge_shape_text", "shape", "text", "contains")],
        plan_items=[
            plan_item("plan_shape", "shape", [0, 0, 100, 60], "shape_replay", "m29_shape"),
            plan_item(
                "plan_text",
                "text",
                [20, 20, 30, 10],
                "text_replay",
                "m29_text",
                cleanup_targets=[{"target": "copied_image_asset", "targetSourceObjectId": "shape", "reason": "invalid"}],
            ),
        ],
    )

    assert any(item["type"] == "invalid_copied_image_asset_cleanup" for item in report["conflicts"])
    assert report["summary"]["errorCount"] == 1


def test_shape_background_copied_cleanup_target_is_valid_when_contained_by_media(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
            m292_object("shape", [20, 20, 40, 20], "control_background", "shape_geometry", "shape_replay"),
        ],
        edges=[edge("edge_media_shape", "media", "shape", "contains")],
        plan_items=[
            plan_item("plan_media", "media", [0, 0, 100, 60], "image_replay", "m29_image"),
            plan_item(
                "plan_shape",
                "shape",
                [20, 20, 40, 20],
                "shape_replay",
                "m29_shape",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "shape_background_contained_by_media"},
                ],
            ),
        ],
    )

    assert not [item for item in report["conflicts"] if item["type"] == "invalid_copied_image_asset_cleanup"]
    assert report["summary"]["errorCount"] == 0


def test_shape_behind_text_overlap_is_explainable_background_foreground_overlap(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("shape", [0, 0, 100, 60], "control_background", "shape_geometry", "shape_replay"),
            m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
        ],
        edges=[edge("edge_shape_text", "shape", "text", "contains")],
        plan_items=[
            plan_item("plan_shape", "shape", [0, 0, 100, 60], "shape_replay", "m29_shape"),
            plan_item("plan_text", "text", [20, 20, 30, 10], "text_replay", "m29_text"),
        ],
    )

    assert report["summary"]["conflictCount"] == 0


def test_shape_behind_image_overlap_is_explainable_background_foreground_overlap(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("shape", [0, 0, 100, 60], "control_background", "shape_geometry", "shape_replay"),
            m292_object("media", [20, 20, 30, 20], "media_region", "preserve_raster", "image_replay"),
        ],
        edges=[edge("edge_shape_media", "shape", "media", "overlaps", metrics={"leftInRightRatio": 0.1, "rightInLeftRatio": 0.8})],
        plan_items=[
            plan_item("plan_shape", "shape", [0, 0, 100, 60], "shape_replay", "m29_shape"),
            plan_item("plan_media", "media", [20, 20, 30, 20], "image_replay", "m29_image"),
        ],
    )

    assert report["summary"]["conflictCount"] == 0


def test_near_equal_visible_claims_are_reported_as_overlap(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("left", [10, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay"),
            m292_object("right", [11, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay"),
        ],
        edges=[edge("edge_near_equal", "left", "right", "near_equal")],
        plan_items=[
            plan_item("plan_left", "left", [10, 10, 20, 10], "text_replay", "m29_text"),
            plan_item("plan_right", "right", [11, 10, 20, 10], "text_replay", "m29_text"),
        ],
    )

    assert any(item["type"] == "visible_ownership_overlap" for item in report["conflicts"])
    assert report["summary"]["conflictTypeCounts"]["visible_ownership_overlap"] == 1


def test_small_bbox_edge_overlap_is_not_reported_as_visible_ownership_conflict(tmp_path: Path) -> None:
    report = ownership_report(
        tmp_path,
        objects=[
            m292_object("left", [10, 10, 100, 20], "control_background", "shape_geometry", "shape_replay"),
            m292_object("right", [105, 10, 100, 20], "control_background", "shape_geometry", "shape_replay"),
        ],
        edges=[edge("edge_small_overlap", "left", "right", "overlaps")],
        plan_items=[
            plan_item("plan_left", "left", [10, 10, 100, 20], "shape_replay", "m29_shape"),
            plan_item("plan_right", "right", [105, 10, 100, 20], "shape_replay", "m29_shape"),
        ],
    )

    assert report["summary"]["conflictCount"] == 0


def ownership_report(
    tmp_path: Path,
    *,
    objects: list[dict],
    plan_items: list[dict],
    edges: list[dict] | None = None,
) -> dict:
    result = extract_m29_ownership_conservation_report(
        task_id="task_ownership",
        m292_document=m292_document(objects),
        m2931_report=m2931_report(edges or []),
        m295_report=m295_report(plan_items),
        output_dir=tmp_path / "m29_ownership_conservation",
    )
    assert (tmp_path / "m29_ownership_conservation" / "ownership_conservation_report.json").exists()
    return result.report


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
    source_evidence: dict | None = None,
) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": source_evidence or {},
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
    }


def m2931_report(edges: list[dict]) -> dict:
    return {
        "schemaName": "M2931RegionRelationGraphReport",
        "schemaVersion": "0.1",
        "edges": edges,
    }


def edge(edge_id: str, left: str, right: str, primary: str, *, metrics: dict | None = None) -> dict:
    return {
        "edgeId": edge_id,
        "leftObjectId": left,
        "rightObjectId": right,
        "primarySetRelation": primary,
        "secondaryGeometryRelations": [],
        "metrics": metrics or {},
    }


def m295_report(plan_items: list[dict]) -> dict:
    return {
        "schemaName": "M295ReplayPlan",
        "schemaVersion": "0.1",
        "planItems": plan_items,
    }


def plan_item(
    plan_id: str,
    source_id: str,
    bbox: list[int],
    action: str,
    target_role: str | None,
    *,
    cleanup_targets: list[dict] | None = None,
    source_evidence: dict | None = None,
) -> dict:
    return {
        "id": plan_id,
        "sourceObjectId": source_id,
        "bbox": bbox,
        "finalReplayAction": action,
        "targetRole": target_role,
        "pixelOwner": "editable_text",
        "cleanupTargets": cleanup_targets or [],
        "suppressedSourceObjectIds": [],
        "relationEdgeIds": [],
        "clusterIds": [],
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
        "sourceEvidence": source_evidence or {},
    }
