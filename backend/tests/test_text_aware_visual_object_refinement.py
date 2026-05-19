from __future__ import annotations

from pathlib import Path

import pytest

from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from app.text_aware_visual_object_refinement import (
    M2905Options,
    RefinedVisualAsset,
    extract_text_aware_visual_object_refinement,
    validate_text_aware_visual_object_refinement_document,
)
from app.visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


def test_refines_each_m2904_object_exactly_once(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    m2904, m2903, m2902 = fixture_docs(
        objects=[
            object_candidate("voc_001", "visual_text_pair", [10, 10, 70, 24], [member("evidence_0001", [10, 10, 20, 20], "visual"), member("evidence_0002", [42, 12, 34, 12], "text")]),
            object_candidate("voc_002", "single_visual", [110, 10, 20, 20], [member("evidence_0003", [110, 10, 20, 20], "visual")]),
        ],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 20, 20], "visual", "icon_candidate"),
            evidence_node("evidence_0002", "m2902_text_box", "text_1", [42, 12, 34, 12], "text", None, text="Label"),
            evidence_node("evidence_0003", "m2903_visual_evidence", "visual_2", [110, 10, 20, 20], "visual", "icon_candidate"),
        ],
        m2903_items=[
            visual_item("visual_1", "icon_candidate", [10, 10, 20, 20]),
            visual_item("visual_2", "icon_candidate", [110, 10, 20, 20]),
        ],
        text_boxes=[text_box("text_1", [42, 12, 34, 12], "Label")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert len(document.objects) == len(m2904["objects"])
    assert {item.source_object_id for item in document.objects} == {"voc_001", "voc_002"}
    assert all(item.combined_asset_use == "audit_only" for item in document.objects)


def test_does_not_create_object_from_lookup_only_inputs(tmp_path: Path) -> None:
    canvas = make_canvas(120, 80)
    m2904, m2903, m2902 = fixture_docs(
        objects=[],
        evidence=[],
        m2903_items=[visual_item("lookup_visual", "icon_candidate", [10, 10, 20, 20])],
        text_boxes=[text_box("lookup_text", [40, 10, 20, 10], "T")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert document.objects == []
    assert document.visual_assets == []
    assert document.text_members == []


def test_visual_text_pair_low_overlap_separates_visual_and_text(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "visual_text_pair", [10, 10, 88, 24], [member("evidence_0001", [10, 10, 24, 24], "visual"), member("evidence_0002", [58, 14, 40, 12], "text")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 24, 24], "visual", "icon_candidate"),
            evidence_node("evidence_0002", "m2902_text_box", "text_1", [58, 14, 40, 12], "text", None, text="Open"),
        ],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 24, 24])],
        text_boxes=[text_box("text_1", [58, 14, 40, 12], "Open")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    refined = document.objects[0]
    assert refined.decision == "separated"
    assert len(refined.visual_asset_ids) == 1
    assert len(refined.text_member_ids) == 1
    asset = document.visual_assets[0]
    assert asset.asset_use == "icon_asset"
    assert asset.text_overlap_ratio == 0
    assert asset.asset_path and asset.asset_path.startswith("assets/visual_assets/")
    crop = decode_png_pixels((tmp_path / asset.asset_path).read_bytes())
    assert [crop.width, crop.height] == asset.bbox[2:4]


def test_high_text_overlap_visual_becomes_unresolved_without_visual_asset(tmp_path: Path) -> None:
    canvas = make_canvas(160, 100)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "visual_text_pair", [10, 10, 50, 28], [member("evidence_0001", [10, 10, 24, 24], "visual"), member("evidence_0002", [10, 10, 12, 24], "text")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 24, 24], "visual", "icon_candidate"),
            evidence_node("evidence_0002", "m2902_text_box", "text_1", [10, 10, 12, 24], "text", None, text="I"),
        ],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 24, 24])],
        text_boxes=[text_box("text_1", [10, 10, 12, 24], "I")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert document.visual_assets == []
    assert document.objects[0].decision == "partially_separated"
    assert any(item.reason == "high_text_overlap" for item in document.unresolved_members)


def test_weak_visual_is_unresolved_and_does_not_rewrite_upstream(tmp_path: Path) -> None:
    canvas = make_canvas(140, 100)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "visual_text_pair", [10, 10, 70, 24], [member("evidence_0001", [10, 10, 22, 22], "weak_visual"), member("evidence_0002", [48, 12, 30, 12], "text")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "weak_1", [10, 10, 22, 22], "weak_visual_text_noise", "text_noise", risks=["text_overlap", "icon_like_text_noise"]),
            evidence_node("evidence_0002", "m2902_text_box", "text_1", [48, 12, 30, 12], "text", None, text="A"),
        ],
        m2903_items=[visual_item("weak_1", "text_noise", [10, 10, 22, 22])],
        text_boxes=[text_box("text_1", [48, 12, 30, 12], "A")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert document.visual_assets == []
    assert any("weak_visual" in item.risks for item in document.unresolved_members)
    assert document.objects[0].decision == "partially_separated"


def test_compound_visual_exports_multiple_assets_not_forced_big_crop(tmp_path: Path) -> None:
    canvas = make_canvas(220, 100)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "compound_visual", [10, 10, 80, 24], [member("evidence_0001", [10, 10, 20, 20], "visual"), member("evidence_0002", [60, 10, 20, 20], "visual")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 20, 20], "visual", "icon_candidate"),
            evidence_node("evidence_0002", "m2903_visual_evidence", "visual_2", [60, 10, 20, 20], "visual", "icon_candidate"),
        ],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 20, 20]), visual_item("visual_2", "icon_candidate", [60, 10, 20, 20])],
        text_boxes=[],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert len(document.visual_assets) == 2
    assert sorted(item.bbox for item in document.visual_assets) == [[10, 10, 20, 20], [60, 10, 20, 20]]
    assert document.objects[0].decision == "visual_only"


def test_safe_visual_union_excludes_text_bbox(tmp_path: Path) -> None:
    canvas = make_canvas(140, 90)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "compound_visual", [10, 10, 48, 20], [member("evidence_0001", [10, 10, 18, 18], "visual"), member("evidence_0002", [32, 10, 18, 18], "visual")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 18, 18], "visual", "icon_candidate"),
            evidence_node("evidence_0002", "m2903_visual_evidence", "visual_2", [32, 10, 18, 18], "visual", "icon_candidate"),
        ],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 18, 18]), visual_item("visual_2", "icon_candidate", [32, 10, 18, 18])],
        text_boxes=[],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902, options=M2905Options(max_visual_union_gap=6))

    union = [item for item in document.visual_assets if len(item.source_evidence_node_ids) == 2]
    assert union
    assert union[0].bbox == [10, 10, 40, 18]


def test_shape_like_member_becomes_shape_candidate_even_with_text_overlay(tmp_path: Path) -> None:
    canvas = make_canvas(160, 100)
    shape_metrics = metrics(color_count=8, texture_score=0.04, edge_score=0.05, fill_ratio=0.92)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "visual_text_pair", [10, 10, 80, 26], [member("evidence_0001", [10, 10, 70, 24], "visual"), member("evidence_0002", [20, 14, 40, 12], "text")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 70, 24], "visual", "other_candidate", metrics_value=shape_metrics),
            evidence_node("evidence_0002", "m2902_text_box", "text_1", [20, 14, 40, 12], "text", None, text="Go"),
        ],
        m2903_items=[visual_item("visual_1", "other_candidate", [10, 10, 70, 24], metrics_value=shape_metrics)],
        text_boxes=[text_box("text_1", [20, 14, 40, 12], "Go")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert document.visual_assets == []
    assert len(document.shape_candidates) == 1
    assert {"contains_text", "text_overlay_shape"} <= set(document.shape_candidates[0].risks)
    assert document.shape_candidates[0].preview_asset_path
    assert not document.shape_candidates[0].preview_asset_path.startswith("assets/visual_assets/")


def test_icon_candidate_with_shape_like_metrics_remains_icon_asset(tmp_path: Path) -> None:
    canvas = make_canvas(160, 100)
    shape_metrics = metrics(color_count=8, texture_score=0.04, edge_score=0.05, fill_ratio=0.92)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "visual_text_pair", [10, 10, 88, 26], [member("evidence_0001", [10, 10, 24, 24], "visual"), member("evidence_0002", [58, 14, 40, 12], "text")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 24, 24], "visual", "icon_candidate", metrics_value=shape_metrics),
            evidence_node("evidence_0002", "m2902_text_box", "text_1", [58, 14, 40, 12], "text", None, text="Go"),
        ],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 24, 24], metrics_value=shape_metrics)],
        text_boxes=[text_box("text_1", [58, 14, 40, 12], "Go")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert len(document.visual_assets) == 1
    assert document.visual_assets[0].asset_use == "icon_asset"
    assert document.shape_candidates == []


def test_text_cluster_becomes_text_only_without_visual_asset(tmp_path: Path) -> None:
    canvas = make_canvas(160, 80)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "text_cluster", [10, 10, 70, 14], [member("evidence_0001", [10, 10, 30, 12], "text"), member("evidence_0002", [50, 10, 30, 12], "text")], decision="rejected")],
        evidence=[
            evidence_node("evidence_0001", "m2902_text_box", "text_1", [10, 10, 30, 12], "text", None, text="A"),
            evidence_node("evidence_0002", "m2902_text_box", "text_2", [50, 10, 30, 12], "text", None, text="B"),
        ],
        m2903_items=[],
        text_boxes=[text_box("text_1", [10, 10, 30, 12], "A"), text_box("text_2", [50, 10, 30, 12], "B")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert document.objects[0].decision == "text_only"
    assert document.visual_assets == []
    assert len(document.text_members) == 2


def test_split_candidate_does_not_export_child_visual_asset(tmp_path: Path) -> None:
    canvas = make_canvas(220, 120)
    m2904, m2903, m2902 = fixture_docs(
        objects=[
            object_candidate(
                "voc_001",
                "split_candidate",
                [10, 10, 140, 24],
                [
                    member("evidence_0001", [10, 10, 140, 24], "wide_source"),
                    member("evidence_0002", [20, 12, 20, 20], "visual"),
                ],
                risks=["wide_source_bbox", "split_needed"],
            )
        ],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "wide", [10, 10, 140, 24], "wide_visual_source", "other_candidate", risks=["wide_source_bbox"]),
            evidence_node("evidence_0002", "m2903_visual_evidence", "visual_1", [20, 12, 20, 20], "visual", "icon_candidate"),
        ],
        m2903_items=[
            visual_item("wide", "other_candidate", [10, 10, 140, 24]),
            visual_item("visual_1", "icon_candidate", [20, 12, 20, 20]),
        ],
        text_boxes=[],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert document.objects[0].decision == "split_needed"
    assert document.visual_assets == []
    assert document.shape_candidates == []
    assert document.objects[0].visual_asset_ids == []
    assert any(item.reason == "wide_source" for item in document.unresolved_members)


def test_visual_text_overlap_ratio_uses_visual_bbox_area(tmp_path: Path) -> None:
    canvas = make_canvas(160, 100)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "visual_text_pair", [10, 10, 70, 24], [member("evidence_0001", [10, 10, 20, 20], "visual"), member("evidence_0002", [10, 10, 10, 20], "text")])],
        evidence=[
            evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 20, 20], "visual", "icon_candidate"),
            evidence_node("evidence_0002", "m2902_text_box", "text_1", [10, 10, 10, 20], "text", None, text="X"),
        ],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 20, 20])],
        text_boxes=[text_box("text_1", [10, 10, 10, 20], "X")],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    unresolved = next(item for item in document.unresolved_members if item.reason == "high_text_overlap")
    assert unresolved.bbox == [10, 10, 20, 20]
    assert document.visual_assets == []


def test_text_preview_required_and_markdown_truncates_long_text(tmp_path: Path) -> None:
    canvas = make_canvas(240, 100)
    long_text = "abcdefghijklmnopqrstuvwxyz0123456789"
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "text_cluster", [10, 10, 160, 12], [member("evidence_0001", [10, 10, 160, 12], "text")])],
        evidence=[evidence_node("evidence_0001", "m2902_text_box", "text_1", [10, 10, 160, 12], "text", None, text=long_text)],
        m2903_items=[],
        text_boxes=[text_box("text_1", [10, 10, 160, 12], long_text)],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert document.text_members[0].text_preview == "abcdefghijklmnopqrstuvwx..."
    md = (tmp_path / "refined_visual_objects.md").read_text(encoding="utf-8")
    assert long_text not in md
    assert "abcdefghijklmnopqrstuvwx..." in md


def test_validation_rejects_bad_refs_and_invalid_visual_asset_use(tmp_path: Path) -> None:
    canvas = make_canvas(160, 100)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "single_visual", [10, 10, 20, 20], [member("evidence_0001", [10, 10, 20, 20], "visual")])],
        evidence=[evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 20, 20], "visual", "icon_candidate")],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 20, 20])],
        text_boxes=[],
    )
    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)
    first = document.visual_assets[0]
    bad_asset = RefinedVisualAsset(
        id=first.id,
        source_object_id=first.source_object_id,
        source_evidence_node_ids=first.source_evidence_node_ids,
        bbox=first.bbox,
        visual_kind=first.visual_kind,
        asset_use="audit_only",
        decision=first.decision,
        asset_path=first.asset_path,
        text_overlap_ratio=first.text_overlap_ratio,
        metrics=first.metrics,
        risks=first.risks,
        reasons=first.reasons,
    )
    broken = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m2904_visual_object_candidates_json=document.source_m2904_visual_object_candidates_json,
        source_m2903_visual_evidence_json=document.source_m2903_visual_evidence_json,
        source_m2902_audit_json=document.source_m2902_audit_json,
        source_expansion_refs=document.source_expansion_refs,
        options=document.options,
        objects=document.objects,
        visual_assets=[bad_asset],
        shape_candidates=document.shape_candidates,
        text_members=document.text_members,
        unresolved_members=document.unresolved_members,
        audit=document.audit,
        debug=document.debug,
        warnings=document.warnings,
        meta=document.meta,
    )
    with pytest.raises(ValueError, match="invalid assetUse"):
        validate_text_aware_visual_object_refinement_document(broken, tmp_path, canvas.width, canvas.height, m2904, m2902)


def test_preview_and_overlays_are_readable_source_sized(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    m2904, m2903, m2902 = fixture_docs(
        objects=[object_candidate("voc_001", "single_visual", [10, 10, 20, 20], [member("evidence_0001", [10, 10, 20, 20], "visual")])],
        evidence=[evidence_node("evidence_0001", "m2903_visual_evidence", "visual_1", [10, 10, 20, 20], "visual", "icon_candidate")],
        m2903_items=[visual_item("visual_1", "icon_candidate", [10, 10, 20, 20])],
        text_boxes=[],
    )

    document = run_extract(tmp_path, canvas, m2904, m2903, m2902)

    assert read_png_metadata((tmp_path / "preview_text_aware_refinement.png").read_bytes()) is not None
    for rel in document.debug.to_dict().values():
        meta = read_png_metadata((tmp_path / rel).read_bytes())
        assert meta is not None
        assert (meta.width, meta.height) == (canvas.width, canvas.height)


def run_extract(tmp_path: Path, canvas: PngPixels, m2904: dict, m2903: dict, m2902: dict, *, options: M2905Options | None = None):
    return extract_text_aware_visual_object_refinement(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2904_document=m2904,
        m2904_visual_object_candidates_json_path="/tmp/m29_0_4/visual_object_candidates.json",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
        options=options,
    )


def fixture_docs(*, objects: list[dict], evidence: list[dict], m2903_items: list[dict], text_boxes: list[dict]) -> tuple[dict, dict, dict]:
    return (
        {
            "schemaName": "M2904GenericVisualObjectCandidateAuditDocument",
            "schemaVersion": "0.1",
            "evidenceNodes": evidence,
            "objects": objects,
        },
        {"schemaName": "M2903VisualEvidenceDocument", "schemaVersion": "0.1", "items": m2903_items},
        {"schemaName": "M2902TextMaskedMediaAuditDocument", "schemaVersion": "0.1", "textBoxes": text_boxes},
    )


def object_candidate(id: str, kind: str, bbox: list[int], members: list[dict], *, decision: str = "candidate", risks: list[str] | None = None) -> dict:
    return {
        "id": id,
        "objectKind": kind,
        "decision": decision,
        "bbox": bbox,
        "confidence": 0.72,
        "members": members,
        "edgeIds": [],
        "risks": risks or [],
        "reasons": ["test"],
        "suggestedNextAction": None,
        "assetPath": f"assets/visual_objects/{id}.png",
    }


def member(evidence_node_id: str, bbox: list[int], role: str) -> dict:
    return {
        "evidenceNodeId": evidence_node_id,
        "source": "m2903_visual_evidence" if role in {"visual", "weak_visual", "wide_source"} else "m2902_text_box",
        "sourceId": evidence_node_id,
        "bbox": bbox,
        "memberRole": role,
        "confidence": 0.8,
        "risks": [],
        "reasons": ["test"],
    }


def evidence_node(
    id: str,
    source: str,
    source_id: str,
    bbox: list[int],
    node_kind: str,
    source_visual_kind: str | None,
    *,
    text: str | None = None,
    risks: list[str] | None = None,
    metrics_value: M29PrimitiveMetrics | None = None,
) -> dict:
    return {
        "id": id,
        "source": source,
        "sourceId": source_id,
        "bbox": bbox,
        "nodeKind": node_kind,
        "sourceVisualKind": source_visual_kind,
        "sourceDecision": "candidate",
        "text": text,
        "textPreview": text,
        "confidence": 0.8,
        "metrics": metrics_to_dict(metrics_value or metrics()),
        "risks": risks or [],
        "reasons": ["test"],
    }


def visual_item(id: str, visual_kind: str, bbox: list[int], *, metrics_value: M29PrimitiveMetrics | None = None) -> dict:
    return {
        "id": id,
        "sourceEvidenceId": id,
        "source": "m29_symbol",
        "bbox": bbox,
        "regionName": "full",
        "visualKind": visual_kind,
        "decision": "candidate",
        "confidence": 0.72,
        "assetPath": f"assets/{id}.png",
        "textOverlapRatio": 0.0,
        "imageOverlapRatio": 0.0,
        "metrics": metrics_to_dict(metrics_value or metrics()),
        "reasons": ["test"],
        "sourceDecision": "test",
        "suggestedNextAction": "review",
    }


def text_box(id: str, bbox: list[int], text: str) -> dict:
    return {
        "id": id,
        "bbox": bbox,
        "text": text,
        "confidence": 0.98,
        "source": "ocr",
        "kind": "line",
    }


def metrics(
    *,
    color_count: int = 48,
    texture_score: float = 0.22,
    edge_score: float = 0.12,
    fill_ratio: float = 0.8,
) -> M29PrimitiveMetrics:
    return M29PrimitiveMetrics(
        color_count=color_count,
        texture_score=texture_score,
        edge_score=edge_score,
        fill_ratio=fill_ratio,
        aspect_ratio=1.0,
        brightness=120,
        mean_rgb=(100, 100, 100),
    )


def make_canvas(width: int, height: int, fill: tuple[int, int, int] = (255, 255, 255)) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def pixels_to_png(canvas: PngPixels) -> bytes:
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)
