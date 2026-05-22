from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.png_tools import PngPixels, encode_rgb_png


def test_upload_m30_preview_completes_and_serves_m30_dsl(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload-m30-preview", files={"file": png_file})

    assert upload.status_code == 200
    body = upload.json()
    assert body["success"] is True
    task_id = body["data"]["taskId"]
    assert body["data"]["status"] in {"processing", "completed"}
    assert body["data"]["stage"] in {"m30_queued", "m30_completed"}

    task = client.get(f"/api/tasks/{task_id}")
    assert task.status_code == 200
    task_data = task.json()["data"]
    assert task_data["status"] == "completed"
    assert task_data["stage"] == "m30_completed"

    dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    dsl = dsl_response.json()["data"]["dsl"]
    assert "m30_evidence_grounded_materialization" in dsl["meta"]["qualityFlags"]
    assert has_role(dsl, "fallback_region")
    assert has_role(dsl, "m30_text_member")
    assert not has_role(dsl, "m30_text_cover")
    assert not any(child.get("type") == "icon" for child in dsl["root"]["children"])
    assert visible_audit_only_children(dsl) == 0

    for asset in dsl["assets"]:
        if asset.get("role") in {"fallback_region", "m30_visual_asset", "m30_composite_media_asset"}:
            assert str(asset["url"]).startswith(f"http://localhost:8000/files/assets/{task_id}/m30/")
            file_response = client.get(str(asset["url"]).replace("http://localhost:8000", ""))
            assert file_response.status_code == 200
            assert file_response.content.startswith(b"\x89PNG\r\n\x1a\n")

    report = client.get(f"/api/tasks/{task_id}/m30-materialization")
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["summary"]["fallbackPreserved"] is True
    assert report_data["summary"]["permissionViolationCount"] == 0
    assert report_data["summary"]["createdNewBBoxCount"] == 0
    assert "materializedAcceptedImageCount" in report_data["summary"]
    assert "materializedCompositeMediaCount" in report_data["summary"]
    assert "cleanedMaterializedImageAssetCount" in report_data["summary"]
    assert "erasedTextFromMaterializedImageAssetCount" in report_data["summary"]
    assert "skippedCompositeMediaCount" in report_data["summary"]
    assert "materializedTextCoverCount" in report_data["summary"]
    report_file = Path(report_data["outputDsl"]).with_name("m30_materialization_report.json")
    full_report = json.loads(report_file.read_text(encoding="utf-8"))
    assert full_report["options"]["accepted_image_materialization_enabled"] is True
    assert full_report["options"]["accepted_image_max_text_overlap"] == 0.02
    assert full_report["options"]["accepted_image_min_area"] == 20000
    assert full_report["options"]["image_asset_text_erasure_enabled"] is True
    assert full_report["options"]["composite_media_materialization_enabled"] is True
    assert full_report["options"]["composite_media_min_area"] == 50000
    assert report_data["debugPreviewPath"] is None
    assert report_data["stageTimings"]["schemaName"] == "M3011StageTimings"
    assert {item["stage"] for item in report_data["stageTimings"]["stages"]} >= {
        "ocr",
        "m29",
        "m31_reconstruction",
        "m29_0_5",
        "m30_materialization",
        "m39_boundary_classification",
        "m37_hierarchy_readiness",
        "m38_hierarchy_materialization",
        "m39_1_unit_structure_readiness_audit",
    }
    m39 = client.get(f"/api/tasks/{task_id}/m39-boundary-classification")
    assert m39.status_code == 200
    m39_data = m39.json()["data"]
    assert m39_data["summary"]["totalClassifiedNodeCount"] > 0
    assert "modelSkippedReason" in m39_data
    assert isinstance(m39_data["classifiedNodes"], list)
    assert str(m39_data["outputReport"]).endswith("m39_boundary_classification_report.json")
    m391 = client.get(f"/api/tasks/{task_id}/m39-1-unit-structure-readiness")
    assert m391.status_code == 200
    m391_data = m391.json()["data"]
    assert m391_data["summary"]["candidateUnitCount"] >= 0
    assert m391_data["summary"]["dslChanged"] is False
    assert m391_data["summary"]["createdVisibleNodeCount"] == 0
    assert m391_data["summary"]["assetChanged"] is False
    assert "modelSkippedReason" in m391_data
    assert isinstance(m391_data["candidateUnits"], list)
    assert isinstance(m391_data["promotionHints"], list)
    assert str(m391_data["outputReport"]).endswith("unit_structure_readiness_report.json")

    m31 = client.get(f"/api/tasks/{task_id}/m31-reconstruction")
    assert m31.status_code == 200
    m31_data = m31.json()["data"]
    assert m31_data["status"] == "completed"
    assert m31_data["stage"] == "m30_completed"
    assert m31_data["summary"]["createdDetectionBBoxCount"] == 0
    assert m31_data["summary"]["permissionViolationCount"] == 0
    assert m31_data["summary"]["rootLeafPrimitiveCount"] == 0
    assert m31_data["summary"]["unitFallbackCoverage"] == 1.0
    assert m31_data["summary"]["forbiddenHitCount"] == 0
    assert str(m31_data["outputTree"]).endswith("m31_reconstruction_tree.json")
    assert m31_data["debugOverlayPath"] is None
    assert {item["stage"] for item in m31_data["stageTimings"]["stages"]} >= {"m31_reconstruction"}


def test_upload_m30_preview_uses_production_artifact_profile_by_default(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload-m30-preview", files={"file": png_file})
    assert upload.status_code == 200
    task_id = upload.json()["data"]["taskId"]

    task = client.get(f"/api/tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["data"]["status"] == "completed"

    report = client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]
    stages = report["stageTimings"]["stages"]
    assert all(stage["status"] == "completed" for stage in stages)
    assert all(isinstance(stage["elapsedSeconds"], float) for stage in stages)

    task_root = Path(report["outputDsl"]).parent.parent
    assert (task_root / "stage_timings.json").exists()
    assert (task_root / "m31" / "m31_reconstruction_tree.json").exists()
    assert (task_root / "m31" / "m31_reconstruction_tree_report.json").exists()
    assert (task_root / "m31" / "m31_unit_fallback_assets").exists()
    assert (task_root / "m37" / "m37_hierarchy_readiness_report.json").exists()
    assert (task_root / "m39" / "m39_boundary_classification_report.json").exists()
    assert (task_root / "m39_1" / "unit_structure_readiness_report.json").exists()
    m37_report = json.loads((task_root / "m37" / "m37_hierarchy_readiness_report.json").read_text(encoding="utf-8"))
    assert m37_report["summary"]["createdVisibleFrameCount"] == 0
    assert m37_report["summary"]["dslChanged"] is False
    assert (task_root / "m38" / "hierarchy_materialization_report.json").exists()
    m38_report = json.loads((task_root / "m38" / "hierarchy_materialization_report.json").read_text(encoding="utf-8"))
    assert m38_report["summary"]["absolutePositionViolationCount"] == 0
    assert m38_report["summary"]["fallbackMovedCount"] == 0
    assert m38_report["summary"]["originalReferenceMovedCount"] == 0
    assert m38_report["summary"]["assetChanged"] is False
    m391_report = json.loads((task_root / "m39_1" / "unit_structure_readiness_report.json").read_text(encoding="utf-8"))
    assert m391_report["summary"]["dslChanged"] is False
    assert m391_report["summary"]["createdVisibleNodeCount"] == 0
    assert m391_report["summary"]["assetChanged"] is False
    final_dsl = json.loads((task_root / "m30" / "m30_materialized_dsl.json").read_text(encoding="utf-8"))
    assert all_m30_classifiable_nodes_have_boundary_classification(final_dsl)
    if m38_report["summary"]["dslChanged"]:
        assert has_role_recursive(final_dsl, "m38_container")
        assert (task_root / "m30" / "m30_materialized_dsl_flat.json").exists()
    assert not list(task_root.glob("**/overlays"))
    assert not list(task_root.glob("**/preview*.png"))
    assert not (task_root / "m30" / "m30_materialization_preview.png").exists()
    assert not (task_root / "m31" / "m31_reconstruction_tree_overlay.png").exists()
    assert (task_root / "ocr" / "ocr.json").exists()
    assert (task_root / "m29" / "nodes.json").exists()
    assert (task_root / "m29_0_5" / "refined_visual_objects.json").exists()
    assert (task_root / "m30" / "m30_materialized_dsl.json").exists()


def test_upload_m30_preview_development_profile_keeps_diagnostics(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M30_PREVIEW_PROFILE", "development")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        report = local_client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]

    task_root = Path(report["outputDsl"]).parent.parent
    assert (task_root / "m29" / "overlays").exists()
    assert (task_root / "m29" / "preview_sheet.png").exists()
    assert (task_root / "m30" / "m30_materialization_preview.png").exists()
    assert (task_root / "m31" / "m31_reconstruction_tree_overlay.png").exists()


def test_m31_upload_diagnostics_can_be_disabled(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M31_UPLOAD_DIAGNOSTICS_ENABLED", "false")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        report = local_client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]
        m31 = local_client.get(f"/api/tasks/{task_id}/m31-reconstruction")

    task_root = Path(report["outputDsl"]).parent.parent
    assert not (task_root / "m31").exists()
    assert not (task_root / "m37").exists()
    assert not (task_root / "m38").exists()
    assert not (task_root / "m39_1").exists()
    assert "m31_reconstruction" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert "m37_hierarchy_readiness" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert "m38_hierarchy_materialization" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert "m39_1_unit_structure_readiness_audit" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert m31.status_code == 404
    assert m31.json()["error"]["code"] == "M31_RECONSTRUCTION_NOT_FOUND"


def test_m31_optional_failure_does_not_block_m30_output(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    pipeline = importlib.import_module("app.m30_upload_pipeline")
    monkeypatch.setattr(pipeline, "extract_m31_reconstruction_ui_tree", fail_m31)
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        task = local_client.get(f"/api/tasks/{task_id}")
        assert task.status_code == 200
        assert task.json()["data"]["status"] == "completed"

        dsl = local_client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl.status_code == 200

        report = local_client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]
        m31 = local_client.get(f"/api/tasks/{task_id}/m31-reconstruction")

    m31_timing = next(item for item in report["stageTimings"]["stages"] if item["stage"] == "m31_reconstruction")
    assert m31_timing["status"] == "failed"
    assert m31_timing["errorCode"] == "RuntimeError"
    assert "m37_hierarchy_readiness" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert m31.status_code == 404
    assert m31.json()["error"]["code"] == "M31_RECONSTRUCTION_NOT_FOUND"


def test_m38_hierarchy_materialization_can_be_disabled(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M38_HIERARCHY_MATERIALIZATION_ENABLED", "false")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        report = local_client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]

    task_root = Path(report["outputDsl"]).parent.parent
    assert (task_root / "m37" / "m37_hierarchy_readiness_report.json").exists()
    assert not (task_root / "m38").exists()
    assert (task_root / "m39_1" / "unit_structure_readiness_report.json").exists()
    assert "m38_hierarchy_materialization" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert "m39_1_unit_structure_readiness_audit" in {item["stage"] for item in report["stageTimings"]["stages"]}


def test_m39_content_chrome_classification_can_be_disabled(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M39_CONTENT_CHROME_CLASSIFICATION_ENABLED", "false")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        report = local_client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]
        dsl = local_client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        m39 = local_client.get(f"/api/tasks/{task_id}/m39-boundary-classification")

    task_root = Path(report["outputDsl"]).parent.parent
    assert not (task_root / "m39").exists()
    assert "m39_boundary_classification" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert no_m30_classifiable_nodes_have_boundary_classification(dsl)
    assert m39.status_code == 404
    assert m39.json()["error"]["code"] == "M39_BOUNDARY_CLASSIFICATION_NOT_FOUND"


def test_m39_missing_model_keeps_upload_completed(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M39_ONNX_MODEL_PATH", str(tmp_path / "missing.onnx"))

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        task = local_client.get(f"/api/tasks/{task_id}").json()["data"]
        m39 = local_client.get(f"/api/tasks/{task_id}/m39-boundary-classification").json()["data"]

    assert task["status"] == "completed"
    assert m39["modelSkippedReason"] == "missing_model"
    assert m39["summary"]["onnxModelLoaded"] is False
    assert m39["summary"]["ruleOnlyClassificationCount"] == m39["summary"]["totalClassifiedNodeCount"]


def test_m39_1_unit_structure_readiness_can_be_disabled(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M39_1_UNIT_STRUCTURE_READINESS_ENABLED", "false")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        report = local_client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]
        m391 = local_client.get(f"/api/tasks/{task_id}/m39-1-unit-structure-readiness")

    task_root = Path(report["outputDsl"]).parent.parent
    assert not (task_root / "m39_1").exists()
    assert "m39_1_unit_structure_readiness_audit" not in {item["stage"] for item in report["stageTimings"]["stages"]}
    assert m391.status_code == 404
    assert m391.json()["error"]["code"] == "M39_1_UNIT_STRUCTURE_READINESS_NOT_FOUND"


def test_m39_1_missing_model_keeps_upload_completed(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M39_1_ONNX_MODEL_PATH", str(tmp_path / "missing.onnx"))

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        task = local_client.get(f"/api/tasks/{task_id}").json()["data"]
        m391 = local_client.get(f"/api/tasks/{task_id}/m39-1-unit-structure-readiness").json()["data"]

    assert task["status"] == "completed"
    assert m391["modelSkippedReason"] == "missing_model"
    assert m391["summary"]["onnxModelLoaded"] is False
    assert m391["summary"]["onnxCandidateCount"] == 0


def test_m38_optional_failure_does_not_block_m30_output(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    pipeline = importlib.import_module("app.m30_upload_pipeline")
    monkeypatch.setattr(pipeline, "materialize_m38_hierarchy", fail_m38)
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        task = local_client.get(f"/api/tasks/{task_id}")
        assert task.status_code == 200
        assert task.json()["data"]["status"] == "completed"

        report = local_client.get(f"/api/tasks/{task_id}/m30-materialization").json()["data"]

    m38_timing = next(item for item in report["stageTimings"]["stages"] if item["stage"] == "m38_hierarchy_materialization")
    assert m38_timing["status"] == "failed"
    assert m38_timing["errorCode"] == "RuntimeError"


def test_m38_strict_failure_marks_task_failed(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M38_HIERARCHY_MATERIALIZATION_STRICT", "true")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    pipeline = importlib.import_module("app.m30_upload_pipeline")
    monkeypatch.setattr(pipeline, "materialize_m38_hierarchy", fail_m38)
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        task = local_client.get(f"/api/tasks/{task_id}")
        assert task.status_code == 200
        data = task.json()["data"]
        assert data["status"] == "failed"
        assert data["stage"] == "m38_hierarchy_materialization"
        assert "forced m38 failure" in data["message"]

        dsl = local_client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl.status_code == 409


def test_m31_strict_failure_marks_task_failed(tmp_path: Path, monkeypatch, png_file: tuple[str, bytes, str]) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("M31_UPLOAD_DIAGNOSTICS_STRICT", "true")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    pipeline = importlib.import_module("app.m30_upload_pipeline")
    monkeypatch.setattr(pipeline, "extract_m31_reconstruction_ui_tree", fail_m31)
    with TestClient(main.create_app()) as local_client:
        upload = local_client.post("/api/upload-m30-preview", files={"file": png_file})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        task = local_client.get(f"/api/tasks/{task_id}")
        assert task.status_code == 200
        data = task.json()["data"]
        assert data["status"] == "failed"
        assert data["stage"] == "m31_reconstruction"
        assert "forced m31 failure" in data["message"]

        dsl = local_client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl.status_code == 409


def test_upload_m30_preview_rejects_non_png(client: TestClient) -> None:
    response = client.post("/api/upload-m30-preview", files={"file": ("input.txt", b"not png", "text/plain")})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_FILE_TYPE"
    assert body["error"]["stage"] == "upload_m30_preview"


def test_upload_m30_preview_records_ocr_failure(tmp_path: Path, monkeypatch) -> None:
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
            "/api/upload-m30-preview",
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


def has_role(dsl: dict, role: str) -> bool:
    return any(child.get("role") == role for child in dsl["root"]["children"] if isinstance(child, dict))


def has_role_recursive(dsl: dict, role: str) -> bool:
    def visit(node: Any) -> bool:
        if not isinstance(node, dict):
            return False
        if node.get("role") == role:
            return True
        return any(visit(child) for child in node.get("children", []) if isinstance(node.get("children"), list))

    return visit(dsl["root"])


def visible_audit_only_children(dsl: dict) -> int:
    count = 0
    for child in dsl["root"]["children"]:
        if not isinstance(child, dict):
            continue
        meta = child.get("meta") if isinstance(child.get("meta"), dict) else {}
        if meta.get("sourceKind") in {"m2913_audit", "m29032_review", "mixed_symbol_text_candidate"}:
            count += 1
    return count


def all_m30_classifiable_nodes_have_boundary_classification(dsl: dict) -> bool:
    found = False
    for node in walk_nodes(dsl.get("root")):
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        if meta.get("m30Materialized") is True and node.get("role") in {"m30_text_member", "m30_shape_candidate", "m30_visual_asset", "m30_composite_media_asset"}:
            found = True
            if meta.get("boundaryClassification") not in {"chrome", "content"}:
                return False
    return found


def no_m30_classifiable_nodes_have_boundary_classification(dsl: dict) -> bool:
    for node in walk_nodes(dsl.get("root")):
        meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
        if meta.get("m30Materialized") is True and node.get("role") in {"m30_text_member", "m30_shape_candidate", "m30_visual_asset", "m30_composite_media_asset"}:
            if "boundaryClassification" in meta:
                return False
    return True


def walk_nodes(node: Any) -> list[dict]:
    if not isinstance(node, dict):
        return []
    result = [node]
    for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
        result.extend(walk_nodes(child))
    return result


def make_png(width: int, height: int) -> bytes:
    canvas = PngPixels(width=width, height=height, rows=[bytes((240, 240, 240)) * width for _ in range(height)])
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)


def fail_m31(**_kwargs: Any) -> None:
    raise RuntimeError("forced m31 failure")


def fail_m38(**_kwargs: Any) -> None:
    raise RuntimeError("forced m38 failure")
