from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.icon_candidate import (
    IconCandidateStorageAdapter,
    apply_icon_candidate_metadata,
    build_failed_icon_candidate_document,
    build_icon_candidate_document,
)
from app.component_annotation import ComponentAnnotationDocument, ComponentAnnotationItem
from app.component_structure import ComponentStructureDocument, ComponentStructureItem
from app.png_tools import PngMetadata, decode_png_pixels, encode_rgb_png, read_png_metadata
from app.text_binding import TextPrimitiveBinding, TextPrimitiveBindingDocument
from conftest import PNG_BYTES
from test_asset_slice import home_like_slice_inputs, make_asset_settings
from test_component_annotation import flatten_elements
from test_component_structure import create_client_with_env as create_component_client


def test_icon_candidate_default_upload_creates_report_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-candidates")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["status"] == "completed"
        assert document["meta"]["notes"] == "icon_candidate_extraction_harness"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m20_icon_candidate_extraction" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["iconCandidateCount"] == document["meta"]["iconCount"]
        assert dsl["meta"]["iconCroppedAssetCount"] == document["meta"]["croppedIconCount"]
        assert dsl["meta"]["iconBlockedCount"] == document["meta"]["blockedCount"]
        assert dsl["meta"]["iconFailedCropCount"] == document["meta"]["failedCropCount"]
        assert {asset["assetId"] for asset in dsl["assets"]} == {
            "asset_original",
            "asset_region_header",
            "asset_region_content",
            "asset_region_bottom",
        }


def test_icon_candidate_disabled_has_no_result_and_keeps_m19_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "ICON_CANDIDATE_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/icon-candidates")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ICON_CANDIDATE_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m19_local_asset_slice_candidates" in dsl["meta"]["qualityFlags"]
        assert "m20_icon_candidate_extraction" not in dsl["meta"]["qualityFlags"]
        assert "iconCandidateCount" not in dsl["meta"]


def test_icon_candidate_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/icon-candidates")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_icon_candidates",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No icon candidates.",
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
    not_found = client.get("/api/tasks/task_without_icon_candidates/icon-candidates")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "ICON_CANDIDATE_NOT_FOUND"

    state.database.insert_icon_candidate_result(
        {
            "task_id": "task_without_icon_candidates",
            "status": "completed",
            "icon_path": "/tmp/does-not-exist.json",
            "icon_count": 0,
            "cropped_icon_count": 0,
            "blocked_count": 0,
            "failed_crop_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_icon_candidates/icon-candidates")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "ICON_CANDIDATE_NOT_FOUND"


def test_icon_candidate_rules_crop_supported_sources(tmp_path) -> None:
    image, _ocr, _replacement, binding, structure, annotation, separation, dsl, png = home_like_icon_inputs(
        [
            ([145, 842, 22, 18], (38, 132, 255)),
            ([145, 958, 22, 18], (38, 132, 255)),
            ([148, 1548, 22, 18], (38, 132, 255)),
            ([70, 1326, 16, 16], (38, 132, 255)),
        ]
    )

    document = build_icon_candidate_document(
        task_id="task_home",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=separation,
        asset_slice_document=None,
        dsl=dsl,
        settings=make_icon_settings(icon_candidate_min_confidence=0.70),
        storage=IconCandidateStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    candidates = [icon for icon in document.icons if icon.status == "candidate"]
    sources = {icon.source for icon in candidates}
    assert {"shortcut_card_leading_icon", "bottom_nav_label_above", "tip_title_leading_icon"} <= sources
    assert document.meta["iconCount"] == len(candidates)
    assert document.meta["croppedIconCount"] == len(candidates)
    assert document.meta["sourceSummary"] == summarize_sources(candidates)
    assert document.meta["roleSummary"] == summarize_roles(candidates)

    for icon in candidates:
        assert icon.assetPath is not None
        assert Path(icon.assetPath).exists()
        metadata = read_png_metadata(Path(icon.assetPath).read_bytes())
        assert metadata is not None
        assert [metadata.width, metadata.height] == icon.bbox[2:4]
        assert all(not overlaps_too_much(icon.bbox, element["layout"]) for element in text_and_cover_elements(dsl))


def test_icon_candidate_field_label_source_requires_paired_detail_rows(tmp_path) -> None:
    image, binding, structure, annotation, dsl, png = field_label_fixture()

    document = build_icon_candidate_document(
        task_id="task_field",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=None,
        asset_slice_document=None,
        dsl=dsl,
        settings=make_icon_settings(icon_candidate_max_component_area_ratio=0.60),
        storage=IconCandidateStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    candidates = [icon for icon in document.icons if icon.status == "candidate"]
    assert len(candidates) == 2
    assert {icon.source for icon in candidates} == {"field_label_leading_icon"}
    assert all(icon.componentRole == "preview_card" for icon in candidates)
    assert all(Path(icon.assetPath).exists() for icon in candidates if icon.assetPath)


def test_icon_candidate_field_label_rejects_text_stroke_like_blob(tmp_path) -> None:
    image, binding, structure, annotation, dsl, png = field_label_fixture(icon_bboxes=[[138, 70, 8, 28]])

    document = build_icon_candidate_document(
        task_id="task_field",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=None,
        asset_slice_document=None,
        dsl=dsl,
        settings=make_icon_settings(icon_candidate_max_component_area_ratio=0.60),
        storage=IconCandidateStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    assert document.meta["iconCount"] == 0
    assert not list((tmp_path / "assets").glob("**/*.png"))


def test_icon_candidate_does_not_crop_text_or_cover_overlap(tmp_path) -> None:
    image, _ocr, _replacement, binding, structure, annotation, separation, dsl, png = home_like_icon_inputs(
        [
            ([185, 831, 24, 20], (38, 132, 255)),
            ([187, 871, 24, 18], (38, 132, 255)),
        ]
    )

    document = build_icon_candidate_document(
        task_id="task_home",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=separation,
        asset_slice_document=None,
        dsl=dsl,
        settings=make_icon_settings(),
        storage=IconCandidateStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    assert document.meta["iconCount"] == 0
    assert not list((tmp_path / "assets").glob("**/*.png"))


def test_icon_candidate_limit_stops_cropping_and_records_warning(tmp_path) -> None:
    image, _ocr, _replacement, binding, structure, annotation, separation, dsl, png = home_like_icon_inputs(
        [
            ([145, 842, 22, 18], (38, 132, 255)),
            ([562, 842, 22, 18], (38, 132, 255)),
            ([145, 958, 22, 18], (38, 132, 255)),
        ]
    )

    document = build_icon_candidate_document(
        task_id="task_home",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=separation,
        asset_slice_document=None,
        dsl=dsl,
        settings=make_icon_settings(icon_candidate_max_candidates=1),
        storage=IconCandidateStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    assert document.status == "completed"
    assert document.meta["iconCount"] == 1
    assert any(warning.code == "icon_candidate_limit_reached" for warning in document.warnings)


def test_icon_candidate_metadata_only_changes_top_level_meta(tmp_path) -> None:
    image, _ocr, _replacement, binding, structure, annotation, separation, dsl, png = home_like_icon_inputs(
        [([145, 842, 22, 18], (38, 132, 255))]
    )
    before = deepcopy(dsl)
    document = build_icon_candidate_document(
        task_id="task_home",
        image=image,
        png_data=png,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        layer_separation_document=separation,
        asset_slice_document=None,
        dsl=dsl,
        settings=make_icon_settings(),
        storage=IconCandidateStorageAdapter(tmp_path / "assets", "http://localhost:8000"),
    )

    after = apply_icon_candidate_metadata(dsl, document)

    assert flatten_elements(after) == flatten_elements(before)
    assert after["root"] == before["root"]
    assert after["assets"] == before["assets"]
    assert after["meta"] != before["meta"]


def test_icon_candidate_failed_document_does_not_change_dsl_meta() -> None:
    document = build_failed_icon_candidate_document(
        task_id="task_failed",
        image=PngMetadata(100, 100, 8, 2, 0, 0, 0),
        code="ICON_CANDIDATE_VALIDATION_FAILED",
        message="Icon candidate validation failed.",
    )
    dsl = {"meta": {"qualityFlags": ["m19_local_asset_slice_candidates"]}, "root": {"children": []}}

    next_dsl = apply_icon_candidate_metadata(dsl, document)

    assert next_dsl == dsl


def test_generated_icon_asset_is_available_from_assets_api(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]
        document = client.get(f"/api/tasks/{task_id}/icon-candidates").json()["data"]
        candidate = next((item for item in document["icons"] if item.get("assetId")), None)
        if candidate is None:
            return

        asset = client.get(f"/api/assets/{candidate['assetId']}")
        assert asset.status_code == 200
        assert asset.json()["data"]["role"] == "asset_icon_candidate"
        png = client.get(candidate["assetUrl"].replace("http://localhost:8000", ""))
        assert png.status_code == 200
        assert read_png_metadata(png.content) is not None


def home_like_icon_inputs(icon_regions: list[tuple[list[int], tuple[int, int, int]]]):
    image, ocr, replacement, binding, structure, annotation, separation, dsl, base_png = home_like_slice_inputs()
    del base_png
    rows = [bytearray(bytes((247, 248, 250)) * image.width) for _ in range(image.height)]
    for block in ocr.blocks:
        draw_sparse_rect(rows, image.width, image.height, block.bbox, (20, 20, 20), step=3, inset=2)
    for bbox, rgb in icon_regions:
        draw_solid_rect(rows, image.width, image.height, bbox, rgb)
    return image, ocr, replacement, binding, structure, annotation, separation, dsl, encode_rgb_png(image.width, image.height, [bytes(row) for row in rows])


def field_label_fixture(icon_bboxes: list[list[int]] | None = None):
    image = PngMetadata(360, 260, 8, 2, 0, 0, 0)
    bindings = [
        TextPrimitiveBinding(
            id="binding_001",
            ocrBlockId="ocr_text_001",
            text="Label A",
            replacementElementId="visible_text_ocr_text_001",
            containerId="container_preview_card_001",
            containerRole="preview_card",
            relationship="card_subtitle",
            confidence=0.94,
            reason="synthetic_field_label",
            bbox=[90, 70, 56, 22],
            containerBBox=[40, 40, 280, 170],
        ),
        TextPrimitiveBinding(
            id="binding_002",
            ocrBlockId="ocr_text_002",
            text="Value A",
            replacementElementId="visible_text_ocr_text_002",
            containerId="container_preview_card_001",
            containerRole="preview_card",
            relationship="card_subtitle",
            confidence=0.94,
            reason="synthetic_field_value",
            bbox=[190, 70, 70, 22],
            containerBBox=[40, 40, 280, 170],
        ),
        TextPrimitiveBinding(
            id="binding_003",
            ocrBlockId="ocr_text_003",
            text="Label B",
            replacementElementId="visible_text_ocr_text_003",
            containerId="container_preview_card_001",
            containerRole="preview_card",
            relationship="card_subtitle",
            confidence=0.94,
            reason="synthetic_field_label",
            bbox=[90, 124, 56, 22],
            containerBBox=[40, 40, 280, 170],
        ),
        TextPrimitiveBinding(
            id="binding_004",
            ocrBlockId="ocr_text_004",
            text="Value B",
            replacementElementId="visible_text_ocr_text_004",
            containerId="container_preview_card_001",
            containerRole="preview_card",
            relationship="card_subtitle",
            confidence=0.94,
            reason="synthetic_field_value",
            bbox=[190, 124, 70, 22],
            containerBBox=[40, 40, 280, 170],
        ),
    ]
    binding = TextPrimitiveBindingDocument(
        version="0.1",
        taskId="task_field",
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        containers=[],
        bindings=bindings,
        unboundTextIds=[],
        warnings=[],
        meta={},
    )
    component = ComponentStructureItem(
        id="component_preview_card_001",
        role="preview_card",
        source="synthetic",
        bbox=[40, 40, 280, 170],
        confidence=0.94,
        reason="synthetic_field_rows",
        containerIds=[],
        bindingIds=[binding.id for binding in bindings],
        relationships={"card_subtitle": [binding.id for binding in bindings]},
        layout={"pattern": "vertical_stack", "axis": "vertical", "itemCount": 4, "gapEstimate": 32},
        quality={"risk": "low", "reasons": ["synthetic"]},
    )
    structure = ComponentStructureDocument(
        version="0.1",
        taskId="task_field",
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        components=[component],
        groups=[],
        unstructuredContainerIds=[],
        warnings=[],
        meta={},
    )
    children: list[dict[str, Any]] = []
    annotations: list[ComponentAnnotationItem] = []
    for index, binding_item in enumerate(bindings, start=1):
        element_id = f"visible_text_{binding_item.ocrBlockId}"
        children.append(
            {
                "id": element_id,
                "type": "text",
                "role": "visible_text_replacement",
                "layout": {"x": binding_item.bbox[0], "y": binding_item.bbox[1], "width": binding_item.bbox[2], "height": binding_item.bbox[3]},
                "style": {"visible": True},
                "content": {"text": binding_item.text},
            }
        )
        annotations.append(
            ComponentAnnotationItem(
                id=f"annotation_{index:03d}",
                dslElementId=element_id,
                elementType="text",
                elementRole="visible_text_replacement",
                componentId=component.id,
                componentRole=component.role,
                groupIds=[],
                relationship="card_subtitle",
                bindingId=binding_item.id,
                ocrBlockId=binding_item.ocrBlockId,
                confidence=0.94,
                reason="synthetic_field_annotation",
                layerName=f"Preview Card / Text / {binding_item.text}",
            )
        )
    dsl = {
        "version": "0.1",
        "taskId": "task_field",
        "assets": [],
        "meta": {"qualityFlags": ["m19_local_asset_slice_candidates"]},
        "root": {
            "id": "root",
            "type": "frame",
            "layout": {"x": 0, "y": 0, "width": image.width, "height": image.height},
            "children": children,
        },
    }
    annotation = ComponentAnnotationDocument(
        version="0.1",
        taskId="task_field",
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        annotations=annotations,
        groupHints=[],
        unannotatedElementIds=[],
        unresolvedComponentIds=[],
        warnings=[],
        meta={},
    )
    rows = [bytearray(bytes((247, 248, 250)) * image.width) for _ in range(image.height)]
    for binding_item in bindings:
        draw_sparse_rect(rows, image.width, image.height, binding_item.bbox, (20, 20, 20), step=3, inset=2)
    for bbox in icon_bboxes or [[58, 70, 22, 22], [58, 124, 22, 22]]:
        draw_solid_rect(rows, image.width, image.height, bbox, (38, 132, 255))
    return image, binding, structure, annotation, dsl, encode_rgb_png(image.width, image.height, [bytes(row) for row in rows])


def draw_solid_rect(rows: list[bytearray], width: int, height: int, bbox: list[int], rgb: tuple[int, int, int]) -> None:
    x, y, rect_width, rect_height = bbox
    for row_index in range(max(0, y), min(height, y + rect_height)):
        row = rows[row_index]
        for column in range(max(0, x), min(width, x + rect_width)):
            offset = column * 3
            row[offset : offset + 3] = bytes(rgb)


def draw_sparse_rect(
    rows: list[bytearray],
    width: int,
    height: int,
    bbox: list[int],
    rgb: tuple[int, int, int],
    *,
    step: int,
    inset: int,
) -> None:
    x, y, rect_width, rect_height = bbox
    for row_index in range(max(0, y + inset), min(height, y + rect_height - inset)):
        row = rows[row_index]
        for column in range(max(0, x + inset), min(width, x + rect_width - inset), step):
            offset = column * 3
            row[offset : offset + 3] = bytes(rgb)


def text_and_cover_elements(dsl: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        element
        for element in flatten_elements(dsl).values()
        if element.get("role") in {"visible_text_replacement", "text_replacement_cover"}
    ]


def overlaps_too_much(left: list[int], layout: dict[str, Any]) -> bool:
    right = [
        round(layout["x"]),
        round(layout["y"]),
        round(layout["width"]),
        round(layout["height"]),
    ]
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    if x2 <= x1 or y2 <= y1:
        return False
    intersection = (x2 - x1) * (y2 - y1)
    union = left[2] * left[3] + right[2] * right[3] - intersection
    return intersection / max(1, union) > 0.10


def summarize_sources(icons) -> dict[str, int]:
    summary: dict[str, int] = {}
    for icon in icons:
        summary[icon.source] = summary.get(icon.source, 0) + 1
    return summary


def summarize_roles(icons) -> dict[str, int]:
    summary: dict[str, int] = {}
    for icon in icons:
        summary[icon.componentRole] = summary.get(icon.componentRole, 0) + 1
    return summary


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    return create_component_client(monkeypatch, tmp_path, env)


def make_icon_settings(**overrides: Any):
    values = {
        "icon_candidate_enabled": True,
        "icon_candidate_min_confidence": 0.70,
        "icon_candidate_max_candidates": 64,
        "icon_candidate_min_size": 8,
        "icon_candidate_max_size": 96,
        "icon_candidate_foreground_distance": 32,
        "icon_candidate_max_component_area_ratio": 0.20,
    }
    values.update(overrides)
    return make_asset_settings(**values)
