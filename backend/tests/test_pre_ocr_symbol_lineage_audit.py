from __future__ import annotations

from pathlib import Path

from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.pre_ocr_symbol_lineage_audit import extract_pre_ocr_symbol_lineage_audit
from app.visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


def test_audit_finds_eligible_blocked_not_grouped(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80)
    document = run_audit(
        tmp_path,
        canvas,
        m29_document=make_m29_document(blocked=[blocked("blocked_001", [10, 10, 10, 10], ["weak_symbol_metrics"])]),
        m291_document=m291_document(),
    )

    finding = next(item for item in document.findings if item.finding_kind == "eligible_blocked_not_grouped")
    assert finding.m29_blocked_id == "blocked_001"
    assert finding.lineage_loss_stage == "m29_1"
    assert finding.example_asset_paths
    assert read_png_metadata((tmp_path / "overlay_pre_ocr_symbol_lineage.png").read_bytes()) is not None


def test_audit_traces_lineage_demoted_to_text_noise_and_suppressed(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100)
    group = {
        "id": "group_001",
        "decision": "uncertain",
        "bbox": [10, 10, 30, 20],
        "members": [{"candidateId": "fragment_001", "sourceNodeId": "symbol_001", "role": "foreground_symbol"}],
        "sourceLineage": {
            "preOcrSymbolCandidate": True,
            "lineageStrength": "medium",
            "lineageSource": "m291_group",
            "m29NodeIds": ["symbol_001"],
            "m291CandidateIds": ["fragment_001"],
            "m291GroupId": "group_001",
            "ownershipHint": "visual_or_mixed",
        },
        "reasons": ["group_confidence_uncertain"],
    }
    document = run_audit(
        tmp_path,
        canvas,
        m29_document=make_m29_document(nodes=[symbol("symbol_001", [10, 10, 30, 20])]),
        m291_document=m291_document(groups=[group]),
        m2902_document={"mediaEvidence": [media_evidence("m291_group_001", "m291_group", [10, 10, 30, 20])]},
        m2903_document={"items": [visual_item("text_noise_001", "m291_group_001", "text_noise", [10, 10, 30, 20])]},
        m2907_document={
            "ownershipDecisions": [
                {
                    "id": "own_0001",
                    "source": "m2903_visual_evidence",
                    "sourceVisualEvidenceItemId": "text_noise_001",
                    "bbox": [10, 10, 30, 20],
                    "ownership": "text_owned",
                    "suppressedAsVisual": True,
                    "risks": [],
                    "reasons": ["text_noise_owned_by_ocr"],
                }
            ]
        },
    )

    finding = next(item for item in document.findings if item.finding_kind == "visual_lineage_lost_after_text_mask")
    assert finding.m291_group_id == "group_001"
    assert finding.matched_m2902_media_evidence_id == "m291_group_001"
    assert finding.matched_m2903_visual_evidence_item_id == "text_noise_001"
    assert finding.matched_m2907_ownership_decision_id == "own_0001"
    assert finding.lineage_loss_stage == "m29_0_7"
    assert finding.later_visual_kind == "text_noise"
    assert finding.later_ownership == "text_owned"


def test_audit_records_text_like_glyph_without_surviving_lineage(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100)
    group = {
        "id": "group_001",
        "decision": "rejected",
        "bbox": [10, 10, 50, 10],
        "members": [],
        "rejectedLineageReason": "text_like_glyph_sequence",
        "reasons": ["text_like_sequence"],
    }
    document = run_audit(
        tmp_path,
        canvas,
        m29_document=make_m29_document(),
        m291_document=m291_document(groups=[group]),
    )

    finding = next(item for item in document.findings if item.finding_kind == "text_like_glyph_sequence")
    assert finding.lineage_strength == "weak"
    assert finding.example_asset_paths[0].startswith("assets/text_like_glyph_examples/")


def test_audit_traces_mixed_symbol_text_conflict(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100)
    group = {
        "id": "group_001",
        "decision": "uncertain",
        "bbox": [10, 10, 30, 20],
        "members": [],
        "sourceLineage": {"preOcrSymbolCandidate": True, "lineageStrength": "weak", "lineageSource": "m291_group", "m291GroupId": "group_001"},
        "reasons": ["group_confidence_uncertain"],
    }
    document = run_audit(
        tmp_path,
        canvas,
        m29_document=make_m29_document(),
        m291_document=m291_document(groups=[group]),
        m2902_document={"mediaEvidence": [media_evidence("m291_group_001", "m291_group", [10, 10, 30, 20])]},
        m2903_document={"items": [visual_item("mixed_001", "m291_group_001", "mixed_symbol_text_candidate", [10, 10, 30, 20])]},
        m2907_document={
            "ownershipDecisions": [
                {"id": "own_0001", "source": "m2903_visual_evidence", "sourceVisualEvidenceItemId": "mixed_001", "bbox": [10, 10, 30, 20], "ownership": "mixed_or_uncertain", "suppressedAsVisual": False}
            ]
        },
    )

    finding = next(item for item in document.findings if item.finding_kind == "symbol_text_ownership_conflict")
    assert finding.later_visual_kind == "mixed_symbol_text_candidate"
    assert finding.later_ownership == "mixed_or_uncertain"
    assert finding.example_asset_paths[0].startswith("assets/mixed_conflict_examples/")


def test_audit_outputs_only_existing_bboxes_and_no_formal_assets(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80)
    existing_bbox = [10, 10, 10, 10]
    document = run_audit(
        tmp_path,
        canvas,
        m29_document=make_m29_document(blocked=[blocked("blocked_001", existing_bbox, ["weak_symbol_metrics"])]),
        m291_document=m291_document(),
    )

    assert {tuple(item.bbox) for item in document.findings} == {tuple(existing_bbox)}
    assert not (tmp_path / "visual_assets").exists()
    assert not any("formalVisualAssetPath" in finding for finding in document.to_dict()["findings"])


def run_audit(
    output_dir: Path,
    canvas: PngPixels,
    *,
    m29_document: dict,
    m291_document: dict | None = None,
    m2902_document: dict | None = None,
    m2903_document: dict | None = None,
    m2907_document: dict | None = None,
):
    png = encode_rgb_png(canvas.width, canvas.height, canvas.rows)
    return extract_pre_ocr_symbol_lineage_audit(
        png_data=png,
        source_image="synthetic.png",
        m29_document=m29_document,
        m29_nodes_json_path="/tmp/m29/nodes.json",
        m291_document=m291_document,
        m291_group_nodes_json_path="/tmp/m29_1/group_nodes.json" if m291_document else None,
        m2902_document=m2902_document,
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json" if m2902_document else None,
        m2903_document=m2903_document,
        m2903_visual_evidence_json_path="/tmp/m29_0_3/visual_evidence.json" if m2903_document else None,
        m2907_document=m2907_document,
        m2907_ownership_json_path="/tmp/m29_0_7/text_visual_ownership_gate.json" if m2907_document else None,
        output_dir=output_dir,
    )


def make_m29_document(nodes: list[dict] | None = None, blocked: list[dict] | None = None) -> dict:
    return {"nodes": nodes or [], "blocked": blocked or [], "meta": {"blockedEvidenceVersion": "0.2"}}


def m291_document(groups: list[dict] | None = None, candidates: list[dict] | None = None) -> dict:
    return {"schemaName": "M291SymbolFragmentGroupingDocument", "schemaVersion": "0.1", "groups": groups or [], "candidates": candidates or []}


def symbol(id: str, bbox: list[int]) -> dict:
    return {"id": id, "type": "symbol", "bbox": bbox, "metrics": metrics_to_dict(metrics())}


def blocked(id: str, bbox: list[int], reasons: list[str]) -> dict:
    return {"id": id, "bbox": bbox, "reasons": reasons, "metrics": metrics_to_dict(metrics())}


def media_evidence(id: str, source: str, bbox: list[int]) -> dict:
    return {"id": id, "source": source, "bbox": bbox, "reasons": ["test"]}


def visual_item(id: str, source_evidence_id: str, visual_kind: str, bbox: list[int]) -> dict:
    return {"id": id, "sourceEvidenceId": source_evidence_id, "visualKind": visual_kind, "bbox": bbox, "risks": [], "reasons": ["test"]}


def metrics() -> M29PrimitiveMetrics:
    return M29PrimitiveMetrics(24, 0.2, 0.18, 0.5, 1.0, 80, (80, 80, 80))


def make_canvas(width: int, height: int, fill: tuple[int, int, int] = (255, 255, 255)) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])
