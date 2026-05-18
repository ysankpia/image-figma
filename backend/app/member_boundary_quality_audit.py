from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_evidence_normalization import parse_bbox
from .visual_primitive_graph import bbox_area, bbox_contains, bbox_in_bounds, bbox_x2, bbox_y2, crop_pixels, draw_rect


FindingDecision = Literal["fact", "candidate", "uncertain"]
FindingSeverity = Literal["high", "medium", "low"]
SuggestedLayer = Literal["m29_0_2", "m29_0_3", "m29_0_4", "m29_0_5", "m29_1", "asset_dedup", "manual_review"]


@dataclass(frozen=True)
class M2906Options:
    max_examples_per_finding_kind: int = 40
    max_duplicate_groups: int = 80
    max_examples_per_duplicate_group: int = 6
    perceptual_duplicate_hamming_max: int = 6
    output_preview_max_thumb: int = 160
    weak_text_noise_object_ratio_threshold: float = 0.60
    weak_text_noise_batch_ratio_threshold: float = 0.50

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M2906SourceExpansionRefs:
    m291_group_nodes_json: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"m291GroupNodesJson": self.m291_group_nodes_json}


@dataclass(frozen=True)
class SuggestedUpstreamLayer:
    layer: SuggestedLayer
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BoundaryQualityFinding:
    id: str
    finding_kind: str
    decision: FindingDecision
    severity: FindingSeverity
    source_object_id: str | None
    refined_object_id: str | None
    unresolved_member_ids: list[str]
    visual_asset_ids: list[str]
    shape_candidate_ids: list[str]
    text_member_ids: list[str]
    source_evidence_node_ids: list[str]
    member_roles: list[str]
    source_visual_kinds: list[str]
    bbox: list[int] | None
    counts: dict[str, Any]
    ratios: dict[str, float]
    reasons: list[str]
    risks: list[str]
    suggested_upstream_layers: list[SuggestedUpstreamLayer]
    example_asset_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "findingKind": self.finding_kind,
            "decision": self.decision,
            "severity": self.severity,
            "sourceObjectId": self.source_object_id,
            "refinedObjectId": self.refined_object_id,
            "unresolvedMemberIds": self.unresolved_member_ids,
            "visualAssetIds": self.visual_asset_ids,
            "shapeCandidateIds": self.shape_candidate_ids,
            "textMemberIds": self.text_member_ids,
            "sourceEvidenceNodeIds": self.source_evidence_node_ids,
            "memberRoles": self.member_roles,
            "sourceVisualKinds": self.source_visual_kinds,
            "bbox": self.bbox,
            "counts": self.counts,
            "ratios": {key: round(value, 4) for key, value in self.ratios.items()},
            "reasons": self.reasons,
            "risks": self.risks,
            "suggestedUpstreamLayers": [item.to_dict() for item in self.suggested_upstream_layers],
            "exampleAssetPaths": self.example_asset_paths,
        }


@dataclass(frozen=True)
class DuplicateSourceFinding:
    id: str
    duplicate_kind: str
    decision: FindingDecision
    severity: FindingSeverity
    key: str
    source_evidence_node_ids: list[str]
    source_object_ids: list[str]
    refined_object_ids: list[str]
    member_roles: list[str]
    bboxes: list[list[int]]
    counts: dict[str, Any]
    suggested_upstream_layers: list[SuggestedUpstreamLayer]
    example_asset_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "duplicateKind": self.duplicate_kind,
            "decision": self.decision,
            "severity": self.severity,
            "key": self.key,
            "sourceEvidenceNodeIds": self.source_evidence_node_ids,
            "sourceObjectIds": self.source_object_ids,
            "refinedObjectIds": self.refined_object_ids,
            "memberRoles": self.member_roles,
            "bboxes": self.bboxes,
            "counts": self.counts,
            "suggestedUpstreamLayers": [item.to_dict() for item in self.suggested_upstream_layers],
            "exampleAssetPaths": self.example_asset_paths,
        }


@dataclass(frozen=True)
class DuplicateAssetFinding:
    id: str
    duplicate_kind: str
    decision: FindingDecision
    severity: FindingSeverity
    key: str
    visual_asset_ids: list[str]
    source_object_ids: list[str]
    source_evidence_node_ids: list[str]
    bboxes: list[list[int]]
    asset_uses: list[str]
    sha256: str | None
    perceptual_hash: str | None
    counts: dict[str, Any]
    suggested_upstream_layers: list[SuggestedUpstreamLayer]
    example_asset_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "duplicateKind": self.duplicate_kind,
            "decision": self.decision,
            "severity": self.severity,
            "key": self.key,
            "visualAssetIds": self.visual_asset_ids,
            "sourceObjectIds": self.source_object_ids,
            "sourceEvidenceNodeIds": self.source_evidence_node_ids,
            "bboxes": self.bboxes,
            "assetUses": self.asset_uses,
            "sha256": self.sha256,
            "perceptualHash": self.perceptual_hash,
            "counts": self.counts,
            "suggestedUpstreamLayers": [item.to_dict() for item in self.suggested_upstream_layers],
            "exampleAssetPaths": self.example_asset_paths,
        }


@dataclass(frozen=True)
class M2906DebugArtifacts:
    member_boundary_risks: str
    unresolved_attribution: str
    duplicate_sources: str
    duplicate_assets: str

    def to_dict(self) -> dict[str, str]:
        return {
            "memberBoundaryRisks": self.member_boundary_risks,
            "unresolvedAttribution": self.unresolved_attribution,
            "duplicateSources": self.duplicate_sources,
            "duplicateAssets": self.duplicate_assets,
        }


@dataclass(frozen=True)
class M2906Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2905_refined_visual_objects_json: str
    source_m2904_visual_object_candidates_json: str
    source_m2903_visual_evidence_json: str
    source_m2902_audit_json: str
    source_expansion_refs: M2906SourceExpansionRefs
    options: M2906Options
    summary: dict[str, Any]
    findings: list[BoundaryQualityFinding]
    duplicate_source_findings: list[DuplicateSourceFinding]
    duplicate_asset_findings: list[DuplicateAssetFinding]
    success_baseline: dict[str, Any]
    examples: list[dict[str, Any]]
    debug: M2906DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2905RefinedVisualObjectsJson": self.source_m2905_refined_visual_objects_json,
            "sourceM2904VisualObjectCandidatesJson": self.source_m2904_visual_object_candidates_json,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "sourceExpansionRefs": self.source_expansion_refs.to_dict(),
            "options": self.options.to_dict(),
            "summary": self.summary,
            "findings": [item.to_dict() for item in self.findings],
            "duplicateSourceFindings": [item.to_dict() for item in self.duplicate_source_findings],
            "duplicateAssetFindings": [item.to_dict() for item in self.duplicate_asset_findings],
            "successBaseline": self.success_baseline,
            "examples": self.examples,
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_member_boundary_quality_audit(
    *,
    png_data: bytes,
    source_image: str,
    m2905_document: dict[str, Any],
    m2905_refined_visual_objects_json_path: str,
    m2904_document: dict[str, Any],
    m2904_visual_object_candidates_json_path: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    m2905_output_dir: Path | None = None,
    source_expansion_refs: M2906SourceExpansionRefs | None = None,
    options: M2906Options | None = None,
    warnings: list[str] | None = None,
) -> M2906Document:
    options = options or M2906Options()
    source_expansion_refs = source_expansion_refs or M2906SourceExpansionRefs()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    m2905_output_dir = m2905_output_dir or output_dir.parent / "m29_0_5"
    lookups = build_lookup_maps(m2905_document, m2904_document, m2903_document, m2902_document)
    examples: list[dict[str, Any]] = []
    example_counts: dict[str, int] = {}
    findings = build_boundary_findings(pixels, output_dir, lookups, examples, example_counts, options)
    duplicate_source_findings = build_duplicate_source_findings(pixels, output_dir, lookups, examples, example_counts, options)
    duplicate_asset_findings = build_duplicate_asset_findings(output_dir, m2905_output_dir, lookups, examples, example_counts, options)
    success_baseline = build_success_baseline(lookups)
    summary = build_summary(pixels, lookups, findings, duplicate_source_findings, duplicate_asset_findings, success_baseline)
    debug = write_debug_artifacts(pixels, output_dir, lookups, findings, duplicate_source_findings, duplicate_asset_findings)
    preview_path = output_dir / "preview_member_boundary_quality.png"
    preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, examples, options))
    document = M2906Document(
        schema_name="M2906MemberBoundaryQualityAuditDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2905_refined_visual_objects_json=m2905_refined_visual_objects_json_path,
        source_m2904_visual_object_candidates_json=m2904_visual_object_candidates_json_path,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        source_expansion_refs=source_expansion_refs,
        options=options,
        summary=summary,
        findings=findings,
        duplicate_source_findings=duplicate_source_findings,
        duplicate_asset_findings=duplicate_asset_findings,
        success_baseline=success_baseline,
        examples=examples,
        debug=debug,
        warnings=warnings or [],
        meta=build_meta(findings, duplicate_source_findings, duplicate_asset_findings, examples),
    )
    validate_member_boundary_quality_audit_document(document, output_dir, pixels.width, pixels.height, m2905_document, m2904_document)
    write_outputs(document, output_dir)
    return document


def build_lookup_maps(m2905_document: dict[str, Any], m2904_document: dict[str, Any], m2903_document: dict[str, Any], m2902_document: dict[str, Any]) -> dict[str, Any]:
    refined_objects = [item for item in m2905_document.get("objects", []) if isinstance(item, dict)]
    unresolved_members = [item for item in m2905_document.get("unresolvedMembers", []) if isinstance(item, dict)]
    visual_assets = [item for item in m2905_document.get("visualAssets", []) if isinstance(item, dict)]
    shape_candidates = [item for item in m2905_document.get("shapeCandidates", []) if isinstance(item, dict)]
    text_members = [item for item in m2905_document.get("textMembers", []) if isinstance(item, dict)]
    m2904_objects = [item for item in m2904_document.get("objects", []) if isinstance(item, dict)]
    evidence_nodes = [item for item in m2904_document.get("evidenceNodes", []) if isinstance(item, dict)]
    m2903_items = [item for item in m2903_document.get("items", []) if isinstance(item, dict)]
    text_boxes = [item for item in m2902_document.get("textBoxes", []) if isinstance(item, dict)]
    refined_by_id = {str(item.get("id")): item for item in refined_objects if item.get("id")}
    refined_by_source = {str(item.get("sourceObjectId")): item for item in refined_objects if item.get("sourceObjectId")}
    unresolved_by_id = {str(item.get("id")): item for item in unresolved_members if item.get("id")}
    visual_by_id = {str(item.get("id")): item for item in visual_assets if item.get("id")}
    shape_by_id = {str(item.get("id")): item for item in shape_candidates if item.get("id")}
    text_by_id = {str(item.get("id")): item for item in text_members if item.get("id")}
    m2904_by_id = {str(item.get("id")): item for item in m2904_objects if item.get("id")}
    node_by_id = {str(item.get("id")): item for item in evidence_nodes if item.get("id")}
    return {
        "m2905": m2905_document,
        "m2904": m2904_document,
        "m2903": m2903_document,
        "m2902": m2902_document,
        "refinedObjects": refined_objects,
        "refinedById": refined_by_id,
        "refinedBySource": refined_by_source,
        "unresolvedMembers": unresolved_members,
        "unresolvedById": unresolved_by_id,
        "visualAssets": visual_assets,
        "visualById": visual_by_id,
        "shapeCandidates": shape_candidates,
        "shapeById": shape_by_id,
        "textMembers": text_members,
        "textById": text_by_id,
        "m2904Objects": m2904_objects,
        "m2904ById": m2904_by_id,
        "evidenceNodes": evidence_nodes,
        "nodeById": node_by_id,
        "m2903ById": {str(item.get("id")): item for item in m2903_items if item.get("id")},
        "m2903BySourceEvidenceId": {str(item.get("sourceEvidenceId")): item for item in m2903_items if item.get("sourceEvidenceId")},
        "textBoxById": {str(item.get("id")): item for item in text_boxes if item.get("id")},
    }


def build_boundary_findings(
    pixels: PngPixels,
    output_dir: Path,
    lookups: dict[str, Any],
    examples: list[dict[str, Any]],
    example_counts: dict[str, int],
    options: M2906Options,
) -> list[BoundaryQualityFinding]:
    findings: list[BoundaryQualityFinding] = []
    for unresolved in lookups["unresolvedMembers"]:
        member_role = str(unresolved.get("memberRole") or "")
        node = lookups["nodeById"].get(str(unresolved.get("sourceEvidenceNodeId") or ""))
        source_visual_kind = str((node or {}).get("sourceVisualKind") or "")
        node_kind = str((node or {}).get("nodeKind") or "")
        reason = str(unresolved.get("reason") or "")
        if member_role == "weak_visual" and source_visual_kind == "text_noise":
            findings.append(make_member_finding("weak_text_noise_member", "high", unresolved, lookups, [weak_text_noise_layer("member")], ["weak_visual_text_noise_member"], pixels, output_dir, examples, example_counts, options))
            continue
        if member_role == "noise" or node_kind == "noise":
            findings.append(make_member_finding("noise_member_in_object", "medium", unresolved, lookups, [m2904_layer("noise_member_in_object", 0.70)], ["noise_member_kept_in_object_graph"], pixels, output_dir, examples, example_counts, options))
            continue
        if reason == "wide_source":
            findings.append(make_member_finding("source_member_too_wide", "high", unresolved, lookups, [m2904_layer("wide_source_member", 0.85)], ["wide_or_split_source_member"], pixels, output_dir, examples, example_counts, options))
            findings.append(make_member_finding("split_candidate_parent", "high", unresolved, lookups, [m2904_layer("split_candidate_parent", 0.86)], ["split_or_wide_parent_requires_upstream_fragment_split"], pixels, output_dir, examples, example_counts, options))
            continue
        if reason == "high_text_overlap" and member_role == "visual" and source_visual_kind != "text_noise":
            finding_kind = "text_box_overlaps_visual"
            if text_boxes_inside_bbox(parse_bbox(unresolved.get("bbox")), lookups):
                finding_kind = "visual_member_contains_text"
            findings.append(make_member_finding(finding_kind, "medium", unresolved, lookups, [m2902_layer("text_overlap_visual", 0.64), m2904_layer("visual_member_overlap", 0.58)], [f"{finding_kind}_candidate"], pixels, output_dir, examples, example_counts, options, decision="candidate"))
            continue
        if reason == "missing_lookup":
            findings.append(make_member_finding("missing_lookup", "high", unresolved, lookups, [manual_layer("missing_lookup", 0.80)], ["missing_lookup_reference"], pixels, output_dir, examples, example_counts, options))
            continue
        if reason == "invalid_bbox":
            findings.append(make_member_finding("invalid_bbox", "high", unresolved, lookups, [m2904_layer("invalid_member_bbox", 0.80)], ["invalid_member_bbox"], pixels, output_dir, examples, example_counts, options))
            continue
        if member_role not in {"visual", "weak_visual", "text", "nearby_text", "wide_source", "noise"}:
            findings.append(make_member_finding("unknown_member_role", "medium", unresolved, lookups, [m2904_layer("unknown_member_role", 0.74)], ["unknown_member_role"], pixels, output_dir, examples, example_counts, options))
    findings.extend(build_object_dominance_findings(pixels, output_dir, lookups, examples, example_counts, options, start_index=len(findings) + 1))
    findings.extend(build_shape_overlay_findings(pixels, output_dir, lookups, examples, example_counts, options, start_index=len(findings) + 1))
    batch_finding = build_batch_dominance_finding(pixels, lookups, options, len(findings) + 1)
    if batch_finding is not None:
        findings.append(batch_finding)
    return reindex_findings(findings)


def make_member_finding(
    kind: str,
    severity: FindingSeverity,
    unresolved: dict[str, Any],
    lookups: dict[str, Any],
    layers: list[SuggestedUpstreamLayer],
    reasons: list[str],
    pixels: PngPixels,
    output_dir: Path,
    examples: list[dict[str, Any]],
    example_counts: dict[str, int],
    options: M2906Options,
    *,
    decision: FindingDecision = "fact",
) -> BoundaryQualityFinding:
    source_object_id = str(unresolved.get("sourceObjectId") or "")
    refined = lookups["refinedBySource"].get(source_object_id)
    node_id = str(unresolved.get("sourceEvidenceNodeId") or "")
    node = lookups["nodeById"].get(node_id)
    bbox = parse_bbox(unresolved.get("bbox"))
    example_path = export_example_crop(pixels, output_dir, "unresolved_examples", kind, bbox, examples, example_counts, options, source_id=str(unresolved.get("id") or ""))
    source_visual_kind = str((node or {}).get("sourceVisualKind") or "")
    member_role = str(unresolved.get("memberRole") or "")
    return BoundaryQualityFinding(
        id="",
        finding_kind=kind,
        decision=decision,
        severity=severity,
        source_object_id=source_object_id or None,
        refined_object_id=str((refined or {}).get("id") or "") or None,
        unresolved_member_ids=[str(unresolved.get("id") or "")],
        visual_asset_ids=[],
        shape_candidate_ids=[],
        text_member_ids=[],
        source_evidence_node_ids=[node_id] if node_id else [],
        member_roles=[member_role] if member_role else [],
        source_visual_kinds=[source_visual_kind] if source_visual_kind else [],
        bbox=bbox,
        counts=raw_dedup_counts([unresolved], [source_object_id], [node_id], [bbox], crop_hashes_for_bboxes(pixels, [bbox])),
        ratios={},
        reasons=reasons,
        risks=[str(item) for item in unresolved.get("risks", []) if isinstance(item, str)],
        suggested_upstream_layers=layers,
        example_asset_paths=[example_path] if example_path else [],
    )


def build_object_dominance_findings(
    pixels: PngPixels,
    output_dir: Path,
    lookups: dict[str, Any],
    examples: list[dict[str, Any]],
    example_counts: dict[str, int],
    options: M2906Options,
    start_index: int,
) -> list[BoundaryQualityFinding]:
    findings: list[BoundaryQualityFinding] = []
    source_members_by_object = {str(item.get("id")): [member for member in item.get("members", []) if isinstance(member, dict)] for item in lookups["m2904Objects"]}
    unresolved_by_source: dict[str, list[dict[str, Any]]] = {}
    for unresolved in lookups["unresolvedMembers"]:
        unresolved_by_source.setdefault(str(unresolved.get("sourceObjectId") or ""), []).append(unresolved)
    for refined in lookups["refinedObjects"]:
        source_object_id = str(refined.get("sourceObjectId") or "")
        source_members = source_members_by_object.get(source_object_id, [])
        unresolved_members = unresolved_by_source.get(source_object_id, [])
        weak_members = [item for item in unresolved_members if unresolved_is_weak_text_noise(item, lookups)]
        denominator = max(1, len(source_members))
        ratio = len(weak_members) / denominator
        source_kind = str(refined.get("sourceObjectKind") or "")
        if weak_members and (ratio >= options.weak_text_noise_object_ratio_threshold or (source_kind in {"compound_visual", "uncertain_compound"} and len(weak_members) >= max(1, denominator - 1))):
            bbox = parse_bbox(refined.get("bbox"))
            example_path = export_example_crop(pixels, output_dir, "boundary_risk_examples", "weak_text_noise_object_dominance", bbox, examples, example_counts, options, source_id=source_object_id)
            node_ids = [str(item.get("sourceEvidenceNodeId") or "") for item in weak_members]
            findings.append(
                BoundaryQualityFinding(
                    id=f"bqf_{start_index + len(findings):04d}",
                    finding_kind="weak_text_noise_object_dominance",
                    decision="fact",
                    severity="high",
                    source_object_id=source_object_id,
                    refined_object_id=str(refined.get("id") or ""),
                    unresolved_member_ids=[str(item.get("id") or "") for item in weak_members],
                    visual_asset_ids=[],
                    shape_candidate_ids=[],
                    text_member_ids=[],
                    source_evidence_node_ids=dedupe_strings(node_ids),
                    member_roles=["weak_visual"],
                    source_visual_kinds=["text_noise"],
                    bbox=bbox,
                    counts=raw_dedup_counts(
                        weak_members,
                        [source_object_id],
                        node_ids,
                        [parse_bbox(item.get("bbox")) for item in weak_members],
                        crop_hashes_for_bboxes(pixels, [parse_bbox(item.get("bbox")) for item in weak_members]),
                    ),
                    ratios={"weakTextNoiseMemberRatio": ratio},
                    reasons=["object_members_dominated_by_weak_text_noise"],
                    risks=["weak_visual_text_noise_dominance"],
                    suggested_upstream_layers=[m2904_layer("object_graph_contains_many_weak_text_noise_members", 0.86), m2903_layer("source_visual_kind_is_text_noise", 0.55)],
                    example_asset_paths=[example_path] if example_path else [],
                )
            )
    return findings


def build_shape_overlay_findings(
    pixels: PngPixels,
    output_dir: Path,
    lookups: dict[str, Any],
    examples: list[dict[str, Any]],
    example_counts: dict[str, int],
    options: M2906Options,
    start_index: int,
) -> list[BoundaryQualityFinding]:
    findings: list[BoundaryQualityFinding] = []
    for shape in lookups["shapeCandidates"]:
        risks = [str(item) for item in shape.get("risks", []) if isinstance(item, str)]
        if "contains_text" not in risks and "text_overlay_shape" not in risks:
            continue
        source_object_id = str(shape.get("sourceObjectId") or "")
        refined = lookups["refinedBySource"].get(source_object_id)
        bbox = parse_bbox(shape.get("bbox"))
        example_path = export_example_crop(pixels, output_dir, "boundary_risk_examples", "shape_with_text_overlay", bbox, examples, example_counts, options, source_id=str(shape.get("id") or ""))
        findings.append(
            BoundaryQualityFinding(
                id=f"bqf_{start_index + len(findings):04d}",
                finding_kind="shape_with_text_overlay",
                decision="fact",
                severity="low",
                source_object_id=source_object_id or None,
                refined_object_id=str((refined or {}).get("id") or "") or None,
                unresolved_member_ids=[],
                visual_asset_ids=[],
                shape_candidate_ids=[str(shape.get("id") or "")],
                text_member_ids=[],
                source_evidence_node_ids=[str(item) for item in shape.get("sourceEvidenceNodeIds", [])],
                member_roles=["visual"],
                source_visual_kinds=[],
                bbox=bbox,
                counts=raw_dedup_counts([shape], [source_object_id], [str(item) for item in shape.get("sourceEvidenceNodeIds", [])], [bbox], crop_hashes_for_bboxes(pixels, [bbox])),
                ratios={"textOverlapRatio": float(shape.get("textOverlapRatio") or 0.0)},
                reasons=["shape_candidate_contains_text_overlay_risk"],
                risks=risks,
                suggested_upstream_layers=[m2905_layer("shape_candidate_kept_as_shape_not_formal_asset", 0.70)],
                example_asset_paths=[example_path] if example_path else [],
            )
        )
    return findings


def build_batch_dominance_finding(pixels: PngPixels, lookups: dict[str, Any], options: M2906Options, index: int) -> BoundaryQualityFinding | None:
    unresolved = lookups["unresolvedMembers"]
    if not unresolved:
        return None
    weak = [item for item in unresolved if unresolved_is_weak_text_noise(item, lookups)]
    ratio = len(weak) / max(1, len(unresolved))
    if ratio < options.weak_text_noise_batch_ratio_threshold:
        return None
    node_ids = [str(item.get("sourceEvidenceNodeId") or "") for item in weak]
    source_object_ids = [str(item.get("sourceObjectId") or "") for item in weak]
    return BoundaryQualityFinding(
        id=f"bqf_{index:04d}",
        finding_kind="weak_text_noise_batch_dominance",
        decision="fact",
        severity="high",
        source_object_id=None,
        refined_object_id=None,
        unresolved_member_ids=[str(item.get("id") or "") for item in weak[:200]],
        visual_asset_ids=[],
        shape_candidate_ids=[],
        text_member_ids=[],
        source_evidence_node_ids=dedupe_strings(node_ids),
        member_roles=["weak_visual"],
        source_visual_kinds=["text_noise"],
        bbox=None,
        counts=raw_dedup_counts(weak, source_object_ids, node_ids, [parse_bbox(item.get("bbox")) for item in weak], crop_hashes_for_bboxes(pixels, [parse_bbox(item.get("bbox")) for item in weak])),
        ratios={"weakTextNoiseUnresolvedRatio": ratio},
        reasons=["image_unresolved_members_dominated_by_weak_text_noise"],
        risks=["weak_visual_text_noise_dominance"],
        suggested_upstream_layers=[m2904_layer("m2904_consumes_many_text_noise_members", 0.84), m2903_layer("text_noise_source_bucket_dominates_unresolved", 0.62)],
        example_asset_paths=[],
    )


def build_duplicate_source_findings(
    pixels: PngPixels,
    output_dir: Path,
    lookups: dict[str, Any],
    examples: list[dict[str, Any]],
    example_counts: dict[str, int],
    options: M2906Options,
) -> list[DuplicateSourceFinding]:
    member_rows = source_member_rows(lookups)
    groups: list[tuple[str, str, list[dict[str, Any]]]] = []
    groups.extend(group_rows(member_rows, "sameSourceEvidenceNodeAcrossObjects", lambda row: row["sourceEvidenceNodeId"], across_objects=True))
    groups.extend(group_rows(member_rows, "sameSourceEvidenceNodeWithinObject", lambda row: f'{row["sourceObjectId"]}:{row["sourceEvidenceNodeId"]}', within_object=True))
    groups.extend(group_rows(member_rows, "sameBboxAcrossObjects", lambda row: bbox_key(row["bbox"]), across_objects=True))
    groups.extend(group_rows(member_rows, "sameBboxWithinObject", lambda row: f'{row["sourceObjectId"]}:{bbox_key(row["bbox"])}', within_object=True))
    findings: list[DuplicateSourceFinding] = []
    for kind, key, rows in sorted(groups, key=lambda item: len(item[2]), reverse=True)[: options.max_duplicate_groups]:
        bboxes = [row["bbox"] for row in rows if row["bbox"] is not None]
        example_paths: list[str] = []
        for row in rows[: options.max_examples_per_duplicate_group]:
            path = export_example_crop(pixels, output_dir, "duplicate_examples", kind, row["bbox"], examples, example_counts, options, source_id=f'{row["sourceObjectId"]}_{row["sourceEvidenceNodeId"]}')
            if path:
                example_paths.append(path)
        findings.append(
            DuplicateSourceFinding(
                id=f"dsf_{len(findings) + 1:04d}",
                duplicate_kind=kind,
                decision="fact",
                severity="high" if "AcrossObjects" in kind else "medium",
                key=key,
                source_evidence_node_ids=dedupe_strings([row["sourceEvidenceNodeId"] for row in rows if row["sourceEvidenceNodeId"]]),
                source_object_ids=dedupe_strings([row["sourceObjectId"] for row in rows if row["sourceObjectId"]]),
                refined_object_ids=dedupe_strings([row["refinedObjectId"] for row in rows if row["refinedObjectId"]]),
                member_roles=dedupe_strings([row["memberRole"] for row in rows if row["memberRole"]]),
                bboxes=dedupe_bboxes(bboxes),
                counts={
                    "rawMemberCount": len(rows),
                    "uniqueSourceEvidenceNodeCount": len({row["sourceEvidenceNodeId"] for row in rows if row["sourceEvidenceNodeId"]}),
                    "uniqueBboxCount": len({bbox_key(row["bbox"]) for row in rows if row["bbox"] is not None}),
                    "affectedObjectCount": len({row["sourceObjectId"] for row in rows if row["sourceObjectId"]}),
                },
                suggested_upstream_layers=[m2904_layer("same_source_or_bbox_consumed_multiple_times", 0.88)],
                example_asset_paths=dedupe_strings(example_paths),
            )
        )
    return findings


def build_duplicate_asset_findings(
    output_dir: Path,
    m2905_output_dir: Path,
    lookups: dict[str, Any],
    examples: list[dict[str, Any]],
    example_counts: dict[str, int],
    options: M2906Options,
) -> list[DuplicateAssetFinding]:
    rows = visual_asset_rows(m2905_output_dir, lookups)
    findings: list[DuplicateAssetFinding] = []
    duplicate_groups: list[tuple[str, str, FindingDecision, list[dict[str, Any]]]] = []
    duplicate_groups.extend(group_asset_rows(rows, "exactPixelDuplicate", lambda row: row["sha256"], min_size=2, decision="fact"))
    duplicate_groups.extend(group_asset_rows(rows, "sameBboxDuplicate", lambda row: bbox_key(row["bbox"]), min_size=2, decision="fact"))
    duplicate_groups.extend(group_asset_rows(rows, "sameSourceEvidenceDuplicate", lambda row: ",".join(row["sourceEvidenceNodeIds"]), min_size=2, decision="fact"))
    duplicate_groups.extend(perceptual_duplicate_groups(rows, options.perceptual_duplicate_hamming_max))
    duplicate_groups.extend(conflicting_asset_use_groups(rows))
    for kind, key, decision, group_rows_value in sorted(duplicate_groups, key=lambda item: len(item[3]), reverse=True)[: options.max_duplicate_groups]:
        example_paths: list[str] = []
        for row in group_rows_value[: options.max_examples_per_duplicate_group]:
            path = copy_asset_example(output_dir, m2905_output_dir, row, examples, example_counts, options, kind)
            if path:
                example_paths.append(path)
        asset_uses = dedupe_strings([row["assetUse"] for row in group_rows_value if row["assetUse"]])
        findings.append(
            DuplicateAssetFinding(
                id=f"daf_{len(findings) + 1:04d}",
                duplicate_kind="conflictingAssetUseDuplicate" if kind == "conflictingAssetUseDuplicate" else kind,
                decision=decision,
                severity="high" if kind == "conflictingAssetUseDuplicate" else ("medium" if decision == "fact" else "low"),
                key=key,
                visual_asset_ids=dedupe_strings([row["id"] for row in group_rows_value]),
                source_object_ids=dedupe_strings([row["sourceObjectId"] for row in group_rows_value if row["sourceObjectId"]]),
                source_evidence_node_ids=dedupe_strings([node_id for row in group_rows_value for node_id in row["sourceEvidenceNodeIds"]]),
                bboxes=dedupe_bboxes([row["bbox"] for row in group_rows_value if row["bbox"] is not None]),
                asset_uses=asset_uses,
                sha256=key if kind == "exactPixelDuplicate" else (group_rows_value[0]["sha256"] if kind == "conflictingAssetUseDuplicate" else None),
                perceptual_hash=key if kind == "perceptualDuplicateCandidate" else None,
                counts={
                    "rawAssetCount": len(group_rows_value),
                    "uniqueSourceEvidenceNodeCount": len({node_id for row in group_rows_value for node_id in row["sourceEvidenceNodeIds"]}),
                    "uniqueBboxCount": len({bbox_key(row["bbox"]) for row in group_rows_value if row["bbox"] is not None}),
                    "uniqueCropHashCount": len({row["sha256"] for row in group_rows_value if row["sha256"]}),
                    "affectedObjectCount": len({row["sourceObjectId"] for row in group_rows_value if row["sourceObjectId"]}),
                },
                suggested_upstream_layers=[asset_layer("visual_assets_can_share_identity", 0.84)] if kind in {"exactPixelDuplicate", "perceptualDuplicateCandidate"} else [m2905_layer("asset_use_classification_conflict", 0.78), asset_layer("dedup_before_reuse", 0.58)],
                example_asset_paths=dedupe_strings(example_paths),
            )
        )
    return findings


def build_success_baseline(lookups: dict[str, Any]) -> dict[str, Any]:
    objects = lookups["refinedObjects"]
    visual_assets = lookups["visualAssets"]
    successful_assets = [item for item in visual_assets if str(item.get("assetUse") or "") in {"image_asset", "icon_asset"}]
    overlaps = sorted(float(item.get("textOverlapRatio") or 0.0) for item in successful_assets)
    successful_object_kinds = [str(item.get("sourceObjectKind") or "") for item in objects if str(item.get("decision") or "") in {"separated", "visual_only", "text_only"}]
    return {
        "separatedCount": count_where(objects, "decision", "separated"),
        "visualOnlyCount": count_where(objects, "decision", "visual_only"),
        "textOnlyCount": count_where(objects, "decision", "text_only"),
        "successfulVisualAssetCount": len(successful_assets),
        "medianSuccessfulVisualTextOverlap": round(median(overlaps), 4) if overlaps else 0.0,
        "p90SuccessfulVisualTextOverlap": round(percentile(overlaps, 0.90), 4) if overlaps else 0.0,
        "sourceVisualKindsInSuccessfulAssets": count_values(node_visual_kinds_for_assets(successful_assets, lookups)),
        "objectKindsWithHighSuccessRate": count_values(successful_object_kinds),
        "successfulMemberRoleDistribution": success_member_role_distribution(objects, lookups),
    }


def build_summary(
    pixels: PngPixels,
    lookups: dict[str, Any],
    findings: list[BoundaryQualityFinding],
    duplicate_source_findings: list[DuplicateSourceFinding],
    duplicate_asset_findings: list[DuplicateAssetFinding],
    success_baseline: dict[str, Any],
) -> dict[str, Any]:
    unresolved = lookups["unresolvedMembers"]
    weak = [item for item in unresolved if unresolved_is_weak_text_noise(item, lookups)]
    node_ids = [str(item.get("sourceEvidenceNodeId") or "") for item in unresolved]
    bboxes = [parse_bbox(item.get("bbox")) for item in unresolved]
    weak_node_ids = [str(item.get("sourceEvidenceNodeId") or "") for item in weak]
    weak_bboxes = [parse_bbox(item.get("bbox")) for item in weak]
    return {
        "unresolved": raw_dedup_counts(unresolved, [str(item.get("sourceObjectId") or "") for item in unresolved], node_ids, bboxes, crop_hashes_for_bboxes(pixels, bboxes)),
        "weakTextNoise": raw_dedup_counts(weak, [str(item.get("sourceObjectId") or "") for item in weak], weak_node_ids, weak_bboxes, crop_hashes_for_bboxes(pixels, weak_bboxes)),
        "weakTextNoiseUnresolvedRatio": round(len(weak) / max(1, len(unresolved)), 4),
        "findingKindCounts": count_values([item.finding_kind for item in findings]),
        "duplicateSourceKindCounts": count_values([item.duplicate_kind for item in duplicate_source_findings]),
        "duplicateAssetKindCounts": count_values([item.duplicate_kind for item in duplicate_asset_findings]),
        "successBaseline": success_baseline,
    }


def write_debug_artifacts(
    pixels: PngPixels,
    output_dir: Path,
    lookups: dict[str, Any],
    findings: list[BoundaryQualityFinding],
    duplicate_source_findings: list[DuplicateSourceFinding],
    duplicate_asset_findings: list[DuplicateAssetFinding],
) -> M2906DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "memberBoundaryRisks": overlay_dir / "25_member_boundary_risks.png",
        "unresolvedAttribution": overlay_dir / "26_unresolved_attribution.png",
        "duplicateSources": overlay_dir / "27_duplicate_sources.png",
        "duplicateAssets": overlay_dir / "28_duplicate_assets.png",
    }
    paths["memberBoundaryRisks"].write_bytes(overlay_findings(pixels, findings, {"weak_text_noise_member": (235, 64, 52), "weak_text_noise_object_dominance": (238, 140, 40), "shape_with_text_overlay": (0, 122, 255)}))
    paths["unresolvedAttribution"].write_bytes(overlay_unresolved(pixels, lookups))
    paths["duplicateSources"].write_bytes(overlay_duplicate_sources(pixels, duplicate_source_findings))
    paths["duplicateAssets"].write_bytes(overlay_duplicate_assets(pixels, duplicate_asset_findings))
    return M2906DebugArtifacts(
        member_boundary_risks=str(paths["memberBoundaryRisks"].relative_to(output_dir)),
        unresolved_attribution=str(paths["unresolvedAttribution"].relative_to(output_dir)),
        duplicate_sources=str(paths["duplicateSources"].relative_to(output_dir)),
        duplicate_assets=str(paths["duplicateAssets"].relative_to(output_dir)),
    )


def write_outputs(document: M2906Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "member_boundary_quality_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "unresolved_reason_summary.json").write_text(json.dumps(document.summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "duplicate_source_audit.json").write_text(json.dumps([item.to_dict() for item in document.duplicate_source_findings], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "duplicate_asset_audit.json").write_text(json.dumps([item.to_dict() for item in document.duplicate_asset_findings], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "success_baseline_summary.json").write_text(json.dumps(document.success_baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "member_boundary_quality_audit.md").write_text(build_markdown_report(document), encoding="utf-8")


def write_batch_summary(documents: list[tuple[str, M2906Document]], batch_root: Path) -> None:
    rows: list[dict[str, Any]] = []
    for image_id, document in documents:
        summary = document.summary
        weak = summary.get("weakTextNoise", {})
        unresolved = summary.get("unresolved", {})
        rows.append(
            {
                "image": image_id,
                "rawUnresolved": unresolved.get("rawMemberCount", 0),
                "uniqueUnresolvedSources": unresolved.get("uniqueSourceEvidenceNodeCount", 0),
                "rawWeakTextNoise": weak.get("rawMemberCount", 0),
                "uniqueWeakTextNoiseSources": weak.get("uniqueSourceEvidenceNodeCount", 0),
                "weakTextNoiseUnresolvedRatio": summary.get("weakTextNoiseUnresolvedRatio", 0),
                "findingCount": document.meta.get("findingCount", 0),
                "duplicateSourceFindingCount": document.meta.get("duplicateSourceFindingCount", 0),
                "duplicateAssetFindingCount": document.meta.get("duplicateAssetFindingCount", 0),
                "separatedCount": document.success_baseline.get("separatedCount", 0),
                "visualOnlyCount": document.success_baseline.get("visualOnlyCount", 0),
            }
        )
    (batch_root / "m29_0_6_batch_summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (batch_root / "m29_0_6_batch_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["image"])
        writer.writeheader()
        writer.writerows(rows)


def build_markdown_report(document: M2906Document) -> str:
    lines = [
        "# M29.0.6 Member Boundary Quality Audit",
        "",
        f"- Source M29.0.5: `{document.source_m2905_refined_visual_objects_json}`",
        f"- Findings: {len(document.findings)}",
        f"- Duplicate source findings: {len(document.duplicate_source_findings)}",
        f"- Duplicate asset findings: {len(document.duplicate_asset_findings)}",
        f"- Weak text-noise ratio: {document.summary.get('weakTextNoiseUnresolvedRatio', 0)}",
        f"- Success baseline: `{document.success_baseline}`",
        "",
        "## Top Finding Kinds",
        "",
    ]
    for key, value in sorted(document.summary.get("findingKindCounts", {}).items(), key=lambda item: item[1], reverse=True)[:12]:
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Top Findings", ""])
    for finding in document.findings[:80]:
        lines.append(f"- `{finding.id}` `{finding.finding_kind}` severity=`{finding.severity}` counts=`{finding.counts}` ratios=`{finding.ratios}`")
    lines.extend(["", "## Duplicate Assets", ""])
    for finding in document.duplicate_asset_findings[:40]:
        lines.append(f"- `{finding.id}` `{finding.duplicate_kind}` decision=`{finding.decision}` assets={len(finding.visual_asset_ids)} uses=`{finding.asset_uses}`")
    return "\n".join(lines).rstrip() + "\n"


def validate_member_boundary_quality_audit_document(document: M2906Document, output_dir: Path, width: int, height: int, m2905_document: dict[str, Any], m2904_document: dict[str, Any]) -> None:
    if document.schema_name != "M2906MemberBoundaryQualityAuditDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.6 document schema")
    refined_ids = {str(item.get("id")) for item in m2905_document.get("objects", []) if isinstance(item, dict) and item.get("id")}
    source_object_ids = {str(item.get("id")) for item in m2904_document.get("objects", []) if isinstance(item, dict) and item.get("id")}
    unresolved_ids = {str(item.get("id")) for item in m2905_document.get("unresolvedMembers", []) if isinstance(item, dict) and item.get("id")}
    visual_asset_ids = {str(item.get("id")) for item in m2905_document.get("visualAssets", []) if isinstance(item, dict) and item.get("id")}
    source_node_ids = {str(item.get("id")) for item in m2904_document.get("evidenceNodes", []) if isinstance(item, dict) and item.get("id")}
    assert_unique([item.id for item in document.findings], "finding")
    assert_unique([item.id for item in document.duplicate_source_findings], "duplicate source finding")
    assert_unique([item.id for item in document.duplicate_asset_findings], "duplicate asset finding")
    if "rawMemberCount" not in document.summary.get("unresolved", {}) or "uniqueSourceEvidenceNodeCount" not in document.summary.get("unresolved", {}):
        raise ValueError("M29.0.6 summary must include raw and dedup counts")
    for finding in document.findings:
        if finding.severity == "high" and not finding.suggested_upstream_layers:
            raise ValueError(f"M29.0.6 high severity finding requires suggestedUpstreamLayers: {finding.id}")
        if finding.refined_object_id and finding.refined_object_id not in refined_ids:
            raise ValueError(f"M29.0.6 finding references missing refined object: {finding.id}")
        if finding.source_object_id and finding.source_object_id not in source_object_ids:
            raise ValueError(f"M29.0.6 finding references missing source object: {finding.id}")
        for unresolved_id in finding.unresolved_member_ids:
            if unresolved_id not in unresolved_ids:
                raise ValueError(f"M29.0.6 finding references missing unresolved member: {finding.id}")
        for visual_id in finding.visual_asset_ids:
            if visual_id not in visual_asset_ids:
                raise ValueError(f"M29.0.6 finding references missing visual asset: {finding.id}")
        for node_id in finding.source_evidence_node_ids:
            if node_id and node_id not in source_node_ids:
                raise ValueError(f"M29.0.6 finding references missing evidence node: {finding.id}")
        if finding.bbox is not None and not bbox_in_bounds(finding.bbox, width, height):
            raise ValueError(f"M29.0.6 finding bbox out of bounds: {finding.id}")
        for path in finding.example_asset_paths:
            assert_readable_png(output_dir, path)
    for finding in document.duplicate_asset_findings:
        if finding.duplicate_kind == "perceptualDuplicateCandidate" and finding.decision == "fact":
            raise ValueError("M29.0.6 perceptual duplicate cannot be fact")
        if finding.duplicate_kind == "exactPixelDuplicate" and not finding.sha256:
            raise ValueError("M29.0.6 exact duplicate requires sha256")
        for visual_id in finding.visual_asset_ids:
            if visual_id not in visual_asset_ids:
                raise ValueError(f"M29.0.6 duplicate asset references missing visual asset: {finding.id}")
        for path in finding.example_asset_paths:
            assert_readable_png(output_dir, path)
    for finding in document.duplicate_source_findings:
        for node_id in finding.source_evidence_node_ids:
            if node_id and node_id not in source_node_ids:
                raise ValueError(f"M29.0.6 duplicate source references missing evidence node: {finding.id}")
        for path in finding.example_asset_paths:
            assert_readable_png(output_dir, path)
    for path in document.debug.to_dict().values():
        metadata = assert_readable_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.0.6 overlay dimensions do not match source image: {path}")
    assert_readable_png(output_dir, "preview_member_boundary_quality.png")


def unresolved_is_weak_text_noise(unresolved: dict[str, Any], lookups: dict[str, Any]) -> bool:
    if str(unresolved.get("memberRole") or "") != "weak_visual":
        return False
    node = lookups["nodeById"].get(str(unresolved.get("sourceEvidenceNodeId") or ""))
    return str((node or {}).get("sourceVisualKind") or "") == "text_noise"


def source_member_rows(lookups: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_object in lookups["m2904Objects"]:
        source_object_id = str(source_object.get("id") or "")
        refined = lookups["refinedBySource"].get(source_object_id, {})
        for member in source_object.get("members", []):
            if not isinstance(member, dict):
                continue
            rows.append(
                {
                    "sourceObjectId": source_object_id,
                    "refinedObjectId": str(refined.get("id") or ""),
                    "sourceEvidenceNodeId": str(member.get("evidenceNodeId") or ""),
                    "memberRole": str(member.get("memberRole") or ""),
                    "bbox": parse_bbox(member.get("bbox")),
                }
            )
    return rows


def group_rows(rows: list[dict[str, Any]], kind: str, key_fn: Any, *, across_objects: bool = False, within_object: bool = False) -> list[tuple[str, str, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(key_fn(row) or "")
        if not key or key == "None":
            continue
        groups.setdefault(key, []).append(row)
    results: list[tuple[str, str, list[dict[str, Any]]]] = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        object_count = len({row["sourceObjectId"] for row in group})
        if across_objects and object_count < 2:
            continue
        if within_object and object_count != 1:
            continue
        results.append((kind, key, group))
    return results


def visual_asset_rows(m2905_output_dir: Path, lookups: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in lookups["visualAssets"]:
        asset_path = str(asset.get("assetPath") or "")
        resolved = m2905_output_dir / asset_path
        data = resolved.read_bytes() if resolved.exists() else b""
        pixels: PngPixels | None = None
        perceptual = ""
        if data:
            try:
                pixels = decode_png_pixels(data)
                perceptual = average_hash(pixels)
            except UnsupportedPngCropError:
                pixels = None
        rows.append(
            {
                "id": str(asset.get("id") or ""),
                "sourceObjectId": str(asset.get("sourceObjectId") or ""),
                "sourceEvidenceNodeIds": [str(item) for item in asset.get("sourceEvidenceNodeIds", [])],
                "bbox": parse_bbox(asset.get("bbox")),
                "assetUse": str(asset.get("assetUse") or ""),
                "assetPath": asset_path,
                "sha256": hashlib.sha256(data).hexdigest() if data else "",
                "perceptualHash": perceptual,
                "pixels": pixels,
            }
        )
    return rows


def group_asset_rows(rows: list[dict[str, Any]], kind: str, key_fn: Any, *, min_size: int, decision: FindingDecision) -> list[tuple[str, str, FindingDecision, list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(key_fn(row) or "")
        if not key or key == "None":
            continue
        groups.setdefault(key, []).append(row)
    return [(kind, key, decision, group) for key, group in groups.items() if len(group) >= min_size]


def perceptual_duplicate_groups(rows: list[dict[str, Any]], max_hamming: int) -> list[tuple[str, str, FindingDecision, list[dict[str, Any]]]]:
    candidates = [row for row in rows if row.get("perceptualHash")]
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(candidates)):
        for right in range(left + 1, len(candidates)):
            if hamming_distance_hex(str(candidates[left]["perceptualHash"]), str(candidates[right]["perceptualHash"])) <= max_hamming:
                union(left, right)
    groups: dict[int, list[dict[str, Any]]] = {}
    for index, row in enumerate(candidates):
        groups.setdefault(find(index), []).append(row)
    results: list[tuple[str, str, FindingDecision, list[dict[str, Any]]]] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        key = ",".join(sorted({str(row["perceptualHash"]) for row in group}))
        results.append(("perceptualDuplicateCandidate", key, "candidate", group))
    return results


def conflicting_asset_use_groups(rows: list[dict[str, Any]]) -> list[tuple[str, str, FindingDecision, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = f'{row["sha256"]}:{bbox_key(row["bbox"])}:{",".join(row["sourceEvidenceNodeIds"])}'
        grouped.setdefault(key, []).append(row)
    results = []
    for key, group in grouped.items():
        uses = {row["assetUse"] for row in group}
        if len(group) >= 2 and {"image_asset", "icon_asset"} <= uses:
            results.append(("conflictingAssetUseDuplicate", key, "fact", group))
    return results


def hamming_distance_hex(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 65


def text_boxes_inside_bbox(bbox: list[int] | None, lookups: dict[str, Any]) -> bool:
    if bbox is None:
        return False
    text_boxes = [parse_bbox(item.get("bbox")) for item in lookups["m2902"].get("textBoxes", []) if isinstance(item, dict)]
    return any(candidate is not None and bbox_contains(bbox, candidate) for candidate in text_boxes)


def raw_dedup_counts(items: list[dict[str, Any]], source_object_ids: list[str], node_ids: list[str], bboxes: list[list[int] | None], crop_hashes: list[str] | None) -> dict[str, Any]:
    return {
        "rawMemberCount": len(items),
        "uniqueSourceEvidenceNodeCount": len({node_id for node_id in node_ids if node_id}),
        "uniqueBboxCount": len({bbox_key(bbox) for bbox in bboxes if bbox is not None}),
        "uniqueCropHashCount": len({value for value in crop_hashes or [] if value}),
        "affectedObjectCount": len({source_object_id for source_object_id in source_object_ids if source_object_id}),
        "affectedImageCount": 1 if items else 0,
    }


def crop_hashes_for_bboxes(pixels: PngPixels, bboxes: list[list[int] | None]) -> list[str]:
    hashes: list[str] = []
    for bbox in bboxes:
        if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            continue
        hashes.append(hashlib.sha256(crop_pixels(pixels, bbox)).hexdigest())
    return hashes


def export_example_crop(
    pixels: PngPixels,
    output_dir: Path,
    folder: str,
    kind: str,
    bbox: list[int] | None,
    examples: list[dict[str, Any]],
    example_counts: dict[str, int],
    options: M2906Options,
    *,
    source_id: str,
) -> str | None:
    if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
        return None
    count = example_counts.get(kind, 0)
    if count >= options.max_examples_per_finding_kind:
        return None
    example_counts[kind] = count + 1
    target = output_dir / "assets" / folder
    target.mkdir(parents=True, exist_ok=True)
    safe_source = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in source_id)[:60]
    path = target / f"{kind}_{count + 1:04d}_{safe_source}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    rel = str(path.relative_to(output_dir))
    examples.append({"findingKind": kind, "sourceId": source_id, "bbox": bbox, "assetPath": rel})
    return rel


def copy_asset_example(output_dir: Path, m2905_output_dir: Path, row: dict[str, Any], examples: list[dict[str, Any]], example_counts: dict[str, int], options: M2906Options, kind: str) -> str | None:
    count = example_counts.get(kind, 0)
    if count >= options.max_examples_per_finding_kind:
        return None
    source = m2905_output_dir / row["assetPath"]
    if not source.exists():
        return None
    example_counts[kind] = count + 1
    target = output_dir / "assets" / "duplicate_examples"
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{kind}_{count + 1:04d}_{row['id']}.png"
    path.write_bytes(source.read_bytes())
    rel = str(path.relative_to(output_dir))
    examples.append({"findingKind": kind, "sourceId": row["id"], "bbox": row["bbox"], "assetPath": rel})
    return rel


def average_hash(pixels: PngPixels, size: int = 8) -> str:
    values: list[int] = []
    for yy in range(size):
        y = min(pixels.height - 1, int((yy + 0.5) * pixels.height / size))
        row = pixels.rows[y]
        for xx in range(size):
            x = min(pixels.width - 1, int((xx + 0.5) * pixels.width / size))
            index = x * 3
            r, g, b = row[index], row[index + 1], row[index + 2]
            values.append((r * 30 + g * 59 + b * 11) // 100)
    avg = sum(values) / max(1, len(values))
    bits = "".join("1" if value >= avg else "0" for value in values)
    return f"{int(bits, 2):016x}"


def build_preview_sheet(pixels: PngPixels, output_dir: Path, debug: M2906DebugArtifacts, examples: list[dict[str, Any]], options: M2906Options) -> bytes:
    overlays = [decode_png_pixels((output_dir / path).read_bytes()) for path in debug.to_dict().values()]
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.30, (sheet_width - margin * 2 - gap * 4) / max(1, pixels.width * 5))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    previews = crop_previews(output_dir, examples, options.output_preview_max_thumb)
    grid_h = grid_height(previews, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, *overlays]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, previews, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews(output_dir: Path, examples: list[dict[str, Any]], max_edge: int) -> list[tuple[str, PngPixels, int, int]]:
    previews: list[tuple[str, PngPixels, int, int]] = []
    for example in examples[:160]:
        path = example.get("assetPath")
        if not path:
            continue
        try:
            crop = decode_png_pixels((output_dir / path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, crop.width, crop.height))
        previews.append((str(example.get("findingKind") or ""), crop, max(1, round(crop.width * scale)), max(1, round(crop.height * scale))))
    return previews


def overlay_findings(pixels: PngPixels, findings: list[BoundaryQualityFinding], colors: dict[str, tuple[int, int, int]]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for finding in findings:
        if finding.bbox is not None:
            draw_rect(rows, pixels.width, pixels.height, finding.bbox, colors.get(finding.finding_kind, (238, 140, 40)), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_unresolved(pixels: PngPixels, lookups: dict[str, Any]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for unresolved in lookups["unresolvedMembers"]:
        bbox = parse_bbox(unresolved.get("bbox"))
        if bbox is not None:
            color = (235, 64, 52) if unresolved_is_weak_text_noise(unresolved, lookups) else (238, 140, 40)
            draw_rect(rows, pixels.width, pixels.height, bbox, color, 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_duplicate_sources(pixels: PngPixels, findings: list[DuplicateSourceFinding]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for finding in findings[:120]:
        for bbox in finding.bboxes[:6]:
            draw_rect(rows, pixels.width, pixels.height, bbox, (180, 60, 220), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_duplicate_assets(pixels: PngPixels, findings: list[DuplicateAssetFinding]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for finding in findings[:120]:
        for bbox in finding.bboxes[:6]:
            draw_rect(rows, pixels.width, pixels.height, bbox, (0, 122, 255), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_meta(findings: list[BoundaryQualityFinding], duplicate_source_findings: list[DuplicateSourceFinding], duplicate_asset_findings: list[DuplicateAssetFinding], examples: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "notes": "m29_0_6_member_boundary_quality_audit",
        "findingCount": len(findings),
        "duplicateSourceFindingCount": len(duplicate_source_findings),
        "duplicateAssetFindingCount": len(duplicate_asset_findings),
        "exampleCount": len(examples),
        "findingKindCounts": count_values([item.finding_kind for item in findings]),
        "duplicateSourceKindCounts": count_values([item.duplicate_kind for item in duplicate_source_findings]),
        "duplicateAssetKindCounts": count_values([item.duplicate_kind for item in duplicate_asset_findings]),
    }


def reindex_findings(findings: list[BoundaryQualityFinding]) -> list[BoundaryQualityFinding]:
    return [
        BoundaryQualityFinding(
            id=f"bqf_{index + 1:04d}",
            finding_kind=item.finding_kind,
            decision=item.decision,
            severity=item.severity,
            source_object_id=item.source_object_id,
            refined_object_id=item.refined_object_id,
            unresolved_member_ids=item.unresolved_member_ids,
            visual_asset_ids=item.visual_asset_ids,
            shape_candidate_ids=item.shape_candidate_ids,
            text_member_ids=item.text_member_ids,
            source_evidence_node_ids=item.source_evidence_node_ids,
            member_roles=item.member_roles,
            source_visual_kinds=item.source_visual_kinds,
            bbox=item.bbox,
            counts=item.counts,
            ratios=item.ratios,
            reasons=item.reasons,
            risks=item.risks,
            suggested_upstream_layers=item.suggested_upstream_layers,
            example_asset_paths=item.example_asset_paths,
        )
        for index, item in enumerate(findings)
    ]


def weak_text_noise_layer(reason: str) -> SuggestedUpstreamLayer:
    return SuggestedUpstreamLayer(layer="m29_0_4", confidence=0.82, reason=f"weak_text_noise_{reason}_is_consumed_by_object_member_graph")


def m2902_layer(reason: str, confidence: float) -> SuggestedUpstreamLayer:
    return SuggestedUpstreamLayer(layer="m29_0_2", confidence=confidence, reason=reason)


def m2903_layer(reason: str, confidence: float) -> SuggestedUpstreamLayer:
    return SuggestedUpstreamLayer(layer="m29_0_3", confidence=confidence, reason=reason)


def m2904_layer(reason: str, confidence: float) -> SuggestedUpstreamLayer:
    return SuggestedUpstreamLayer(layer="m29_0_4", confidence=confidence, reason=reason)


def m2905_layer(reason: str, confidence: float) -> SuggestedUpstreamLayer:
    return SuggestedUpstreamLayer(layer="m29_0_5", confidence=confidence, reason=reason)


def asset_layer(reason: str, confidence: float) -> SuggestedUpstreamLayer:
    return SuggestedUpstreamLayer(layer="asset_dedup", confidence=confidence, reason=reason)


def manual_layer(reason: str, confidence: float) -> SuggestedUpstreamLayer:
    return SuggestedUpstreamLayer(layer="manual_review", confidence=confidence, reason=reason)


def node_visual_kinds_for_assets(assets: list[dict[str, Any]], lookups: dict[str, Any]) -> list[str]:
    kinds: list[str] = []
    for asset in assets:
        for node_id in asset.get("sourceEvidenceNodeIds", []):
            node = lookups["nodeById"].get(str(node_id))
            if node and node.get("sourceVisualKind"):
                kinds.append(str(node.get("sourceVisualKind")))
    return kinds


def success_member_role_distribution(objects: list[dict[str, Any]], lookups: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for refined in objects:
        if str(refined.get("decision") or "") not in {"separated", "visual_only", "text_only"}:
            continue
        source = lookups["m2904ById"].get(str(refined.get("sourceObjectId") or ""), {})
        for member in source.get("members", []):
            if isinstance(member, dict):
                role = str(member.get("memberRole") or "")
                counts[role] = counts.get(role, 0) + 1
    return dict(sorted(counts.items()))


def count_where(items: list[dict[str, Any]], key: str, value: str) -> int:
    return sum(1 for item in items if str(item.get(key) or "") == value)


def count_values(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if not item:
            continue
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, round((len(values) - 1) * ratio)))
    return values[index]


def bbox_key(bbox: list[int] | None) -> str:
    return ",".join(str(value) for value in bbox) if bbox else ""


def dedupe_bboxes(bboxes: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    seen: set[str] = set()
    for bbox in bboxes:
        key = bbox_key(bbox)
        if key and key not in seen:
            seen.add(key)
            result.append(bbox)
    return result


def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def assert_unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate M29.0.6 {label} id: {value}")
        seen.add(value)
    return seen


def assert_readable_png(output_dir: Path, path: str):
    resolved = output_dir / path
    if not resolved.exists():
        raise ValueError(f"M29.0.6 PNG output missing or unreadable: {path}")
    metadata = read_png_metadata(resolved.read_bytes())
    if metadata is None:
        raise ValueError(f"M29.0.6 PNG output missing or unreadable: {path}")
    return metadata


def grid_height(previews: list[tuple[str, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _label, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[str, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for label, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, frame_color(label))
        fill_rect(canvas, sheet_width, x - 2, y - 2, width + 4, height + 4, (244, 244, 244))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]


def fill_rect(canvas: list[bytearray], sheet_width: int, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def frame_color(label: str) -> tuple[int, int, int]:
    if "duplicate" in label:
        return (0, 122, 255)
    if "weak" in label or "unresolved" in label:
        return (235, 64, 52)
    if "shape" in label:
        return (0, 180, 210)
    return (238, 140, 40)
