from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.png_tools import PngMetadata
from app.visual_primitives import (
    PrimitiveRegionInput,
    VisualPrimitive,
    VisualPrimitiveDocument,
    VisualPrimitiveRelation,
    normalize_primitive_bbox,
    extract_openai_visual_primitives,
    normalized_box_to_pixel_bbox,
    validate_primitive_document,
)
from app.config import Settings
from conftest import PNG_HEIGHT, PNG_WIDTH


def test_upload_creates_fake_visual_primitives_without_api_key(
    client: TestClient,
    png_file: tuple[str, bytes, str],
    tmp_path,
) -> None:
    upload = client.post("/api/upload", files={"file": png_file})
    assert upload.status_code == 200
    task_id = upload.json()["data"]["taskId"]

    response = client.get(f"/api/tasks/{task_id}/primitives")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["taskId"] == task_id
    assert data["status"] == "completed"
    assert data["provider"] == "fake"
    assert data["model"] is None
    assert data["relations"] == []
    assert data["warnings"] == []

    primitives = {primitive["id"]: primitive for primitive in data["primitives"]}
    assert set(primitives) == {
        "vp_region_header",
        "vp_region_content",
        "vp_region_bottom",
    }
    assert primitives["vp_region_header"]["bbox"] == [0, 0, PNG_WIDTH, 260]
    assert primitives["vp_region_content"]["bbox"] == [0, 260, PNG_WIDTH, PNG_HEIGHT - 260 - 220]
    assert primitives["vp_region_bottom"]["bbox"] == [0, PNG_HEIGHT - 220, PNG_WIDTH, 220]
    assert all(primitive["source"] == "fake" for primitive in primitives.values())

    primitive_file = Path(tmp_path / "storage" / "primitives" / f"{task_id}.json")
    assert primitive_file.exists()

    dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
    assert dsl_response.status_code == 200
    child_ids = {child["id"] for child in dsl_response.json()["data"]["dsl"]["root"]["children"]}
    assert "vp_region_header" not in child_ids
    assert child_ids == {
        "original_ref",
        "fallback_region_header",
        "fallback_region_content",
        "fallback_region_bottom",
    }


def test_missing_task_primitives_returns_task_not_found(client: TestClient) -> None:
    response = client.get("/api/tasks/task_missing/primitives")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TASK_NOT_FOUND"


def test_existing_task_without_primitives_returns_primitive_not_found(client: TestClient) -> None:
    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_primitives",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No primitives.",
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

    response = client.get("/api/tasks/task_without_primitives/primitives")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PRIMITIVE_NOT_FOUND"
    assert body["error"]["stage"] == "primitive_lookup"


def test_normalized_box_to_pixel_bbox_converts_region_local_coordinates_and_clamps() -> None:
    image = PngMetadata(941, 1672, 8, 2, 0, 0, 0)
    region = PrimitiveRegionInput("content", "/tmp/content.png", 0, 234, 941, 1237)

    bbox, warnings = normalized_box_to_pixel_bbox([-10, 100, 500, 1010], region, image)

    assert bbox == [0, 358, 471, 1113]
    assert [warning.code for warning in warnings] == ["BOX_CLAMPED"]


def test_invalid_normalized_box_is_dropped() -> None:
    image = PngMetadata(941, 1672, 8, 2, 0, 0, 0)
    region = PrimitiveRegionInput("content", "/tmp/content.png", 0, 234, 941, 1237)

    bbox, warnings = normalized_box_to_pixel_bbox([500, 500, 100, 900], region, image)

    assert bbox is None
    assert warnings[0].code == "INVALID_NORMALIZED_BOX"


def test_validate_primitive_document_drops_duplicate_ids_and_invalid_relations() -> None:
    document = VisualPrimitiveDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 100, "height": 100},
        coordinateSpace="pixel",
        primitives=[
            VisualPrimitive("vp_1", "card", "Card", [0, 0, 10, 10], 2),
            VisualPrimitive("vp_1", "card", "Duplicate", [0, 0, 10, 10], 1),
        ],
        relations=[
            VisualPrimitiveRelation("contains", "vp_1", "vp_missing", 1),
        ],
        warnings=[],
        meta={},
    )

    validated = validate_primitive_document(document)

    assert len(validated.primitives) == 1
    assert validated.primitives[0].confidence == 1
    assert validated.relations == []
    assert [warning.code for warning in validated.warnings] == [
        "DUPLICATE_PRIMITIVE_ID",
        "INVALID_RELATION_REF",
    ]


def test_normalize_primitive_bbox_clamps_light_overflow() -> None:
    bbox, warnings = normalize_primitive_bbox(
        primitive_id="vp_1",
        bbox=[-3, 5, 110, 90],
        image_width=100,
        image_height=100,
    )

    assert bbox == [0, 5, 100, 90]
    assert [warning.code for warning in warnings] == ["PRIMITIVE_BBOX_CLAMPED"]


def test_normalize_primitive_bbox_drops_out_of_bounds_box() -> None:
    bbox, warnings = normalize_primitive_bbox(
        primitive_id="vp_1",
        bbox=[120, 5, 30, 30],
        image_width=100,
        image_height=100,
    )

    assert bbox is None
    assert warnings[0].code == "PRIMITIVE_BBOX_OUT_OF_BOUNDS"


def test_openai_provider_without_key_does_not_break_upload(monkeypatch, tmp_path) -> None:
    import importlib
    import sys

    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("VISUAL_PRIMITIVE_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    from conftest import PNG_BYTES

    with TestClient(main.create_app()) as client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        primitive_response = client.get(f"/api/tasks/{task_id}/primitives")
        assert primitive_response.status_code == 200
        data = primitive_response.json()["data"]
        assert data["status"] == "failed"
        assert data["provider"] == "openai"
        assert data["error"]["code"] == "OPENAI_API_KEY_MISSING"

        dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl_response.status_code == 200


def test_openai_provider_region_failure_returns_failed_document(monkeypatch, tmp_path) -> None:
    import app.visual_primitives as visual_primitives

    class FakeOpenAI:
        def __init__(self, **_kwargs) -> None:
            pass

    def raise_region_error(*_args, **_kwargs):
        raise ValueError("bad json")

    monkeypatch.setattr(visual_primitives, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(visual_primitives, "call_openai_region_extractor", raise_region_error)
    region_path = tmp_path / "region.png"
    region_path.write_bytes(b"not used")
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    settings = Settings(
        version="0.1.0",
        storage_root=tmp_path,
        database_path=tmp_path / "app.db",
        public_base_url="http://localhost:8000",
        max_upload_bytes=10,
        cors_allow_origins=["*"],
        visual_primitive_provider="openai",
        openai_api_key="test-key",
        openai_vision_model="gpt-test",
        openai_timeout_seconds=1,
    )

    document = extract_openai_visual_primitives(
        task_id="task_1",
        image=image,
        region_inputs=[PrimitiveRegionInput("header", str(region_path), 0, 0, 100, 100)],
        settings=settings,
    )

    assert document.status == "failed"
    assert document.error == {
        "code": "PRIMITIVE_EXTRACTION_FAILED",
        "message": "OpenAI visual primitive extraction failed for all regions.",
    }
    assert document.primitives == []
    assert document.warnings[0].code == "OPENAI_REGION_EXTRACTION_FAILED"


def test_openai_provider_normalizes_region_payload(monkeypatch, tmp_path) -> None:
    import app.visual_primitives as visual_primitives

    class FakeOpenAI:
        def __init__(self, **_kwargs) -> None:
            pass

    def fake_region_payload(*_args, **_kwargs):
        return {
            "primitives": [
                {
                    "id": "card_1",
                    "kind": "card",
                    "label": "Activity card",
                    "box": [0, 0, 999, 500],
                    "confidence": 0.72,
                }
            ]
        }

    monkeypatch.setattr(visual_primitives, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(visual_primitives, "call_openai_region_extractor", fake_region_payload)
    region_path = tmp_path / "content.png"
    region_path.write_bytes(b"not used")
    image = PngMetadata(941, 1672, 8, 2, 0, 0, 0)
    settings = Settings(
        version="0.1.0",
        storage_root=tmp_path,
        database_path=tmp_path / "app.db",
        public_base_url="http://localhost:8000",
        max_upload_bytes=10,
        cors_allow_origins=["*"],
        visual_primitive_provider="openai",
        openai_api_key="test-key",
        openai_vision_model="gpt-test",
        openai_timeout_seconds=1,
    )

    document = visual_primitives.extract_openai_visual_primitives(
        task_id="task_1",
        image=image,
        region_inputs=[PrimitiveRegionInput("content", str(region_path), 0, 234, 941, 1237)],
        settings=settings,
    )

    assert document.status == "completed"
    assert document.provider == "openai"
    assert document.model == "gpt-test"
    assert len(document.primitives) == 1
    primitive = document.primitives[0]
    assert primitive.id == "vp_content_card_1"
    assert primitive.kind == "card"
    assert primitive.bbox == [0, 234, 941, 619]
    assert primitive.confidence == 0.72
