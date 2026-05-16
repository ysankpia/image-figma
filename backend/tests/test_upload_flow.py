from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import PNG_HEIGHT, PNG_WIDTH

HEADER_HEIGHT = 260
BOTTOM_HEIGHT = 220
CONTENT_HEIGHT = PNG_HEIGHT - HEADER_HEIGHT - BOTTOM_HEIGHT


def test_upload_png_creates_completed_task_and_dsl(client: TestClient, png_file: tuple[str, bytes, str]) -> None:
    upload = client.post("/api/upload", files={"file": png_file})

    assert upload.status_code == 200
    upload_body = upload.json()
    assert upload_body["success"] is True
    task_id = upload_body["data"]["taskId"]
    assert task_id.startswith("task_")
    assert upload_body["data"]["status"] == "completed"
    assert upload_body["data"]["stage"] == "completed"
    assert upload_body["data"]["progress"] == 100

    task = client.get(f"/api/tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["data"] == {
        "taskId": task_id,
        "status": "completed",
        "stage": "completed",
        "progress": 100,
        "message": "Deterministic DSL is ready.",
    }

    dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    dsl = dsl_response.json()["data"]["dsl"]
    assert dsl["version"] == "0.1"
    assert dsl["taskId"] == task_id
    assert dsl["page"]["name"] == "uploaded_png"
    assert dsl["page"]["width"] == PNG_WIDTH
    assert dsl["page"]["height"] == PNG_HEIGHT
    assert dsl["page"]["originalWidth"] == PNG_WIDTH
    assert dsl["page"]["originalHeight"] == PNG_HEIGHT
    assert dsl["page"]["scaleFactor"] == 1
    assert dsl["meta"]["source"] == "png"
    assert dsl["meta"]["platformHint"] == "mobile"
    assert dsl["meta"]["fallbackCount"] == 3
    assert dsl["meta"]["elementCount"] == 6
    assert dsl["meta"]["notes"] == "deterministic_region_dsl+m9_patch_debug"
    assert dsl["meta"]["qualityFlags"] == [
        "m9_hidden_text_candidates",
        "m15_text_primitive_binding",
        "m16_component_structure_harness",
        "m17_component_annotation",
        "m18_layer_separation_candidates",
        "m19_local_asset_slice_candidates",
    ]
    assert dsl["meta"]["textPrimitiveBindingCount"] == 0
    assert dsl["meta"]["textPrimitiveContainerCount"] == 3
    assert dsl["meta"]["textPrimitiveUnboundCount"] == 2
    assert dsl["meta"]["componentStructureCount"] == 0
    assert dsl["meta"]["componentStructureGroupCount"] == 0
    assert dsl["meta"]["componentStructureUnstructuredCount"] == 0
    assert dsl["meta"]["componentAnnotationCount"] == 0
    assert dsl["meta"]["componentAnnotatedElementCount"] == 0
    assert dsl["meta"]["componentUnannotatedElementCount"] == 2
    assert dsl["meta"]["componentGroupHintCount"] == 0
    assert dsl["meta"]["layerSeparationCandidateCount"] == 0
    assert dsl["meta"]["layerSeparationFillCandidateCount"] == 0
    assert dsl["meta"]["layerSeparationRepairRequiredCount"] == 0
    assert dsl["meta"]["layerSeparationEmbeddedTextCount"] == 0
    assert dsl["meta"]["layerSeparationBlockedCount"] == 0
    assert dsl["meta"]["assetSliceCandidateCount"] == 0
    assert dsl["meta"]["assetSliceFilledCandidateCount"] == 0
    assert dsl["meta"]["assetSliceBlockedCount"] == 0
    assert dsl["meta"]["assetSliceFailedCount"] == 0

    assets = {asset["assetId"]: asset for asset in dsl["assets"]}
    assert set(assets) == {
        "asset_original",
        "asset_region_header",
        "asset_region_content",
        "asset_region_bottom",
    }
    assert assets["asset_original"]["url"] == f"http://localhost:8000/files/uploads/{task_id}/original.png"
    assert assets["asset_region_header"]["url"] == f"http://localhost:8000/files/assets/{task_id}/header.png"
    assert assets["asset_region_content"]["url"] == f"http://localhost:8000/files/assets/{task_id}/content.png"
    assert assets["asset_region_bottom"]["url"] == f"http://localhost:8000/files/assets/{task_id}/bottom.png"
    assert assets["asset_original"]["width"] == PNG_WIDTH
    assert assets["asset_original"]["height"] == PNG_HEIGHT
    assert assets["asset_region_header"]["width"] == PNG_WIDTH
    assert assets["asset_region_header"]["height"] == HEADER_HEIGHT
    assert assets["asset_region_content"]["width"] == PNG_WIDTH
    assert assets["asset_region_content"]["height"] == CONTENT_HEIGHT
    assert assets["asset_region_bottom"]["width"] == PNG_WIDTH
    assert assets["asset_region_bottom"]["height"] == BOTTOM_HEIGHT

    assert dsl["root"]["type"] == "frame"
    assert dsl["root"]["name"] == "uploaded_png"
    assert dsl["root"]["layout"]["width"] == PNG_WIDTH
    assert dsl["root"]["layout"]["height"] == PNG_HEIGHT
    children = {child["id"]: child for child in dsl["root"]["children"]}
    assert set(children) == {
        "original_ref",
        "fallback_region_header",
        "fallback_region_content",
        "fallback_region_bottom",
        "text_ocr_text_001",
        "text_ocr_text_002",
    }
    assert not {"title", "search_card", "search_icon", "divider"}.intersection(children)
    assert children["original_ref"]["source"]["assetId"] == "asset_original"
    assert children["original_ref"]["style"]["visible"] is False
    assert children["original_ref"]["layout"] == {
        "x": 0,
        "y": 0,
        "width": PNG_WIDTH,
        "height": PNG_HEIGHT,
    }
    assert children["fallback_region_header"]["layout"] == {
        "x": 0,
        "y": 0,
        "width": PNG_WIDTH,
        "height": HEADER_HEIGHT,
    }
    assert children["fallback_region_content"]["layout"] == {
        "x": 0,
        "y": HEADER_HEIGHT,
        "width": PNG_WIDTH,
        "height": CONTENT_HEIGHT,
    }
    assert children["fallback_region_bottom"]["layout"] == {
        "x": 0,
        "y": HEADER_HEIGHT + CONTENT_HEIGHT,
        "width": PNG_WIDTH,
        "height": BOTTOM_HEIGHT,
    }

    for region_name in ("header", "content", "bottom"):
        child = children[f"fallback_region_{region_name}"]
        assert child["source"]["assetId"] == f"asset_region_{region_name}"
        assert child["meta"]["fallback"] is True
        assert child["meta"]["reason"] == "m7_deterministic_region"
        assert child["meta"]["annotationRole"] == "fallback_context"
        assert child["meta"]["annotationSource"] == "m17_component_annotation"
        assert child["meta"]["confidence"] == 1
        assert child["meta"]["sourceBBox"] == [
            child["layout"]["x"],
            child["layout"]["y"],
            child["layout"]["width"],
            child["layout"]["height"],
        ]

    for text_id in ("text_ocr_text_001", "text_ocr_text_002"):
        child = children[text_id]
        assert child["type"] == "text"
        assert child["role"] == "candidate_text"
        assert child["style"]["visible"] is False
        assert child["meta"]["candidate"] is True
        assert child["meta"]["source"] == "ocr"

    original_file = client.get(f"/files/uploads/{task_id}/original.png")
    assert original_file.status_code == 200
    assert original_file.content.startswith(b"\x89PNG\r\n\x1a\n")

    for region_name in ("header", "content", "bottom"):
        region_file = client.get(f"/files/assets/{task_id}/{region_name}.png")
        assert region_file.status_code == 200
        assert region_file.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_upload_falls_back_to_full_image_when_crop_format_is_unsupported(
    client: TestClient,
    png_file: tuple[str, bytes, str],
) -> None:
    filename, png_bytes, mime_type = png_file
    unsupported_png = bytearray(png_bytes)
    unsupported_png[25] = 3

    upload = client.post("/api/upload", files={"file": (filename, bytes(unsupported_png), mime_type)})
    assert upload.status_code == 200
    task_id = upload.json()["data"]["taskId"]

    dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    dsl = dsl_response.json()["data"]["dsl"]

    assert dsl["meta"]["fallbackCount"] == 1
    assert dsl["meta"]["elementCount"] == 4
    assert dsl["meta"]["notes"] == "deterministic_fallback_dsl+m9_patch_debug"
    assert dsl["meta"]["qualityFlags"] == ["region_crop_unsupported", "m9_hidden_text_candidates"]

    assets = {asset["assetId"]: asset for asset in dsl["assets"]}
    assert set(assets) == {"asset_original", "asset_banner"}

    children = {child["id"]: child for child in dsl["root"]["children"]}
    assert set(children) == {"original_ref", "fallback_full_image", "text_ocr_text_001", "text_ocr_text_002"}
    assert children["fallback_full_image"]["source"]["assetId"] == "asset_banner"
    assert children["fallback_full_image"]["meta"] == {
        "fallback": True,
        "reason": "m6_deterministic_full_image",
        "confidence": 1,
    }


def test_upload_rejects_non_png(client: TestClient) -> None:
    response = client.post("/api/upload", files={"file": ("input.txt", b"not png", "text/plain")})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_FILE_TYPE"
    assert body["error"]["stage"] == "upload"


def test_upload_rejects_png_without_dimensions(client: TestClient) -> None:
    response = client.post("/api/upload", files={"file": ("broken.png", b"\x89PNG\r\n\x1a\n", "image/png")})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_IMAGE_DIMENSIONS"
    assert body["error"]["stage"] == "upload"


def test_upload_rejects_large_png(client: TestClient) -> None:
    response = client.post(
        "/api/upload",
        files={"file": ("large.png", b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024), "image/png")},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FILE_TOO_LARGE"


def test_missing_task_returns_task_not_found(client: TestClient) -> None:
    response = client.get("/api/tasks/task_missing")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TASK_NOT_FOUND"
    assert body["error"]["taskId"] == "task_missing"


def test_figma_origin_cors_preflight_is_allowed(client: TestClient) -> None:
    response = client.options(
        "/api/upload",
        headers={
            "Origin": "https://www.figma.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_cors_allow_origins_can_be_restricted(tmp_path, monkeypatch) -> None:
    import importlib
    import sys

    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://www.figma.com,http://localhost:8000")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    with TestClient(main.create_app()) as restricted_client:
        response = restricted_client.options(
            "/api/upload",
            headers={
                "Origin": "https://www.figma.com",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://www.figma.com"
