from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.dsl_patch import (
    apply_dsl_patch,
    build_dsl_patch,
    validate_enhanced_dsl,
)
from app.ocr import (
    OCRBlock,
    OCRDocument,
    normalize_ocr_bbox,
    validate_ocr_document,
)
from app.png_tools import PngMetadata
from app.visual_primitives import VisualPrimitive, VisualPrimitiveDocument
from conftest import PNG_HEIGHT, PNG_WIDTH


def test_upload_creates_ocr_patch_and_hidden_text_candidates(
    legacy_client: TestClient,
    png_file: tuple[str, bytes, str],
    tmp_path,
) -> None:
    upload = legacy_client.post("/api/upload", files={"file": png_file})
    assert upload.status_code == 200
    task_id = upload.json()["data"]["taskId"]

    ocr_response = legacy_client.get(f"/api/tasks/{task_id}/ocr")
    assert ocr_response.status_code == 200
    ocr_data = ocr_response.json()["data"]
    assert ocr_data["taskId"] == task_id
    assert ocr_data["status"] == "completed"
    assert ocr_data["provider"] == "fake"
    assert len(ocr_data["blocks"]) == 2

    patch_response = legacy_client.get(f"/api/tasks/{task_id}/dsl-patch")
    assert patch_response.status_code == 200
    patch_data = patch_response.json()["data"]
    assert patch_data["taskId"] == task_id
    assert patch_data["status"] == "completed"
    assert patch_data["mode"] == "debug"
    assert len(patch_data["patches"]) == 2

    ocr_file = Path(tmp_path / "storage" / "ocr" / f"{task_id}.json")
    patch_file = Path(tmp_path / "storage" / "patches" / f"{task_id}.json")
    assert ocr_file.exists()
    assert patch_file.exists()

    dsl_response = legacy_client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    dsl = dsl_response.json()["data"]["dsl"]
    children = {child["id"]: child for child in dsl["root"]["children"]}

    assert {
        "original_ref",
        "fallback_region_header",
        "fallback_region_content",
        "fallback_region_bottom",
    }.issubset(children)
    candidate_ids = {child_id for child_id, child in children.items() if child.get("role") == "candidate_text"}
    assert candidate_ids == {"text_ocr_text_001", "text_ocr_text_002"}
    for candidate_id in candidate_ids:
        candidate = children[candidate_id]
        assert candidate["type"] == "text"
        assert candidate["style"]["visible"] is False
        assert candidate["meta"]["candidate"] is True
        assert candidate["meta"]["source"] == "ocr"
        assert candidate["meta"]["nearestPrimitiveId"].startswith("vp_region_")
    assert dsl["meta"]["elementCount"] == 6
    assert dsl["meta"]["notes"] == "deterministic_region_dsl+m9_patch_debug"
    assert "m9_hidden_text_candidates" in dsl["meta"]["qualityFlags"]


def test_dsl_patch_mode_off_returns_base_dsl(monkeypatch, tmp_path) -> None:
    import importlib
    import sys

    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("LEGACY_PRE_M29_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("DSL_PATCH_MODE", "off")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    from conftest import PNG_BYTES

    with TestClient(main.create_app()) as client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        patch_response = client.get(f"/api/tasks/{task_id}/dsl-patch")
        assert patch_response.status_code == 200
        assert patch_response.json()["data"]["status"] == "skipped"
        assert patch_response.json()["data"]["mode"] == "off"

        dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl_response.status_code == 200
        dsl = dsl_response.json()["data"]["dsl"]
        child_ids = {child["id"] for child in dsl["root"]["children"]}
        assert child_ids == {
            "original_ref",
            "fallback_region_header",
            "fallback_region_content",
            "fallback_region_bottom",
        }
        assert dsl["meta"]["elementCount"] == 4
        assert dsl["meta"]["notes"] == "deterministic_region_dsl"


def test_missing_task_ocr_returns_task_not_found(legacy_client: TestClient) -> None:
    response = legacy_client.get("/api/tasks/task_missing/ocr")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_existing_task_without_ocr_returns_ocr_not_found(legacy_client: TestClient) -> None:
    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_ocr",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No OCR.",
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

    response = legacy_client.get("/api/tasks/task_without_ocr/ocr")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "OCR_NOT_FOUND"
    assert response.json()["error"]["stage"] == "ocr_lookup"


def test_existing_task_without_patch_returns_patch_not_found(legacy_client: TestClient) -> None:
    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_patch",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No patch.",
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

    response = legacy_client.get("/api/tasks/task_without_patch/dsl-patch")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DSL_PATCH_NOT_FOUND"
    assert response.json()["error"]["stage"] == "dsl_patch_lookup"


def test_validate_ocr_document_drops_empty_invalid_and_duplicate_blocks() -> None:
    document = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 100, "height": 100},
        coordinateSpace="pixel",
        blocks=[
            OCRBlock("ocr_1", "  Hello ", [0, 0, 20, 20], 2, "line_1", "block_1"),
            OCRBlock("ocr_1", "Duplicate", [0, 0, 20, 20], 1, "line_1", "block_1"),
            OCRBlock("ocr_empty", " ", [0, 0, 20, 20], 1, "line_2", "block_2"),
            OCRBlock("ocr_bad", "Bad", [120, 0, 20, 20], 1, "line_3", "block_3"),
        ],
        warnings=[],
    )

    validated = validate_ocr_document(document)

    assert [block.id for block in validated.blocks] == ["ocr_1"]
    assert validated.blocks[0].text == "Hello"
    assert validated.blocks[0].confidence == 1
    assert [warning.code for warning in validated.warnings] == [
        "DUPLICATE_OCR_BLOCK_ID",
        "OCR_TEXT_EMPTY",
        "OCR_BBOX_OUT_OF_BOUNDS",
    ]


def test_normalize_ocr_bbox_clamps_light_overflow() -> None:
    bbox, warnings = normalize_ocr_bbox(
        block_id="ocr_1",
        bbox=[-5, 10, 80, 20],
        image_width=60,
        image_height=100,
    )

    assert bbox == [0, 10, 60, 20]
    assert [warning.code for warning in warnings] == ["OCR_BBOX_CLAMPED"]


def test_patch_builder_applies_hidden_text_without_removing_fallbacks() -> None:
    base_dsl = {
        "version": "0.1",
        "taskId": "task_1",
        "page": {"width": PNG_WIDTH, "height": PNG_HEIGHT},
        "assets": [{"assetId": "asset_original", "type": "image", "url": "http://localhost/original.png"}],
        "root": {
            "id": "root",
            "type": "frame",
            "layout": {"x": 0, "y": 0, "width": PNG_WIDTH, "height": PNG_HEIGHT},
            "children": [
                {
                    "id": "original_ref",
                    "type": "image",
                    "layout": {"x": 0, "y": 0, "width": PNG_WIDTH, "height": PNG_HEIGHT},
                    "source": {"assetId": "asset_original"},
                }
            ],
        },
        "meta": {"notes": "deterministic_region_dsl", "elementCount": 1},
    }
    ocr_document = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": PNG_WIDTH, "height": PNG_HEIGHT},
        coordinateSpace="pixel",
        blocks=[OCRBlock("ocr_1", "Hello", [10, 20, 80, 24], 0.8, "line_1", "block_1")],
        warnings=[],
    )
    primitive_document = VisualPrimitiveDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": PNG_WIDTH, "height": PNG_HEIGHT},
        coordinateSpace="pixel",
        primitives=[
            VisualPrimitive("vp_region_header", "region", "Header", [0, 0, PNG_WIDTH, 260], 1, "header", "fake")
        ],
        relations=[],
        warnings=[],
    )

    patch = build_dsl_patch(
        base_dsl=base_dsl,
        ocr_document=ocr_document,
        primitive_document=primitive_document,
        mode="debug",
    )
    enhanced = apply_dsl_patch(base_dsl, patch)

    assert patch.status == "completed"
    assert len(patch.patches) == 1
    assert validate_enhanced_dsl(enhanced) == []
    children = {child["id"]: child for child in enhanced["root"]["children"]}
    assert set(children) == {"original_ref", "text_ocr_1"}
    assert children["text_ocr_1"]["style"]["visible"] is False
    assert children["text_ocr_1"]["meta"]["nearestPrimitiveId"] == "vp_region_header"
