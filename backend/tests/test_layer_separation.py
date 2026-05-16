from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi.testclient import TestClient

from app.component_annotation import (
    apply_component_annotations,
    build_component_annotation_document,
)
from app.component_structure import ComponentStructureItem
from app.layer_separation import (
    apply_layer_separation_metadata,
    build_failed_layer_separation_document,
    build_layer_separation_document,
)
from app.png_tools import PngMetadata
from test_component_annotation import (
    flatten_elements,
    home_like_annotation_inputs,
    make_annotation_settings,
)
from test_component_structure import create_client_with_env as create_component_client
from test_text_replacement import make_text_fixture_png
from conftest import PNG_BYTES


def test_layer_separation_default_upload_creates_report_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/layer-separation-candidates")
        assert response.status_code == 200
        separation = response.json()["data"]
        assert separation["status"] == "completed"
        assert separation["meta"]["notes"] == "component_aware_layer_separation_candidates"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m18_layer_separation_candidates" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["layerSeparationCandidateCount"] == separation["meta"]["candidateCount"]
        assert dsl["meta"]["layerSeparationFillCandidateCount"] == separation["meta"]["fillCandidateCount"]
        assert dsl["meta"]["layerSeparationRepairRequiredCount"] == separation["meta"]["repairRequiredCount"]
        assert dsl["meta"]["layerSeparationEmbeddedTextCount"] == separation["meta"]["embeddedTextCount"]
        assert dsl["meta"]["layerSeparationBlockedCount"] == separation["meta"]["blockedCount"]


def test_layer_separation_disabled_has_no_result_and_keeps_m17_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "LAYER_SEPARATION_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/layer-separation-candidates")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "LAYER_SEPARATION_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m17_component_annotation" in dsl["meta"]["qualityFlags"]
        assert "m18_layer_separation_candidates" not in dsl["meta"]["qualityFlags"]
        assert "layerSeparationCandidateCount" not in dsl["meta"]


def test_layer_separation_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/layer-separation-candidates")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_layer_separation",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No layer separation.",
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
    not_found = client.get("/api/tasks/task_without_layer_separation/layer-separation-candidates")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "LAYER_SEPARATION_NOT_FOUND"

    state.database.insert_layer_separation_result(
        {
            "task_id": "task_without_layer_separation",
            "status": "completed",
            "separation_path": "/tmp/does-not-exist.json",
            "candidate_count": 0,
            "fill_candidate_count": 0,
            "repair_required_count": 0,
            "embedded_text_count": 0,
            "blocked_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_layer_separation/layer-separation-candidates")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "LAYER_SEPARATION_NOT_FOUND"


def test_home_like_layer_separation_rules_cover_m18_candidates() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    document = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png_for_ocr(image, ocr),
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    assert document.status == "completed"
    by_id = {candidate.componentId: candidate for candidate in document.candidates}
    primary = by_id["component_primary_button_001"]
    assert primary.strategy == "shape_background_plus_editable_text"
    assert primary.fillCandidate["enabled"] is True
    assert primary.fillCandidate["mode"] == "solid_color_fill"
    assert primary.textSeparation["mode"] == "editable_text_over_fill"

    assert by_id["component_badge_001"].strategy == "shape_background_plus_editable_text"
    assert by_id["component_badge_002"].strategy == "shape_background_plus_editable_text"
    assert by_id["component_status_badge_001"].strategy == "shape_background_plus_editable_text"
    assert by_id["component_outline_button_001"].strategy == "shape_background_plus_editable_text"

    tip = by_id["component_tip_card_001"]
    assert tip.strategy == "image_slice_with_simple_fill_candidate"
    assert tip.fillCandidate["enabled"] is True

    nav = by_id["component_bottom_nav_item_003"]
    assert nav.strategy == "shape_background_plus_editable_text"
    assert nav.fillCandidate["enabled"] is True
    assert all(target[1] >= nav.bbox[1] + nav.bbox[3] * 0.42 for target in nav.fillCandidate["targetBBoxes"])

    fallback_ids = {context.dslElementId for context in document.fallbackContexts}
    assert {"fallback_region_header", "fallback_region_content", "fallback_region_bottom"} <= fallback_ids
    assert not any(candidate.componentId.startswith("fallback_") for candidate in document.candidates)
    assert document.meta["candidateCount"] == len(document.candidates)
    assert document.meta["fillCandidateCount"] == sum(1 for candidate in document.candidates if candidate.fillCandidate["enabled"])


def test_complex_preview_background_requires_repair_before_slice() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    preview_binding_ids = next(component.bindingIds for component in structure.components if component.id == "component_preview_card_001")
    preview_ocr_ids = {item.ocrBlockId for item in binding.bindings if item.id in preview_binding_ids}
    for decision in replacement.decisions:
        if decision.ocrBlockId in preview_ocr_ids and decision.background is not None:
            decision.background["maxChannelDelta"] = 80
            decision.background["confidence"] = 0.1
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    document = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png_for_ocr(image, ocr),
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    preview = next(candidate for candidate in document.candidates if candidate.componentId == "component_preview_card_001")
    assert preview.strategy == "image_slice_with_repair_required"
    assert preview.textSeparation["mode"] == "editable_text_over_repaired_background"
    assert "repair_required_before_slice" in preview.reasons


def test_mixed_background_component_does_not_get_single_color_fill() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    preview_binding_ids = next(component.bindingIds for component in structure.components if component.id == "component_preview_card_001")
    preview_ocr_ids = {item.ocrBlockId for item in binding.bindings if item.id in preview_binding_ids}
    for index, decision in enumerate(decision for decision in replacement.decisions if decision.ocrBlockId in preview_ocr_ids):
        decision.decision = "accepted"
        decision.quality["applyEligible"] = True
        decision.application = {"status": "applied", "reason": "quality_gate_passed"}
        if decision.background is None:
            decision.background = {}
        if index == 0:
            decision.background.update(
                {
                    "color": "#1468E6",
                    "meanRgb": [20, 104, 230],
                    "maxChannelDelta": 4,
                    "confidence": 0.89,
                }
            )
        else:
            decision.background.update(
                {
                    "color": "#F7F8FA",
                    "meanRgb": [247, 248, 250],
                    "maxChannelDelta": 5,
                    "confidence": 0.88,
                }
            )
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    document = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png_for_ocr(image, ocr),
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    preview = next(candidate for candidate in document.candidates if candidate.componentId == "component_preview_card_001")
    assert preview.strategy == "image_slice_with_repair_required"
    assert preview.fillCandidate["enabled"] is False
    assert preview.fillCandidate["targetBBoxes"] == []
    assert "simple_fill_candidate" not in preview.reasons


def test_component_without_text_becomes_image_slice_without_text() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    structure.components.append(
        ComponentStructureItem(
            id="component_unknown_999",
            role="unknown",
            source="m16_from_text_bindings",
            bbox=[20, 1450, 80, 80],
            confidence=0.82,
            reason="synthetic_no_text_component",
            containerIds=[],
            bindingIds=[],
            relationships={},
            layout={"pattern": "single", "axis": "none", "itemCount": 0, "gapEstimate": 0},
            quality={"risk": "low", "reasons": ["container_confidence_ok"]},
        )
    )
    structure.meta["componentCount"] = len(structure.components)
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    document = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png_for_ocr(image, ocr),
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    unknown = next(candidate for candidate in document.candidates if candidate.componentId == "component_unknown_999")
    assert unknown.strategy == "image_slice_without_text"
    assert unknown.status == "not_applicable"
    assert unknown.textSeparation["mode"] == "no_text"


def test_component_bbox_too_large_is_blocked() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    first = structure.components[0]
    first.bbox = [0, 0, image.width, image.height]
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    document = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png_for_ocr(image, ocr),
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=dsl,
        settings=make_layer_settings(layer_separation_max_component_area_ratio=0.20),
    )

    candidate = next(item for item in document.candidates if item.componentId == first.id)
    assert candidate.status == "blocked"
    assert candidate.strategy == "blocked"
    assert "component_bbox_too_large" in candidate.reasons
    assert first.id in document.blockedComponentIds


def test_bottom_nav_fill_target_invading_icon_area_is_blocked() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    nav_component = next(component for component in structure.components if component.id == "component_bottom_nav_item_003")
    nav_binding_ids = set(nav_component.bindingIds)
    nav_ocr_ids = {item.ocrBlockId for item in binding.bindings if item.id in nav_binding_ids}
    for decision in replacement.decisions:
        if decision.ocrBlockId in nav_ocr_ids:
            decision.expandedBBox = [nav_component.bbox[0], nav_component.bbox[1], nav_component.bbox[2], nav_component.bbox[3]]
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    document = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png_for_ocr(image, ocr),
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=dsl,
        settings=make_layer_settings(),
    )

    candidate = next(item for item in document.candidates if item.componentId == nav_component.id)
    assert candidate.status == "blocked"
    assert "near_bottom_nav_icon" in candidate.reasons


def test_layer_separation_metadata_only_changes_top_level_meta() -> None:
    image, ocr, replacement, binding, structure, dsl = home_like_annotation_inputs()
    annotation = build_component_annotation_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        dsl=dsl,
        settings=make_layer_settings(),
    )
    annotated_dsl = apply_component_annotations(dsl, annotation, layer_naming=True)
    before = deepcopy(annotated_dsl)
    document = build_layer_separation_document(
        task_id="task_home",
        image=image,
        png_data=png_for_ocr(image, ocr),
        replacement_document=replacement,
        binding_document=binding,
        structure_document=structure,
        annotation_document=annotation,
        dsl=annotated_dsl,
        settings=make_layer_settings(),
    )

    after = apply_layer_separation_metadata(annotated_dsl, document)

    assert flatten_elements(after) == flatten_elements(before)
    assert after["root"] == before["root"]
    assert after["meta"] != before["meta"]


def test_layer_separation_failed_document_does_not_change_dsl_meta() -> None:
    document = build_failed_layer_separation_document(
        task_id="task_failed",
        image=PngMetadata(100, 100, 8, 2, 0, 0, 0),
        code="LAYER_SEPARATION_VALIDATION_FAILED",
        message="Layer separation validation failed.",
    )
    dsl = {"meta": {"qualityFlags": ["m17_component_annotation"]}, "root": {"children": []}}

    next_dsl = apply_layer_separation_metadata(dsl, document)

    assert next_dsl == dsl


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    return create_component_client(monkeypatch, tmp_path, env)


def make_layer_settings(**overrides: Any):
    values = {
        "layer_separation_enabled": True,
        "layer_separation_min_confidence": 0.70,
        "layer_separation_simple_fill_tolerance": 24,
        "layer_separation_max_component_area_ratio": 0.35,
    }
    values.update(overrides)
    return make_annotation_settings(**values)


def png_for_ocr(image, ocr) -> bytes:
    return make_text_fixture_png(
        image.width,
        image.height,
        (247, 248, 250),
        [(block.bbox, (20, 20, 20)) for block in ocr.blocks],
    )
