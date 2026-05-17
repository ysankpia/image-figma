from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.component_annotation import index_dsl_elements
from app.icon_business_candidate import unique_bboxes
from app.icon_candidate import IconCandidateDocument, IconCandidateItem
from app.icon_coverage import bboxes_by_role
from app.png_tools import PngMetadata, decode_png_pixels, read_png_metadata
from app.sam_visual_candidate import (
    SamVisualContext,
    SamVisualStorageAdapter,
    append_mask_candidate,
    build_sam_visual_candidate_document,
    clear_sam2_runtime_cache,
    collect_existing_icon_bboxes,
    get_sam2_runtime,
    header_title_zones,
    illustration_zones,
    status_bar_zones,
    bed_map_zones,
    validate_sam_visual_candidate_document,
)
from conftest import PNG_BYTES
from test_icon_business_candidate import business_probe_fixture, make_business_settings
from test_icon_gap_candidate import create_client_with_env


def test_sam_visual_disabled_by_default_has_no_result_and_does_not_change_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/sam-visual-candidates")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SAM_VISUAL_CANDIDATE_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m27_sam2_visual_candidate_filtering" not in dsl["meta"].get("qualityFlags", [])
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_sam_visual_enabled_missing_checkpoint_saves_skipped_document(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "SAM_VISUAL_CANDIDATE_ENABLED": "true",
            "SAM_VISUAL_CANDIDATE_CHECKPOINT": str(tmp_path / "missing.pt"),
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/sam-visual-candidates")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "skipped"
        assert document["error"]["code"] == "SAM_VISUAL_PROVIDER_UNAVAILABLE"
        assert document["warnings"][0]["code"] == "model_missing"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m25_icon_business_candidates" in dsl["meta"]["qualityFlags"]
        assert "m27_sam2_visual_candidate_filtering" not in dsl["meta"].get("qualityFlags", [])


def test_sam_visual_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/sam-visual-candidates")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_sam_visual",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No sam visual.",
            "original_filename": "input.png",
            "mime_type": "image/png",
            "file_size": 1,
            "upload_path": "/tmp/input.png",
            "created_at": "2026-05-18T00:00:00+00:00",
            "updated_at": "2026-05-18T00:00:00+00:00",
            "completed_at": "2026-05-18T00:00:00+00:00",
            "failed_at": None,
        }
    )
    not_found = client.get("/api/tasks/task_without_sam_visual/sam-visual-candidates")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "SAM_VISUAL_CANDIDATE_NOT_FOUND"

    state.database.insert_sam_visual_candidate_result(
        {
            "task_id": "task_without_sam_visual",
            "status": "completed",
            "candidate_path": "/tmp/does-not-exist.json",
            "overlay_asset_id": None,
            "raw_mask_count": 0,
            "candidate_count": 0,
            "blocked_count": 0,
            "failed_count": 0,
            "elapsed_ms": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-18T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_sam_visual/sam-visual-candidates")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "SAM_VISUAL_CANDIDATE_NOT_FOUND"


def test_mock_sam_masks_filter_text_cover_existing_exclusion_and_accept_valid(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    dsl["root"]["children"].extend(
        [
            {"id": "text_hit", "type": "text", "role": "visible_text_replacement", "layout": {"x": 40, "y": 520, "width": 80, "height": 30}},
            {"id": "cover_hit", "type": "shape", "role": "text_replacement_cover", "layout": {"x": 140, "y": 520, "width": 80, "height": 30}},
            {"id": "candidate_hit", "type": "text", "role": "candidate_text", "layout": {"x": 240, "y": 520, "width": 80, "height": 30}},
        ]
    )
    icon_document = IconCandidateDocument(
        version="0.1",
        taskId="task_sam_visual",
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        icons=[
            IconCandidateItem(
                id="icon_candidate_001",
                componentId="component_001",
                componentRole="shortcut_card",
                source="component_local_visual_blob",
                status="candidate",
                bbox=[40, 620, 32, 32],
                confidence=0.9,
                assetId="asset_icon_candidate_001",
                assetPath=None,
                assetUrl=None,
                relatedTextElementIds=[],
                relatedBindingIds=[],
                quality={"risk": "low", "reasons": []},
            )
        ],
        blockedComponentIds=[],
        warnings=[],
        meta={},
    )
    context = build_context(tmp_path, image, dsl, png, make_sam_settings(), icon_document=icon_document)
    candidates = []
    blocked = []

    cases = [
        ([40, 520, 50, 24], 1000, "candidate_text_overlap"),
        ([140, 520, 50, 24], 1000, "cover_overlap"),
        ([240, 520, 50, 24], 1000, "candidate_text_overlap"),
        ([40, 620, 32, 32], 800, "duplicate_existing_icon"),
        ([10, 5, 28, 18], 500, "inside_status_bar"),
        ([20, round(image.height * 0.31), 80, 80], 3200, "inside_bed_map_zone"),
        ([10, 700, 120, 4], 480, "mask_area_too_small"),
            ([120, 392, 32, 32], 900, None),
    ]
    for bbox, mask_area, expected_reason in cases:
        append_mask_candidate(
            context=context,
            candidates=candidates,
            blocked=blocked,
            bbox=bbox,
            mask_area=mask_area,
            raw_confidence=0.9,
            raw_reasons=["sam_quality_score_ok"],
        )
        if expected_reason is not None:
            assert expected_reason in blocked[-1].reasons

    assert len(candidates) == 1
    assert candidates[0].bbox == [120, 392, 32, 32]
    assert candidates[0].kind == "button_candidate"
    assert candidates[0].quality.risk == "low"


def test_sam_visual_overlay_validation_and_asset_record(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    context = build_context(tmp_path, image, dsl, png, make_sam_settings())
    candidates = []
    blocked = []
    append_mask_candidate(
        context=context,
        candidates=candidates,
        blocked=blocked,
        bbox=[120, 392, 32, 32],
        mask_area=900,
        raw_confidence=0.9,
        raw_reasons=[],
    )

    from app.sam_visual_candidate import SamVisualCandidateDocument, SamVisualRuntime, build_meta, build_overlay, sam_visual_overlay_asset_records

    overlay = build_overlay(context, candidates, blocked)
    assert overlay is not None
    assert Path(overlay.assetPath).exists()
    assert read_png_metadata(Path(overlay.assetPath).read_bytes()) == image

    document = SamVisualCandidateDocument(
        version="0.1",
        taskId="task_overlay",
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        sam=SamVisualRuntime("configs/sam2.1/sam2.1_hiera_t.yaml", "cpu", "configured", 10, 1, 1280),
        candidates=candidates,
        blockedCandidates=blocked,
        overlay=overlay,
        warnings=[],
        meta=build_meta(candidates, blocked, 1),
    )
    assert validate_sam_visual_candidate_document(document, image) == []
    records = sam_visual_overlay_asset_records(document, "task_overlay", "2026-05-18T00:00:00+00:00")
    assert records[0]["role"] == "asset_sam_visual_candidate_overlay"


def test_sam_visual_builder_skips_when_dependency_missing_after_checkpoint(monkeypatch, tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    checkpoint = tmp_path / "sam.pt"
    checkpoint.write_bytes(b"placeholder")

    import app.sam_visual_candidate as module

    original_import = module.importlib.import_module

    def fake_import(name: str):
        if name == "torch":
            raise ImportError("missing torch")
        return original_import(name)

    monkeypatch.setattr(module.importlib, "import_module", fake_import)
    document = build_sam_visual_candidate_document(
        task_id="task_missing_dependency",
        image=image,
        png_data=png,
        dsl=dsl,
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_placement_document=None,
        icon_business_document=None,
        settings=make_sam_settings(sam_visual_candidate_checkpoint=str(checkpoint)),
        storage=SamVisualStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "skipped"
    assert document.error["code"] == "SAM_VISUAL_PROVIDER_UNAVAILABLE"
    assert document.warnings[0].code == "dependency_missing"


def test_sam2_runtime_is_cached_for_same_checkpoint_config_and_device(monkeypatch, tmp_path) -> None:
    checkpoint = tmp_path / "sam2.1_hiera_tiny.pt"
    checkpoint.write_bytes(b"placeholder")
    settings = make_sam_settings(sam_visual_candidate_checkpoint=str(checkpoint), sam_visual_candidate_device="cpu")
    clear_sam2_runtime_cache()
    build_calls = []

    class FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return False

    class FakeMps:
        @staticmethod
        def is_available() -> bool:
            return False

    class FakeBackends:
        mps = FakeMps()

    class FakeTorch:
        cuda = FakeCuda()
        backends = FakeBackends()

    class FakeNumpy:
        uint8 = object()

    class FakeBuildModule:
        @staticmethod
        def build_sam2(config, checkpoint_path, *, device, apply_postprocessing):
            build_calls.append((config, checkpoint_path, device, apply_postprocessing))
            return object()

    class FakeMaskModule:
        class SAM2AutomaticMaskGenerator:
            def __init__(self, model, **params):
                self.model = model
                self.params = params

    def fake_import(name: str):
        modules = {
            "torch": FakeTorch,
            "numpy": FakeNumpy,
            "sam2.build_sam": FakeBuildModule,
            "sam2.automatic_mask_generator": FakeMaskModule,
        }
        return modules[name]

    import app.sam_visual_candidate as module

    monkeypatch.setattr(module.importlib, "import_module", fake_import)
    first, first_cached = get_sam2_runtime(settings)
    second, second_cached = get_sam2_runtime(settings)

    assert first is second
    assert first_cached is False
    assert second_cached is True
    assert len(build_calls) == 1
    assert first.device == "cpu"
    assert first.loadMs >= 0
    clear_sam2_runtime_cache()


def build_context(
    tmp_path,
    image: PngMetadata,
    dsl: dict[str, Any],
    png: bytes,
    settings,
    *,
    icon_document: IconCandidateDocument | None = None,
) -> SamVisualContext:
    elements = index_dsl_elements(dsl)
    return SamVisualContext(
        task_id="task_context",
        image=image,
        png_data=png,
        dsl=dsl,
        settings=settings,
        storage=SamVisualStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
        icon_candidate_document=icon_document,
        icon_gap_document=None,
        icon_placement_document=None,
        icon_business_document=None,
        pixels=decode_png_pixels(png),
        text_bboxes=unique_bboxes(bboxes_by_role(elements, {"visible_text_replacement"}) + bboxes_by_role(elements, {"candidate_text"})),
        cover_bboxes=unique_bboxes(bboxes_by_role(elements, {"text_replacement_cover"})),
        existing_icon_bboxes=collect_existing_icon_bboxes(
            icon_candidate_document=icon_document,
            icon_gap_document=None,
            icon_placement_document=None,
            icon_business_document=None,
            elements=elements,
        ),
        status_bar_bboxes=status_bar_zones(image),
        header_title_bboxes=header_title_zones(image),
        illustration_bboxes=illustration_zones(image),
        bed_map_bboxes=bed_map_zones(image),
    )


def make_sam_settings(**overrides: Any):
    values = {
        "sam_visual_candidate_enabled": True,
        "sam_visual_candidate_model_cfg": "",
        "sam_visual_candidate_checkpoint": "",
        "sam_visual_candidate_device": "auto",
        "sam_visual_candidate_max_image_edge": 960,
        "sam_visual_candidate_max_masks": 300,
        "sam_visual_candidate_points_per_side": 8,
        "sam_visual_candidate_points_per_batch": 64,
        "sam_visual_candidate_max_candidates": 120,
        "sam_visual_candidate_min_confidence": 0.72,
        "sam_visual_candidate_min_area": 64,
        "sam_visual_candidate_max_area_ratio": 0.12,
        "sam_visual_candidate_text_overlap_iou": 0.10,
        "sam_visual_candidate_existing_icon_iou": 0.50,
        "sam_visual_candidate_overlay_enabled": True,
    }
    values.update(overrides)
    return make_business_settings(**values)
