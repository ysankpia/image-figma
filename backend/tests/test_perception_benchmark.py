from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.icon_business_candidate import IconBusinessStorageAdapter, build_icon_business_candidate_document
from app.perception_benchmark import (
    PerceptionStorageAdapter,
    build_perception_benchmark_document,
    opencv_provider,
    sam2_provider,
)
from app.png_tools import PngMetadata, decode_png_pixels, read_png_metadata
from conftest import PNG_BYTES
from test_icon_business_candidate import business_probe_fixture, make_business_settings
from test_icon_gap_candidate import create_client_with_env


def test_perception_benchmark_disabled_by_default_has_no_result_and_keeps_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/perception-benchmark")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PERCEPTION_BENCHMARK_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m25_icon_business_candidates" in dsl["meta"]["qualityFlags"]
        assert "m26_visual_perception_provider_benchmark" not in dsl["meta"].get("qualityFlags", [])


def test_perception_benchmark_enabled_creates_report_overlay_and_does_not_modify_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "PERCEPTION_BENCHMARK_ENABLED": "true",
            "PERCEPTION_BENCHMARK_PROVIDERS": "current_rules,opencv,sam2,uied",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/perception-benchmark")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "visual_perception_provider_benchmark"
        providers = {provider["provider"]: provider for provider in document["providers"]}
        assert set(providers) == {"current_rules", "opencv", "sam2", "uied"}
        assert providers["current_rules"]["status"] == "completed"
        assert providers["current_rules"]["overlay"] is not None
        assert providers["opencv"]["status"] == "unavailable"
        assert providers["sam2"]["status"] == "unavailable"
        assert providers["uied"]["status"] == "unavailable"
        assert document["comparison"]["recommendedProvider"] in {"current_rules", "opencv_plus_rules"}

        overlay = client.get(providers["current_rules"]["overlay"]["assetUrl"].replace("http://localhost:8000", ""))
        assert overlay.status_code == 200
        assert read_png_metadata(overlay.content) is not None

        asset = client.get("/api/assets/asset_perception_overlay_rules")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_perception_overlay_rules"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m26_visual_perception_provider_benchmark" not in dsl["meta"].get("qualityFlags", [])
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_perception_benchmark_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/perception-benchmark")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_perception",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No perception benchmark.",
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
    not_found = client.get("/api/tasks/task_without_perception/perception-benchmark")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "PERCEPTION_BENCHMARK_NOT_FOUND"

    state.database.insert_perception_benchmark_result(
        {
            "task_id": "task_without_perception",
            "status": "completed",
            "benchmark_path": "/tmp/does-not-exist.json",
            "rules_overlay_asset_id": None,
            "opencv_overlay_asset_id": None,
            "sam2_overlay_asset_id": None,
            "uied_overlay_asset_id": None,
            "provider_count": 0,
            "candidate_count": 0,
            "blocked_count": 0,
            "recommended_provider": None,
            "elapsed_ms": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-18T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_perception/perception-benchmark")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "PERCEPTION_BENCHMARK_NOT_FOUND"


def test_current_rules_provider_converts_m25_candidates_to_unified_contract(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    business_document = build_icon_business_candidate_document(
        task_id="task_perception_rules",
        image=image,
        png_data=png,
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_placement_document=None,
        dsl=dsl,
        settings=make_perception_settings(),
        storage=IconBusinessStorageAdapter(tmp_path / "business_assets", "http://localhost:8000"),
    )

    document = build_perception_benchmark_document(
        task_id="task_perception_rules",
        image=image,
        png_data=png,
        dsl=dsl,
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_business_document=business_document,
        settings=make_perception_settings(perception_benchmark_providers=["current_rules"]),
        storage=PerceptionStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    assert len(document.providers) == 1
    provider = document.providers[0]
    assert provider.provider == "current_rules"
    assert provider.status == "completed"
    assert provider.candidateCount == business_document.meta["businessIconCount"]
    assert provider.overlay is not None
    assert Path(provider.overlay.assetPath).exists()
    assert provider.candidates[0].source == "m25_business_icon"
    assert "from_existing_m25_candidate" in provider.candidates[0].quality.reasons


def test_opencv_provider_unavailable_when_disabled_or_dependency_missing(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    context = build_context(tmp_path, image, dsl, png, make_perception_settings(perception_opencv_enabled=False))

    disabled = opencv_provider(context)

    assert disabled.status == "unavailable"
    assert disabled.error["code"] == "provider_unavailable"

    missing_context = build_context(
        tmp_path,
        image,
        dsl,
        png,
        make_perception_settings(perception_opencv_enabled=True, perception_opencv_import_name="definitely_missing_cv2"),
    )

    missing = opencv_provider(missing_context)

    assert missing.status == "unavailable"
    assert missing.error["code"] == "dependency_missing"


def test_sam2_provider_requires_checkpoint_and_dependency(tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    context = build_context(tmp_path, image, dsl, png, make_perception_settings(perception_sam2_enabled=True))

    result = sam2_provider(context)

    assert result.status == "unavailable"
    assert result.error["code"] == "model_missing"


def test_mock_uied_command_json_is_converted_to_candidates(monkeypatch, tmp_path) -> None:
    image, dsl, png = business_probe_fixture()
    script = tmp_path / "mock_uied.py"
    script.write_text(
        "import json,sys; sys.stdin.buffer.read(); print(json.dumps({'candidates':[{'bbox':[40,528,28,28],'kind':'icon_candidate','source':'uied_component','confidence':0.9}]}))",
        encoding="utf-8",
    )
    settings = make_perception_settings(
        perception_benchmark_providers=["uied"],
        perception_uied_enabled=True,
        perception_uied_command=f"python {script}",
    )

    document = build_perception_benchmark_document(
        task_id="task_uied",
        image=image,
        png_data=png,
        dsl=dsl,
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_business_document=None,
        settings=settings,
        storage=PerceptionStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    provider = document.providers[0]
    assert provider.provider == "uied"
    assert provider.status == "completed"
    assert provider.candidateCount == 1
    assert provider.candidates[0].bbox == [40, 528, 28, 28]


def build_context(tmp_path, image: PngMetadata, dsl: dict[str, Any], png: bytes, settings):
    from app.perception_benchmark import PerceptionContext, collect_existing_icon_bboxes, exclusion_zones
    from app.component_annotation import index_dsl_elements
    from app.icon_coverage import bboxes_by_role
    from app.icon_business_candidate import unique_bboxes

    elements = index_dsl_elements(dsl)
    return PerceptionContext(
        task_id="task_context",
        image=image,
        png_data=png,
        dsl=dsl,
        settings=settings,
        storage=PerceptionStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
        icon_candidate_document=None,
        icon_gap_document=None,
        icon_business_document=None,
        pixels=decode_png_pixels(png),
        text_bboxes=unique_bboxes(bboxes_by_role(elements, {"visible_text_replacement"}) + bboxes_by_role(elements, {"candidate_text"})),
        cover_bboxes=unique_bboxes(bboxes_by_role(elements, {"text_replacement_cover"})),
        existing_icon_bboxes=collect_existing_icon_bboxes(
            icon_candidate_document=None,
            icon_gap_document=None,
            icon_business_document=None,
            elements=elements,
        ),
        exclusion_bboxes=exclusion_zones(image),
    )


def make_perception_settings(**overrides: Any):
    values = {
        "perception_benchmark_enabled": True,
        "perception_benchmark_providers": ["current_rules", "opencv"],
        "perception_benchmark_max_candidates_per_provider": 300,
        "perception_benchmark_overlay_enabled": True,
        "perception_opencv_enabled": False,
        "perception_opencv_import_name": "cv2",
        "perception_sam2_enabled": False,
        "perception_sam2_model_cfg": "",
        "perception_sam2_checkpoint": "",
        "perception_sam2_device": "auto",
        "perception_sam2_max_image_edge": 1280,
        "perception_sam2_max_masks": 300,
        "perception_uied_enabled": False,
        "perception_uied_command": "",
    }
    values.update(overrides)
    return make_business_settings(**values)
