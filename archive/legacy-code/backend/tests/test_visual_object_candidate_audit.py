from __future__ import annotations

from pathlib import Path

import pytest

from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from app.visual_object_candidate_audit import (
    M2904Options,
    VisualObjectCandidate,
    VisualObjectSetCandidate,
    extract_visual_object_candidate_audit,
    validate_visual_object_candidate_audit_document,
)
from app.visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


def test_builds_evidence_nodes_from_m2903_items_and_m2902_text_boxes(tmp_path: Path) -> None:
    canvas = make_canvas(220, 160)
    m2903 = {"items": [visual_item("visual_1", "icon_candidate", [20, 40, 24, 24])]}
    m2902 = {"textBoxes": [text_box("text_1", [50, 44, 36, 14], "Label")]}

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert document.schema_name == "M2904GenericVisualObjectCandidateAuditDocument"
    assert {node.source for node in document.evidence_nodes} == {"m2903_visual_evidence", "m2902_text_box"}
    assert any(item.object_kind == "visual_text_pair" for item in document.objects)
    pair = next(item for item in document.objects if item.object_kind == "visual_text_pair")
    assert {member.member_role for member in pair.members} == {"visual", "text"}
    assert read_png_metadata((tmp_path / "preview_visual_objects.png").read_bytes()) is not None
    assert read_png_metadata((tmp_path / "overlays" / "16_visual_object_candidates.png").read_bytes()) is not None


def test_unknown_visual_kind_becomes_noise_with_warning(tmp_path: Path) -> None:
    canvas = make_canvas(90, 90)
    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document={"items": [visual_item("future_kind", "future_bucket", [10, 10, 20, 20])]},
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document={"textBoxes": []},
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert document.evidence_nodes[0].node_kind == "noise"
    assert "unknown_visual_kind" in document.evidence_nodes[0].risks
    assert any("unknown_visual_kind" in warning for warning in document.warnings)


def test_lookup_inputs_do_not_create_candidates(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100)
    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document={"items": []},
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document={
            "textBoxes": [],
            "mediaEvidence": [visual_item("legacy_media", "icon_candidate", [10, 10, 20, 20])],
        },
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert document.evidence_nodes == []
    assert document.objects == []


def test_icon_like_text_noise_is_only_weak_visual_member(tmp_path: Path) -> None:
    canvas = make_canvas(160, 120)
    m2903 = {"items": [visual_item("weak_icon", "text_noise", [20, 40, 22, 22], text_overlap=0.92)]}
    m2902 = {"textBoxes": [text_box("near_text", [48, 42, 30, 14], "A")]}

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    weak = next(node for node in document.evidence_nodes if node.source_id == "weak_icon")
    assert weak.node_kind == "weak_visual_text_noise"
    assert {"text_overlap", "icon_like_text_noise"} <= set(weak.risks)
    pair = next(item for item in document.objects if item.object_kind == "visual_text_pair")
    assert any(member.member_role == "weak_visual" for member in pair.members)
    assert "icon_like_text_noise" in pair.risks


def test_ownership_absent_keeps_baseline_weak_text_noise_objecting(tmp_path: Path) -> None:
    canvas = make_canvas(160, 120)
    m2903 = {"items": [visual_item("weak_icon", "text_noise", [20, 40, 22, 22], text_overlap=0.92)]}
    m2902 = {"textBoxes": [text_box("near_text", [48, 42, 30, 14], "A")]}

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert any(item.object_kind == "visual_text_pair" and any(member.member_role == "weak_visual" for member in item.members) for item in document.objects)
    assert all("ownershipRouting" not in node.to_dict() for node in document.evidence_nodes)


def test_ownership_blocks_weak_text_noise_as_visual_side(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    m2903 = {"items": [visual_item("weak_icon", "text_noise", [20, 40, 22, 22], text_overlap=0.92), visual_item("real_icon", "icon_candidate", [50, 40, 22, 22])]}
    m2902 = {"textBoxes": [text_box("near_text", [140, 92, 30, 14], "A")]}
    ownership = ownership_document(
        [
            ownership_decision("weak_icon", "text_owned", allowed_visual=False, allowed_text=True, suppressed=True),
            ownership_decision("real_icon", "visual_owned", allowed_visual=True, allowed_text=False, suppressed=False),
            ownership_text_box("near_text"),
        ]
    )

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
        m2907_ownership_document=ownership,
    )

    assert not any(item.object_kind == "uncertain_compound" and any(member.source_id == "weak_icon" for member in item.members) for item in document.objects)
    assert not any(item.object_kind == "compound_visual" and any(member.source_id == "weak_icon" for member in item.members) for item in document.objects)
    pair = next(item for item in document.objects if item.object_kind == "visual_text_pair" and any(member.source_id == "real_icon" for member in item.members))
    weak_member = next(member for member in pair.members if member.source_id == "weak_icon")
    assert weak_member.member_role == "text"
    weak_node = next(node for node in document.evidence_nodes if node.source_id == "weak_icon")
    assert weak_node.ownership_routing is not None
    assert "ownership_suppressed_as_visual" in weak_node.risks


def test_pure_text_fragments_do_not_become_accepted_visual_object(tmp_path: Path) -> None:
    canvas = make_canvas(180, 100)
    m2902 = {"textBoxes": [text_box("text_1", [20, 40, 30, 12], "A"), text_box("text_2", [56, 40, 30, 12], "B")]}

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document={"items": []},
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert any(item.object_kind == "text_cluster" for item in document.objects)
    assert all(not (item.object_kind == "text_cluster" and item.decision == "accepted") for item in document.objects)


def test_wide_source_bbox_creates_split_candidate_without_child_crop(tmp_path: Path) -> None:
    canvas = make_canvas(260, 120)
    m2903 = {"items": [visual_item("wide_source", "other_candidate", [20, 30, 170, 24])]}
    m2902 = {"textBoxes": [text_box("text_a", [40, 62, 26, 12], "A"), text_box("text_b", [128, 62, 26, 12], "B")]}

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    split = next(item for item in document.objects if item.object_kind == "split_candidate")
    assert split.decision == "uncertain"
    assert {"wide_source_bbox", "split_needed"} <= set(split.risks)
    crop = decode_png_pixels((tmp_path / split.asset_path).read_bytes())
    assert crop.width == split.bbox[2]
    assert crop.height == split.bbox[3]
    assert not any(item.object_kind == "visual_text_pair" and any(member.source_id == "wide_source" for member in item.members) for item in document.objects)


def test_repeated_visual_text_pairs_form_set_without_rejected_members(tmp_path: Path) -> None:
    canvas = make_canvas(320, 140)
    centers = [40, 110, 180, 250]
    m2903 = {"items": [visual_item(f"visual_{index}", "icon_candidate", [center - 10, 40, 20, 20]) for index, center in enumerate(centers, 1)]}
    m2902 = {"textBoxes": [text_box(f"text_{index}", [center - 14, 68, 28, 12], f"T{index}") for index, center in enumerate(centers, 1)]}

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document=m2903,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )

    assert any(item.set_kind in {"repeated_visual_set", "aligned_row_set"} for item in document.sets)
    rejected_ids = {item.id for item in document.objects if item.decision == "rejected"}
    assert all(not (set(item.member_object_ids) & rejected_ids) for item in document.sets)


def test_spatial_pruning_limits_large_evidence_graph(tmp_path: Path) -> None:
    canvas = make_canvas(1200, 800)
    items = []
    for index in range(340):
        x = (index % 34) * 34 + 4
        y = (index // 34) * 34 + 4
        items.append(visual_item(f"visual_{index}", "icon_candidate", [x, y, 12, 12]))

    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document={"items": items},
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document={"textBoxes": []},
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
        options=M2904Options(max_full_pair_nodes=20, max_neighbors_per_node=4),
    )

    full_pair_count = len(items) * (len(items) - 1) // 2
    assert len(document.evidence_edges) < full_pair_count // 4


def test_validation_rejects_bad_references_and_missing_assets(tmp_path: Path) -> None:
    canvas = make_canvas(120, 100)
    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document={"items": [visual_item("visual", "icon_candidate", [10, 10, 20, 20])]},
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document={"textBoxes": []},
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )
    first = document.objects[0]
    broken_asset = VisualObjectCandidate(
        id="broken",
        object_kind=first.object_kind,
        decision=first.decision,
        bbox=first.bbox,
        confidence=first.confidence,
        members=first.members,
        edge_ids=first.edge_ids,
        risks=first.risks,
        reasons=first.reasons,
        suggested_next_action=first.suggested_next_action,
        asset_path="missing.png",
    )
    broken = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m2903_visual_evidence_json=document.source_m2903_visual_evidence_json,
        source_m2902_audit_json=document.source_m2902_audit_json,
        source_expansion_refs=document.source_expansion_refs,
        options=document.options,
        evidence_nodes=document.evidence_nodes,
        evidence_edges=document.evidence_edges,
        objects=[broken_asset],
        sets=[],
        edge_audit=document.edge_audit,
        debug=document.debug,
        warnings=document.warnings,
        meta=document.meta,
    )
    with pytest.raises(ValueError, match="missing or unreadable"):
        validate_visual_object_candidate_audit_document(broken, tmp_path, canvas.width, canvas.height)

    bad_set = VisualObjectSetCandidate(
        id="set_bad",
        set_kind="aligned_row_set",
        decision="candidate",
        member_object_ids=["missing_object"],
        bbox=[0, 0, 10, 10],
        confidence=0.5,
        edge_ids=[],
        risks=[],
        reasons=[],
    )
    broken_ref = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m2903_visual_evidence_json=document.source_m2903_visual_evidence_json,
        source_m2902_audit_json=document.source_m2902_audit_json,
        source_expansion_refs=document.source_expansion_refs,
        options=document.options,
        evidence_nodes=document.evidence_nodes,
        evidence_edges=document.evidence_edges,
        objects=document.objects,
        sets=[bad_set],
        edge_audit=document.edge_audit,
        debug=document.debug,
        warnings=document.warnings,
        meta=document.meta,
    )
    with pytest.raises(ValueError, match="missing object"):
        validate_visual_object_candidate_audit_document(broken_ref, tmp_path, canvas.width, canvas.height)


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


def text_box(id: str, bbox: list[int], text: str) -> dict:
    return {
        "id": id,
        "bbox": bbox,
        "text": text,
        "confidence": 0.98,
        "source": "ocr",
        "kind": "line",
    }


def ownership_document(decisions: list[dict]) -> dict:
    return {
        "schemaName": "M2907TextVisualOwnershipGateDocument",
        "schemaVersion": "0.1",
        "ownershipDecisions": decisions,
    }


def ownership_decision(
    source_id: str,
    ownership: str,
    *,
    allowed_visual: bool,
    allowed_text: bool,
    suppressed: bool,
) -> dict:
    return {
        "id": f"own_{source_id}",
        "source": "m2903_visual_evidence",
        "sourceEvidenceId": source_id,
        "sourceVisualEvidenceItemId": source_id,
        "sourceTextBoxId": None,
        "sourceVisualKind": "text_noise" if ownership == "text_owned" else "icon_candidate",
        "ownership": ownership,
        "decision": "accepted",
        "ownershipReasonKind": "weak_visual_text_noise_owned_by_text" if ownership == "text_owned" else "visual_candidate_kept",
        "matchedTextBoxIds": ["near_text"] if ownership == "text_owned" else [],
        "textPreview": "A" if ownership == "text_owned" else "",
        "suppressedAsVisual": suppressed,
        "allowedForObjectFormingVisualSide": allowed_visual,
        "allowedForTextSide": allowed_text,
        "allowedForAuditOnly": True,
    }


def ownership_text_box(text_id: str) -> dict:
    return {
        "id": f"own_{text_id}",
        "source": "m2902_text_box",
        "sourceEvidenceId": text_id,
        "sourceVisualEvidenceItemId": None,
        "sourceTextBoxId": text_id,
        "sourceVisualKind": None,
        "ownership": "text_owned",
        "decision": "accepted",
        "ownershipReasonKind": "high_ocr_overlap_text_noise",
        "matchedTextBoxIds": [text_id],
        "textPreview": "A",
        "suppressedAsVisual": False,
        "allowedForObjectFormingVisualSide": False,
        "allowedForTextSide": True,
        "allowedForAuditOnly": True,
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


def test_isolated_text_box_is_preserved_as_rejected_text_cluster(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100)
    m2902 = {"textBoxes": [text_box("text_isolated", [10, 10, 40, 15], "Hello")]}
    document = extract_visual_object_candidate_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2903_document={"items": []},
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=m2902,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
    )
    assert len(document.objects) == 1
    obj = document.objects[0]
    assert obj.object_kind == "text_cluster"
    assert obj.decision == "rejected"
    assert len(obj.members) == 1
    assert obj.members[0].source_id == "text_isolated"
    assert obj.members[0].member_role == "text"

