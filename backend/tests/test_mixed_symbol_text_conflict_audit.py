from __future__ import annotations

import json
from pathlib import Path

from app.mixed_symbol_text_conflict_audit import (
    FORBIDDEN_CONTRACT_TERMS,
    build_batch_summary,
    extract_mixed_symbol_text_conflict_audit,
    find_forbidden_contract_terms,
)
from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata


def test_only_mixed_items_become_conflicts(tmp_path: Path) -> None:
    document = run_audit(
        tmp_path,
        make_pattern_canvas(120, 120),
        m2903_document={
            "items": [
                mixed_item("mixed_001", [10, 10, 24, 24]),
                {"id": "icon_001", "sourceEvidenceId": "icon_source", "visualKind": "icon_candidate", "bbox": [50, 10, 24, 24]},
            ]
        },
    )

    assert [conflict.source_visual_evidence_item_id for conflict in document.conflicts] == ["mixed_001"]


def test_unknown_signals_default_to_keep_mixed(tmp_path: Path) -> None:
    document = run_audit(tmp_path, make_canvas(100, 100), m2903_document={"items": [mixed_item("mixed_001", [10, 10, 20, 20], lineage={})]})

    conflict = document.conflicts[0]
    assert conflict.classification == "keep_mixed_symbol_text_conflict"
    assert conflict.allowed_for_current_promotion is False
    assert conflict.allowed_for_object_forming_visual_side is False
    assert conflict.allowed_for_formal_visual_asset is False
    assert conflict.allowed_for_routing_change is False


def test_full_ocr_coverage_and_glyph_risk_rejects_to_text(tmp_path: Path) -> None:
    document = run_audit(
        tmp_path,
        make_pattern_canvas(160, 80),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 100, 20], lineage={"lineageStrength": "weak", "lineageSource": "eligible_blocked"})]},
        m2902_document={"textBoxes": [text_box("ocr_001", [10, 10, 100, 20], "9")]},
    )

    conflict = document.conflicts[0]
    assert conflict.classification == "text_owned_rejected_lineage"
    assert conflict.signals.full_ocr_coverage is True
    assert conflict.signals.glyph_sequence_risk is True
    assert "text_contamination_possible" in conflict.risks


def test_text_like_glyph_sequence_finding_rejects_to_text(tmp_path: Path) -> None:
    document = run_audit(
        tmp_path,
        make_pattern_canvas(120, 80),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 30, 20])]},
        m2911_document={
            "findings": [
                {
                    "id": "lineage_finding_001",
                    "findingKind": "text_like_glyph_sequence",
                    "matchedM2903VisualEvidenceItemId": "mixed_001",
                    "bbox": [10, 10, 30, 20],
                }
            ]
        },
    )

    conflict = document.conflicts[0]
    assert conflict.classification == "text_owned_rejected_lineage"
    assert conflict.source_m2911_finding_ids == ["lineage_finding_001"]


def test_strong_compact_partial_overlap_future_review_candidate(tmp_path: Path) -> None:
    document = run_audit(
        tmp_path,
        make_pattern_canvas(140, 100),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 30, 30], lineage={"lineageStrength": "strong", "lineageSource": "m291_group", "m291GroupId": "group_001", "m291CandidateIds": ["fragment_001"]})]},
        m2902_document={"textBoxes": [text_box("ocr_001", [30, 20, 40, 20], "label")]},
        m291_document={"groups": [{"id": "group_001", "bbox": [10, 10, 30, 30]}], "candidates": [{"id": "fragment_001", "bbox": [10, 10, 30, 30]}]},
        m2907_document={"ownershipDecisions": [ownership_decision("own_001", "mixed_001")]},
    )

    conflict = document.conflicts[0]
    assert conflict.classification == "future_promotable_uncertain_symbol_candidate"
    assert conflict.source_m291_group_id == "group_001"
    assert conflict.source_m291_candidate_ids == ["fragment_001"]
    assert conflict.source_m2907_ownership_decision_id == "own_001"
    assert conflict.signals.partial_ocr_overlap is True
    assert conflict.allowed_for_current_promotion is False


def test_conflicting_signals_remain_keep_mixed(tmp_path: Path) -> None:
    document = run_audit(
        tmp_path,
        make_canvas(140, 100, fill=(120, 120, 120)),
        m2903_document={"items": [mixed_item("mixed_001", [10, 10, 30, 30], lineage={"lineageStrength": "strong", "lineageSource": "m291_group"})]},
        m2902_document={"textBoxes": [text_box("ocr_001", [30, 20, 40, 20], "label")]},
    )

    conflict = document.conflicts[0]
    assert conflict.classification == "keep_mixed_symbol_text_conflict"
    assert conflict.signals.partial_ocr_overlap is True
    assert conflict.signals.visual_structure_hint is False


def test_examples_overlay_and_no_new_bbox_or_formal_asset(tmp_path: Path) -> None:
    source_bbox = [10, 10, 24, 24]
    document = run_audit(tmp_path, make_pattern_canvas(100, 100), m2903_document={"items": [mixed_item("mixed_001", source_bbox)]})

    assert [conflict.bbox for conflict in document.conflicts] == [source_bbox]
    assert document.conflicts[0].example_asset_paths
    assert document.conflicts[0].example_asset_paths[0].startswith("assets/")
    assert not (tmp_path / "visual_assets").exists()
    assert "formalVisualAssetPath" not in json.dumps(document.to_dict(), ensure_ascii=False)
    assert read_png_metadata((tmp_path / "overlay_mixed_symbol_text_conflicts.png").read_bytes()).width == 100


def test_source_documents_are_not_rewritten(tmp_path: Path) -> None:
    canvas = make_pattern_canvas(100, 100)
    source_path = tmp_path / "visual_evidence.json"
    source_path.write_text(json.dumps({"items": [mixed_item("mixed_001", [10, 10, 24, 24])]}), encoding="utf-8")
    before = source_path.read_bytes()

    run_audit(tmp_path / "out", canvas, m2903_document=json.loads(source_path.read_text(encoding="utf-8")), m2903_path=str(source_path))

    assert source_path.read_bytes() == before


def test_batch_summary_includes_totals_and_example_counts(tmp_path: Path) -> None:
    first = run_audit(tmp_path / "one", make_pattern_canvas(100, 100), m2903_document={"items": [mixed_item("mixed_001", [10, 10, 24, 24])]})
    second = run_audit(
        tmp_path / "two",
        make_pattern_canvas(120, 80),
        m2903_document={"items": [mixed_item("mixed_002", [10, 10, 80, 18])]},
        m2902_document={"textBoxes": [text_box("ocr_001", [10, 10, 80, 18], "1")]},
    )

    rows = build_batch_summary(
        [("image_01", first), ("image_02", second)],
        tmp_path,
        m2905_by_image={"image_01": {"visualAssets": [{"id": "asset_001"}]}},
        m2906_by_image={"image_01": {"summary": {"weakTextNoiseUnresolvedRatio": 0.0}}},
    )

    assert len(rows) == 2
    assert rows[0]["mixedCount"] == 1
    assert rows[0]["keepMixedExampleCount"] == 1
    assert rows[0]["visualAssetCountFromM2905"] == 1
    assert (tmp_path / "m29_1_3_batch_summary.json").exists()
    assert (tmp_path / "m29_1_3_batch_summary.csv").exists()


def test_outputs_do_not_contain_forbidden_contract_terms(tmp_path: Path) -> None:
    document = run_audit(tmp_path, make_pattern_canvas(100, 100), m2903_document={"items": [mixed_item("mixed_001", [10, 10, 24, 24])]})
    json_text = json.dumps(document.to_dict(), ensure_ascii=False).lower()
    md_text = (tmp_path / "mixed_symbol_text_conflict_audit.md").read_text(encoding="utf-8").lower()

    for term in FORBIDDEN_CONTRACT_TERMS:
        assert term not in find_forbidden_contract_terms(json_text)
        assert term not in find_forbidden_contract_terms(md_text)


def run_audit(
    output_dir: Path,
    canvas: PngPixels,
    *,
    m2903_document: dict,
    m2902_document: dict | None = None,
    m2907_document: dict | None = None,
    m291_document: dict | None = None,
    m2911_document: dict | None = None,
    m2903_path: str = "/tmp/m29_0_3/visual_evidence.json",
):
    return extract_mixed_symbol_text_conflict_audit(
        png_data=encode_rgb_png(canvas.width, canvas.height, canvas.rows),
        source_image="synthetic.png",
        m2903_document=m2903_document,
        m2903_visual_evidence_json_path=m2903_path,
        output_dir=output_dir,
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
    if lineage is None:
        source_lineage = {
            "preOcrSymbolCandidate": True,
            "lineageStrength": "medium",
            "lineageSource": "m291_group",
            "m291GroupId": "group_001",
            "m291CandidateIds": ["fragment_001"],
        }
    else:
        source_lineage = dict(lineage)
    return {
        "id": id,
        "sourceEvidenceId": f"source_{id}",
        "visualKind": "mixed_symbol_text_candidate",
        "decision": "uncertain",
        "bbox": bbox,
        "sourceLineage": source_lineage,
        "reasons": ["pre_ocr_symbol_lineage_preserved"],
    }


def text_box(id: str, bbox: list[int], text: str) -> dict:
    return {"id": id, "bbox": bbox, "text": text, "confidence": 0.99}


def ownership_decision(id: str, source_item_id: str) -> dict:
    return {
        "id": id,
        "sourceVisualEvidenceItemId": source_item_id,
        "sourceVisualKind": "mixed_symbol_text_candidate",
        "ownership": "mixed_or_uncertain",
        "allowedForObjectFormingVisualSide": False,
    }


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
