from __future__ import annotations

import importlib
import sys
from copy import deepcopy
from typing import Any

from fastapi.testclient import TestClient

from app.component_annotation import (
    apply_component_annotations,
    build_component_annotation_document,
    build_failed_component_annotation_document,
)
from app.component_structure import build_component_structure_document
from app.dsl_factory import DslRegionAsset, build_deterministic_dsl
from app.dsl_patch import apply_dsl_patch, build_dsl_patch
from app.png_tools import PngMetadata
from app.text_replacement import apply_text_replacements
from conftest import PNG_BYTES
from test_component_structure import home_like_binding_document, make_component_settings
from test_text_binding import fake_primitive_document


def test_component_annotation_default_upload_creates_report_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/component-annotations")
        assert response.status_code == 200
        annotation = response.json()["data"]
        assert annotation["status"] == "completed"
        assert annotation["meta"]["notes"] == "dsl_component_annotation_harness"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m17_component_annotation" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["componentAnnotationCount"] == annotation["meta"]["annotationCount"]
        assert dsl["meta"]["componentAnnotatedElementCount"] == annotation["meta"]["annotatedElementCount"]
        assert dsl["meta"]["componentUnannotatedElementCount"] == annotation["meta"]["unannotatedElementCount"]
        assert dsl["meta"]["componentGroupHintCount"] == annotation["meta"]["groupHintCount"]


def test_component_annotation_disabled_has_no_result_and_keeps_m16_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "COMPONENT_ANNOTATION_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/component-annotations")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "COMPONENT_ANNOTATION_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m16_component_structure_harness" in dsl["meta"]["qualityFlags"]
        assert "m17_component_annotation" not in dsl["meta"]["qualityFlags"]
        assert "componentAnnotationCount" not in dsl["meta"]


def test_component_annotation_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/component-annotations")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_annotations",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No component annotations.",
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
    not_found = client.get("/api/tasks/task_without_annotations/component-annotations")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "COMPONENT_ANNOTATION_NOT_FOUND"

    state.database.insert_component_annotation_result(
        {
            "task_id": "task_without_annotations",
            "status": "completed",
            "annotation_path": "/tmp/does-not-exist.json",
            "annotation_count": 0,
            "group_hint_count": 0,
            "unannotated_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_annotations/component-annotations")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "COMPONENT_ANNOTATION_NOT_FOUND"


def test_home_like_component_annotation_links_dsl_elements_to_components() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    document = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_annotation_settings(),
    )

    assert document.status == "completed"
    by_element = {annotation.dslElementId: annotation for annotation in document.annotations}
    visible = by_element["visible_text_ocr_text_016"]
    cover = by_element["cover_ocr_text_016"]
    candidate = by_element["text_ocr_text_016"]
    assert visible.componentId == cover.componentId == candidate.componentId
    assert visible.componentRole == "primary_button"
    assert cover.componentRole == "primary_button"
    assert candidate.componentRole == "primary_button"
    assert visible.relationship == "button_label"
    assert visible.layerName == "Primary Button / Text / 开始选床"
    assert cover.layerName == "Primary Button / Cover"
    assert candidate.layerName == "Primary Button / Candidate Text / 开始选床"

    assert by_element["visible_text_ocr_text_004"].componentRole == "badge"
    assert by_element["visible_text_ocr_text_007"].componentRole == "status_badge"
    assert by_element["visible_text_ocr_text_032"].componentRole == "tip_card"
    assert by_element["visible_text_ocr_text_038"].componentRole == "bottom_nav_item"
    assert any(hint.role == "legend_group" and hint.status == "ready_for_future_grouping" for hint in document.groupHints)
    assert any(hint.role == "bottom_nav_group" and hint.status == "ready_for_future_grouping" for hint in document.groupHints)
    assert document.meta["roleSummary"]["primary_button"] == 3

    annotated_dsl = apply_component_annotations(dsl, document, layer_naming=True)
    elements = flatten_elements(annotated_dsl)
    assert elements["visible_text_ocr_text_016"]["name"] == "Primary Button / Text / 开始选床"
    assert elements["cover_ocr_text_016"]["name"] == "Primary Button / Cover"
    assert elements["text_ocr_text_016"]["name"] == "Primary Button / Candidate Text / 开始选床"
    assert elements["fallback_region_content"]["name"] == "Fallback / Content"
    assert elements["fallback_region_content"]["meta"]["annotationRole"] == "fallback_context"
    assert "componentId" not in elements["fallback_region_content"]["meta"]


def test_component_annotation_only_changes_name_and_meta() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    before = deepcopy(dsl)
    document = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_annotation_settings(),
    )
    after = apply_component_annotations(dsl, document, layer_naming=True)

    before_elements = flatten_elements(before)
    after_elements = flatten_elements(after)
    assert before_elements.keys() == after_elements.keys()
    for element_id, before_element in before_elements.items():
        after_element = after_elements[element_id]
        assert comparable_without_name_meta(after_element) == comparable_without_name_meta(before_element)


def test_component_annotation_failed_document_does_not_change_dsl_meta() -> None:
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    document = build_failed_component_annotation_document(
        task_id="task_failed",
        image=image,
        code="COMPONENT_ANNOTATION_VALIDATION_FAILED",
        message="Component annotation validation failed.",
    )
    dsl = {"meta": {"qualityFlags": ["m16_component_structure_harness"]}, "root": {"children": []}}

    next_dsl = apply_component_annotations(dsl, document, layer_naming=True)

    assert next_dsl == dsl


def home_like_annotation_inputs():
    image, ocr, replacement, binding = home_like_binding_document()
    primitive_document = fake_primitive_document("task_home", image)
    structure = build_component_structure_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        primitive_document=primitive_document,
        replacement_document=replacement,
        binding_document=binding,
        dsl={"root": {"children": []}},
        settings=make_annotation_settings(),
    )
    dsl = build_home_like_dsl(image, ocr, primitive_document, replacement)
    return image, ocr, replacement, binding, structure, dsl


def build_home_like_dsl(image, ocr, primitive_document, replacement):
    header_height = 234
    bottom_height = 201
    content_height = image.height - header_height - bottom_height
    regions = [
        DslRegionAsset("asset_region_header", "header", "http://localhost:8000/files/assets/task_home/header.png", 0, 0, image.width, header_height),
        DslRegionAsset(
            "asset_region_content",
            "content",
            "http://localhost:8000/files/assets/task_home/content.png",
            0,
            header_height,
            image.width,
            content_height,
        ),
        DslRegionAsset(
            "asset_region_bottom",
            "bottom",
            "http://localhost:8000/files/assets/task_home/bottom.png",
            0,
            header_height + content_height,
            image.width,
            bottom_height,
        ),
    ]
    base = build_deterministic_dsl(
        task_id="task_home",
        original_url="http://localhost:8000/files/uploads/task_home/original.png",
        fallback_url="http://localhost:8000/files/assets/task_home/banner.png",
        image=image,
        regions=regions,
        quality_flags=[],
    )
    patch = build_dsl_patch(
        base_dsl=base,
        ocr_document=ocr,
        primitive_document=primitive_document,
        mode="debug",
    )
    patched = apply_dsl_patch(base, patch)
    return apply_text_replacements(patched, replacement, ocr)


def flatten_elements(dsl: dict[str, Any]) -> dict[str, dict[str, Any]]:
    elements: dict[str, dict[str, Any]] = {}

    def visit(element: Any) -> None:
        if not isinstance(element, dict):
            return
        element_id = element.get("id")
        if isinstance(element_id, str):
            elements[element_id] = element
        children = element.get("children")
        if isinstance(children, list):
            for child in children:
                visit(child)

    visit(dsl["root"])
    return elements


def comparable_without_name_meta(element: dict[str, Any]) -> dict[str, Any]:
    comparable = {
        key: deepcopy(value)
        for key, value in element.items()
        if key not in {"name", "meta", "children"}
    }
    children = element.get("children")
    if isinstance(children, list):
        comparable["children"] = [comparable_without_name_meta(child) for child in children if isinstance(child, dict)]
    return comparable


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    return TestClient(main.create_app())


def make_annotation_settings(**overrides: Any):
    values = {
        "component_structure_enabled": True,
        "component_structure_min_confidence": 0.70,
        "component_annotation_enabled": True,
        "component_annotation_layer_naming": True,
        "component_annotation_min_confidence": 0.70,
    }
    values.update(overrides)
    return make_component_settings(**values)
