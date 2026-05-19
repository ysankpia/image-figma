from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.icon_candidate import IconCandidateStorageAdapter, build_icon_candidate_document
from app.icon_coverage import IconCoverageStorageAdapter, build_icon_coverage_audit_document, build_skipped_icon_coverage_document
from app.icon_gap_candidate import (
    IconGapStorageAdapter,
    apply_icon_gap_metadata,
    build_failed_icon_gap_document,
    build_icon_gap_candidate_document,
    touches_search_edge,
)
from app.png_tools import PngMetadata, decode_png_pixels, read_png_metadata
from conftest import PNG_BYTES
from test_component_annotation import flatten_elements
from test_icon_candidate import (
    draw_solid_rect,
    field_label_fixture,
    home_like_icon_inputs,
    make_icon_settings,
)
from test_icon_coverage import bytes_from_rows, make_coverage_settings, png_with_extra_regions


def test_icon_gap_default_upload_creates_report_overlay_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-gap-candidates")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "region_guided_icon_gap_candidate_harness"
        assert document["gapOverlay"] is not None

        overlay = client.get(document["gapOverlay"]["assetUrl"].replace("http://localhost:8000", ""))
        assert overlay.status_code == 200
        assert read_png_metadata(overlay.content) is not None

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m22_icon_gap_candidates" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["iconGapCandidateCount"] == document["meta"]["gapIconCount"]
        assert dsl["meta"]["iconGapCroppedAssetCount"] == document["meta"]["croppedGapIconCount"]
        assert dsl["meta"]["iconGapBlockedCount"] == document["meta"]["blockedCount"]
        assert dsl["meta"]["iconGapFailedCropCount"] == document["meta"]["failedCropCount"]
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_icon_gap_disabled_has_no_result_and_keeps_m21_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ICON_GAP_CANDIDATE_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-gap-candidates")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ICON_GAP_CANDIDATE_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m21_icon_coverage_audit" in dsl["meta"]["qualityFlags"]
        assert "m22_icon_gap_candidates" not in dsl["meta"]["qualityFlags"]
        assert "iconGapCandidateCount" not in dsl["meta"]


def test_icon_gap_endpoint_errors(legacy_client: TestClient) -> None:
    missing = legacy_client.get("/api/tasks/task_missing/icon-gap-candidates")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_icon_gap",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No icon gap candidates.",
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
    not_found = legacy_client.get("/api/tasks/task_without_icon_gap/icon-gap-candidates")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "ICON_GAP_CANDIDATE_NOT_FOUND"

    state.database.insert_icon_gap_candidate_result(
        {
            "task_id": "task_without_icon_gap",
            "status": "completed",
            "gap_path": "/tmp/does-not-exist.json",
            "overlay_asset_id": None,
            "gap_icon_count": 0,
            "cropped_gap_icon_count": 0,
            "blocked_count": 0,
            "failed_crop_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = legacy_client.get("/api/tasks/task_without_icon_gap/icon-gap-candidates")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "ICON_GAP_CANDIDATE_NOT_FOUND"


def test_icon_gap_upgrades_m21_header_and_trailing_hints_to_crops(tmp_path) -> None:
    document, _coverage_document, _icon_document, _dsl, image = home_like_gap_document(
        tmp_path,
        icon_regions=[([145, 842, 22, 18], (38, 132, 255))],
        missed_regions=[
            ([28, 86, 24, 24], (38, 132, 255)),
            ([872, 86, 24, 24], (38, 132, 255)),
            ([810, 1160, 18, 22], (38, 132, 255)),
            ([450, 1548, 22, 18], (38, 132, 255)),
        ],
    )

    assert document.status == "completed"
    candidates = [icon for icon in document.gapIcons if icon.status == "candidate"]
    sources = {icon.source for icon in candidates}
    assert "header_left_nav_icon" in sources
    assert "header_right_action_icon" in sources
    assert {"row_trailing_icon", "card_trailing_icon"} & sources
    assert "bottom_nav_missing_icon" in sources
    assert document.meta["gapIconCount"] == len(candidates)
    assert document.meta["croppedGapIconCount"] == len(candidates)
    assert document.gapOverlay is not None

    for icon in candidates:
        assert icon.assetPath is not None
        assert Path(icon.assetPath).exists()
        metadata = read_png_metadata(Path(icon.assetPath).read_bytes())
        assert metadata is not None
        assert [metadata.width, metadata.height] == icon.bbox[2:4]
        assert icon.bbox[1] >= 75
    overlay_metadata = read_png_metadata(Path(document.gapOverlay.assetPath).read_bytes())
    assert overlay_metadata is not None
    assert (overlay_metadata.width, overlay_metadata.height) == (image.width, image.height)


def test_icon_gap_does_not_duplicate_m20_or_crop_text_candidate(tmp_path) -> None:
    image, binding, structure, annotation, dsl, png = field_label_fixture(icon_bboxes=[])
    dsl["root"]["children"].append(
        {
            "id": "text_unreplaced_large_label",
            "type": "text",
            "role": "candidate_text",
            "layout": {"x": 58, "y": 74, "width": 26, "height": 34},
            "content": {"text": "2F"},
            "visible": False,
        }
    )
    pixels = decode_png_pixels(png)
    rows = [bytearray(row) for row in pixels.rows]
    draw_solid_rect(rows, image.width, image.height, [58, 74, 26, 34], (20, 20, 20))
    png_with_candidate_text = bytes_from_rows(image.width, image.height, rows)
    settings = make_gap_settings(icon_candidate_max_component_area_ratio=0.60, icon_coverage_min_hint_confidence=0.60)
    icon_document = build_icon_candidate_document(
        task_id="task_candidate_text_gap",
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
    coverage_document = build_icon_coverage_audit_document(
        task_id="task_candidate_text_gap",
        image=image,
        png_data=png_with_candidate_text,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        asset_slice_document=None,
        dsl=dsl,
        settings=settings,
        storage=IconCoverageStorageAdapter(tmp_path / "coverage", "http://localhost:8000"),
    )
    document = build_icon_gap_candidate_document(
        task_id="task_candidate_text_gap",
        image=image,
        png_data=png_with_candidate_text,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        icon_coverage_document=coverage_document,
        dsl=dsl,
        settings=settings,
        storage=IconGapStorageAdapter(tmp_path / "gap", "http://localhost:8000"),
    )

    assert document.status == "completed"
    assert all(not overlaps_too_much(icon.bbox, [58, 74, 26, 34], 0.10) for icon in document.gapIcons)


def test_icon_gap_blocks_text_stroke_like_field_hint(tmp_path) -> None:
    document, _coverage_document, _icon_document, _dsl, _image = field_gap_document_with_manual_hint(
        tmp_path,
        field_region=[58, 74, 14, 32],
        hint_bbox=[56, 72, 18, 36],
    )

    assert document.status == "completed"
    assert document.meta["gapIconCount"] == 0
    assert document.blockedHints
    assert any("gap_bbox_text_like" in hint.reasons for hint in document.blockedHints)


def test_icon_gap_multiple_blocked_hints_keep_unique_ids(tmp_path) -> None:
    image, binding, structure, annotation, dsl, png = field_label_fixture(icon_bboxes=[])
    settings = make_gap_settings(icon_candidate_max_component_area_ratio=0.60)
    icon_document = build_icon_candidate_document(
        task_id="task_multiple_blocked_gap",
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
    coverage_document = build_icon_coverage_audit_document(
        task_id="task_multiple_blocked_gap",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        asset_slice_document=None,
        dsl=dsl,
        settings=settings,
        storage=IconCoverageStorageAdapter(tmp_path / "coverage", "http://localhost:8000"),
    )
    from app.icon_coverage import MissedIconHintItem

    coverage_document.missedIconHints = [
        MissedIconHintItem(
            id="missed_icon_hint_blocked_001",
            source="field_icon_hint",
            status="hint_only",
            bbox=[56, 72, 18, 36],
            componentId=structure.components[0].id,
            componentRole=structure.components[0].role,
            confidence=0.74,
            suggestedNextRule="field_icon_candidate",
            reasons=["field_leading_visual", "hint_only_no_crop"],
        ),
        MissedIconHintItem(
            id="missed_icon_hint_blocked_002",
            source="field_icon_hint",
            status="hint_only",
            bbox=[58, 112, 18, 36],
            componentId=structure.components[0].id,
            componentRole=structure.components[0].role,
            confidence=0.74,
            suggestedNextRule="field_icon_candidate",
            reasons=["field_leading_visual", "hint_only_no_crop"],
        ),
    ]

    document = build_icon_gap_candidate_document(
        task_id="task_multiple_blocked_gap",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        icon_coverage_document=coverage_document,
        dsl=dsl,
        settings=settings,
        storage=IconGapStorageAdapter(tmp_path / "gap", "http://localhost:8000"),
    )

    assert document.status == "completed"
    assert len(document.blockedHints) == 2
    blocked_ids = [hint.id for hint in document.blockedHints]
    assert len(set(blocked_ids)) == len(blocked_ids)


def test_icon_gap_retries_edge_clipped_candidate(tmp_path) -> None:
    document, coverage_document, icon_document, dsl, image = home_like_gap_document(
        tmp_path,
        icon_regions=[],
        missed_regions=[
            ([12, 86, 32, 24], (38, 132, 255)),
        ],
    )
    coverage_document.missedIconHints[0].bbox = [12, 86, 20, 24]
    document = build_icon_gap_candidate_document(
        task_id="task_home",
        image=image,
        png_data=png_with_extra_regions(image, None, [([12, 86, 32, 24], (38, 132, 255))]),
        binding_document=home_like_icon_inputs([])[3],
        structure_document=home_like_icon_inputs([])[4],
        icon_candidate_document=icon_document,
        icon_coverage_document=coverage_document,
        dsl=dsl,
        settings=make_gap_settings(),
        storage=IconGapStorageAdapter(tmp_path / "edge-gap", "http://localhost:8000"),
    )

    candidates = [icon for icon in document.gapIcons if icon.status == "candidate"]
    assert candidates
    assert any(hint.reasons == ["no_foreground_blob"] for hint in document.blockedHints)
    assert touches_search_edge([8, 82, 40, 32], [4, 78, 36, 40], 3)


def test_icon_gap_metadata_only_changes_top_level_meta(tmp_path) -> None:
    document, _coverage_document, _icon_document, dsl, _image = home_like_gap_document(
        tmp_path,
        icon_regions=[],
        missed_regions=[([28, 86, 24, 24], (38, 132, 255))],
    )
    before = deepcopy(dsl)

    after = apply_icon_gap_metadata(dsl, document)

    assert flatten_elements(after) == flatten_elements(before)
    assert after["root"] == before["root"]
    assert after["assets"] == before["assets"]
    assert after["meta"] != before["meta"]


def test_icon_gap_failed_document_does_not_change_dsl_meta() -> None:
    document = build_failed_icon_gap_document(
        task_id="task_failed",
        image=PngMetadata(100, 100, 8, 2, 0, 0, 0),
        code="ICON_GAP_CANDIDATE_VALIDATION_FAILED",
        message="Icon gap candidate validation failed.",
    )
    dsl = {"meta": {"qualityFlags": ["m21_icon_coverage_audit"]}, "root": {"children": []}}

    next_dsl = apply_icon_gap_metadata(dsl, document)

    assert next_dsl == dsl


def test_icon_gap_assets_are_available_from_assets_api(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        document = client.get(f"/api/tasks/{task_id}/icon-gap-candidates").json()["data"]
        overlay = document["gapOverlay"]
        assert overlay is not None

        overlay_asset = client.get(f"/api/assets/{overlay['assetId']}")
        assert overlay_asset.status_code == 200
        assert overlay_asset.json()["data"]["role"] == "asset_icon_gap_overlay"

        candidate = next((item for item in document["gapIcons"] if item.get("assetId")), None)
        if candidate is None:
            return
        asset = client.get(f"/api/assets/{candidate['assetId']}")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_icon_gap_candidate"
        png = client.get(candidate["assetUrl"].replace("http://localhost:8000", ""))
        assert png.status_code == 200
        assert read_png_metadata(png.content) is not None


def home_like_gap_document(
    tmp_path,
    icon_regions: list[tuple[list[int], tuple[int, int, int]]],
    missed_regions: list[tuple[list[int], tuple[int, int, int]]],
):
    image, ocr, _replacement, binding, structure, annotation, separation, dsl, _png = home_like_icon_inputs(icon_regions)
    settings = make_gap_settings()
    icon_png = png_with_extra_regions(image, ocr, icon_regions)
    audit_png = png_with_extra_regions(image, ocr, icon_regions + missed_regions)
    icon_document = build_icon_candidate_document(
        task_id="task_home",
        image=image,
        png_data=icon_png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=separation,
        asset_slice_document=None,
        dsl=dsl,
        settings=settings,
        storage=IconCandidateStorageAdapter(tmp_path / "icons", "http://localhost:8000"),
    )
    coverage_document = build_icon_coverage_audit_document(
        task_id="task_home",
        image=image,
        png_data=audit_png,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        asset_slice_document=None,
        dsl=dsl,
        settings=settings,
        storage=IconCoverageStorageAdapter(tmp_path / "coverage", "http://localhost:8000"),
    )
    document = build_icon_gap_candidate_document(
        task_id="task_home",
        image=image,
        png_data=audit_png,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        icon_coverage_document=coverage_document,
        dsl=dsl,
        settings=settings,
        storage=IconGapStorageAdapter(tmp_path / "gap", "http://localhost:8000"),
    )
    return document, coverage_document, icon_document, dsl, image


def field_gap_document(tmp_path, field_region: list[int]):
    image, binding, structure, annotation, dsl, png = field_label_fixture(icon_bboxes=[])
    settings = make_gap_settings(icon_candidate_max_component_area_ratio=0.60, icon_coverage_min_hint_confidence=0.40)
    pixels = decode_png_pixels(png)
    rows = [bytearray(row) for row in pixels.rows]
    draw_solid_rect(rows, image.width, image.height, field_region, (20, 20, 20))
    png_with_field = bytes_from_rows(image.width, image.height, rows)
    icon_document = build_icon_candidate_document(
        task_id="task_field_gap",
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
    coverage_document = build_icon_coverage_audit_document(
        task_id="task_field_gap",
        image=image,
        png_data=png_with_field,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        asset_slice_document=None,
        dsl=dsl,
        settings=settings,
        storage=IconCoverageStorageAdapter(tmp_path / "coverage", "http://localhost:8000"),
    )
    document = build_icon_gap_candidate_document(
        task_id="task_field_gap",
        image=image,
        png_data=png_with_field,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        icon_coverage_document=coverage_document,
        dsl=dsl,
        settings=settings,
        storage=IconGapStorageAdapter(tmp_path / "gap", "http://localhost:8000"),
    )
    return document, coverage_document, icon_document, dsl, image


def field_gap_document_with_manual_hint(tmp_path, field_region: list[int], hint_bbox: list[int]):
    image, binding, structure, annotation, dsl, png = field_label_fixture(icon_bboxes=[])
    settings = make_gap_settings(icon_candidate_max_component_area_ratio=0.60)
    pixels = decode_png_pixels(png)
    rows = [bytearray(row) for row in pixels.rows]
    draw_solid_rect(rows, image.width, image.height, field_region, (20, 20, 20))
    png_with_field = bytes_from_rows(image.width, image.height, rows)
    icon_document = build_icon_candidate_document(
        task_id="task_field_gap",
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
    coverage_document = build_icon_coverage_audit_document(
        task_id="task_field_gap",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        asset_slice_document=None,
        dsl=dsl,
        settings=settings,
        storage=IconCoverageStorageAdapter(tmp_path / "coverage", "http://localhost:8000"),
    )
    from app.icon_coverage import MissedIconHintItem

    coverage_document.missedIconHints = [
        MissedIconHintItem(
            id="missed_icon_hint_manual",
            source="field_icon_hint",
            status="hint_only",
            bbox=hint_bbox,
            componentId=structure.components[0].id,
            componentRole=structure.components[0].role,
            confidence=0.74,
            suggestedNextRule="field_icon_candidate",
            reasons=["field_leading_visual", "hint_only_no_crop"],
        )
    ]
    document = build_icon_gap_candidate_document(
        task_id="task_field_gap",
        image=image,
        png_data=png_with_field,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        icon_coverage_document=coverage_document,
        dsl=dsl,
        settings=settings,
        storage=IconGapStorageAdapter(tmp_path / "gap", "http://localhost:8000"),
    )
    return document, coverage_document, icon_document, dsl, image


def overlaps_too_much(left: list[int], right: list[int], threshold: float) -> bool:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    if x2 <= x1 or y2 <= y1:
        return False
    intersection = (x2 - x1) * (y2 - y1)
    union = left[2] * left[3] + right[2] * right[3] - intersection
    return intersection / max(1, union) > threshold


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    from test_component_structure import create_client_with_env as create_component_client

    return create_component_client(monkeypatch, tmp_path, env)


def make_gap_settings(**overrides: Any):
    values = {
        "icon_gap_candidate_enabled": True,
        "icon_gap_candidate_min_confidence": 0.72,
        "icon_gap_candidate_max_candidates": 48,
        "icon_gap_candidate_min_size": 8,
        "icon_gap_candidate_max_size": 80,
        "icon_gap_candidate_foreground_distance": 32,
        "icon_gap_candidate_retry_padding": 12,
        "icon_gap_candidate_edge_clip_tolerance": 3,
        "icon_gap_candidate_overlay_enabled": True,
    }
    values.update(overrides)
    return make_coverage_settings(**values)
