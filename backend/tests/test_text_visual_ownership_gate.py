from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.text_visual_ownership_gate import (
    M2907Options,
    OwnershipDecision,
    extract_text_visual_ownership_gate,
    validate_text_visual_ownership_gate_document,
)
from app.visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


def test_text_noise_high_ocr_overlap_becomes_text_owned(tmp_path: Path) -> None:
    canvas = make_canvas(120, 90)
    document = run_extract(
        tmp_path,
        canvas,
        m2903={"items": [visual_item("noise_1", "text_noise", [10, 10, 40, 12], text_overlap=0.95)]},
        m2902={"textBoxes": [text_box("text_1", [10, 10, 40, 12], "Title", confidence=0.92)]},
    )

    decision = next(item for item in document.ownership_decisions if item.source_visual_evidence_item_id == "noise_1")
    assert decision.ownership == "text_owned"
    assert decision.decision == "accepted"
    assert decision.suppressed_as_visual is True
    assert decision.allowed_for_object_forming_visual_side is False
    assert decision.allowed_for_text_side is True
    assert decision.matched_text_box_ids == ["text_1"]
    assert document.routing_views["bySourceVisualEvidenceItemId"]["noise_1"]["allowedForObjectFormingVisualSide"] is False
    assert read_png_metadata((tmp_path / "preview_text_visual_ownership_gate.png").read_bytes()) is not None


def test_text_noise_low_ocr_confidence_is_not_visual_side(tmp_path: Path) -> None:
    canvas = make_canvas(120, 90)
    document = run_extract(
        tmp_path,
        canvas,
        m2903={"items": [visual_item("noise_1", "text_noise", [10, 10, 40, 12], text_overlap=0.95)]},
        m2902={"textBoxes": [text_box("text_1", [10, 10, 40, 12], "Title", confidence=0.2)]},
    )

    decision = next(item for item in document.ownership_decisions if item.source_visual_evidence_item_id == "noise_1")
    assert decision.ownership == "mixed_or_uncertain"
    assert decision.decision == "uncertain"
    assert decision.allowed_for_object_forming_visual_side is False
    assert decision.allowed_for_text_side is False
    assert "low_ocr_confidence" in decision.risks


def test_icon_overlap_is_mixed_not_suppressed(tmp_path: Path) -> None:
    canvas = make_canvas(120, 90)
    document = run_extract(
        tmp_path,
        canvas,
        m2903={"items": [visual_item("icon_1", "icon_candidate", [10, 10, 30, 30], text_overlap=0.0)]},
        m2902={"textBoxes": [text_box("text_1", [10, 10, 30, 30], "X")]},
    )

    decision = next(item for item in document.ownership_decisions if item.source_visual_evidence_item_id == "icon_1")
    assert decision.ownership == "mixed_or_uncertain"
    assert decision.ownership_reason_kind == "conflicting_ownership"
    assert decision.suppressed_as_visual is False
    assert decision.allowed_for_object_forming_visual_side is True


def test_media_internal_text_records_overlay_without_suppression(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    document = run_extract(
        tmp_path,
        canvas,
        m2903={"items": [visual_item("media_1", "media_candidate", [10, 10, 120, 60], text_overlap=0.0)]},
        m2902={"textBoxes": [text_box("text_1", [30, 24, 40, 14], "Banner")]},
    )

    decision = next(item for item in document.ownership_decisions if item.source_visual_evidence_item_id == "media_1")
    assert decision.ownership == "visual_owned"
    assert decision.ownership_reason_kind == "image_with_text_overlay"
    assert decision.suppressed_as_visual is False
    assert decision.allowed_for_object_forming_visual_side is True
    assert "text_overlay_on_visual" in decision.risks


def test_mixed_symbol_text_candidate_is_audit_only(tmp_path: Path) -> None:
    canvas = make_canvas(120, 90)
    document = run_extract(
        tmp_path,
        canvas,
        m2903={"items": [visual_item("mixed_1", "mixed_symbol_text_candidate", [10, 10, 30, 30], text_overlap=0.8)]},
        m2902={"textBoxes": [text_box("text_1", [10, 10, 30, 30], "X")]},
    )

    decision = next(item for item in document.ownership_decisions if item.source_visual_evidence_item_id == "mixed_1")
    assert decision.ownership == "mixed_or_uncertain"
    assert decision.decision == "uncertain"
    assert decision.ownership_reason_kind == "symbol_text_ownership_conflict"
    assert decision.suppressed_as_visual is False
    assert decision.allowed_for_object_forming_visual_side is False
    assert decision.allowed_for_text_side is False
    assert "pre_ocr_symbol_lineage_conflict" in decision.risks


def test_text_box_produces_text_owned_routing_and_outputs(tmp_path: Path) -> None:
    canvas = make_canvas(100, 80)
    document = run_extract(
        tmp_path,
        canvas,
        m2903={"items": []},
        m2902={"textBoxes": [text_box("text_1", [10, 10, 30, 12], "Long text value here")]},
    )

    decision = document.ownership_decisions[0]
    assert decision.source == "m2902_text_box"
    assert decision.ownership == "text_owned"
    assert decision.allowed_for_text_side is True
    assert (tmp_path / "text_owned_evidence.json").exists()
    for rel in document.debug.to_dict().values():
        metadata = read_png_metadata((tmp_path / rel).read_bytes())
        assert metadata is not None
        assert (metadata.width, metadata.height) == (canvas.width, canvas.height)


def test_validation_rejects_bad_refs_and_text_owned_visual_side(tmp_path: Path) -> None:
    canvas = make_canvas(100, 80)
    m2903 = {"items": [visual_item("noise_1", "text_noise", [10, 10, 30, 12], text_overlap=0.9)]}
    m2902 = {"textBoxes": [text_box("text_1", [10, 10, 30, 12], "A")]}
    document = run_extract(tmp_path, canvas, m2903=m2903, m2902=m2902)
    original = next(item for item in document.ownership_decisions if item.source_visual_evidence_item_id == "noise_1")
    bad = OwnershipDecision(
        id=original.id,
        source=original.source,
        source_evidence_id=original.source_evidence_id,
        source_visual_evidence_item_id=original.source_visual_evidence_item_id,
        source_text_box_id=original.source_text_box_id,
        source_visual_kind=original.source_visual_kind,
        bbox=original.bbox,
        ownership=original.ownership,
        decision=original.decision,
        ownership_reason_kind=original.ownership_reason_kind,
        matched_text_box_ids=original.matched_text_box_ids,
        text_overlap_ratio=original.text_overlap_ratio,
        ocr_overlap_ratio=original.ocr_overlap_ratio,
        text_preview=original.text_preview,
        ocr_confidence=original.ocr_confidence,
        suppressed_as_visual=original.suppressed_as_visual,
        allowed_for_object_forming_visual_side=True,
        allowed_for_text_side=original.allowed_for_text_side,
        allowed_for_audit_only=original.allowed_for_audit_only,
        risks=original.risks,
        reasons=original.reasons,
    )
    broken = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m2903_visual_evidence_json=document.source_m2903_visual_evidence_json,
        source_m2902_audit_json=document.source_m2902_audit_json,
        options=document.options,
        ownership_decisions=[bad],
        routing_views=document.routing_views,
        audit=document.audit,
        debug=document.debug,
        warnings=document.warnings,
        meta=document.meta,
    )
    with pytest.raises(ValueError, match="text-owned"):
        validate_text_visual_ownership_gate_document(broken, tmp_path, canvas.width, canvas.height, m2903, m2902)


def test_routing_views_use_existing_sources_and_do_not_emit_formal_assets(tmp_path: Path) -> None:
    canvas = make_canvas(140, 100)
    m2903 = {"items": [visual_item("noise_1", "text_noise", [10, 10, 40, 12], text_overlap=0.95), visual_item("icon_1", "icon_candidate", [70, 10, 24, 24])]}
    m2902 = {"textBoxes": [text_box("text_1", [10, 10, 40, 12], "Title")]}
    document = run_extract(tmp_path, canvas, m2903=m2903, m2902=m2902)
    payload = document.to_dict()

    existing_bboxes = {tuple(item["bbox"]) for item in m2903["items"]} | {tuple(item["bbox"]) for item in m2902["textBoxes"]}
    existing_visual_ids = {item["id"] for item in m2903["items"]}
    existing_text_ids = {item["id"] for item in m2902["textBoxes"]}
    for decision in payload["ownershipDecisions"]:
        assert tuple(decision["bbox"]) in existing_bboxes
        assert "assetPath" not in decision
        assert "formalVisualAssetPath" not in decision
    assert set(payload["routingViews"]["bySourceVisualEvidenceItemId"]) == existing_visual_ids
    assert set(payload["routingViews"]["byTextBoxId"]) == existing_text_ids
    assert not (tmp_path / "visual_assets").exists()


def test_validation_rejects_wrong_schema_duplicate_ids_and_out_of_bounds(tmp_path: Path) -> None:
    canvas = make_canvas(100, 80)
    m2903 = {"items": [visual_item("noise_1", "text_noise", [10, 10, 30, 12], text_overlap=0.9)]}
    m2902 = {"textBoxes": [text_box("text_1", [10, 10, 30, 12], "A")]}
    document = run_extract(tmp_path, canvas, m2903=m2903, m2902=m2902)

    with pytest.raises(ValueError, match="schema"):
        validate_text_visual_ownership_gate_document(replace(document, schema_name="WrongSchema"), tmp_path, canvas.width, canvas.height, m2903, m2902)

    first = document.ownership_decisions[0]
    with pytest.raises(ValueError, match="duplicate"):
        validate_text_visual_ownership_gate_document(replace(document, ownership_decisions=[first, first]), tmp_path, canvas.width, canvas.height, m2903, m2902)

    bad_bbox = replace(first, bbox=[-1, 0, 10, 10])
    with pytest.raises(ValueError, match="out of bounds"):
        validate_text_visual_ownership_gate_document(replace(document, ownership_decisions=[bad_bbox]), tmp_path, canvas.width, canvas.height, m2903, m2902)


def run_extract(tmp_path: Path, canvas: PngPixels, *, m2903: dict, m2902: dict):
    return extract_text_visual_ownership_gate(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
        options=M2907Options(),
    )


def visual_item(id: str, visual_kind: str, bbox: list[int], *, text_overlap: float = 0.0) -> dict:
    return {
        "id": id,
        "sourceEvidenceId": id,
        "source": "m29_symbol",
        "bbox": bbox,
        "regionName": "full",
        "visualKind": visual_kind,
        "decision": "candidate" if visual_kind != "text_noise" else "noise",
        "confidence": 0.72,
        "assetPath": f"assets/{id}.png",
        "textOverlapRatio": text_overlap,
        "imageOverlapRatio": 0.0,
        "metrics": metrics_to_dict(metrics()),
        "reasons": ["test"],
        "sourceDecision": "test",
        "suggestedNextAction": "review",
    }


def text_box(id: str, bbox: list[int], text: str, *, confidence: float = 0.98) -> dict:
    return {
        "id": id,
        "bbox": bbox,
        "text": text,
        "confidence": confidence,
        "source": "ocr",
        "kind": "line",
    }


def metrics() -> M29PrimitiveMetrics:
    return M29PrimitiveMetrics(
        color_count=48,
        texture_score=0.22,
        edge_score=0.12,
        fill_ratio=0.8,
        aspect_ratio=1.0,
        brightness=120,
        mean_rgb=(100, 100, 100),
    )


def make_canvas(width: int, height: int, fill: tuple[int, int, int] = (255, 255, 255)) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def pixels_to_png(canvas: PngPixels) -> bytes:
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)
