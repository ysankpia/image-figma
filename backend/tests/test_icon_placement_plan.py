from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.asset_slice import AssetSliceCandidateDocument, AssetSliceItem
from app.component_annotation import ComponentAnnotationDocument
from app.icon_candidate import IconCandidateStorageAdapter, build_icon_candidate_document
from app.icon_coverage import IconCoverageStorageAdapter, build_icon_coverage_audit_document
from app.icon_gap_candidate import IconGapStorageAdapter, build_icon_gap_candidate_document
from app.icon_placement_plan import (
    IconPlacementStorageAdapter,
    apply_icon_placement_plan_metadata,
    build_icon_placement_plan_document,
)
from app.png_tools import PngMetadata, read_png_metadata
from conftest import PNG_BYTES
from test_icon_candidate import home_like_icon_inputs
from test_icon_coverage import png_with_extra_regions
from test_icon_gap_candidate import create_client_with_env, home_like_gap_document, make_gap_settings


def test_icon_placement_default_upload_creates_report_overlay_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-placement-plan")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "icon_placement_plan_and_layering_readiness"
        assert document["placementOverlay"] is not None

        overlay = client.get(document["placementOverlay"]["assetUrl"].replace("http://localhost:8000", ""))
        assert overlay.status_code == 200
        assert read_png_metadata(overlay.content) is not None

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m23_icon_placement_plan" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["iconPlacementPlanCount"] == document["meta"]["placementCount"]
        assert dsl["meta"]["iconPlacementReadyCount"] == document["meta"]["readyCount"]
        assert dsl["meta"]["iconPlacementNeedsFallbackMaskCount"] == document["meta"]["needsFallbackMaskCount"]
        assert dsl["meta"]["iconPlacementNeedsSliceCoordinationCount"] == document["meta"]["needsSliceCoordinationCount"]
        assert dsl["meta"]["iconPlacementBlockedCount"] == document["meta"]["blockedCount"]
        assert dsl["meta"]["iconPlacementDedupedCount"] == document["meta"]["dedupedCount"]
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_icon_placement_disabled_has_no_result_and_keeps_m22_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ICON_PLACEMENT_PLAN_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-placement-plan")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ICON_PLACEMENT_PLAN_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m22_icon_gap_candidates" in dsl["meta"]["qualityFlags"]
        assert "m23_icon_placement_plan" not in dsl["meta"]["qualityFlags"]
        assert "iconPlacementPlanCount" not in dsl["meta"]


def test_icon_placement_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/icon-placement-plan")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_icon_placement",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No icon placement plan.",
            "original_filename": "input.png",
            "mime_type": "image/png",
            "file_size": 1,
            "upload_path": "/tmp/input.png",
            "created_at": "2026-05-16T00:00:00+00:00",
            "updated_at": "2026-05-16T00:00:00+00:00",
            "completed_at": "2026-05-16T00:00:00+00:00",
            "failed_at": None,
        }
    )
    not_found = client.get("/api/tasks/task_without_icon_placement/icon-placement-plan")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "ICON_PLACEMENT_PLAN_NOT_FOUND"

    state.database.insert_icon_placement_plan_result(
        {
            "task_id": "task_without_icon_placement",
            "status": "completed",
            "plan_path": "/tmp/does-not-exist.json",
            "overlay_asset_id": None,
            "placement_count": 0,
            "ready_count": 0,
            "needs_fallback_mask_count": 0,
            "needs_slice_coordination_count": 0,
            "needs_fallback_coordination_count": 0,
            "review_required_count": 0,
            "blocked_count": 0,
            "deduped_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_icon_placement/icon-placement-plan")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "ICON_PLACEMENT_PLAN_NOT_FOUND"


def test_icon_placement_dedupes_m20_and_m22_candidates(tmp_path) -> None:
    gap_document, coverage_document, icon_document, dsl, image = home_like_gap_document(
        tmp_path,
        icon_regions=[([145, 842, 22, 18], (38, 132, 255))],
        missed_regions=[([145, 842, 22, 18], (38, 132, 255))],
    )
    if not gap_document.gapIcons:
        gap_document.gapIcons.append(
            make_gap_clone(gap_document, icon_document.icons[0].bbox, icon_document.icons[0].assetPath, tmp_path)
        )
    else:
        gap_document.gapIcons[0].bbox = list(icon_document.icons[0].bbox)

    document = build_plan(
        tmp_path,
        image=image,
        png_data=png_with_extra_regions(image, None, []),
        binding=home_like_icon_inputs([])[3],
        structure=home_like_icon_inputs([])[4],
        annotation=home_like_icon_inputs([])[5],
        asset_slice=None,
        icon_document=icon_document,
        coverage_document=coverage_document,
        gap_document=gap_document,
        dsl=dsl,
    )

    assert document.status == "completed"
    assert document.dedupedIcons
    assert document.meta["dedupedCount"] == len(document.dedupedIcons)


def test_icon_placement_decisions_for_fallback_slice_text_and_ready(tmp_path) -> None:
    image, _ocr, _replacement, binding, structure, annotation, _separation, dsl, _png = home_like_icon_inputs(
        [([145, 842, 22, 18], (38, 132, 255))]
    )
    settings = make_plan_settings(icon_candidate_max_component_area_ratio=0.60)
    png = png_with_extra_regions(image, None, [([145, 842, 22, 18], (38, 132, 255))])
    icon_document = build_icon_candidate_document(
        task_id="task_plan",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=None,
        asset_slice_document=None,
        dsl=dsl,
        settings=settings,
        storage=IconCandidateStorageAdapter(tmp_path / "icons", "http://localhost:8000"),
    )
    assert icon_document.icons

    ready_icon = deepcopy(icon_document.icons[0])
    ready_icon.id = "icon_candidate_ready"
    ready_icon.bbox = [20, image.height + 10, 20, 20]
    ready_icon.assetId = "asset_icon_ready"
    ready_icon.assetPath = icon_document.icons[0].assetPath
    ready_icon.assetUrl = icon_document.icons[0].assetUrl
    ready_icon.componentId = None
    ready_icon.componentRole = None
    ready_icon.relatedTextElementIds = []
    ready_icon.relatedBindingIds = []
    image_for_ready = PngMetadata(
        width=image.width,
        height=image.height + 80,
        bit_depth=image.bit_depth,
        color_type=image.color_type,
        compression=image.compression,
        filter_method=image.filter_method,
        interlace=image.interlace,
    )
    icon_document.icons.append(ready_icon)

    text_overlap = deepcopy(icon_document.icons[0])
    text_overlap.id = "icon_candidate_text_overlap"
    text_overlap.bbox = [95, image.height + 10, 22, 22]
    text_overlap.assetId = "asset_icon_text_overlap"
    text_overlap.assetPath = icon_document.icons[0].assetPath
    text_overlap.assetUrl = icon_document.icons[0].assetUrl
    text_overlap.componentId = None
    text_overlap.componentRole = None
    text_overlap.relatedTextElementIds = []
    text_overlap.relatedBindingIds = []
    icon_document.icons.append(text_overlap)

    slice_icon = deepcopy(icon_document.icons[0])
    slice_icon.id = "icon_candidate_slice"
    slice_icon.bbox = [20, image.height + 45, 20, 20]
    slice_icon.assetId = "asset_icon_slice"
    slice_icon.assetPath = icon_document.icons[0].assetPath
    slice_icon.assetUrl = icon_document.icons[0].assetUrl
    slice_icon.componentId = None
    slice_icon.componentRole = None
    slice_icon.relatedTextElementIds = []
    slice_icon.relatedBindingIds = []
    icon_document.icons.append(slice_icon)

    dsl_without_fallback = deepcopy(dsl)
    dsl_without_fallback["root"]["children"] = [
        child for child in dsl_without_fallback["root"]["children"] if not child["id"].startswith("fallback_region_")
    ]
    dsl_without_fallback["root"]["children"].append(
        {
            "id": "visible_text_overlap",
            "type": "text",
            "role": "visible_text_replacement",
            "layout": {"x": 95, "y": image.height + 10, "width": 22, "height": 22},
            "content": {"text": "Text"},
        }
    )
    asset_slice = AssetSliceCandidateDocument(
        version="0.1",
        taskId="task_plan",
        status="completed",
        imageSize={"width": image_for_ready.width, "height": image_for_ready.height},
        slices=[
            AssetSliceItem(
                id="asset_slice_test",
                componentId="component_slice",
                componentRole="preview_card",
                layerSeparationCandidateId="layer_sep_test",
                sourceStrategy="image_slice_with_simple_fill_candidate",
                status="candidate",
                strategy="local_slice_original",
                bbox=[0, image.height + 35, 80, 40],
                assetId="asset_slice_test",
                assetPath=str(tmp_path / "slice.png"),
                assetUrl="http://localhost:8000/files/assets/task_plan/slices/slice.png",
                filledAssetId=None,
                filledAssetPath=None,
                filledAssetUrl=None,
                fillOperations=[],
                quality={"risk": "low", "reasons": []},
            )
        ],
        blockedComponentIds=[],
        warnings=[],
        meta={},
    )

    document = build_plan(
        tmp_path,
        image=image_for_ready,
        png_data=png_with_extra_regions(image_for_ready, None, []),
        binding=binding,
        structure=structure,
        annotation=annotation,
        asset_slice=asset_slice,
        icon_document=icon_document,
        coverage_document=None,
        gap_document=None,
        dsl=dsl_without_fallback,
        settings=settings,
    )
    decisions = {placement.sourceIconId: placement.decision for placement in document.placements}

    assert decisions["icon_candidate_ready"] == "ready_for_visible_icon"
    assert decisions["icon_candidate_text_overlap"] == "blocked"
    assert decisions["icon_candidate_slice"] == "needs_slice_coordination"


def test_icon_placement_future_hint_and_metadata_do_not_modify_dsl_children(tmp_path) -> None:
    gap_document, coverage_document, icon_document, dsl, image = home_like_gap_document(
        tmp_path,
        icon_regions=[([145, 842, 22, 18], (38, 132, 255))],
        missed_regions=[],
    )
    document = build_plan(
        tmp_path,
        image=image,
        png_data=png_with_extra_regions(image, None, []),
        binding=home_like_icon_inputs([])[3],
        structure=home_like_icon_inputs([])[4],
        annotation=home_like_icon_inputs([])[5],
        asset_slice=None,
        icon_document=icon_document,
        coverage_document=coverage_document,
        gap_document=gap_document,
        dsl=dsl,
    )

    before_children = deepcopy(dsl["root"]["children"])
    before_assets = deepcopy(dsl["assets"])
    next_dsl = apply_icon_placement_plan_metadata(dsl, document)

    assert next_dsl["root"]["children"] == before_children
    assert next_dsl["assets"] == before_assets
    assert "m23_icon_placement_plan" in next_dsl["meta"]["qualityFlags"]
    for placement in document.placements:
        if placement.decision != "blocked":
            assert placement.futureDslNodeHint is not None
            assert placement.futureDslNodeHint["type"] == "image"
            assert placement.futureDslNodeHint["role"] == "icon_fallback"


def test_icon_placement_assets_api_returns_overlay(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        document = client.get(f"/api/tasks/{task_id}/icon-placement-plan").json()["data"]
        overlay = document["placementOverlay"]
        assert overlay is not None

        asset = client.get(f"/api/assets/{overlay['assetId']}")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_icon_placement_overlay"


def build_plan(
    tmp_path,
    *,
    image,
    png_data,
    binding,
    structure,
    annotation,
    asset_slice,
    icon_document,
    coverage_document,
    gap_document,
    dsl,
    settings=None,
):
    return build_icon_placement_plan_document(
        task_id="task_plan",
        image=image,
        png_data=png_data,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        asset_slice_document=asset_slice,
        icon_candidate_document=icon_document,
        icon_coverage_document=coverage_document,
        icon_gap_document=gap_document,
        dsl=dsl,
        settings=settings or make_plan_settings(),
        storage=IconPlacementStorageAdapter(tmp_path / "placement", "http://localhost:8000"),
    )


def make_gap_clone(_gap_document, bbox, asset_path, _tmp_path):
    from app.icon_gap_candidate import IconGapItem

    return IconGapItem(
        id="icon_gap_clone",
        source="shortcut_missing_icon",
        sourceHintId=None,
        status="candidate",
        bbox=list(bbox),
        confidence=0.80,
        componentId=None,
        componentRole=None,
        assetId="asset_icon_gap_clone",
        assetPath=asset_path,
        assetUrl="http://localhost:8000/files/assets/task_home/icons_gap/icon_gap_clone.png",
        relatedTextElementIds=[],
        relatedBindingIds=[],
        quality={"risk": "low", "reasons": []},
    )


def make_plan_settings(**overrides: Any):
    values = {
        "icon_placement_plan_enabled": True,
        "icon_placement_plan_overlay_enabled": True,
        "icon_placement_plan_dedup_iou": 0.50,
        "icon_placement_plan_text_overlap_iou": 0.10,
        "icon_placement_plan_slice_overlap_iou": 0.50,
        "icon_placement_plan_max_placements": 128,
    }
    values.update(overrides)
    return make_gap_settings(**values)
