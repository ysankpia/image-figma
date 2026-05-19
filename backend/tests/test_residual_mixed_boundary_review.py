from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.mixed_symbol_text_conflict_audit import FORBIDDEN_CONTRACT_TERMS, find_forbidden_contract_terms
from app.residual_mixed_boundary_review import (
    build_batch_summary,
    extract_residual_mixed_boundary_review,
)
from scripts.run_m29_0_3_2_residual_mixed_boundary_review import require_ocr_provider_ready


def test_only_mixed_items_become_review_items(tmp_path: Path) -> None:
    document = run_review(
        tmp_path,
        make_pattern_canvas(120, 120),
        m2903_document={
            "items": [
                mixed_item("mixed_001", [10, 10, 24, 24]),
                {"id": "icon_001", "sourceEvidenceId": "icon_source", "visualKind": "icon_candidate", "bbox": [50, 10, 24, 24]},
                {"id": "noise_001", "sourceEvidenceId": "noise_source", "visualKind": "text_noise", "bbox": [80, 10, 24, 16]},
            ]
        },
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "keep_mixed_symbol_text_conflict")]},
    )

    assert [review.source_visual_evidence_item_id for review in document.reviews] == ["mixed_001"]
    assert document.reviews[0].allowed_for_promotion_now is False
    assert document.reviews[0].allowed_for_visual_side_now is False
    assert document.reviews[0].allowed_for_formal_asset_now is False


def test_missing_m2913_conflict_produces_insufficient_evidence(tmp_path: Path) -> None:
    document = run_review(tmp_path, make_pattern_canvas(100, 100), m2903_document={"items": [mixed_item("mixed_001", [10, 10, 24, 24])]})

    review = document.reviews[0]
    assert review.review_conclusion == "insufficient_evidence"
    assert review.recommended_next_stage == "keep_audit_only"
    assert review.should_tighten_m2903 is False
    assert "insufficient_evidence" in review.risks


def test_text_rejected_with_m2903_readable_text_signals_becomes_tightening_candidate(tmp_path: Path) -> None:
    document = run_review(
        tmp_path,
        make_pattern_canvas(160, 80),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 100, 20], lineage={"lineageStrength": "weak", "lineageSource": "eligible_blocked"})]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "text_owned_rejected_lineage")]},
        m2902_document={"textBoxes": [text_box("ocr_001", [10, 10, 100, 20], "9")]},
    )

    review = document.reviews[0]
    assert review.review_conclusion == "m2903_tightening_candidate"
    assert review.recommended_next_stage == "consider_m2903_text_counter_evidence"
    assert review.should_tighten_m2903 is True
    assert review.signals.full_ocr_coverage is True
    assert "text_contamination_possible" in review.risks


def test_text_rejected_without_m2903_readable_signal_becomes_m2913_adjustment_candidate(tmp_path: Path) -> None:
    document = run_review(
        tmp_path,
        make_pattern_canvas(120, 100),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 24, 24], lineage={"lineageStrength": "medium", "lineageSource": "m291_group"})]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "text_owned_rejected_lineage")]},
    )

    review = document.reviews[0]
    assert review.review_conclusion == "m2913_classification_adjustment_candidate"
    assert review.should_adjust_m2913 is True


def test_future_with_text_like_risk_becomes_m2913_adjustment_candidate(tmp_path: Path) -> None:
    document = run_review(
        tmp_path,
        make_pattern_canvas(160, 80),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 120, 20])]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "future_promotable_uncertain_symbol_candidate")]},
        m2902_document={"textBoxes": [text_box("ocr_001", [10, 10, 120, 20], "1")]},
    )

    review = document.reviews[0]
    assert review.review_conclusion == "m2913_classification_adjustment_candidate"
    assert review.should_adjust_m2913 is True
    assert review.candidate_for_future_uncertain_review is False


def test_future_with_compact_partial_non_glyph_signals_becomes_future_review_candidate(tmp_path: Path) -> None:
    document = run_review(
        tmp_path,
        make_pattern_canvas(140, 100),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 30, 30])]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "future_promotable_uncertain_symbol_candidate")]},
        m2902_document={"textBoxes": [text_box("ocr_001", [30, 20, 40, 20], "label")]},
    )

    review = document.reviews[0]
    assert review.review_conclusion == "candidate_for_future_uncertain_review"
    assert review.recommended_next_stage == "future_uncertain_review_only"
    assert review.candidate_for_future_uncertain_review is True


def test_conflicting_or_unknown_signals_default_to_keep_residual_mixed(tmp_path: Path) -> None:
    document = run_review(
        tmp_path,
        make_canvas(140, 100, fill=(120, 120, 120)),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 30, 30])]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "keep_mixed_symbol_text_conflict")]},
        m2902_document={"textBoxes": [text_box("ocr_001", [30, 20, 40, 20], "label")]},
    )

    review = document.reviews[0]
    assert review.review_conclusion == "keep_residual_mixed_conflict"
    assert review.recommended_next_stage == "keep_audit_only"


def test_example_crops_review_sheet_and_no_new_bbox_or_formal_asset(tmp_path: Path) -> None:
    source_bbox = [10, 10, 24, 24]
    document = run_review(
        tmp_path,
        make_pattern_canvas(100, 100),
        m2903_document={"items": [mixed_item("mixed_001", source_bbox)]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "keep_mixed_symbol_text_conflict")]},
    )

    review = document.reviews[0]
    assert review.bbox == source_bbox
    assert review.example_crop_path is not None
    assert review.example_crop_path.startswith("assets/")
    assert not (tmp_path / "visual_assets").exists()
    assert "formalVisualAssetPath" not in json.dumps(document.to_dict(), ensure_ascii=False)
    assert read_png_metadata((tmp_path / "review_sheet_remaining_mixed.png").read_bytes()).width == 100


def test_forbidden_terms_are_rejected_from_output(tmp_path: Path) -> None:
    document = run_review(
        tmp_path,
        make_pattern_canvas(100, 100),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 24, 24])]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "keep_mixed_symbol_text_conflict")]},
    )
    json_text = json.dumps(document.to_dict(), ensure_ascii=False).lower()
    md_text = (tmp_path / "residual_mixed_boundary_review.md").read_text(encoding="utf-8").lower()

    for term in FORBIDDEN_CONTRACT_TERMS:
        assert term not in find_forbidden_contract_terms(json_text)
        assert term not in find_forbidden_contract_terms(md_text)


def test_full_batch_preflight_rejects_missing_baidu_token(monkeypatch) -> None:
    class Args:
        ocr_provider = "baidu_ppocrv5"

    class Settings:
        baidu_paddle_ocr_token = ""

    monkeypatch.setattr(
        "scripts.run_m29_0_3_2_residual_mixed_boundary_review.get_settings",
        lambda: Settings(),
    )

    with pytest.raises(RuntimeError, match="BAIDU_PADDLE_OCR_TOKEN is required"):
        require_ocr_provider_ready(Args())


def test_batch_summary_includes_totals_and_failures(tmp_path: Path) -> None:
    first = run_review(
        tmp_path / "one",
        make_pattern_canvas(100, 100),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 24, 24])]},
        m2913_document={"conflicts": [m2913_conflict("conflict_001", "mixed_001", "keep_mixed_symbol_text_conflict")]},
    )
    second = run_review(
        tmp_path / "two",
        make_pattern_canvas(160, 80),
        m2903_document={"items": [mixed_item("mixed_002", [10, 10, 100, 20])]},
        m2913_document={"conflicts": [m2913_conflict("conflict_002", "mixed_002", "text_owned_rejected_lineage")]},
        m2902_document={"textBoxes": [text_box("ocr_001", [10, 10, 100, 20], "1")]},
    )

    payload = build_batch_summary(
        [("image_001", first), ("image_002", second)],
        tmp_path,
        failures=[{"imageId": "image_003", "sourceImage": "missing.png", "failedStage": "m29", "error": "missing"}],
        m2905_by_image={"image_001": {"summary": {"visualAssetCount": 2, "textMemberCount": 3}}},
        m2906_by_image={"image_001": {"summary": {"weakTextNoiseUnresolvedRatio": 0.0}}},
    )

    assert payload["totals"]["totalImages"] == 3
    assert payload["totals"]["completedImages"] == 2
    assert payload["totals"]["failedImages"] == 1
    assert payload["totals"]["totalTighteningCandidates"] == 1
    assert payload["totals"]["totalVisualAssets"] == 2
    assert (tmp_path / "m29_0_3_2_batch_summary.json").exists()
    assert (tmp_path / "m29_0_3_2_batch_summary.csv").exists()


def run_review(
    output_dir: Path,
    canvas: PngPixels,
    *,
    m2903_document: dict,
    m2913_document: dict | None = None,
    m2902_document: dict | None = None,
    m2907_document: dict | None = None,
    m291_document: dict | None = None,
    m2911_document: dict | None = None,
):
    return extract_residual_mixed_boundary_review(
        png_data=encode_rgb_png(canvas.width, canvas.height, canvas.rows),
        source_image="synthetic.png",
        source_image_id="image_001",
        m2903_document=m2903_document,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        output_dir=output_dir,
        m2913_document=m2913_document,
        m2913_conflict_audit_json_path="/tmp/m29_1_3/mixed_symbol_text_conflict_audit.json" if m2913_document else None,
        m2902_document=m2902_document,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json" if m2902_document else None,
        m2907_document=m2907_document,
        m2907_ownership_json_path="/tmp/m29_0_7/text_visual_ownership_gate.json" if m2907_document else None,
        m291_document=m291_document,
        m291_group_nodes_json_path="/tmp/m29_1/group_nodes.json" if m291_document else None,
        m2911_document=m2911_document,
        m2911_lineage_audit_json_path="/tmp/m29_1_1/pre_ocr_symbol_lineage_audit.json" if m2911_document else None,
    )


def mixed_item(id: str, bbox: list[int], lineage: dict | None = None) -> dict:
    return {
        "id": id,
        "sourceEvidenceId": f"source_{id}",
        "visualKind": "mixed_symbol_text_candidate",
        "decision": "uncertain",
        "bbox": bbox,
        "sourceLineage": {
            "preOcrSymbolCandidate": True,
            "lineageStrength": "medium",
            "lineageSource": "m291_group",
            "m291GroupId": "group_001",
            "m291CandidateIds": ["fragment_001"],
            **(lineage or {}),
        },
        "reasons": ["pre_ocr_symbol_lineage_preserved"],
    }


def m2913_conflict(id: str, source_item_id: str, classification: str) -> dict:
    return {
        "id": id,
        "sourceVisualEvidenceItemId": source_item_id,
        "bbox": [10, 10, 24, 24],
        "classification": classification,
        "signals": {
            "lineageStrength": "medium",
            "lineageSource": "m291_group",
            "glyphSequenceRisk": False,
        },
    }


def text_box(id: str, bbox: list[int], text: str) -> dict:
    return {"id": id, "bbox": bbox, "text": text, "confidence": 0.99}


def make_canvas(width: int, height: int, fill: tuple[int, int, int] = (255, 255, 255)) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def make_pattern_canvas(width: int, height: int) -> PngPixels:
    rows: list[bytes] = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row.extend((30, 30, 30) if (x // 4 + y // 4) % 2 == 0 else (220, 220, 220))
        rows.append(bytes(row))
    return PngPixels(width=width, height=height, rows=rows)
