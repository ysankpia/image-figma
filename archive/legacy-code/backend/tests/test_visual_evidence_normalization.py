from __future__ import annotations

from pathlib import Path

import pytest

from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from app.visual_evidence_normalization import (
    VisualEvidenceItem,
    VisualEvidenceOptions,
    extract_visual_evidence_normalization,
    validate_visual_evidence_document,
)
from app.visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


def test_normalization_preserves_every_m2902_evidence_item_and_exports_crops(tmp_path: Path) -> None:
    canvas = make_canvas(220, 180, (255, 255, 255))
    draw_noise_patch(canvas, 10, 10, 80, 40)
    draw_noise_patch(canvas, 100, 10, 48, 48)
    draw_rect(canvas, 10, 80, 28, 28, (240, 0, 0))
    draw_rect(canvas, 60, 80, 24, 12, (20, 20, 20))

    m2902 = {
        "schemaName": "M2902TextMaskedMediaAuditDocument",
        "schemaVersion": "0.1",
        "mediaEvidence": [
            evidence("m29_image_001", "m29_image", "accepted_image", [10, 10, 80, 40], "keep_accepted_image", 0.05),
            evidence("m29_blocked_001", "m29_blocked", "image_like_blocked", [100, 10, 48, 48], "review_blocked_media_candidate", 0.0),
            evidence("m29_symbol_001", "m29_symbol", "image_like_symbol", [10, 80, 28, 28], "review_symbol_vs_image", 0.0),
            evidence("m291_group_001", "m291_group", "symbol_group", [60, 80, 24, 12], "likely_text_noise", 0.8),
        ],
    }

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert document.schema_name == "M2903VisualEvidenceDocument"
    assert len(document.items) == len(m2902["mediaEvidence"])
    assert {item.source_evidence_id for item in document.items} == {"m29_image_001", "m29_blocked_001", "m29_symbol_001", "m291_group_001"}
    assert read_png_metadata((tmp_path / "preview_visual_evidence.png").read_bytes()) is not None
    assert read_png_metadata((tmp_path / "overlays" / "13_visual_evidence_buckets.png").read_bytes()) is not None

    accepted = next(item for item in document.items if item.source_evidence_id == "m29_image_001")
    assert accepted.visual_kind == "accepted_image"
    assert accepted.decision == "accepted"
    accepted_crop = decode_png_pixels((tmp_path / accepted.asset_path).read_bytes())
    assert accepted_crop.width == 80 and accepted_crop.height == 40

    media = next(item for item in document.items if item.source_evidence_id == "m29_blocked_001")
    assert media.visual_kind == "media_candidate"
    assert media.decision == "candidate"
    assert media.asset_path.startswith("assets/media_candidates/")

    icon = next(item for item in document.items if item.source_evidence_id == "m29_symbol_001")
    assert icon.visual_kind == "icon_candidate"
    assert icon.decision == "candidate"
    assert icon.asset_path.startswith("assets/icon_candidates/")

    noise = next(item for item in document.items if item.source_evidence_id == "m291_group_001")
    assert noise.visual_kind == "text_noise"
    assert noise.decision == "noise"
    assert noise.asset_path.startswith("assets/text_noise/")


def test_media_candidate_is_not_dropped_because_source_is_blocked(tmp_path: Path) -> None:
    canvas = make_canvas(90, 70, (255, 255, 255))
    draw_noise_patch(canvas, 10, 10, 50, 40)
    m2902 = {
        "mediaEvidence": [
            evidence("blocked_media", "m29_blocked", "image_like_blocked", [10, 10, 50, 40], "review_blocked_media_candidate", 0.0)
        ]
    }

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert document.items[0].visual_kind == "media_candidate"
    assert document.groups["byVisualKind"] == {"media_candidate": 1}


def test_text_noise_is_retained_and_sorted_after_candidates(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_noise_patch(canvas, 10, 10, 50, 40)
    draw_rect(canvas, 10, 70, 30, 12, (20, 20, 20))
    m2902 = {
        "mediaEvidence": [
            evidence("noise", "m29_symbol", "image_like_symbol", [10, 70, 30, 12], "likely_text_noise", 0.9),
            evidence("media", "m29_unknown", "image_like_unknown", [10, 10, 50, 40], "review_image_threshold", 0.0),
        ]
    }

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert [item.visual_kind for item in document.items] == ["media_candidate", "text_noise"]
    assert document.groups["byVisualKind"]["text_noise"] == 1


def test_high_overlap_without_lineage_stays_text_noise(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_rect(canvas, 10, 70, 30, 12, (20, 20, 20))
    m2902 = {
        "mediaEvidence": [
            evidence("noise", "m29_symbol", "image_like_symbol", [10, 70, 30, 12], "likely_text_noise", 0.9),
        ]
    }

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert document.items[0].visual_kind == "text_noise"
    assert document.items[0].decision == "noise"


def test_source_support_shape_survives_high_text_overlap(tmp_path: Path) -> None:
    canvas = make_canvas(140, 90, (248, 248, 248))
    draw_rect(canvas, 30, 30, 84, 26, (255, 232, 235))
    m2902 = {
        "mediaEvidence": [
            evidence(
                "m29_shape_001",
                "m29_shape",
                "support_shape",
                [30, 30, 84, 26],
                "support_shape_candidate",
                0.42,
                reasons=["text_support_background_region", "sourceSubtype:text_support_background"],
            ),
            evidence("m29_symbol_001", "m29_symbol", "image_like_symbol", [20, 64, 42, 12], "likely_text_noise", 0.9),
        ]
    }

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    support = next(item for item in document.items if item.source_evidence_id == "m29_shape_001")
    assert support.source == "m29_shape"
    assert support.visual_kind == "other_candidate"
    assert support.decision == "candidate"
    assert "source_support_shape_retained" in support.reasons
    noise = next(item for item in document.items if item.source_evidence_id == "m29_symbol_001")
    assert noise.visual_kind == "text_noise"


def test_baseline_without_lineage_ignores_text_rejected_gate_even_with_text_boxes(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_rect(canvas, 10, 70, 30, 12, (20, 20, 20))
    m2902 = {
        "textBoxes": [text_box("ocr_001", [10, 70, 30, 12], "1")],
        "mediaEvidence": [
            evidence("noise", "m29_symbol", "image_like_symbol", [10, 70, 30, 12], "likely_text_noise", 0.95),
        ],
    }

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    item = document.items[0]
    assert item.visual_kind == "text_noise"
    assert item.source_lineage is None
    assert "text_owned_rejected_lineage" not in item.reasons
    assert "sourceLineage" not in item.to_dict()


def test_partial_overlap_with_pre_ocr_lineage_remains_mixed_symbol_text_candidate(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_rect(canvas, 10, 60, 30, 30, (20, 20, 20))
    m2902 = {
        "mediaEvidence": [
            evidence("candidate", "m291_group", "symbol_group", [10, 60, 30, 30], "likely_text_noise", 0.5),
        ]
    }
    lineage = m291_lineage_document(
        groups=[
            {
                "id": "group_001",
                "decision": "uncertain",
                "bbox": [10, 60, 30, 30],
                "sourceLineage": {
                    "preOcrSymbolCandidate": True,
                    "lineageStrength": "medium",
                    "lineageSource": "m291_group",
                    "m291GroupId": "group_001",
                    "ownershipHint": "visual_or_mixed",
                },
            }
        ]
    )

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        m291_lineage_document=lineage,
        m291_lineage_json_path="/tmp/m29_1/group_nodes.json",
        output_dir=tmp_path,
    )

    item = document.items[0]
    assert item.visual_kind == "mixed_symbol_text_candidate"
    assert item.decision == "uncertain"
    assert item.source_lineage is not None
    assert "pre_ocr_symbol_lineage_preserved" in item.reasons
    assert item.asset_path.startswith("assets/mixed_symbol_text_candidates/")


def test_full_ocr_overlap_with_pre_ocr_lineage_becomes_text_rejected_lineage(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_rect(canvas, 10, 70, 30, 12, (20, 20, 20))
    m2902 = {
        "textBoxes": [text_box("ocr_001", [10, 70, 30, 12], "1")],
        "mediaEvidence": [
            evidence("candidate", "m291_group", "symbol_group", [10, 70, 30, 12], "likely_text_noise", 0.9),
        ],
    }
    lineage = m291_lineage_document(
        groups=[
            {
                "id": "group_001",
                "decision": "uncertain",
                "bbox": [10, 70, 30, 12],
                "sourceLineage": {
                    "preOcrSymbolCandidate": True,
                    "lineageStrength": "medium",
                    "lineageSource": "m291_group",
                    "m291GroupId": "group_001",
                    "ownershipHint": "visual_or_mixed",
                },
            }
        ]
    )

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        m291_lineage_document=lineage,
        output_dir=tmp_path,
    )

    item = document.items[0]
    assert item.visual_kind == "text_noise"
    assert item.decision == "noise"
    assert "text_owned_rejected_lineage" in item.reasons
    assert item.source_lineage is not None
    assert item.source_lineage["rejectedLineageReason"] == "text_owned_rejected_lineage"
    assert item.source_lineage["conflictClass"] == "text_owned_rejected_lineage"
    assert item.source_lineage["preOcrSymbolCandidate"] is True
    assert item.source_lineage["survivingPreOcrSymbolCandidate"] is False
    assert "full_ocr_coverage" in item.source_lineage["counterEvidence"]
    assert "single_text_like_token" in item.source_lineage["counterEvidence"]


def test_rejected_text_like_lineage_stays_text_noise(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_rect(canvas, 10, 70, 30, 12, (20, 20, 20))
    m2902 = {
        "mediaEvidence": [
            evidence("candidate", "m291_group", "symbol_group", [10, 70, 30, 12], "likely_text_noise", 0.9),
        ]
    }
    lineage = m291_lineage_document(
        groups=[
            {
                "id": "group_001",
                "decision": "rejected",
                "bbox": [10, 70, 30, 12],
                "rejectedLineageReason": "text_like_glyph_sequence",
                "reasons": ["text_like_sequence"],
            }
        ]
    )

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        m291_lineage_document=lineage,
        output_dir=tmp_path,
    )

    assert document.items[0].visual_kind == "text_noise"
    assert "rejected_pre_ocr_lineage_text_like" in document.items[0].reasons
    assert document.items[0].source_lineage is not None
    assert document.items[0].source_lineage["conflictClass"] == "text_owned_rejected_lineage"
    assert document.items[0].source_lineage["survivingPreOcrSymbolCandidate"] is False


def test_weak_eligible_blocked_lineage_with_high_overlap_becomes_text_rejected_lineage(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_rect(canvas, 10, 70, 24, 24, (20, 20, 20))
    m2902 = {
        "mediaEvidence": [
            evidence("candidate", "m29_blocked", "image_like_blocked", [10, 70, 24, 24], "likely_text_noise", 0.5),
        ],
    }
    lineage = m291_lineage_document(
        candidates=[
            {
                "id": "fragment_001",
                "sourceNodeId": "blocked_001",
                "sourceKind": "blocked",
                "bbox": [10, 70, 24, 24],
                "sourceLineage": {
                    "preOcrSymbolCandidate": True,
                    "lineageStrength": "weak",
                    "lineageSource": "eligible_blocked",
                    "m29BlockedIds": ["blocked_001"],
                    "m291CandidateIds": ["fragment_001"],
                    "ownershipHint": "visual_or_mixed",
                },
            }
        ]
    )

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        m291_lineage_document=lineage,
        output_dir=tmp_path,
    )

    item = document.items[0]
    assert item.visual_kind == "text_noise"
    assert "text_owned_rejected_lineage" in item.reasons
    assert item.source_lineage is not None
    assert "weak_eligible_blocked_high_ocr_overlap" in item.source_lineage["counterEvidence"]


def test_glyph_sequence_candidate_baseline_becomes_text_rejected_lineage(tmp_path: Path) -> None:
    canvas = make_canvas(140, 100, (255, 255, 255))
    draw_rect(canvas, 10, 70, 16, 12, (20, 20, 20))
    draw_rect(canvas, 30, 70, 16, 12, (20, 20, 20))
    draw_rect(canvas, 50, 70, 16, 12, (20, 20, 20))
    m2902 = {
        "mediaEvidence": [
            evidence("candidate", "m291_group", "symbol_group", [10, 68, 56, 16], "likely_text_noise", 0.5),
        ],
    }
    lineage = m291_lineage_document(
        candidates=[
            {"id": "fragment_001", "sourceNodeId": "symbol_001", "sourceKind": "symbol", "bbox": [10, 70, 16, 12], "sourceLineage": {"preOcrSymbolCandidate": True, "lineageStrength": "medium", "lineageSource": "m29_symbol", "m291CandidateIds": ["fragment_001"], "ownershipHint": "visual_or_mixed"}},
            {"id": "fragment_002", "sourceNodeId": "symbol_002", "sourceKind": "symbol", "bbox": [30, 70, 16, 12], "sourceLineage": {"preOcrSymbolCandidate": True, "lineageStrength": "medium", "lineageSource": "m29_symbol", "m291CandidateIds": ["fragment_002"], "ownershipHint": "visual_or_mixed"}},
            {"id": "fragment_003", "sourceNodeId": "symbol_003", "sourceKind": "symbol", "bbox": [50, 70, 16, 12], "sourceLineage": {"preOcrSymbolCandidate": True, "lineageStrength": "medium", "lineageSource": "m29_symbol", "m291CandidateIds": ["fragment_003"], "ownershipHint": "visual_or_mixed"}},
        ],
        groups=[
            {
                "id": "group_001",
                "decision": "uncertain",
                "bbox": [10, 68, 56, 16],
                "sourceLineage": {
                    "preOcrSymbolCandidate": True,
                    "lineageStrength": "medium",
                    "lineageSource": "m291_group",
                    "m291GroupId": "group_001",
                    "m291CandidateIds": ["fragment_001", "fragment_002", "fragment_003"],
                    "ownershipHint": "visual_or_mixed",
                },
            }
        ],
    )

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        m291_lineage_document=lineage,
        output_dir=tmp_path,
    )

    item = document.items[0]
    assert item.visual_kind == "text_noise"
    assert item.source_lineage is not None
    assert "glyph_sequence_risk" in item.source_lineage["counterEvidence"]


def test_small_symbol_group_prefers_icon_over_media_candidate(tmp_path: Path) -> None:
    canvas = make_canvas(90, 90, (255, 255, 255))
    draw_noise_patch(canvas, 20, 20, 48, 48)
    m2902 = {
        "mediaEvidence": [
            evidence("tool_icon", "m291_group", "symbol_group", [20, 20, 48, 48], "review_symbol_group", 0.0)
        ]
    }

    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert document.items[0].visual_kind == "icon_candidate"


def test_validation_rejects_bad_bbox_duplicate_id_and_missing_asset(tmp_path: Path) -> None:
    canvas = make_canvas(40, 40, (255, 255, 255))
    m2902 = {"mediaEvidence": [evidence("ok", "m29_symbol", "image_like_symbol", [4, 4, 10, 10], "review_symbol_vs_image", 0.0)]}
    document = extract_visual_evidence_normalization(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )
    item = document.items[0]
    duplicate = VisualEvidenceItem(
        id=item.id,
        source_evidence_id="other",
        source=item.source,
        bbox=item.bbox,
        region_name=item.region_name,
        visual_kind=item.visual_kind,
        decision=item.decision,
        confidence=item.confidence,
        asset_path=item.asset_path,
        text_overlap_ratio=item.text_overlap_ratio,
        image_overlap_ratio=item.image_overlap_ratio,
        metrics=item.metrics,
        reasons=item.reasons,
        source_decision=item.source_decision,
        suggested_next_action=item.suggested_next_action,
    )
    broken = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m2902_audit_json=document.source_m2902_audit_json,
        options=document.options,
        items=[item, duplicate],
        groups=document.groups,
        debug=document.debug,
        warnings=document.warnings,
        meta=document.meta,
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_visual_evidence_document(broken, tmp_path, 40, 40, expected_count=2)

    missing_asset = VisualEvidenceItem(
        id="missing",
        source_evidence_id="missing_source",
        source=item.source,
        bbox=item.bbox,
        region_name=item.region_name,
        visual_kind=item.visual_kind,
        decision=item.decision,
        confidence=item.confidence,
        asset_path="missing.png",
        text_overlap_ratio=item.text_overlap_ratio,
        image_overlap_ratio=item.image_overlap_ratio,
        metrics=item.metrics,
        reasons=item.reasons,
        source_decision=item.source_decision,
        suggested_next_action=item.suggested_next_action,
    )
    broken_asset = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m2902_audit_json=document.source_m2902_audit_json,
        options=document.options,
        items=[missing_asset],
        groups=document.groups,
        debug=document.debug,
        warnings=document.warnings,
        meta=document.meta,
    )
    with pytest.raises(ValueError, match="missing or unreadable"):
        validate_visual_evidence_document(broken_asset, tmp_path, 40, 40, expected_count=1)


def evidence(
    id: str,
    source: str,
    decision: str,
    bbox: list[int],
    action: str,
    text_overlap: float,
    *,
    reasons: list[str] | None = None,
) -> dict:
    return {
        "id": id,
        "source": source,
        "bbox": bbox,
        "regionName": "full",
        "decision": decision,
        "textOverlapRatio": text_overlap,
        "imageOverlapRatio": 0.0,
        "metrics": metrics_to_dict(metrics()),
        "reasons": reasons or ["test"],
        "suggestedNextAction": action,
    }


def m291_lineage_document(groups: list[dict] | None = None, candidates: list[dict] | None = None) -> dict:
    return {
        "schemaName": "M291SymbolFragmentGroupingDocument",
        "schemaVersion": "0.1",
        "sourceM29NodesJson": "/tmp/m29/nodes.json",
        "sourceImage": "synthetic.png",
        "options": {},
        "candidates": candidates or [],
        "edges": [],
        "groups": groups or [],
        "assetAudit": [],
        "edgeAudit": [],
        "debug": {},
        "warnings": [],
        "meta": {},
    }


def text_box(id: str, bbox: list[int], text: str, confidence: float = 0.98) -> dict:
    return {"id": id, "bbox": bbox, "text": text, "confidence": confidence, "source": "ocr", "kind": "line"}


def metrics() -> M29PrimitiveMetrics:
    return M29PrimitiveMetrics(
        color_count=48,
        texture_score=0.24,
        edge_score=0.12,
        fill_ratio=0.8,
        aspect_ratio=1.0,
        brightness=120,
        mean_rgb=(100, 100, 100),
    )


def make_canvas(width: int, height: int, fill: tuple[int, int, int]) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def draw_rect(canvas: PngPixels, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    color_bytes = bytes(color)
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            rows[row_index][column * 3 : column * 3 + 3] = color_bytes
    canvas.rows[:] = [bytes(row) for row in rows]


def draw_noise_patch(canvas: PngPixels, x: int, y: int, width: int, height: int) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            rows[row_index][column * 3 : column * 3 + 3] = bytes(
                (
                    (column * 31 + row_index * 17) % 220,
                    (column * 13 + row_index * 29) % 220,
                    (column * 7 + row_index * 11) % 220,
                )
            )
    canvas.rows[:] = [bytes(row) for row in rows]


def pixels_to_png(canvas: PngPixels) -> bytes:
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)
