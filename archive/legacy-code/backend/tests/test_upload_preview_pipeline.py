from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png


def test_upload_preview_completes_and_serves_m29_plan_driven_dsl(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload-preview", files={"file": png_file})

    assert upload.status_code == 200
    body = upload.json()
    assert body["success"] is True
    task_id = body["data"]["taskId"]
    assert body["data"]["status"] in {"processing", "completed"}
    assert body["data"]["stage"] in {"m29_queued", "m29_completed"}

    task = client.get(f"/api/tasks/{task_id}")
    assert task.status_code == 200
    task_data = task.json()["data"]
    assert task_data["status"] == "completed"
    assert task_data["stage"] == "m29_completed"

    dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    dsl = dsl_response.json()["data"]["dsl"]
    assert "m29_plan_driven_materialization" in dsl["meta"]["qualityFlags"]
    assert dsl["meta"]["m29PlanDrivenMaterialization"] is True
    assert has_role(dsl, "fallback_region")
    assert has_role(dsl, "m29_text")
    removed_text_role = "m" + "30_text_member"
    removed_visual_role = "m" + "30_visual_asset"
    assert not has_role(dsl, removed_text_role)
    assert not has_role(dsl, removed_visual_role)
    assert not has_role(dsl, "m29_direct_text")

    for asset in dsl["assets"]:
        if asset.get("role") in {"fallback_region", "m29_image", "m29_symbol"}:
            assert str(asset["url"]).startswith(f"http://localhost:8000/files/assets/{task_id}/m29/")
            file_response = client.get(str(asset["url"]).replace("http://localhost:8000", ""))
            assert file_response.status_code == 200
            assert file_response.content.startswith(b"\x89PNG\r\n\x1a\n")

    report = client.get(f"/api/tasks/{task_id}/materialization")
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["summary"]["visibleNodeCount"] >= 1
    assert report_data["summary"]["m295ReplayPlan"]["plannedVisibleNodeCount"] >= 1
    assert report_data["summary"]["copiedImageAssetTextErasedCount"] >= 0
    assert report_data["stageTimings"]["schemaName"] == "UploadPreviewStageTimings"
    stages = {item["stage"] for item in report_data["stageTimings"]["stages"]}
    assert stages >= {
        "ocr",
        "m29",
        "m29_2_source_ui_physical_graph",
        "m29_3_relation_graph_report",
        "m29_4_stable_design_cluster",
        "m29_5_replay_plan",
        "m29_ownership_conservation",
        "m29_media_internal_decomposition",
        "m29_transparent_assets",
        "m29_evidence_contract",
        "m29_internal_source_promotion",
        "m29_3_relation_graph_report_promoted",
        "m29_4_stable_design_cluster_promoted",
        "m29_5_replay_plan_promoted",
        "m29_ownership_conservation_promoted",
        "m29_hierarchy_candidates",
        "m29_sibling_groups",
        "m29_layout_energy",
        "m29_auto_layout_permission",
        "m29_materialization",
        "m29_bridge_fate_trace",
        "m29_design_tokens",
        "m29_b_stage_quality",
        "m29_asset_publish",
        "m29_dsl_visual_comparison",
    }
    assert "m29_direct_replay" not in stages
    removed_materialization_stage = "m" + "30_materialization"
    assert removed_materialization_stage not in stages

    assert client.get(f"/api/tasks/{task_id}/m29-direct-dsl").status_code == 404
    removed_materialization_endpoint = "m" + "30-materialization"
    assert client.get(f"/api/tasks/{task_id}/{removed_materialization_endpoint}").status_code == 404


def test_upload_preview_uses_production_artifact_profile_by_default(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload-preview", files={"file": png_file})
    assert upload.status_code == 200
    task_id = upload.json()["data"]["taskId"]

    report = client.get(f"/api/tasks/{task_id}/materialization").json()["data"]
    stages = report["stageTimings"]["stages"]
    assert all(stage["status"] == "completed" for stage in stages)
    assert all(isinstance(stage["elapsedSeconds"], float) for stage in stages)

    task_root = Path(report["outputDsl"]).parent.parent
    assert (task_root / "stage_timings.json").exists()
    assert not (task_root / "m29_direct").exists()
    removed_materializer_dir = "m" + "30"
    assert not (task_root / removed_materializer_dir).exists()
    assert not (task_root / "m29_0_2").exists()
    assert not (task_root / "m29_0_3").exists()
    assert not (task_root / "m29_0_4").exists()
    assert not (task_root / "m29_0_5").exists()
    assert not (task_root / "m29_0_7").exists()
    assert not list(task_root.glob("**/overlays"))
    assert not list(task_root.glob("**/preview*.png"))
    assert (task_root / "ocr" / "ocr.json").exists()
    assert (task_root / "m29" / "nodes.json").exists()
    assert (task_root / "m29_2" / "source_ui_physical_graph.json").exists()
    assert (task_root / "m29_2" / "source_ui_physical_graph_overlay.png").exists()
    assert (task_root / "m29_3" / "region_relation_graph_report.json").exists()
    assert (task_root / "m29_4" / "stable_design_cluster_report.json").exists()
    assert (task_root / "m29_5" / "replay_plan.json").exists()
    assert (task_root / "m29_ownership_conservation" / "ownership_conservation_report.json").exists()
    assert (task_root / "m29_media_internal_decomposition" / "media_internal_decomposition_report.json").exists()
    assert (task_root / "m29_transparent_assets" / "transparent_asset_report.json").exists()
    assert (task_root / "m29_evidence_contract" / "evidence_contract_report.json").exists()
    assert (task_root / "m29_internal_source_promotion" / "internal_source_promotion_report.json").exists()
    assert (task_root / "m29_internal_source_promotion" / "source_ui_physical_graph.promoted.json").exists()
    assert (task_root / "m29_bridge_fate_trace" / "bridge_fate_trace_report.json").exists()
    assert (task_root / "m29_hierarchy_candidates" / "hierarchy_candidate_report.json").exists()
    assert (task_root / "m29_sibling_groups" / "sibling_group_candidate_report.json").exists()
    assert (task_root / "m29_layout_energy" / "layout_energy_report.json").exists()
    assert (task_root / "m29_auto_layout_permission" / "auto_layout_permission_report.json").exists()
    assert (task_root / "materialized_design" / "design.dsl.json").exists()
    assert (task_root / "materialized_design" / "materialization_report.json").exists()
    assert (task_root / "m29_design_tokens" / "design_token_report.json").exists()
    assert (task_root / "m29_b_stage_quality" / "b_stage_quality_report.json").exists()
    assert (task_root / "m29_dsl_visual_comparison" / "dsl_visual_comparison_report.json").exists()
    assert (task_root / "m29_dsl_visual_comparison" / "dsl_render.png").exists()
    assert (task_root / "m29_dsl_visual_comparison" / "source_diff.png").exists()
    assert (task_root / "m29_dsl_visual_comparison" / "source_gate_diff.png").exists()
    visual_report = json.loads((task_root / "m29_dsl_visual_comparison" / "dsl_visual_comparison_report.json").read_text(encoding="utf-8"))
    visual_summary = visual_report["summary"]
    assert visual_summary["textExclusionSource"] == "dsl_visible_text_plus_source_ocr_text"
    assert visual_summary["sourceTextBboxCount"] > 0


def test_upload_preview_development_profile_keeps_m29_diagnostics(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("UPLOAD_PREVIEW_PROFILE", "development")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        report = local_client.get(f"/api/tasks/{task_id}/materialization").json()["data"]

    task_root = Path(report["outputDsl"]).parent.parent
    assert (task_root / "m29" / "overlays").exists()
    assert (task_root / "m29" / "preview_sheet.png").exists()
    removed_materializer_dir = "m" + "30"
    assert not (task_root / removed_materializer_dir).exists()
    assert not (task_root / "m29_direct").exists()


def test_m29_materialization_failure_blocks_mainline_output(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    stages = importlib.import_module("app.upload_preview.stages")
    monkeypatch.setattr(stages, "build_plan_driven_dsl", fail_m29_materialization)
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        task = local_client.get(f"/api/tasks/{task_id}")
        assert task.status_code == 200
        data = task.json()["data"]
        assert data["status"] == "failed"
        assert data["stage"] == "m29_materialization"

        dsl = local_client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl.status_code == 409


def test_upload_preview_rejects_non_png(client: TestClient) -> None:
    response = client.post("/api/upload-preview", files={"file": ("input.txt", b"not png", "text/plain")})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_FILE_TYPE"
    assert body["error"]["stage"] == "upload_preview"


def test_upload_preview_records_ocr_failure(tmp_path: Path, monkeypatch) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("OCR_PROVIDER", "baidu_ppocrv5")
    monkeypatch.delenv("BAIDU_PADDLE_OCR_TOKEN", raising=False)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        response = local_client.post(
            "/api/upload-preview",
            files={"file": ("input.png", make_png(80, 80), "image/png")},
        )
        assert response.status_code == 200
        task_id = response.json()["data"]["taskId"]

        task = local_client.get(f"/api/tasks/{task_id}")
        assert task.status_code == 200
        data = task.json()["data"]
        assert data["status"] == "failed"
        assert data["stage"] == "ocr"
        assert "BAIDU_PADDLE_OCR_TOKEN" in data["message"]

        dsl = local_client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl.status_code == 409


def test_upload_preview_samples_dark_source_background(client: TestClient) -> None:
    png = make_dark_ui_png()
    upload = client.post("/api/upload-preview", files={"file": ("dark.png", png, "image/png")})
    assert upload.status_code == 200
    task_id = upload.json()["data"]["taskId"]

    dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
    assert dsl["page"]["background"]["value"] != "#F7F8FA"
    assert dsl["root"]["style"]["fill"] != "#F7F8FA"

    fallback_asset = next(asset for asset in dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_response = client.get(str(fallback_asset["url"]).replace("http://localhost:8000", ""))
    pixels = decode_png_pixels(fallback_response.content)
    assert max(pixels.rows[1][0:3]) < 80


def has_role(dsl: dict, role: str) -> bool:
    def visit(node: dict) -> bool:
        if node.get("role") == role:
            return True
        return any(visit(child) for child in node.get("children", []) if isinstance(child, dict))

    return visit(dsl["root"])


def make_png(width: int, height: int) -> bytes:
    canvas = PngPixels(width=width, height=height, rows=[bytes((240, 240, 240)) * width for _ in range(height)])
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)


def make_dark_ui_png() -> bytes:
    width, height = 160, 120
    rows = [bytearray(bytes((8, 14, 28)) * width) for _ in range(height)]
    for row in range(24, 92):
        for col in range(18, 142):
            value = (20 + ((row + col) % 40), 28 + (col % 30), 50 + (row % 45))
            rows[row][col * 3 : col * 3 + 3] = bytes(value)
    for row in range(42, 54):
        for col in range(34, 78):
            rows[row][col * 3 : col * 3 + 3] = b"\xe8\xe8\xe8"
    return encode_rgb_png(width, height, [bytes(row) for row in rows])


def fail_m29_materialization(**_kwargs):
    raise RuntimeError("forced m29 materialization failure")
