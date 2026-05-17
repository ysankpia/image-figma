from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.icon_placement_plan import IconPlacementPlanItem, IconPlacementPlanDocument, IconPlacementCollision
from app.icon_visible_fallback import (
    IconVisibleFallbackStorageAdapter,
    apply_icon_visible_fallback_to_dsl,
    build_icon_visible_fallback_document,
    validate_icon_visible_fallback_document,
)
from app.png_tools import PngMetadata, encode_rgb_png, read_png_metadata
from conftest import PNG_BYTES
from test_icon_candidate import draw_solid_rect
from test_icon_gap_candidate import create_client_with_env
from test_icon_placement_plan import make_plan_settings


def test_icon_visible_fallback_default_disabled_has_no_result_and_keeps_m23_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-visible-fallback")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ICON_VISIBLE_FALLBACK_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m23_icon_placement_plan" in dsl["meta"]["qualityFlags"]
        assert "m24_visible_icon_fallback_replay" not in dsl["meta"]["qualityFlags"]
        assert not [child for child in dsl["root"]["children"] if child.get("role") == "visible_icon_fallback"]


def test_icon_visible_fallback_enabled_upload_appends_nodes_assets_report_and_overlay(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ICON_VISIBLE_FALLBACK_ENABLED": "true",
            "ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE": "0.70",
            "ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE": "255",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-visible-fallback")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "visible_icon_fallback_replay_experiment"
        assert document["visibleFallbackOverlay"] is not None
        overlay = client.get(document["visibleFallbackOverlay"]["assetUrl"].replace("http://localhost:8000", ""))
        assert overlay.status_code == 200
        assert read_png_metadata(overlay.content) is not None

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m24_visible_icon_fallback_replay" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["visibleIconFallbackAppliedCount"] == document["meta"]["appliedCount"]
        assert dsl["meta"]["visibleIconFallbackBlockedCount"] == document["meta"]["blockedCount"]

        applied_count = document["meta"]["appliedCount"]
        cover_nodes = [child for child in dsl["root"]["children"] if child.get("role") == "icon_fallback_cover"]
        icon_nodes = [child for child in dsl["root"]["children"] if child.get("role") == "visible_icon_fallback"]
        assert len(cover_nodes) == applied_count
        assert len(icon_nodes) == applied_count
        if applied_count:
            assert dsl["root"]["children"].index(cover_nodes[0]) < dsl["root"]["children"].index(icon_nodes[0])
            asset_ids = {asset["assetId"] for asset in dsl["assets"]}
            assert all(node["source"]["assetId"] in asset_ids for node in icon_nodes)


def test_icon_visible_fallback_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/icon-visible-fallback")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_icon_visible_fallback",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No icon visible fallback.",
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
    not_found = client.get("/api/tasks/task_without_icon_visible_fallback/icon-visible-fallback")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "ICON_VISIBLE_FALLBACK_NOT_FOUND"

    state.database.insert_icon_visible_fallback_result(
        {
            "task_id": "task_without_icon_visible_fallback",
            "status": "completed",
            "fallback_path": "/tmp/does-not-exist.json",
            "overlay_asset_id": None,
            "selected_count": 0,
            "applied_count": 0,
            "blocked_count": 0,
            "skipped_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_icon_visible_fallback/icon-visible-fallback")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "ICON_VISIBLE_FALLBACK_NOT_FOUND"


def test_icon_visible_fallback_applies_only_safe_allowed_placements(tmp_path) -> None:
    image = PngMetadata(200, 200, 8, 2, 0, 0, 0)
    png = solid_png(image, (255, 255, 255), [([20, 20, 20, 20], (0, 0, 0)), ([80, 20, 20, 20], (0, 0, 0))])
    icon_path = tmp_path / "icon.png"
    icon_path.write_bytes(solid_png(PngMetadata(20, 20, 8, 2, 0, 0, 0), (0, 0, 0), []))
    dsl = base_dsl(image)
    dsl["root"]["children"].append(
        {
            "id": "fallback_full_image",
            "type": "image",
            "role": "fallback_region",
            "layout": {"x": 0, "y": 0, "width": 200, "height": 200},
            "source": {"assetId": "asset_original"},
        }
    )
    plan = placement_document(
        image,
        [
            placement("icon_place_001", "nav_icon", [20, 20, 20, 20], str(icon_path), confidence=0.91),
            placement("icon_place_002", "trailing_icon", [80, 20, 20, 20], str(icon_path), confidence=0.91),
            placement("icon_place_003", "leading_icon", [20, 70, 20, 20], str(icon_path), confidence=0.50),
        ],
    )
    settings = make_m24_settings(icon_visible_fallback_min_confidence=0.85)

    document = build_icon_visible_fallback_document(
        task_id="task_visible",
        image=image,
        png_data=png,
        icon_placement_document=plan,
        dsl=dsl,
        settings=settings,
        storage=IconVisibleFallbackStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    assert [item.placementId for item in document.visibleIcons] == ["icon_place_001"]
    blocked_reasons = {item.placementId: item.reasons for item in document.blockedPlacements}
    assert "role_not_allowed_for_m24" in blocked_reasons["icon_place_002"]
    assert "confidence_below_m24_min" in blocked_reasons["icon_place_003"]


def test_icon_visible_fallback_blocks_text_overlap_and_bad_background(tmp_path) -> None:
    image = PngMetadata(200, 200, 8, 2, 0, 0, 0)
    rows = [bytearray(bytes((255, 255, 255)) * image.width) for _ in range(image.height)]
    draw_solid_rect(rows, image.width, image.height, [20, 20, 20, 20], (0, 0, 0))
    for row_index in range(78, 104):
        for column in range(78, 104):
            value = 0 if (row_index + column) % 2 == 0 else 255
            offset = column * 3
            rows[row_index][offset : offset + 3] = bytes((value, value, value))
    png = encode_rgb_png(image.width, image.height, [bytes(row) for row in rows])
    icon_path = tmp_path / "icon.png"
    icon_path.write_bytes(solid_png(PngMetadata(20, 20, 8, 2, 0, 0, 0), (0, 0, 0), []))
    dsl = base_dsl(image)
    dsl["root"]["children"].append(
        {
            "id": "visible_text_overlap",
            "type": "text",
            "role": "visible_text_replacement",
            "layout": {"x": 20, "y": 20, "width": 20, "height": 20},
            "content": {"text": "T"},
        }
    )
    plan = placement_document(
        image,
        [
            placement("icon_place_001", "nav_icon", [20, 20, 20, 20], str(icon_path)),
            placement("icon_place_002", "nav_icon", [80, 80, 20, 20], str(icon_path)),
        ],
    )
    settings = make_m24_settings(icon_visible_fallback_solid_bg_tolerance=20)

    document = build_icon_visible_fallback_document(
        task_id="task_visible",
        image=image,
        png_data=png,
        icon_placement_document=plan,
        dsl=dsl,
        settings=settings,
        storage=IconVisibleFallbackStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    blocked_reasons = {item.placementId: item.reasons for item in document.blockedPlacements}
    assert "overlaps_visible_text" in blocked_reasons["icon_place_001"]
    assert "solid_background_sample_failed" in blocked_reasons["icon_place_002"]


def test_icon_visible_fallback_dsl_append_is_regression_safe(tmp_path) -> None:
    image = PngMetadata(120, 120, 8, 2, 0, 0, 0)
    png = solid_png(image, (255, 255, 255), [([20, 20, 20, 20], (0, 0, 0))])
    icon_path = tmp_path / "icon.png"
    icon_path.write_bytes(solid_png(PngMetadata(20, 20, 8, 2, 0, 0, 0), (0, 0, 0), []))
    dsl = base_dsl(image)
    dsl["root"]["children"].append(
        {
            "id": "fallback_full_image",
            "type": "image",
            "role": "fallback_region",
            "layout": {"x": 0, "y": 0, "width": 120, "height": 120},
            "source": {"assetId": "asset_original"},
        }
    )
    plan = placement_document(image, [placement("icon_place_001", "nav_icon", [20, 20, 20, 20], str(icon_path))])
    before_children = deepcopy(dsl["root"]["children"])
    before_assets = deepcopy(dsl["assets"])
    document = build_icon_visible_fallback_document(
        task_id="task_visible",
        image=image,
        png_data=png,
        icon_placement_document=plan,
        dsl=dsl,
        settings=make_m24_settings(),
        storage=IconVisibleFallbackStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )
    next_dsl = apply_icon_visible_fallback_to_dsl(dsl, document)

    assert next_dsl["root"]["children"][: len(before_children)] == before_children
    assert next_dsl["assets"][: len(before_assets)] == before_assets
    assert len(next_dsl["root"]["children"]) == len(before_children) + 2
    assert len(next_dsl["assets"]) == len(before_assets) + 1
    assert not validate_icon_visible_fallback_document(
        document=document,
        icon_placement_document=plan,
        final_dsl=next_dsl,
        image=image,
    )


def test_icon_visible_fallback_overlay_asset_is_available_from_assets_api(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ICON_VISIBLE_FALLBACK_ENABLED": "true",
            "ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE": "0.70",
            "ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE": "255",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        document = client.get(f"/api/tasks/{task_id}/icon-visible-fallback").json()["data"]
        overlay = document["visibleFallbackOverlay"]
        assert overlay is not None

        asset = client.get(f"/api/assets/{overlay['assetId']}")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_icon_visible_fallback_overlay"


def solid_png(
    image: PngMetadata,
    background: tuple[int, int, int],
    regions: list[tuple[list[int], tuple[int, int, int]]],
) -> bytes:
    rows = [bytearray(bytes(background) * image.width) for _ in range(image.height)]
    for bbox, rgb in regions:
        draw_solid_rect(rows, image.width, image.height, bbox, rgb)
    return encode_rgb_png(image.width, image.height, [bytes(row) for row in rows])


def base_dsl(image: PngMetadata) -> dict[str, Any]:
    return {
        "version": "0.1",
        "taskId": "task_visible",
        "page": {"width": image.width, "height": image.height},
        "assets": [
            {
                "assetId": "asset_original",
                "type": "image",
                "role": "original",
                "url": "http://localhost:8000/files/uploads/task_visible/original.png",
                "format": "png",
                "width": image.width,
                "height": image.height,
                "storage": "local",
            }
        ],
        "root": {
            "id": "root",
            "type": "frame",
            "layout": {"x": 0, "y": 0, "width": image.width, "height": image.height},
            "children": [],
        },
        "meta": {"qualityFlags": ["m23_icon_placement_plan"]},
    }


def placement_document(image: PngMetadata, placements: list[IconPlacementPlanItem]) -> IconPlacementPlanDocument:
    return IconPlacementPlanDocument(
        version="0.1",
        taskId="task_visible",
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        placements=placements,
        dedupedIcons=[],
        blockedIcons=[],
        placementOverlay=None,
        warnings=[],
        meta={
            "notes": "icon_placement_plan_and_layering_readiness",
            "placementCount": len(placements),
            "readyCount": 0,
            "needsFallbackMaskCount": len(placements),
            "needsSliceCoordinationCount": 0,
            "needsFallbackCoordinationCount": 0,
            "reviewRequiredCount": 0,
            "blockedCount": 0,
            "dedupedCount": 0,
            "sourceStageSummary": {"m20": len(placements)},
            "decisionSummary": {"needs_fallback_mask": len(placements)},
            "roleSummary": {},
        },
    )


def placement(
    placement_id: str,
    role: str,
    bbox: list[int],
    asset_path: str,
    *,
    confidence: float = 0.91,
) -> IconPlacementPlanItem:
    suffix = placement_id.rsplit("_", 1)[-1]
    return IconPlacementPlanItem(
        id=placement_id,
        sourceStage="m20",
        sourceIconId=f"icon_candidate_{suffix}",
        assetId=f"asset_icon_candidate_{suffix}",
        assetPath=asset_path,
        assetUrl=f"http://localhost:8000/files/assets/task_visible/icons/icon_candidate_{suffix}.png",
        componentId=None,
        componentRole=None,
        placementRole=role,
        decision="needs_fallback_mask",
        status="planned",
        bbox=bbox,
        confidence=confidence,
        relatedTextElementIds=[],
        relatedBindingIds=[],
        relatedSliceCandidateIds=[],
        collision=IconPlacementCollision(
            overlapsVisibleText=False,
            overlapsCover=False,
            overlapsCandidateText=False,
            insideFallbackRegion=True,
            insideAssetSlice=False,
            duplicatesPlacementId=None,
        ),
        futureDslNodeHint=None,
        risk="medium",
        reasons=["icon_asset_exists", "bbox_valid", "inside_fallback_region"],
    )


def make_m24_settings(**overrides: Any):
    values = {
        "icon_visible_fallback_enabled": True,
        "icon_visible_fallback_max_placements": 12,
        "icon_visible_fallback_min_confidence": 0.85,
        "icon_visible_fallback_mask_padding": 2,
        "icon_visible_fallback_max_mask_size": 96,
        "icon_visible_fallback_solid_bg_tolerance": 28,
        "icon_visible_fallback_allowed_roles": ["nav_icon", "header_nav_icon", "header_action_icon", "leading_icon"],
        "icon_visible_fallback_overlay_enabled": True,
    }
    values.update(overrides)
    return make_plan_settings(**values)
