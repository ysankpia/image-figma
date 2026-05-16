from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.asset_slice import (
    AssetSliceStorageAdapter,
    apply_asset_slice_metadata,
    build_asset_slice_document,
    build_failed_asset_slice_document,
)
from app.component_annotation import apply_component_annotations, build_component_annotation_document
from app.layer_separation import build_layer_separation_document
from app.png_tools import PngMetadata, decode_png_pixels, read_png_metadata
from conftest import PNG_BYTES
from test_component_annotation import flatten_elements, home_like_annotation_inputs
from test_component_structure import create_client_with_env as create_component_client
from test_layer_separation import make_layer_settings, png_for_ocr


def test_asset_slice_default_upload_creates_report_assets_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/asset-slice-candidates")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "local_asset_slice_experiment_harness"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m19_local_asset_slice_candidates" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["assetSliceCandidateCount"] == document["meta"]["sliceCount"]
        assert dsl["meta"]["assetSliceFilledCandidateCount"] == document["meta"]["filledSliceCount"]
        assert dsl["meta"]["assetSliceBlockedCount"] == document["meta"]["blockedCount"]
        assert dsl["meta"]["assetSliceFailedCount"] == document["meta"]["failedSliceCount"]
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_asset_slice_disabled_has_no_result_and_keeps_m18_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ASSET_SLICE_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/asset-slice-candidates")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ASSET_SLICE_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m18_layer_separation_candidates" in dsl["meta"]["qualityFlags"]
        assert "m19_local_asset_slice_candidates" not in dsl["meta"]["qualityFlags"]
        assert "assetSliceCandidateCount" not in dsl["meta"]


def test_asset_slice_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/asset-slice-candidates")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_asset_slice",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No asset slice.",
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
    not_found = client.get("/api/tasks/task_without_asset_slice/asset-slice-candidates")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "ASSET_SLICE_NOT_FOUND"

    state.database.insert_asset_slice_result(
        {
            "task_id": "task_without_asset_slice",
            "status": "completed",
            "slice_path": "/tmp/does-not-exist.json",
            "slice_count": 0,
            "filled_slice_count": 0,
            "blocked_count": 0,
            "failed_slice_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_asset_slice/asset-slice-candidates")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "ASSET_SLICE_NOT_FOUND"


def test_home_like_asset_slice_generates_tip_card_original_and_filled_assets(tmp_path) -> None:
    image, _ocr, _replacement, _binding, structure, _annotation, separation, dsl, png = home_like_slice_inputs()
    document = build_asset_slice_document(
        task_id="task_home",
        image=image,
        png_data=png,
        layer_separation_document=separation,
        structure_document=structure,
        dsl=dsl,
        settings=make_asset_settings(),
        storage=AssetSliceStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    by_component = {item.componentId: item for item in document.slices}
    tip = by_component["component_tip_card_001"]
    assert tip.status == "candidate"
    assert tip.strategy == "local_slice_with_simple_fill"
    assert tip.assetPath and Path(tip.assetPath).exists()
    assert tip.filledAssetPath and Path(tip.filledAssetPath).exists()
    assert tip.fillOperations

    source_bbox = tip.fillOperations[0]["sourceBBox"]
    local_bbox = tip.fillOperations[0]["sliceLocalBBox"]
    assert local_bbox[0] == source_bbox[0] - tip.bbox[0]
    assert local_bbox[1] == source_bbox[1] - tip.bbox[1]
    filled_pixels = decode_png_pixels(Path(tip.filledAssetPath).read_bytes())
    x, y, width, height = local_bbox
    sample_offset = x * 3
    assert tuple(filled_pixels.rows[y][sample_offset : sample_offset + 3]) == (247, 248, 250)
    assert width > 0 and height > 0

    primary = by_component["component_primary_button_001"]
    assert primary.status == "skipped"
    assert "component_role_not_slice_priority" in primary.quality["reasons"]
    assert primary.assetPath is None

    assert document.meta["sliceCount"] == sum(1 for item in document.slices if item.status == "candidate")
    assert document.meta["filledSliceCount"] >= 1
    assert document.meta["filledSliceCount"] == sum(1 for item in document.slices if item.strategy == "local_slice_with_simple_fill")


def test_asset_slice_blocks_large_slice_candidate(tmp_path) -> None:
    image, _ocr, _replacement, _binding, structure, _annotation, separation, dsl, png = home_like_slice_inputs()
    tip = next(candidate for candidate in separation.candidates if candidate.componentId == "component_tip_card_001")
    tip.bbox = [0, 0, image.width, image.height]

    document = build_asset_slice_document(
        task_id="task_home",
        image=image,
        png_data=png,
        layer_separation_document=separation,
        structure_document=structure,
        dsl=dsl,
        settings=make_asset_settings(asset_slice_max_area_ratio=0.20),
        storage=AssetSliceStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    item = next(slice_item for slice_item in document.slices if slice_item.componentId == "component_tip_card_001")
    assert item.status == "blocked"
    assert "crop_bbox_too_large" in item.quality["reasons"]
    assert item.componentId in document.blockedComponentIds


def test_asset_slice_blocks_fill_target_outside_crop(tmp_path) -> None:
    image, _ocr, _replacement, _binding, structure, _annotation, separation, dsl, png = home_like_slice_inputs()
    tip = next(candidate for candidate in separation.candidates if candidate.componentId == "component_tip_card_001")
    tip.fillCandidate["targetBBoxes"] = [[0, 0, 30, 30]]

    document = build_asset_slice_document(
        task_id="task_home",
        image=image,
        png_data=png,
        layer_separation_document=separation,
        structure_document=structure,
        dsl=dsl,
        settings=make_asset_settings(),
        storage=AssetSliceStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    item = next(slice_item for slice_item in document.slices if slice_item.componentId == "component_tip_card_001")
    assert item.status == "candidate"
    assert item.strategy == "local_slice_original"
    assert "fill_target_outside_crop" in item.quality["reasons"]
    assert item.filledAssetPath is None


def test_asset_slice_metadata_only_changes_top_level_meta(tmp_path) -> None:
    image, _ocr, _replacement, _binding, structure, _annotation, separation, dsl, png = home_like_slice_inputs()
    before = deepcopy(dsl)
    document = build_asset_slice_document(
        task_id="task_home",
        image=image,
        png_data=png,
        layer_separation_document=separation,
        structure_document=structure,
        dsl=dsl,
        settings=make_asset_settings(),
        storage=AssetSliceStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    after = apply_asset_slice_metadata(dsl, document)

    assert flatten_elements(after) == flatten_elements(before)
    assert after["root"] == before["root"]
    assert after["assets"] == before["assets"]
    assert after["meta"] != before["meta"]


def test_asset_slice_failed_document_does_not_change_dsl_meta() -> None:
    document = build_failed_asset_slice_document(
        task_id="task_failed",
        image=PngMetadata(100, 100, 8, 2, 0, 0, 0),
        code="ASSET_SLICE_VALIDATION_FAILED",
        message="Asset slice validation failed.",
    )
    dsl = {"meta": {"qualityFlags": ["m18_layer_separation_candidates"]}, "root": {"children": []}}

    next_dsl = apply_asset_slice_metadata(dsl, document)

    assert next_dsl == dsl


def test_generated_slice_asset_is_available_from_assets_api(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        document = client.get(f"/api/tasks/{task_id}/asset-slice-candidates").json()["data"]
        candidate = next((item for item in document["slices"] if item.get("assetId")), None)
        if candidate is None:
            return

        asset = client.get(f"/api/assets/{candidate['assetId']}")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_slice_candidate"
        png = client.get(candidate["assetUrl"].replace("http://localhost:8000", ""))
        assert png.status_code == 200
        assert read_png_metadata(png.content) is not None


def home_like_slice_inputs():
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_asset_settings(),
    )
    annotated_dsl = apply_component_annotations(dsl, annotation, layer_naming=True)
    png = png_for_ocr(image, ocr)
    separation = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=annotated_dsl,
        settings=make_asset_settings(),
    )
    return image, ocr, replacement, binding, structure, annotation, separation, annotated_dsl, png


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    return create_component_client(monkeypatch, tmp_path, env)


def make_asset_settings(**overrides: Any):
    values = {
        "asset_slice_enabled": True,
        "asset_slice_max_candidates": 24,
        "asset_slice_min_confidence": 0.70,
        "asset_slice_max_area_ratio": 0.25,
        "asset_slice_generate_filled": True,
    }
    values.update(overrides)
    return make_layer_settings(**values)
