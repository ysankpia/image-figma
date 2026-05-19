from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.icon_business_candidate import (
    IconBusinessStorageAdapter,
    apply_icon_business_metadata,
    build_failed_icon_business_document,
    build_icon_business_candidate_document,
)
from app.icon_gap_candidate import IconGapCandidateDocument, IconGapItem
from app.icon_placement_plan import IconPlacementPlanDocument
from app.png_tools import PngMetadata, encode_rgb_png, read_png_metadata
from conftest import PNG_BYTES
from test_component_annotation import flatten_elements
from test_icon_candidate import draw_solid_rect
from test_icon_gap_candidate import create_client_with_env
from test_icon_placement_plan import make_plan_settings


def test_icon_business_default_upload_creates_report_overlay_assets_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-business-candidates")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "region_guided_business_icon_candidate_harness"
        assert document["businessOverlay"] is not None

        overlay = client.get(document["businessOverlay"]["assetUrl"].replace("http://localhost:8000", ""))
        assert overlay.status_code == 200
        assert read_png_metadata(overlay.content) is not None

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m25_icon_business_candidates" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["iconBusinessCandidateCount"] == document["meta"]["businessIconCount"]
        assert dsl["meta"]["iconBusinessCroppedAssetCount"] == document["meta"]["croppedBusinessIconCount"]
        assert dsl["meta"]["iconBusinessBlockedCount"] == document["meta"]["blockedCount"]
        assert dsl["meta"]["iconBusinessFailedCropCount"] == document["meta"]["failedCropCount"]
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_icon_business_disabled_has_no_result_and_keeps_m24_or_m23_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ICON_BUSINESS_CANDIDATE_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-business-candidates")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ICON_BUSINESS_CANDIDATE_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m23_icon_placement_plan" in dsl["meta"]["qualityFlags"]
        assert "m25_icon_business_candidates" not in dsl["meta"]["qualityFlags"]
        assert "iconBusinessCandidateCount" not in dsl["meta"]


def test_icon_business_endpoint_errors(legacy_client: TestClient) -> None:
    missing = legacy_client.get("/api/tasks/task_missing/icon-business-candidates")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_business_icons",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No business icon candidates.",
            "original_filename": "input.png",
            "mime_type": "image/png",
            "file_size": 1,
            "upload_path": "/tmp/input.png",
            "created_at": "2026-05-17T00:00:00+00:00",
            "updated_at": "2026-05-17T00:00:00+00:00",
            "completed_at": "2026-05-17T00:00:00+00:00",
            "failed_at": None,
        }
    )
    not_found = legacy_client.get("/api/tasks/task_without_business_icons/icon-business-candidates")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "ICON_BUSINESS_CANDIDATE_NOT_FOUND"

    state.database.insert_icon_business_candidate_result(
        {
            "task_id": "task_without_business_icons",
            "status": "completed",
            "business_path": "/tmp/does-not-exist.json",
            "overlay_asset_id": None,
            "business_icon_count": 0,
            "cropped_business_icon_count": 0,
            "blocked_count": 0,
            "failed_crop_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-17T00:00:00+00:00",
        }
    )
    missing_file = legacy_client.get("/api/tasks/task_without_business_icons/icon-business-candidates")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "ICON_BUSINESS_CANDIDATE_NOT_FOUND"


def test_icon_business_region_probes_crop_high_value_sources(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()

    document = build_icon_business_candidate_document(
        task_id="task_business",
        image=image,
        png_data=png,
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_placement_document=None,
        dsl=dsl,
        settings=make_business_settings(),
        storage=IconBusinessStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    candidates = [icon for icon in document.businessIcons if icon.status == "candidate"]
    sources = {icon.source for icon in candidates}
    assert sources >= {
        "bottom_nav_region_icon",
        "primary_button_trailing_icon",
        "shortcut_tile_icon",
        "metric_card_icon",
        "room_card_status_icon",
        "row_trailing_arrow",
    }
    assert sum(1 for icon in candidates if icon.source == "bottom_nav_region_icon") == 3
    assert document.meta["businessIconCount"] == len(candidates)
    assert document.meta["croppedBusinessIconCount"] == len(candidates)
    assert document.businessOverlay is not None

    for icon in candidates:
        assert icon.assetPath is not None
        assert Path(icon.assetPath).exists()
        metadata = read_png_metadata(Path(icon.assetPath).read_bytes())
        assert metadata is not None
        assert [metadata.width, metadata.height] == icon.bbox[2:4]


def test_icon_business_primary_button_does_not_crop_leading_text_strokes(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()

    document = build_icon_business_candidate_document(
        task_id="task_business_button_text",
        image=image,
        png_data=png,
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_placement_document=None,
        dsl=dsl,
        settings=make_business_settings(),
        storage=IconBusinessStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert all(icon.source != "primary_button_leading_icon" for icon in document.businessIcons)
    assert any(icon.source == "primary_button_trailing_icon" for icon in document.businessIcons)


def test_icon_business_blocks_existing_icons_and_text_overlap(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    dsl["root"]["children"].append(
        {
            "id": "visible_text_overlap_bottom_nav",
            "type": "text",
            "role": "visible_text_replacement",
            "layout": {"x": 140, "y": 528, "width": 28, "height": 28},
            "content": {"text": "Label"},
        }
    )
    gap_document = gap_document_with_icon(image, [40, 528, 28, 28], tmp_path)

    document = build_icon_business_candidate_document(
        task_id="task_business_block",
        image=image,
        png_data=png,
        icon_candidate_document=None,
        icon_gap_document=gap_document,
        icon_placement_document=None,
        dsl=dsl,
        settings=make_business_settings(),
        storage=IconBusinessStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    candidate_bboxes = [icon.bbox for icon in document.businessIcons if icon.status == "candidate"]
    assert [40, 528, 28, 28] not in candidate_bboxes
    assert [140, 528, 28, 28] not in candidate_bboxes
    blocked_reasons = [reason for item in document.blockedCandidates for reason in item.reasons]
    assert "business_bbox_duplicate_existing_icon" in blocked_reasons
    assert "business_bbox_overlaps_text" in blocked_reasons


def test_icon_business_metadata_only_changes_top_level_meta(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    before = deepcopy(dsl)
    document = build_icon_business_candidate_document(
        task_id="task_business_meta",
        image=image,
        png_data=png,
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_placement_document=None,
        dsl=dsl,
        settings=make_business_settings(),
        storage=IconBusinessStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    after = apply_icon_business_metadata(dsl, document)

    assert flatten_elements(after) == flatten_elements(before)
    assert after["root"] == before["root"]
    assert after["assets"] == before["assets"]
    assert after["meta"] != before["meta"]


def test_icon_business_failed_document_does_not_change_dsl_meta() -> None:
    document = build_failed_icon_business_document(
        task_id="task_failed",
        image=PngMetadata(100, 100, 8, 2, 0, 0, 0),
        code="ICON_BUSINESS_CANDIDATE_VALIDATION_FAILED",
        message="Icon business candidate validation failed.",
    )
    dsl = {"meta": {"qualityFlags": ["m24_visible_icon_fallback_replay"]}, "root": {"children": []}}

    next_dsl = apply_icon_business_metadata(dsl, document)

    assert next_dsl == dsl


def test_generated_business_icon_asset_is_available_from_assets_api(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        document = client.get(f"/api/tasks/{task_id}/icon-business-candidates").json()["data"]
        candidate = next((item for item in document["businessIcons"] if item.get("assetId")), None)
        if candidate is None:
            return

        asset = client.get(f"/api/assets/{candidate['assetId']}")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_icon_business_candidate"
        png = client.get(candidate["assetUrl"].replace("http://localhost:8000", ""))
        assert png.status_code == 200
        assert read_png_metadata(png.content) is not None


def business_probe_fixture() -> tuple[PngMetadata, dict[str, Any], bytes]:
    image = PngMetadata(300, 600, 8, 2, 0, 0, 0)
    rows = [bytearray(bytes((247, 248, 250)) * image.width) for _ in range(image.height)]
    for bbox in ([44, 532, 20, 20], [144, 532, 20, 20], [244, 532, 20, 20]):
        draw_solid_rect(rows, image.width, image.height, bbox, (38, 132, 255))
    draw_solid_rect(rows, image.width, image.height, [30, 420, 240, 50], (20, 120, 245))
    draw_solid_rect(rows, image.width, image.height, [112, 438, 34, 10], (255, 255, 255))
    draw_solid_rect(rows, image.width, image.height, [250, 438, 12, 14], (255, 255, 255))
    draw_solid_rect(rows, image.width, image.height, [28, 282, 30, 30], (220, 235, 255))
    draw_solid_rect(rows, image.width, image.height, [28, 205, 20, 20], (38, 132, 255))
    draw_solid_rect(rows, image.width, image.height, [30, 270, 20, 20], (38, 132, 255))
    draw_solid_rect(rows, image.width, image.height, [260, 310, 16, 18], (38, 132, 255))
    draw_solid_rect(rows, image.width, image.height, [24, 462, 20, 20], (38, 132, 255))
    dsl = {
        "version": "0.1",
        "taskId": "task_business",
        "assets": [],
        "meta": {"qualityFlags": ["m24_visible_icon_fallback_replay"]},
        "root": {
            "id": "root",
            "type": "frame",
            "layout": {"x": 0, "y": 0, "width": image.width, "height": image.height},
            "children": [],
        },
    }
    return image, dsl, encode_rgb_png(image.width, image.height, [bytes(row) for row in rows])


def gap_document_with_icon(image: PngMetadata, bbox: list[int], tmp_path: Path) -> IconGapCandidateDocument:
    icon_path = tmp_path / "existing_gap.png"
    icon_path.write_bytes(encode_rgb_png(bbox[2], bbox[3], [bytes((38, 132, 255)) * bbox[2] for _ in range(bbox[3])]))
    return IconGapCandidateDocument(
        version="0.1",
        taskId="task_business",
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        gapIcons=[
            IconGapItem(
                id="icon_gap_existing",
                source="bottom_nav_missing_icon",
                sourceHintId=None,
                status="candidate",
                bbox=bbox,
                confidence=0.90,
                componentId=None,
                componentRole=None,
                assetId="asset_icon_gap_existing",
                assetPath=str(icon_path),
                assetUrl="http://localhost:8000/files/assets/task_business/icons_gap/icon_gap_existing.png",
                relatedTextElementIds=[],
                relatedBindingIds=[],
                quality={"risk": "low", "reasons": []},
            )
        ],
        blockedHints=[],
        gapOverlay=None,
        warnings=[],
        meta={},
    )


def make_business_settings(**overrides: Any):
    values = {
        "icon_business_candidate_enabled": True,
        "icon_business_candidate_max_candidates": 80,
        "icon_business_candidate_min_confidence": 0.70,
        "icon_business_candidate_min_size": 8,
        "icon_business_candidate_max_size": 96,
        "icon_business_candidate_foreground_distance": 32,
        "icon_business_candidate_retry_padding": 12,
        "icon_business_candidate_edge_clip_tolerance": 3,
        "icon_business_candidate_overlay_enabled": True,
        "icon_business_bottom_nav_enabled": True,
        "icon_business_primary_button_enabled": True,
        "icon_business_shortcut_card_enabled": True,
        "icon_business_metric_card_enabled": True,
        "icon_business_room_card_enabled": True,
        "icon_business_trailing_enabled": True,
        "icon_business_tip_info_enabled": True,
    }
    values.update(overrides)
    return make_plan_settings(**values)
