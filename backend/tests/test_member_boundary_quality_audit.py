from __future__ import annotations

from pathlib import Path

import pytest

from app.member_boundary_quality_audit import (
    DuplicateAssetFinding,
    extract_member_boundary_quality_audit,
    validate_member_boundary_quality_audit_document,
    write_batch_summary,
)
from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.visual_primitive_graph import crop_pixels


def test_creates_audit_and_raw_dedup_counts_for_reused_weak_text_noise(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    docs = fixture_docs(
        objects=[
            object_candidate("voc_001", "compound_visual", [10, 10, 40, 24], [member("evidence_0001", [10, 10, 18, 18], "weak_visual"), member("evidence_0001", [10, 10, 18, 18], "weak_visual")]),
            object_candidate("voc_002", "compound_visual", [80, 10, 40, 24], [member("evidence_0001", [10, 10, 18, 18], "weak_visual")]),
        ],
        evidence=[evidence_node("evidence_0001", "weak_visual_text_noise", "text_noise", [10, 10, 18, 18])],
        refined_objects=[
            refined_object("refined_001", "voc_001", "compound_visual", [10, 10, 40, 24], "unresolved", unresolved=["unresolved_001", "unresolved_002"]),
            refined_object("refined_002", "voc_002", "compound_visual", [80, 10, 40, 24], "unresolved", unresolved=["unresolved_003"]),
        ],
        unresolved=[
            unresolved("unresolved_001", "voc_001", "evidence_0001", [10, 10, 18, 18], "weak_visual", "high_text_overlap"),
            unresolved("unresolved_002", "voc_001", "evidence_0001", [10, 10, 18, 18], "weak_visual", "high_text_overlap"),
            unresolved("unresolved_003", "voc_002", "evidence_0001", [10, 10, 18, 18], "weak_visual", "high_text_overlap"),
        ],
    )

    document = run_extract(tmp_path, canvas, docs)

    assert document.schema_name == "M2906MemberBoundaryQualityAuditDocument"
    weak_summary = document.summary["weakTextNoise"]
    assert weak_summary["rawMemberCount"] == 3
    assert weak_summary["uniqueSourceEvidenceNodeCount"] == 1
    assert weak_summary["uniqueBboxCount"] == 1
    assert weak_summary["uniqueCropHashCount"] == 1
    assert document.summary["weakTextNoiseUnresolvedRatio"] == 1.0
    kinds = [finding.finding_kind for finding in document.findings]
    assert "weak_text_noise_member" in kinds
    assert "weak_text_noise_object_dominance" in kinds
    assert "weak_text_noise_batch_dominance" in kinds
    assert document.duplicate_source_findings
    assert any(item.duplicate_kind == "sameSourceEvidenceNodeAcrossObjects" for item in document.duplicate_source_findings)


def test_does_not_create_findings_from_lookup_only_inputs(tmp_path: Path) -> None:
    canvas = make_canvas(120, 80)
    docs = fixture_docs(
        objects=[],
        evidence=[evidence_node("evidence_0001", "weak_visual_text_noise", "text_noise", [10, 10, 18, 18])],
        refined_objects=[],
        unresolved=[],
    )
    docs["m2903"]["items"] = [{"id": "visual_001", "sourceEvidenceId": "evidence_0001", "visualKind": "text_noise", "bbox": [10, 10, 18, 18]}]
    docs["m2902"]["textBoxes"] = [{"id": "text_001", "bbox": [10, 10, 18, 18], "text": "A"}]

    document = run_extract(tmp_path, canvas, docs)

    assert document.findings == []
    assert document.duplicate_source_findings == []
    assert document.duplicate_asset_findings == []


def test_text_box_overlap_only_for_real_visual_not_weak_text_noise(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    docs = fixture_docs(
        objects=[
            object_candidate("voc_001", "visual_text_pair", [10, 10, 70, 24], [member("evidence_0001", [10, 10, 24, 24], "visual")]),
            object_candidate("voc_002", "visual_text_pair", [80, 10, 70, 24], [member("evidence_0002", [80, 10, 24, 24], "weak_visual")]),
        ],
        evidence=[
            evidence_node("evidence_0001", "visual", "icon_candidate", [10, 10, 24, 24]),
            evidence_node("evidence_0002", "weak_visual_text_noise", "text_noise", [80, 10, 24, 24]),
        ],
        refined_objects=[
            refined_object("refined_001", "voc_001", "visual_text_pair", [10, 10, 70, 24], "unresolved", unresolved=["unresolved_001"]),
            refined_object("refined_002", "voc_002", "visual_text_pair", [80, 10, 70, 24], "unresolved", unresolved=["unresolved_002"]),
        ],
        unresolved=[
            unresolved("unresolved_001", "voc_001", "evidence_0001", [10, 10, 24, 24], "visual", "high_text_overlap"),
            unresolved("unresolved_002", "voc_002", "evidence_0002", [80, 10, 24, 24], "weak_visual", "high_text_overlap"),
        ],
        text_boxes=[{"id": "text_001", "bbox": [12, 12, 8, 8], "text": "x"}],
    )

    document = run_extract(tmp_path, canvas, docs)

    assert any(finding.finding_kind == "visual_member_contains_text" for finding in document.findings)
    assert any(finding.finding_kind == "weak_text_noise_member" for finding in document.findings)
    assert not any(finding.finding_kind == "text_box_overlaps_visual" and finding.source_object_id == "voc_002" for finding in document.findings)


def test_noise_split_shape_and_success_baseline(tmp_path: Path) -> None:
    canvas = make_canvas(220, 140)
    docs = fixture_docs(
        objects=[
            object_candidate("voc_001", "uncertain_compound", [10, 10, 30, 24], [member("evidence_0001", [10, 10, 18, 18], "noise")]),
            object_candidate("voc_002", "split_candidate", [60, 10, 100, 24], [member("evidence_0002", [60, 10, 100, 24], "wide_source")]),
            object_candidate("voc_003", "visual_text_pair", [10, 80, 80, 24], [member("evidence_0003", [10, 80, 20, 20], "visual"), member("evidence_0004", [50, 84, 30, 12], "text")]),
        ],
        evidence=[
            evidence_node("evidence_0001", "noise", "text_noise", [10, 10, 18, 18]),
            evidence_node("evidence_0002", "wide_visual_source", "other_candidate", [60, 10, 100, 24]),
            evidence_node("evidence_0003", "visual", "icon_candidate", [10, 80, 20, 20]),
            evidence_node("evidence_0004", "text", None, [50, 84, 30, 12]),
        ],
        refined_objects=[
            refined_object("refined_001", "voc_001", "uncertain_compound", [10, 10, 30, 24], "unresolved", unresolved=["unresolved_001"]),
            refined_object("refined_002", "voc_002", "split_candidate", [60, 10, 100, 24], "split_needed", unresolved=["unresolved_002"]),
            refined_object("refined_003", "voc_003", "visual_text_pair", [10, 80, 80, 24], "separated", visual=["visual_asset_001"], text=["text_member_001"]),
        ],
        unresolved=[
            unresolved("unresolved_001", "voc_001", "evidence_0001", [10, 10, 18, 18], "noise", "noise_member"),
            unresolved("unresolved_002", "voc_002", "evidence_0002", [60, 10, 100, 24], "wide_source", "wide_source"),
        ],
        visual_assets=[visual_asset("visual_asset_001", "voc_003", ["evidence_0003"], [10, 80, 20, 20], "icon_asset", "assets/visual_assets/visual_asset_001.png", 0.0)],
        shape_candidates=[shape_candidate("shape_001", "voc_003", ["evidence_0003"], [10, 100, 50, 14], ["contains_text", "text_overlay_shape"])],
        text_members=[text_member("text_member_001", "voc_003", "evidence_0004", [50, 84, 30, 12], "Go")],
    )
    write_m2905_asset(tmp_path, "assets/visual_assets/visual_asset_001.png", canvas, [10, 80, 20, 20])

    document = run_extract(tmp_path, canvas, docs)

    kinds = {finding.finding_kind for finding in document.findings}
    assert {"noise_member_in_object", "source_member_too_wide", "split_candidate_parent", "shape_with_text_overlay"} <= kinds
    assert document.success_baseline["separatedCount"] == 1
    assert document.success_baseline["successfulVisualAssetCount"] == 1
    assert document.success_baseline["sourceVisualKindsInSuccessfulAssets"] == {"icon_candidate": 1}


def test_duplicate_visual_asset_exact_perceptual_and_conflicting_use(tmp_path: Path) -> None:
    canvas = make_canvas(220, 140)
    docs = fixture_docs(
        objects=[object_candidate("voc_001", "single_visual", [10, 10, 30, 30], [member("evidence_0001", [10, 10, 20, 20], "visual")])],
        evidence=[evidence_node("evidence_0001", "visual", "icon_candidate", [10, 10, 20, 20])],
        refined_objects=[refined_object("refined_001", "voc_001", "single_visual", [10, 10, 30, 30], "visual_only", visual=["visual_asset_001", "visual_asset_002", "visual_asset_003"])],
        visual_assets=[
            visual_asset("visual_asset_001", "voc_001", ["evidence_0001"], [10, 10, 20, 20], "icon_asset", "assets/visual_assets/visual_asset_001.png", 0.0),
            visual_asset("visual_asset_002", "voc_001", ["evidence_0001"], [10, 10, 20, 20], "image_asset", "assets/visual_assets/visual_asset_002.png", 0.0),
            visual_asset("visual_asset_003", "voc_001", ["evidence_0001"], [50, 10, 20, 20], "icon_asset", "assets/visual_assets/visual_asset_003.png", 0.0),
        ],
    )
    for asset in docs["m2905"]["visualAssets"]:
        write_m2905_asset(tmp_path, asset["assetPath"], canvas, [10, 10, 20, 20])

    document = run_extract(tmp_path, canvas, docs)

    duplicate_kinds = {finding.duplicate_kind: finding for finding in document.duplicate_asset_findings}
    assert "exactPixelDuplicate" in duplicate_kinds
    assert duplicate_kinds["exactPixelDuplicate"].decision == "fact"
    assert duplicate_kinds["exactPixelDuplicate"].sha256
    assert "perceptualDuplicateCandidate" in duplicate_kinds
    assert duplicate_kinds["perceptualDuplicateCandidate"].decision != "fact"
    assert duplicate_kinds["perceptualDuplicateCandidate"].perceptual_hash
    assert "conflictingAssetUseDuplicate" in duplicate_kinds
    assert set(duplicate_kinds["conflictingAssetUseDuplicate"].asset_uses) == {"icon_asset", "image_asset"}


def test_top_k_examples_and_outputs_are_readable(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    unresolved_items = [unresolved(f"unresolved_{index:03d}", "voc_001", "evidence_0001", [10, 10, 18, 18], "weak_visual", "high_text_overlap") for index in range(1, 8)]
    docs = fixture_docs(
        objects=[object_candidate("voc_001", "compound_visual", [10, 10, 40, 24], [member("evidence_0001", [10, 10, 18, 18], "weak_visual")])],
        evidence=[evidence_node("evidence_0001", "weak_visual_text_noise", "text_noise", [10, 10, 18, 18])],
        refined_objects=[refined_object("refined_001", "voc_001", "compound_visual", [10, 10, 40, 24], "unresolved", unresolved=[item["id"] for item in unresolved_items])],
        unresolved=unresolved_items,
    )

    document = run_extract(tmp_path, canvas, docs, max_examples=2)

    weak_examples = [item for item in document.examples if item["findingKind"] == "weak_text_noise_member"]
    assert len(weak_examples) == 2
    assert read_png_metadata((tmp_path / "preview_member_boundary_quality.png").read_bytes()) is not None
    for rel in document.debug.to_dict().values():
        metadata = read_png_metadata((tmp_path / rel).read_bytes())
        assert metadata is not None
        assert (metadata.width, metadata.height) == (canvas.width, canvas.height)


def test_validation_rejects_bad_refs_and_perceptual_fact(tmp_path: Path) -> None:
    canvas = make_canvas(180, 120)
    docs = fixture_docs(
        objects=[object_candidate("voc_001", "single_visual", [10, 10, 20, 20], [member("evidence_0001", [10, 10, 20, 20], "visual")])],
        evidence=[evidence_node("evidence_0001", "visual", "icon_candidate", [10, 10, 20, 20])],
        refined_objects=[refined_object("refined_001", "voc_001", "single_visual", [10, 10, 20, 20], "visual_only", visual=["visual_asset_001"])],
        visual_assets=[visual_asset("visual_asset_001", "voc_001", ["evidence_0001"], [10, 10, 20, 20], "icon_asset", "assets/visual_assets/visual_asset_001.png", 0.0)],
    )
    write_m2905_asset(tmp_path, "assets/visual_assets/visual_asset_001.png", canvas, [10, 10, 20, 20])
    document = run_extract(tmp_path, canvas, docs)
    bad_duplicate = DuplicateAssetFinding(
        id="daf_bad",
        duplicate_kind="perceptualDuplicateCandidate",
        decision="fact",
        severity="low",
        key="abc",
        visual_asset_ids=["visual_asset_001"],
        source_object_ids=["voc_001"],
        source_evidence_node_ids=["evidence_0001"],
        bboxes=[[10, 10, 20, 20]],
        asset_uses=["icon_asset"],
        sha256=None,
        perceptual_hash="abc",
        counts={},
        suggested_upstream_layers=[],
        example_asset_paths=[],
    )
    broken = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m2905_refined_visual_objects_json=document.source_m2905_refined_visual_objects_json,
        source_m2904_visual_object_candidates_json=document.source_m2904_visual_object_candidates_json,
        source_m2903_visual_evidence_json=document.source_m2903_visual_evidence_json,
        source_m2902_audit_json=document.source_m2902_audit_json,
        source_expansion_refs=document.source_expansion_refs,
        options=document.options,
        summary=document.summary,
        findings=document.findings,
        duplicate_source_findings=document.duplicate_source_findings,
        duplicate_asset_findings=[bad_duplicate],
        success_baseline=document.success_baseline,
        examples=document.examples,
        debug=document.debug,
        warnings=document.warnings,
        meta=document.meta,
    )
    with pytest.raises(ValueError, match="perceptual duplicate"):
        validate_member_boundary_quality_audit_document(broken, tmp_path, canvas.width, canvas.height, docs["m2905"], docs["m2904"])


def test_batch_summary_writes_json_and_csv(tmp_path: Path) -> None:
    canvas = make_canvas(120, 80)
    docs = fixture_docs(
        objects=[object_candidate("voc_001", "compound_visual", [10, 10, 40, 24], [member("evidence_0001", [10, 10, 18, 18], "weak_visual")])],
        evidence=[evidence_node("evidence_0001", "weak_visual_text_noise", "text_noise", [10, 10, 18, 18])],
        refined_objects=[refined_object("refined_001", "voc_001", "compound_visual", [10, 10, 40, 24], "unresolved", unresolved=["unresolved_001"])],
        unresolved=[unresolved("unresolved_001", "voc_001", "evidence_0001", [10, 10, 18, 18], "weak_visual", "high_text_overlap")],
    )
    document = run_extract(tmp_path / "image_01", canvas, docs)

    write_batch_summary([("image_01", document)], tmp_path)

    assert (tmp_path / "m29_0_6_batch_summary.json").exists()
    assert (tmp_path / "m29_0_6_batch_summary.csv").exists()
    assert "weakTextNoiseUnresolvedRatio" in (tmp_path / "m29_0_6_batch_summary.csv").read_text(encoding="utf-8")


def run_extract(tmp_path: Path, canvas: PngPixels, docs: dict, *, max_examples: int = 40):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return extract_member_boundary_quality_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        m2905_document=docs["m2905"],
        m2905_refined_visual_objects_json_path="/tmp/m29_0_5/refined_visual_objects.json",
        m2904_document=docs["m2904"],
        m2904_visual_object_candidates_json_path="/tmp/m29_0_4/visual_object_candidates.json",
        m2903_document=docs["m2903"],
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json",
        m2902_document=docs["m2902"],
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        output_dir=tmp_path,
        m2905_output_dir=tmp_path,
        options=__import__("app.member_boundary_quality_audit", fromlist=["M2906Options"]).M2906Options(max_examples_per_finding_kind=max_examples),
    )


def fixture_docs(
    *,
    objects: list[dict],
    evidence: list[dict],
    refined_objects: list[dict],
    unresolved: list[dict] | None = None,
    visual_assets: list[dict] | None = None,
    shape_candidates: list[dict] | None = None,
    text_members: list[dict] | None = None,
    text_boxes: list[dict] | None = None,
) -> dict:
    return {
        "m2904": {"schemaName": "M2904GenericVisualObjectCandidateAuditDocument", "schemaVersion": "0.1", "objects": objects, "evidenceNodes": evidence},
        "m2905": {
            "schemaName": "M2905TextAwareVisualObjectRefinementDocument",
            "schemaVersion": "0.1",
            "objects": refined_objects,
            "unresolvedMembers": unresolved or [],
            "visualAssets": visual_assets or [],
            "shapeCandidates": shape_candidates or [],
            "textMembers": text_members or [],
        },
        "m2903": {"schemaName": "M2903VisualEvidenceDocument", "schemaVersion": "0.1", "items": []},
        "m2902": {"schemaName": "M2902TextMaskedMediaAuditDocument", "schemaVersion": "0.1", "textBoxes": text_boxes or []},
    }


def object_candidate(id: str, kind: str, bbox: list[int], members: list[dict]) -> dict:
    return {"id": id, "objectKind": kind, "decision": "candidate", "bbox": bbox, "members": members, "risks": [], "reasons": ["test"]}


def member(evidence_node_id: str, bbox: list[int], role: str) -> dict:
    return {"evidenceNodeId": evidence_node_id, "sourceId": evidence_node_id, "bbox": bbox, "memberRole": role, "risks": [], "reasons": ["test"]}


def evidence_node(id: str, node_kind: str, source_visual_kind: str | None, bbox: list[int]) -> dict:
    return {"id": id, "sourceId": id, "bbox": bbox, "nodeKind": node_kind, "sourceVisualKind": source_visual_kind, "risks": [], "reasons": ["test"]}


def refined_object(id: str, source_object_id: str, kind: str, bbox: list[int], decision: str, *, unresolved: list[str] | None = None, visual: list[str] | None = None, shape: list[str] | None = None, text: list[str] | None = None) -> dict:
    return {
        "id": id,
        "sourceObjectId": source_object_id,
        "sourceObjectKind": kind,
        "sourceDecision": "candidate",
        "bbox": bbox,
        "decision": decision,
        "combinedAssetPath": f"assets/combined_objects/{id}.png",
        "combinedAssetUse": "audit_only",
        "visualAssetIds": visual or [],
        "shapeCandidateIds": shape or [],
        "textMemberIds": text or [],
        "unresolvedMemberIds": unresolved or [],
        "risks": [],
        "reasons": ["test"],
        "separationQuality": 0.5,
        "suggestedNextAction": None,
    }


def unresolved(id: str, source_object_id: str, node_id: str, bbox: list[int], role: str, reason: str) -> dict:
    return {"id": id, "sourceObjectId": source_object_id, "sourceEvidenceNodeId": node_id, "bbox": bbox, "memberRole": role, "reason": reason, "risks": [reason], "suggestedNextAction": "review"}


def visual_asset(id: str, source_object_id: str, node_ids: list[str], bbox: list[int], asset_use: str, path: str, overlap: float) -> dict:
    return {"id": id, "sourceObjectId": source_object_id, "sourceEvidenceNodeIds": node_ids, "bbox": bbox, "visualKind": "icon_like", "assetUse": asset_use, "decision": "candidate", "assetPath": path, "textOverlapRatio": overlap, "metrics": None, "risks": [], "reasons": ["test"]}


def shape_candidate(id: str, source_object_id: str, node_ids: list[str], bbox: list[int], risks: list[str]) -> dict:
    return {"id": id, "sourceObjectId": source_object_id, "sourceEvidenceNodeIds": node_ids, "bbox": bbox, "assetUse": "shape_candidate", "decision": "uncertain", "metrics": None, "color": None, "textOverlapRatio": 0.2, "reasons": ["test"], "risks": risks, "previewAssetPath": None}


def text_member(id: str, source_object_id: str, node_id: str, bbox: list[int], text: str) -> dict:
    return {"id": id, "sourceObjectId": source_object_id, "source": "m2904_member", "sourceEvidenceNodeId": node_id, "sourceTextBoxId": None, "bbox": bbox, "textPreview": text, "text": text, "confidence": 0.9, "risks": [], "reasons": ["test"], "previewAssetPath": None}


def write_m2905_asset(root: Path, rel: str, canvas: PngPixels, bbox: list[int]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(crop_pixels(canvas, bbox))


def make_canvas(width: int, height: int, fill: tuple[int, int, int] = (255, 255, 255)) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def pixels_to_png(canvas: PngPixels) -> bytes:
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)
