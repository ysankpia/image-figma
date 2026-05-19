from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.asset_slice import AssetSliceStorageAdapter, build_asset_slice_document
from app.icon_candidate import (
    IconCandidateStorageAdapter,
    build_icon_candidate_document,
)
from app.icon_coverage import (
    IconCoverageStorageAdapter,
    apply_icon_coverage_metadata,
    build_icon_coverage_audit_document,
    build_skipped_icon_coverage_document,
)
from app.png_tools import PngMetadata, decode_png_pixels, read_png_metadata
from conftest import PNG_BYTES
from test_asset_slice import home_like_slice_inputs
from test_component_annotation import flatten_elements
from test_icon_candidate import (
    draw_solid_rect,
    field_label_fixture,
    home_like_icon_inputs,
    make_icon_settings,
)
from test_layer_separation import make_text_fixture_png


def test_icon_coverage_default_upload_creates_report_overlay_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-coverage-audit")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "icon_coverage_audit_and_placement_readiness"
        assert document["coverageOverlay"] is not None

        overlay = client.get(document["coverageOverlay"]["assetUrl"].replace("http://localhost:8000", ""))
        assert overlay.status_code == 200
        metadata = read_png_metadata(overlay.content)
        assert metadata is not None

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert (metadata.width, metadata.height) == (dsl["page"]["width"], dsl["page"]["height"])
        assert "m21_icon_coverage_audit" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["iconCoverageCandidateCount"] == document["meta"]["iconCandidateCount"]
        assert dsl["meta"]["iconCoveragePlacementCount"] == document["meta"]["placementCount"]
        assert dsl["meta"]["iconCoverageMissedHintCount"] == document["meta"]["missedIconHintCount"]
        assert dsl["meta"]["iconPlacementReadyCount"] == document["meta"]["readyCount"]
        assert dsl["meta"]["iconPlacementNeedsFallbackCoordinationCount"] == document["meta"]["needsFallbackCoordinationCount"]
        assert dsl["meta"]["iconPlacementNeedsSliceCoordinationCount"] == document["meta"]["needsSliceCoordinationCount"]
        assert dsl["meta"]["iconPlacementBlockedCount"] == document["meta"]["blockedCount"]
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_icon_coverage_disabled_has_no_result_and_keeps_m20_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ICON_COVERAGE_AUDIT_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-coverage-audit")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ICON_COVERAGE_AUDIT_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m20_icon_candidate_extraction" in dsl["meta"]["qualityFlags"]
        assert "m21_icon_coverage_audit" not in dsl["meta"]["qualityFlags"]
        assert "iconCoverageCandidateCount" not in dsl["meta"]


def test_icon_coverage_endpoint_errors(legacy_client: TestClient) -> None:
    missing = legacy_client.get("/api/tasks/task_missing/icon-coverage-audit")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_icon_coverage",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No icon coverage.",
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
    not_found = legacy_client.get("/api/tasks/task_without_icon_coverage/icon-coverage-audit")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "ICON_COVERAGE_AUDIT_NOT_FOUND"

    state.database.insert_icon_coverage_audit_result(
        {
            "task_id": "task_without_icon_coverage",
            "status": "completed",
            "audit_path": "/tmp/does-not-exist.json",
            "overlay_asset_id": None,
            "placement_count": 0,
            "missed_hint_count": 0,
            "ready_count": 0,
            "needs_fallback_coordination_count": 0,
            "needs_slice_coordination_count": 0,
            "blocked_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = legacy_client.get("/api/tasks/task_without_icon_coverage/icon-coverage-audit")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "ICON_COVERAGE_AUDIT_NOT_FOUND"


def test_icon_coverage_placement_roles_and_fallback_readiness(tmp_path) -> None:
    document, _icon_document, _dsl, _image = home_like_coverage_document(
        tmp_path,
        [
            ([145, 842, 22, 18], (38, 132, 255)),
            ([145, 958, 22, 18], (38, 132, 255)),
            ([148, 1548, 22, 18], (38, 132, 255)),
            ([70, 1326, 16, 16], (38, 132, 255)),
        ],
    )

    assert document.status == "completed"
    placements = document.placements
    assert {placement.placementRole for placement in placements} >= {"leading_icon", "nav_icon", "title_leading_icon"}
    assert all(placement.status == "needs_fallback_coordination" for placement in placements)
    assert all(placement.collision["insideFallbackRegion"] for placement in placements)
    assert all(placement.futureDslNodeHint is not None for placement in placements)
    assert document.meta["coverageBySource"] == {
        "shortcut_card_leading_icon": 2,
        "tip_title_leading_icon": 1,
        "bottom_nav_label_above": 1,
    }


def test_icon_coverage_field_label_role_maps_to_field_leading_icon(tmp_path) -> None:
    image, binding, structure, annotation, dsl, png = field_label_fixture()
    settings = make_coverage_settings(icon_candidate_max_component_area_ratio=0.60)
    icon_document = build_icon_candidate_document(
        task_id="task_field",
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
    document = build_icon_coverage_audit_document(
        task_id="task_field",
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

    assert document.status == "completed"
    assert len(document.placements) == 2
    assert {placement.placementRole for placement in document.placements} == {"field_leading_icon"}
    assert {placement.status for placement in document.placements} == {"ready_for_future_visible_icon"}


def test_icon_coverage_detects_slice_coordination_without_fallback(tmp_path) -> None:
    image, ocr, replacement, binding, structure, annotation, separation, dsl, png = home_like_slice_inputs()
    dsl_without_fallback = deepcopy(dsl)
    dsl_without_fallback["root"]["children"] = [
        child for child in dsl_without_fallback["root"]["children"] if not str(child.get("id", "")).startswith("fallback_region_")
    ]
    icon_png = png_with_extra_regions(
        image,
        ocr,
        [
            ([145, 842, 22, 18], (38, 132, 255)),
        ],
    )
    asset_slice_document = build_asset_slice_document(
        task_id="task_home",
        image=image,
        png_data=png,
        layer_separation_document=separation,
        structure_document=structure,
        dsl=dsl_without_fallback,
        settings=make_coverage_settings(),
        storage=AssetSliceStorageAdapter(tmp_path / "slices", "http://localhost:8000"),
    )
    icon_document = build_icon_candidate_document(
        task_id="task_home",
        image=image,
        png_data=icon_png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=separation,
        asset_slice_document=asset_slice_document,
        dsl=dsl_without_fallback,
        settings=make_coverage_settings(),
        storage=IconCandidateStorageAdapter(tmp_path / "icons", "http://localhost:8000"),
    )
    document = build_icon_coverage_audit_document(
        task_id="task_home",
        image=image,
        png_data=icon_png,
        binding_document=binding,
        structure_document=structure,
        icon_candidate_document=icon_document,
        asset_slice_document=asset_slice_document,
        dsl=dsl_without_fallback,
        settings=make_coverage_settings(),
        storage=IconCoverageStorageAdapter(tmp_path / "coverage", "http://localhost:8000"),
    )

    placement = document.placements[0]
    assert placement.status == "needs_slice_coordination"
    assert placement.collision == {
        "overlapsVisibleText": False,
        "overlapsCover": False,
        "insideFallbackRegion": False,
        "insideAssetSlice": True,
    }


def test_icon_coverage_blocks_missing_asset_and_text_overlap(tmp_path) -> None:
    document, icon_document, dsl, image = home_like_coverage_document(
        tmp_path,
        [([145, 842, 22, 18], (38, 132, 255))],
    )
    assert document.status == "completed"
    icon_document.icons[0].assetPath = "/tmp/missing-icon.png"
    icon_document.icons[0].bbox = [184, 830, 30, 30]

    blocked = build_icon_coverage_audit_document(
        task_id="task_home",
        image=image,
        png_data=png_with_extra_regions(image, None, []),
        binding_document=home_like_slice_inputs()[3],
        structure_document=home_like_slice_inputs()[4],
        icon_candidate_document=icon_document,
        asset_slice_document=None,
        dsl=dsl,
        settings=make_coverage_settings(),
        storage=IconCoverageStorageAdapter(tmp_path / "blocked", "http://localhost:8000"),
    )

    assert blocked.status == "completed"
    assert blocked.placements[0].status == "blocked"
    assert "asset_missing" in blocked.placements[0].reasons
    assert "overlaps_visible_text" in blocked.placements[0].reasons
    assert blocked.blockedIconCandidateIds == [icon_document.icons[0].id]


def test_icon_coverage_missed_hints_and_overlay(tmp_path) -> None:
    document, icon_document, _dsl, image = home_like_coverage_document(
        tmp_path,
        [([145, 842, 22, 18], (38, 132, 255))],
        missed_regions=[
            ([32, 28, 58, 28], (20, 20, 20)),
            ([860, 28, 42, 24], (20, 20, 20)),
            ([28, 86, 24, 24], (38, 132, 255)),
            ([872, 86, 24, 24], (38, 132, 255)),
            ([810, 1160, 18, 22], (38, 132, 255)),
            ([450, 1548, 22, 18], (38, 132, 255)),
        ],
    )

    assert document.status == "completed"
    sources = {hint.source for hint in document.missedIconHints}
    assert "header_left_visual_hint" in sources
    assert "header_right_visual_hint" in sources
    assert "bottom_nav_missing_icon_hint" in sources
    header_hints = [hint for hint in document.missedIconHints if hint.source in {"header_left_visual_hint", "header_right_visual_hint"}]
    assert header_hints
    assert all(hint.bbox[1] >= 75 for hint in header_hints)
    assert document.coverageOverlay is not None
    overlay_metadata = read_png_metadata(Path(document.coverageOverlay.assetPath).read_bytes())
    assert overlay_metadata is not None
    assert (overlay_metadata.width, overlay_metadata.height) == (image.width, image.height)
    pixels = decode_png_pixels(Path(document.coverageOverlay.assetPath).read_bytes())
    placement = document.placements[0]
    x, y, _width, _height = placement.bbox
    assert tuple(pixels.rows[y][x * 3 : x * 3 + 3]) == (150, 80, 220)

    for hint in document.missedIconHints:
        assert all(not overlaps_too_much(hint.bbox, icon.bbox, 0.50) for icon in icon_document.icons)


def test_icon_coverage_missed_hints_ignore_hidden_candidate_text(tmp_path) -> None:
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
    settings = make_coverage_settings(icon_coverage_min_hint_confidence=0.60)
    icon_document = build_icon_candidate_document(
        task_id="task_candidate_text_hint",
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
    document = build_icon_coverage_audit_document(
        task_id="task_candidate_text_hint",
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

    assert document.status == "completed"
    assert all(not overlaps_too_much(hint.bbox, [58, 74, 26, 34], 0.10) for hint in document.missedIconHints)


def test_icon_coverage_missed_hints_reject_large_visual_regions(tmp_path) -> None:
    document, _icon_document, _dsl, _image = home_like_coverage_document(
        tmp_path,
        [([145, 842, 22, 18], (38, 132, 255))],
        missed_regions=[
            ([535, 1361, 86, 94], (38, 132, 255)),
        ],
    )

    assert document.status == "completed"
    assert all(hint.bbox[2] <= 72 and hint.bbox[3] <= 72 for hint in document.missedIconHints)
    assert all(not overlaps_too_much(hint.bbox, [535, 1361, 86, 94], 0.50) for hint in document.missedIconHints)


def test_icon_coverage_metadata_only_changes_top_level_meta(tmp_path) -> None:
    document, _icon_document, dsl, _image = home_like_coverage_document(
        tmp_path,
        [([145, 842, 22, 18], (38, 132, 255))],
    )
    before = deepcopy(dsl)

    after = apply_icon_coverage_metadata(dsl, document)

    assert flatten_elements(after) == flatten_elements(before)
    assert after["root"] == before["root"]
    assert after["assets"] == before["assets"]
    assert after["meta"] != before["meta"]


def test_icon_coverage_skipped_or_failed_document_does_not_change_dsl_meta() -> None:
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    document = build_skipped_icon_coverage_document(
        task_id="task_skipped",
        image=image,
        code="icon_candidate_not_completed",
        message="Icon coverage skipped.",
    )
    dsl = {"meta": {"qualityFlags": ["m20_icon_candidate_extraction"]}, "root": {"children": []}}

    next_dsl = apply_icon_coverage_metadata(dsl, document)

    assert next_dsl == dsl


def test_icon_coverage_overlay_asset_is_available_from_assets_api(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        document = client.get(f"/api/tasks/{task_id}/icon-coverage-audit").json()["data"]
        overlay = document["coverageOverlay"]
        assert overlay is not None

        asset = client.get(f"/api/assets/{overlay['assetId']}")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_icon_coverage_overlay"
        png = client.get(overlay["assetUrl"].replace("http://localhost:8000", ""))
        assert png.status_code == 200
        assert read_png_metadata(png.content) is not None


def home_like_coverage_document(
    tmp_path,
    icon_regions: list[tuple[list[int], tuple[int, int, int]]],
    *,
    missed_regions: list[tuple[list[int], tuple[int, int, int]]] | None = None,
):
    image, ocr, _replacement, binding, structure, annotation, separation, dsl, _png = home_like_icon_inputs(icon_regions)
    settings = make_coverage_settings()
    icon_png = png_with_extra_regions(image, ocr, icon_regions)
    audit_png = png_with_extra_regions(image, ocr, icon_regions + (missed_regions or []))
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
    document = build_icon_coverage_audit_document(
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
    return document, icon_document, dsl, image


def png_with_extra_regions(
    image: PngMetadata,
    ocr,
    regions: list[tuple[list[int], tuple[int, int, int]]],
) -> bytes:
    text_regions = [] if ocr is None else [(block.bbox, (20, 20, 20)) for block in ocr.blocks]
    png = make_text_fixture_png(image.width, image.height, (247, 248, 250), text_regions)
    pixels = decode_png_pixels(png)
    rows = [bytearray(row) for row in pixels.rows]
    for bbox, rgb in regions:
        draw_solid_rect(rows, image.width, image.height, bbox, rgb)
    return bytes_from_rows(image.width, image.height, rows)


def bytes_from_rows(width: int, height: int, rows: list[bytearray]) -> bytes:
    from app.png_tools import encode_rgb_png

    return encode_rgb_png(width, height, [bytes(row) for row in rows])


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


def make_coverage_settings(**overrides: Any):
    values = {
        "icon_coverage_audit_enabled": True,
        "icon_coverage_overlay_enabled": True,
        "icon_coverage_missed_hints_enabled": True,
        "icon_coverage_min_hint_confidence": 0.60,
        "icon_coverage_max_missed_hints": 80,
        "icon_coverage_foreground_distance": 32,
    }
    values.update(overrides)
    return make_icon_settings(**values)
