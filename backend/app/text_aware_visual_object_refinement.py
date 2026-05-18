from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_evidence_normalization import parse_bbox, parse_metrics
from .visual_primitive_graph import (
    M29PrimitiveMetrics,
    bbox_area,
    bbox_gap_distance,
    bbox_in_bounds,
    bbox_x2,
    bbox_y2,
    crop_pixels,
    draw_rect,
    metrics_to_dict,
)


RefinedObjectDecision = Literal["separated", "partially_separated", "visual_only", "text_only", "unresolved", "split_needed", "rejected"]
VisualKind = Literal["image_like", "icon_like", "weak_visual", "unknown_visual"]
VisualAssetUse = Literal["image_asset", "icon_asset", "audit_only", "unresolved"]
VisualAssetDecision = Literal["accepted", "candidate", "uncertain", "rejected"]
ShapeDecision = Literal["candidate", "uncertain", "rejected"]
TextMemberSource = Literal["m2904_member", "m2902_text_box"]
UnresolvedReason = Literal[
    "text_touching_visual",
    "high_text_overlap",
    "weak_visual",
    "noise_member",
    "wide_source",
    "source_conflict",
    "missing_lookup",
    "unsafe_union",
    "invalid_bbox",
]


@dataclass(frozen=True)
class M2905Options:
    text_preview_max_chars: int = 24
    visual_asset_text_overlap_max: float = 0.12
    icon_asset_text_overlap_max: float = 0.18
    weak_visual_text_overlap_max: float = 0.28
    min_visual_asset_area: int = 16
    max_icon_asset_area: int = 12000
    max_icon_asset_edge: int = 128
    max_visual_union_members: int = 4
    max_visual_union_gap: int = 12
    min_separation_quality: float = 0.62
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M2905SourceExpansionRefs:
    m29_nodes_json: str | None = None
    m291_group_nodes_json: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "m29NodesJson": self.m29_nodes_json,
            "m291GroupNodesJson": self.m291_group_nodes_json,
        }


@dataclass(frozen=True)
class RefinedVisualObject:
    id: str
    source_object_id: str
    source_object_kind: str
    source_decision: str
    bbox: list[int]
    decision: RefinedObjectDecision
    combined_asset_path: str
    combined_asset_use: Literal["audit_only"]
    visual_asset_ids: list[str]
    shape_candidate_ids: list[str]
    text_member_ids: list[str]
    unresolved_member_ids: list[str]
    risks: list[str]
    reasons: list[str]
    separation_quality: float
    suggested_next_action: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceObjectKind": self.source_object_kind,
            "sourceDecision": self.source_decision,
            "bbox": self.bbox,
            "decision": self.decision,
            "combinedAssetPath": self.combined_asset_path,
            "combinedAssetUse": self.combined_asset_use,
            "visualAssetIds": self.visual_asset_ids,
            "shapeCandidateIds": self.shape_candidate_ids,
            "textMemberIds": self.text_member_ids,
            "unresolvedMemberIds": self.unresolved_member_ids,
            "risks": self.risks,
            "reasons": self.reasons,
            "separationQuality": round(self.separation_quality, 3),
            "suggestedNextAction": self.suggested_next_action,
        }


@dataclass(frozen=True)
class RefinedVisualAsset:
    id: str
    source_object_id: str
    source_evidence_node_ids: list[str]
    bbox: list[int]
    visual_kind: VisualKind
    asset_use: VisualAssetUse
    decision: VisualAssetDecision
    asset_path: str | None
    text_overlap_ratio: float
    metrics: M29PrimitiveMetrics | None
    risks: list[str]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceEvidenceNodeIds": self.source_evidence_node_ids,
            "bbox": self.bbox,
            "visualKind": self.visual_kind,
            "assetUse": self.asset_use,
            "decision": self.decision,
            "assetPath": self.asset_path,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "metrics": metrics_to_dict(self.metrics) if self.metrics is not None else None,
            "risks": self.risks,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class ShapeCandidate:
    id: str
    source_object_id: str
    source_evidence_node_ids: list[str]
    bbox: list[int]
    asset_use: Literal["shape_candidate"]
    decision: ShapeDecision
    metrics: M29PrimitiveMetrics | None
    color: str | None
    text_overlap_ratio: float
    reasons: list[str]
    risks: list[str]
    preview_asset_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceEvidenceNodeIds": self.source_evidence_node_ids,
            "bbox": self.bbox,
            "assetUse": self.asset_use,
            "decision": self.decision,
            "metrics": metrics_to_dict(self.metrics) if self.metrics is not None else None,
            "color": self.color,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "reasons": self.reasons,
            "risks": self.risks,
            "previewAssetPath": self.preview_asset_path,
        }


@dataclass(frozen=True)
class RefinedTextMember:
    id: str
    source_object_id: str
    source: TextMemberSource
    source_evidence_node_id: str | None
    source_text_box_id: str | None
    bbox: list[int]
    text_preview: str
    text: str | None
    confidence: float
    risks: list[str]
    reasons: list[str]
    preview_asset_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "source": self.source,
            "sourceEvidenceNodeId": self.source_evidence_node_id,
            "sourceTextBoxId": self.source_text_box_id,
            "bbox": self.bbox,
            "textPreview": self.text_preview,
            "text": self.text,
            "confidence": round(self.confidence, 3),
            "risks": self.risks,
            "reasons": self.reasons,
            "previewAssetPath": self.preview_asset_path,
        }


@dataclass(frozen=True)
class UnresolvedMember:
    id: str
    source_object_id: str
    source_evidence_node_id: str | None
    bbox: list[int]
    member_role: str
    reason: UnresolvedReason
    risks: list[str]
    suggested_next_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceEvidenceNodeId": self.source_evidence_node_id,
            "bbox": self.bbox,
            "memberRole": self.member_role,
            "reason": self.reason,
            "risks": self.risks,
            "suggestedNextAction": self.suggested_next_action,
        }


@dataclass(frozen=True)
class TextVisualSeparationAuditItem:
    id: str
    source_object_id: str
    refined_object_id: str
    decision: RefinedObjectDecision
    visual_asset_ids: list[str]
    shape_candidate_ids: list[str]
    text_member_ids: list[str]
    unresolved_member_ids: list[str]
    combined_asset_path: str
    risks: list[str]
    reasons: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "refinedObjectId": self.refined_object_id,
            "decision": self.decision,
            "visualAssetIds": self.visual_asset_ids,
            "shapeCandidateIds": self.shape_candidate_ids,
            "textMemberIds": self.text_member_ids,
            "unresolvedMemberIds": self.unresolved_member_ids,
            "combinedAssetPath": self.combined_asset_path,
            "risks": self.risks,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class M2905DebugArtifacts:
    visual_assets: str
    text_members: str
    text_visual_separation: str
    unresolved_refinement: str
    shape_candidates: str

    def to_dict(self) -> dict[str, str]:
        return {
            "visualAssets": self.visual_assets,
            "textMembers": self.text_members,
            "textVisualSeparation": self.text_visual_separation,
            "unresolvedRefinement": self.unresolved_refinement,
            "shapeCandidates": self.shape_candidates,
        }


@dataclass(frozen=True)
class M2905Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2904_visual_object_candidates_json: str
    source_m2903_visual_evidence_json: str
    source_m2902_audit_json: str
    source_expansion_refs: M2905SourceExpansionRefs
    options: M2905Options
    objects: list[RefinedVisualObject]
    visual_assets: list[RefinedVisualAsset]
    shape_candidates: list[ShapeCandidate]
    text_members: list[RefinedTextMember]
    unresolved_members: list[UnresolvedMember]
    audit: list[TextVisualSeparationAuditItem]
    debug: M2905DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2904VisualObjectCandidatesJson": self.source_m2904_visual_object_candidates_json,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "sourceExpansionRefs": self.source_expansion_refs.to_dict(),
            "options": self.options.to_dict(),
            "objects": [item.to_dict() for item in self.objects],
            "visualAssets": [item.to_dict() for item in self.visual_assets],
            "shapeCandidates": [item.to_dict() for item in self.shape_candidates],
            "textMembers": [item.to_dict() for item in self.text_members],
            "unresolvedMembers": [item.to_dict() for item in self.unresolved_members],
            "audit": [item.to_dict() for item in self.audit],
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_text_aware_visual_object_refinement(
    *,
    png_data: bytes,
    source_image: str,
    m2904_document: dict[str, Any],
    m2904_visual_object_candidates_json_path: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    source_expansion_refs: M2905SourceExpansionRefs | None = None,
    options: M2905Options | None = None,
    warnings: list[str] | None = None,
) -> M2905Document:
    options = options or M2905Options()
    source_expansion_refs = source_expansion_refs or M2905SourceExpansionRefs()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    lookups = build_lookup_maps(m2904_document, m2903_document, m2902_document, pixels.width, pixels.height, options)
    objects, visual_assets, shape_candidates, text_members, unresolved_members, audit = refine_objects(
        pixels=pixels,
        output_dir=output_dir,
        lookups=lookups,
        options=options,
    )
    debug = write_debug_artifacts(pixels, output_dir, objects, visual_assets, shape_candidates, text_members, unresolved_members)
    preview_path = output_dir / "preview_text_aware_refinement.png"
    preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, objects, visual_assets, shape_candidates, text_members, unresolved_members, options))
    document = M2905Document(
        schema_name="M2905TextAwareVisualObjectRefinementDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2904_visual_object_candidates_json=m2904_visual_object_candidates_json_path,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        source_expansion_refs=source_expansion_refs,
        options=options,
        objects=objects,
        visual_assets=visual_assets,
        shape_candidates=shape_candidates,
        text_members=text_members,
        unresolved_members=unresolved_members,
        audit=audit,
        debug=debug,
        warnings=warnings or [],
        meta=build_meta(objects, visual_assets, shape_candidates, text_members, unresolved_members, audit),
    )
    validate_text_aware_visual_object_refinement_document(document, output_dir, pixels.width, pixels.height, m2904_document, m2902_document)
    write_outputs(document, output_dir)
    return document


def build_lookup_maps(
    m2904_document: dict[str, Any],
    m2903_document: dict[str, Any],
    m2902_document: dict[str, Any],
    width: int,
    height: int,
    options: M2905Options,
) -> dict[str, Any]:
    objects = [item for item in m2904_document.get("objects", []) if isinstance(item, dict)]
    evidence_nodes = [item for item in m2904_document.get("evidenceNodes", []) if isinstance(item, dict)]
    text_boxes = [item for item in m2902_document.get("textBoxes", []) if isinstance(item, dict)]
    m2903_items = [item for item in m2903_document.get("items", []) if isinstance(item, dict)]
    valid_text_boxes: list[dict[str, Any]] = []
    text_bboxes: list[list[int]] = []
    for raw in text_boxes:
        bbox = parse_bbox(raw.get("bbox"))
        source_id = str(raw.get("id") or "")
        if bbox is not None and source_id and bbox_in_bounds(bbox, width, height):
            item = dict(raw)
            item["bbox"] = bbox
            item["id"] = source_id
            valid_text_boxes.append(item)
            text_bboxes.append(bbox)
    for raw in evidence_nodes:
        if raw.get("nodeKind") == "text":
            bbox = parse_bbox(raw.get("bbox"))
            if bbox is not None and bbox_in_bounds(bbox, width, height):
                text_bboxes.append(bbox)
    return {
        "objects": objects,
        "objectById": {str(item.get("id")): item for item in objects if item.get("id")},
        "evidenceNodeById": {str(item.get("id")): item for item in evidence_nodes if item.get("id")},
        "m2903ById": {str(item.get("id")): item for item in m2903_items if item.get("id")},
        "m2903BySourceEvidenceId": {str(item.get("sourceEvidenceId")): item for item in m2903_items if item.get("sourceEvidenceId")},
        "textBoxById": {str(item.get("id")): item for item in valid_text_boxes if item.get("id")},
        "textBboxes": text_bboxes,
        "options": options,
    }


def refine_objects(
    *,
    pixels: PngPixels,
    output_dir: Path,
    lookups: dict[str, Any],
    options: M2905Options,
) -> tuple[list[RefinedVisualObject], list[RefinedVisualAsset], list[ShapeCandidate], list[RefinedTextMember], list[UnresolvedMember], list[TextVisualSeparationAuditItem]]:
    refined_objects: list[RefinedVisualObject] = []
    visual_assets: list[RefinedVisualAsset] = []
    shape_candidates: list[ShapeCandidate] = []
    text_members: list[RefinedTextMember] = []
    unresolved_members: list[UnresolvedMember] = []
    audit: list[TextVisualSeparationAuditItem] = []
    for raw_object in lookups["objects"]:
        object_id = str(raw_object.get("id") or "")
        bbox = parse_bbox(raw_object.get("bbox"))
        if not object_id or bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            continue
        combined_path = export_crop(pixels, output_dir, "combined_objects", f"refined_{len(refined_objects) + 1:04d}", bbox)
        block_formal_visual_assets = source_object_requires_split(raw_object)
        member_results = refine_object_members(
            pixels=pixels,
            output_dir=output_dir,
            raw_object=raw_object,
            lookups=lookups,
            options=options,
            visual_start=len(visual_assets) + 1,
            shape_start=len(shape_candidates) + 1,
            text_start=len(text_members) + 1,
            unresolved_start=len(unresolved_members) + 1,
            block_formal_visual_assets=block_formal_visual_assets,
        )
        object_visual_assets, object_shape_candidates, object_text_members, object_unresolved = member_results
        hard_split = is_split_source_object(raw_object, object_unresolved)
        if hard_split:
            split_path = output_dir / "assets" / "split_candidates" / f"refined_{len(refined_objects) + 1:04d}.png"
            split_path.parent.mkdir(parents=True, exist_ok=True)
            split_path.write_bytes(crop_pixels(pixels, bbox))
            object_visual_assets = []
            object_shape_candidates = []
        if object_unresolved and not hard_split:
            unresolved_path = output_dir / "assets" / "unresolved_objects" / f"refined_{len(refined_objects) + 1:04d}.png"
            unresolved_path.parent.mkdir(parents=True, exist_ok=True)
            unresolved_path.write_bytes(crop_pixels(pixels, bbox))

        object_decision = decide_refined_object(object_visual_assets, object_shape_candidates, object_text_members, object_unresolved, hard_split)
        risks = object_risks(object_visual_assets, object_shape_candidates, object_text_members, object_unresolved, hard_split)
        reasons = object_reasons(raw_object, object_visual_assets, object_shape_candidates, object_text_members, object_unresolved, hard_split)
        separation_quality = separation_quality_for(object_decision, object_visual_assets, object_shape_candidates, object_text_members, object_unresolved)
        refined = RefinedVisualObject(
            id=f"refined_{len(refined_objects) + 1:04d}",
            source_object_id=object_id,
            source_object_kind=str(raw_object.get("objectKind") or ""),
            source_decision=str(raw_object.get("decision") or ""),
            bbox=bbox,
            decision=object_decision,
            combined_asset_path=combined_path,
            combined_asset_use="audit_only",
            visual_asset_ids=[item.id for item in object_visual_assets],
            shape_candidate_ids=[item.id for item in object_shape_candidates],
            text_member_ids=[item.id for item in object_text_members],
            unresolved_member_ids=[item.id for item in object_unresolved],
            risks=risks,
            reasons=reasons,
            separation_quality=separation_quality,
            suggested_next_action=suggested_action(object_decision, risks),
        )
        visual_assets.extend(object_visual_assets)
        shape_candidates.extend(object_shape_candidates)
        text_members.extend(object_text_members)
        unresolved_members.extend(object_unresolved)
        refined_objects.append(refined)
        audit.append(
            TextVisualSeparationAuditItem(
                id=f"audit_{len(audit) + 1:04d}",
                source_object_id=object_id,
                refined_object_id=refined.id,
                decision=refined.decision,
                visual_asset_ids=refined.visual_asset_ids,
                shape_candidate_ids=refined.shape_candidate_ids,
                text_member_ids=refined.text_member_ids,
                unresolved_member_ids=refined.unresolved_member_ids,
                combined_asset_path=combined_path,
                risks=risks,
                reasons=reasons,
                metrics={
                    "visualAssetCount": len(refined.visual_asset_ids),
                    "shapeCandidateCount": len(refined.shape_candidate_ids),
                    "textMemberCount": len(refined.text_member_ids),
                    "unresolvedMemberCount": len(refined.unresolved_member_ids),
                    "separationQuality": round(separation_quality, 4),
                },
            )
        )
    return refined_objects, visual_assets, shape_candidates, text_members, unresolved_members, audit


def refine_object_members(
    *,
    pixels: PngPixels,
    output_dir: Path,
    raw_object: dict[str, Any],
    lookups: dict[str, Any],
    options: M2905Options,
    visual_start: int,
    shape_start: int,
    text_start: int,
    unresolved_start: int,
    block_formal_visual_assets: bool,
) -> tuple[list[RefinedVisualAsset], list[ShapeCandidate], list[RefinedTextMember], list[UnresolvedMember]]:
    visual_assets: list[RefinedVisualAsset] = []
    shape_candidates: list[ShapeCandidate] = []
    text_members: list[RefinedTextMember] = []
    unresolved_members: list[UnresolvedMember] = []
    object_id = str(raw_object.get("id") or "")
    for member in raw_object.get("members", []):
        if not isinstance(member, dict):
            continue
        member_role = str(member.get("memberRole") or "unknown")
        node_id = str(member.get("evidenceNodeId") or "")
        node = lookups["evidenceNodeById"].get(node_id)
        bbox = parse_bbox(member.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            unresolved_members.append(make_unresolved(object_id, node_id or None, bbox or [0, 0, 1, 1], member_role, "invalid_bbox", ["invalid_bbox"], unresolved_start + len(unresolved_members)))
            continue
        if node is None:
            unresolved_members.append(make_unresolved(object_id, node_id or None, bbox, member_role, "missing_lookup", ["missing_lookup"], unresolved_start + len(unresolved_members)))
            continue
        if member_role in {"text", "nearby_text"}:
            text_member = make_text_member(pixels, output_dir, object_id, node, member, lookups, text_start + len(text_members), options)
            if text_member is None:
                unresolved_members.append(make_unresolved(object_id, node_id, bbox, member_role, "missing_lookup", ["missing_text"], unresolved_start + len(unresolved_members)))
            else:
                text_members.append(text_member)
            continue
        if member_role == "wide_source":
            unresolved_members.append(make_unresolved(object_id, node_id, bbox, member_role, "wide_source", ["wide_source", "split_needed"], unresolved_start + len(unresolved_members)))
            continue
        if member_role == "noise":
            unresolved_members.append(make_unresolved(object_id, node_id, bbox, member_role, "noise_member", ["noise_member"], unresolved_start + len(unresolved_members)))
            continue
        if member_role == "weak_visual":
            unresolved_members.append(refine_weak_visual(object_id, node_id, bbox, node, lookups, unresolved_start + len(unresolved_members), options))
            continue
        if member_role == "visual":
            if block_formal_visual_assets:
                unresolved_members.append(make_unresolved(object_id, node_id, bbox, member_role, "wide_source", ["split_needed", "wide_source"], unresolved_start + len(unresolved_members)))
                continue
            result = refine_visual_member(
                pixels=pixels,
                output_dir=output_dir,
                object_id=object_id,
                node_id=node_id,
                bbox=bbox,
                node=node,
                lookups=lookups,
                visual_index=visual_start + len(visual_assets),
                shape_index=shape_start + len(shape_candidates),
                unresolved_index=unresolved_start + len(unresolved_members),
                options=options,
            )
            if isinstance(result, RefinedVisualAsset):
                visual_assets.append(result)
            elif isinstance(result, ShapeCandidate):
                shape_candidates.append(result)
            else:
                unresolved_members.append(result)
            continue
        unresolved_members.append(make_unresolved(object_id, node_id, bbox, member_role, "source_conflict", ["source_conflict"], unresolved_start + len(unresolved_members)))
    union_asset = maybe_build_visual_union(pixels, output_dir, object_id, visual_assets, text_members, unresolved_members, visual_start + len(visual_assets), lookups, options)
    if union_asset is not None:
        visual_assets.append(union_asset)
    return visual_assets, shape_candidates, text_members, unresolved_members


def refine_visual_member(
    *,
    pixels: PngPixels,
    output_dir: Path,
    object_id: str,
    node_id: str,
    bbox: list[int],
    node: dict[str, Any],
    lookups: dict[str, Any],
    visual_index: int,
    shape_index: int,
    unresolved_index: int,
    options: M2905Options,
) -> RefinedVisualAsset | ShapeCandidate | UnresolvedMember:
    metrics = parse_node_metrics(node)
    visual_kind = classify_visual_kind(node, bbox, metrics, options)
    overlap = visual_text_overlap_ratio(bbox, lookups["textBboxes"])
    if visual_kind == "shape_like":
        risks: list[str] = []
        if overlap > options.visual_asset_text_overlap_max:
            risks.extend(["contains_text", "text_overlay_shape"])
        return ShapeCandidate(
            id=f"shape_{shape_index:04d}",
            source_object_id=object_id,
            source_evidence_node_ids=[node_id],
            bbox=bbox,
            asset_use="shape_candidate",
            decision="candidate" if not risks else "uncertain",
            metrics=metrics,
            color=metrics_color(metrics),
            text_overlap_ratio=overlap,
            reasons=["shape_like_member"],
            risks=risks,
            preview_asset_path=export_crop(pixels, output_dir, "shape_candidates", f"shape_{shape_index:04d}", bbox),
        )
    threshold = options.icon_asset_text_overlap_max if visual_kind == "icon_like" else options.visual_asset_text_overlap_max
    if overlap > threshold:
        return make_unresolved(object_id, node_id, bbox, "visual", "high_text_overlap", ["high_text_overlap", "text_touching_visual"], unresolved_index)
    if bbox_area(bbox) < options.min_visual_asset_area:
        return make_unresolved(object_id, node_id, bbox, "visual", "invalid_bbox", ["invalid_bbox"], unresolved_index)
    asset_use: VisualAssetUse = "icon_asset" if visual_kind == "icon_like" else "image_asset"
    path = export_crop(pixels, output_dir, "visual_assets", f"visual_asset_{visual_index:04d}", bbox)
    return RefinedVisualAsset(
        id=f"visual_asset_{visual_index:04d}",
        source_object_id=object_id,
        source_evidence_node_ids=[node_id],
        bbox=bbox,
        visual_kind=visual_kind if visual_kind in {"image_like", "icon_like"} else "unknown_visual",
        asset_use=asset_use,
        decision="candidate",
        asset_path=path,
        text_overlap_ratio=overlap,
        metrics=metrics,
        risks=[],
        reasons=[f"{asset_use}_from_existing_member_bbox"],
    )


def refine_weak_visual(
    object_id: str,
    node_id: str,
    bbox: list[int],
    node: dict[str, Any],
    lookups: dict[str, Any],
    unresolved_index: int,
    options: M2905Options,
) -> UnresolvedMember:
    overlap = visual_text_overlap_ratio(bbox, lookups["textBboxes"])
    risks = ["weak_visual"]
    reason: UnresolvedReason = "weak_visual"
    if overlap > options.weak_visual_text_overlap_max:
        risks.extend(["high_text_overlap", "text_touching_visual"])
        reason = "high_text_overlap"
    risks.extend(str(item) for item in node.get("risks", []) if isinstance(item, str))
    return make_unresolved(object_id, node_id, bbox, "weak_visual", reason, dedupe_strings(risks), unresolved_index)


def make_text_member(
    pixels: PngPixels,
    output_dir: Path,
    object_id: str,
    node: dict[str, Any],
    member: dict[str, Any],
    lookups: dict[str, Any],
    index: int,
    options: M2905Options,
) -> RefinedTextMember | None:
    bbox = parse_bbox(member.get("bbox")) or parse_bbox(node.get("bbox")) or [0, 0, 1, 1]
    source_text_box_id = str(node.get("sourceId") or "") if node.get("source") == "m2902_text_box" else None
    text_box = lookups["textBoxById"].get(source_text_box_id or "")
    text = str((text_box or {}).get("text") or node.get("text") or "").strip() or None
    preview = truncate_text(text, options.text_preview_max_chars) or ""
    if not preview:
        return None
    path = export_crop(pixels, output_dir, "text_member_previews", f"text_member_{index:04d}", bbox)
    return RefinedTextMember(
        id=f"text_member_{index:04d}",
        source_object_id=object_id,
        source="m2902_text_box" if source_text_box_id else "m2904_member",
        source_evidence_node_id=str(node.get("id") or "") or None,
        source_text_box_id=source_text_box_id,
        bbox=bbox,
        text_preview=preview,
        text=text,
        confidence=float(node.get("confidence", member.get("confidence", 1.0))),
        risks=[str(item) for item in member.get("risks", []) if isinstance(item, str)],
        reasons=["text_member_from_existing_object_member"],
        preview_asset_path=path,
    )


def make_unresolved(
    object_id: str,
    node_id: str | None,
    bbox: list[int],
    member_role: str,
    reason: UnresolvedReason,
    risks: list[str],
    index: int,
) -> UnresolvedMember:
    return UnresolvedMember(
        id=f"unresolved_{index:04d}",
        source_object_id=object_id,
        source_evidence_node_id=node_id,
        bbox=bbox,
        member_role=member_role,
        reason=reason,
        risks=dedupe_strings(risks),
        suggested_next_action="review_text_visual_separation",
    )


def maybe_build_visual_union(
    pixels: PngPixels,
    output_dir: Path,
    object_id: str,
    assets: list[RefinedVisualAsset],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    index: int,
    lookups: dict[str, Any],
    options: M2905Options,
) -> RefinedVisualAsset | None:
    if len(assets) < 2 or len(assets) > options.max_visual_union_members or unresolved_members:
        return None
    if any(asset.asset_use not in {"image_asset", "icon_asset"} for asset in assets):
        return None
    if text_members:
        return None
    for left_index, left in enumerate(assets):
        for right in assets[left_index + 1 :]:
            if bbox_gap_distance(left.bbox, right.bbox) > options.max_visual_union_gap:
                return None
    union_bbox = bbox_union([asset.bbox for asset in assets])
    overlap = visual_text_overlap_ratio(union_bbox, lookups["textBboxes"])
    if overlap > options.visual_asset_text_overlap_max:
        return None
    path = export_crop(pixels, output_dir, "visual_assets", f"visual_asset_{index:04d}", union_bbox)
    return RefinedVisualAsset(
        id=f"visual_asset_{index:04d}",
        source_object_id=object_id,
        source_evidence_node_ids=[node_id for asset in assets for node_id in asset.source_evidence_node_ids],
        bbox=union_bbox,
        visual_kind="image_like",
        asset_use="image_asset",
        decision="candidate",
        asset_path=path,
        text_overlap_ratio=overlap,
        metrics=None,
        risks=[],
        reasons=["safe_union_of_existing_visual_member_bboxes"],
    )


def decide_refined_object(
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    hard_split: bool,
) -> RefinedObjectDecision:
    if hard_split:
        return "split_needed"
    if unresolved_members and (visual_assets or shape_candidates or text_members):
        return "partially_separated"
    if unresolved_members:
        return "unresolved"
    if visual_assets and text_members:
        return "separated"
    if visual_assets and not text_members:
        return "visual_only"
    if text_members and not visual_assets and not shape_candidates:
        return "text_only"
    if shape_candidates or text_members:
        return "partially_separated"
    return "rejected"


def object_risks(
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    hard_split: bool,
) -> list[str]:
    risks: list[str] = []
    if hard_split:
        risks.extend(["wide_source", "split_needed"])
    risks.extend(risk for item in visual_assets for risk in item.risks)
    risks.extend(risk for item in shape_candidates for risk in item.risks)
    risks.extend(risk for item in text_members for risk in item.risks)
    risks.extend(risk for item in unresolved_members for risk in item.risks)
    return dedupe_strings(risks)


def object_reasons(
    raw_object: dict[str, Any],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    hard_split: bool,
) -> list[str]:
    reasons = ["refined_existing_m2904_object"]
    if hard_split:
        reasons.append("split_needed_from_existing_object_or_member")
    if visual_assets:
        reasons.append("formal_visual_assets_from_existing_member_bboxes")
    if shape_candidates:
        reasons.append("shape_candidates_from_existing_member_bboxes")
    if text_members:
        reasons.append("text_members_from_existing_member_bboxes")
    if unresolved_members:
        reasons.append("unsafe_members_kept_for_audit")
    source_kind = str(raw_object.get("objectKind") or "")
    if source_kind:
        reasons.append(f"source_object_kind_recorded:{source_kind}")
    return dedupe_strings(reasons)


def separation_quality_for(
    decision: RefinedObjectDecision,
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
) -> float:
    if decision == "separated":
        return 0.82
    if decision in {"visual_only", "text_only"}:
        return 0.70
    if decision == "partially_separated":
        usable = len(visual_assets) + len(shape_candidates) + len(text_members)
        total = usable + len(unresolved_members)
        return max(0.35, min(0.68, usable / max(1, total)))
    if decision == "split_needed":
        return 0.40
    if decision == "unresolved":
        return 0.30
    return 0.0


def suggested_action(decision: RefinedObjectDecision, risks: list[str]) -> str | None:
    if decision == "split_needed":
        return "needs_upstream_fragment_split_or_manual_review"
    if decision in {"unresolved", "partially_separated"}:
        return "review_text_visual_separation"
    if "contains_text" in risks or "text_overlay_shape" in risks:
        return "review_shape_text_overlay"
    return None


def is_split_source_object(raw_object: dict[str, Any], unresolved_members: list[UnresolvedMember]) -> bool:
    if source_object_requires_split(raw_object):
        return True
    return any(item.reason == "wide_source" or "split_needed" in item.risks for item in unresolved_members)


def source_object_requires_split(raw_object: dict[str, Any]) -> bool:
    if str(raw_object.get("objectKind") or "") == "split_candidate":
        return True
    if "split_needed" in {str(risk) for risk in raw_object.get("risks", [])}:
        return True
    return any(isinstance(item, dict) and str(item.get("memberRole") or "") == "wide_source" for item in raw_object.get("members", []))


def classify_visual_kind(node: dict[str, Any], bbox: list[int], metrics: M29PrimitiveMetrics | None, options: M2905Options) -> str:
    source_kind = str(node.get("sourceVisualKind") or "")
    area = bbox_area(bbox)
    max_edge = max(bbox[2], bbox[3])
    if metrics is not None and metrics.fill_ratio >= 0.70 and metrics.texture_score <= 0.16 and metrics.edge_score <= 0.20:
        return "shape_like"
    if source_kind == "icon_candidate" or (area <= options.max_icon_asset_area and max_edge <= options.max_icon_asset_edge and source_kind in {"other_candidate", "accepted_image", "media_candidate"}):
        return "icon_like"
    if source_kind in {"accepted_image", "media_candidate"}:
        return "image_like"
    if source_kind == "other_candidate":
        return "shape_like" if metrics is not None and metrics.color_count <= 24 else "unknown_visual"
    return "unknown_visual"


def parse_node_metrics(node: dict[str, Any]) -> M29PrimitiveMetrics | None:
    try:
        return parse_metrics(node.get("metrics"))
    except ValueError:
        return None


def visual_text_overlap_ratio(bbox: list[int], text_bboxes: list[list[int]]) -> float:
    area = bbox_area(bbox)
    if area <= 0:
        return 0.0
    return min(1.0, rectangle_union_intersection_area(bbox, text_bboxes) / area)


def rectangle_union_intersection_area(target: list[int], bboxes: list[list[int]]) -> int:
    rects: list[tuple[int, int, int, int]] = []
    tx1, ty1, tx2, ty2 = target[0], target[1], bbox_x2(target), bbox_y2(target)
    for bbox in bboxes:
        x1 = max(tx1, bbox[0])
        y1 = max(ty1, bbox[1])
        x2 = min(tx2, bbox_x2(bbox))
        y2 = min(ty2, bbox_y2(bbox))
        if x2 > x1 and y2 > y1:
            rects.append((x1, y1, x2, y2))
    if not rects:
        return 0
    xs = sorted({coord for rect in rects for coord in (rect[0], rect[2])})
    area = 0
    for index in range(len(xs) - 1):
        x1, x2 = xs[index], xs[index + 1]
        if x2 <= x1:
            continue
        intervals = [(rect[1], rect[3]) for rect in rects if rect[0] <= x1 and rect[2] >= x2]
        area += (x2 - x1) * union_interval_length(intervals)
    return area


def union_interval_length(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return sum(end - start for start, end in merged)


def export_crop(pixels: PngPixels, output_dir: Path, folder: str, id: str, bbox: list[int]) -> str:
    target = output_dir / "assets" / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{id}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    return str(path.relative_to(output_dir))


def write_debug_artifacts(
    pixels: PngPixels,
    output_dir: Path,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
) -> M2905DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    visual_assets_path = overlay_dir / "20_visual_assets.png"
    text_members_path = overlay_dir / "21_text_members.png"
    separation_path = overlay_dir / "22_text_visual_separation.png"
    unresolved_path = overlay_dir / "23_unresolved_refinement.png"
    shape_path = overlay_dir / "24_shape_candidates.png"
    visual_assets_path.write_bytes(overlay_visual_assets(pixels, visual_assets))
    text_members_path.write_bytes(overlay_text_members(pixels, text_members))
    separation_path.write_bytes(overlay_separation(pixels, objects, visual_assets, shape_candidates, text_members, unresolved_members))
    unresolved_path.write_bytes(overlay_unresolved(pixels, objects, unresolved_members))
    shape_path.write_bytes(overlay_shapes(pixels, shape_candidates))
    return M2905DebugArtifacts(
        visual_assets=str(visual_assets_path.relative_to(output_dir)),
        text_members=str(text_members_path.relative_to(output_dir)),
        text_visual_separation=str(separation_path.relative_to(output_dir)),
        unresolved_refinement=str(unresolved_path.relative_to(output_dir)),
        shape_candidates=str(shape_path.relative_to(output_dir)),
    )


def overlay_visual_assets(pixels: PngPixels, visual_assets: list[RefinedVisualAsset]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in visual_assets:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 200, 90), 3)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_text_members(pixels: PngPixels, text_members: list[RefinedTextMember]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in text_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (238, 190, 40), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_shapes(pixels: PngPixels, shape_candidates: list[ShapeCandidate]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in shape_candidates:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 122, 255), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_unresolved(pixels: PngPixels, objects: list[RefinedVisualObject], unresolved_members: list[UnresolvedMember]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in objects:
        if item.decision in {"unresolved", "partially_separated", "split_needed", "rejected"}:
            draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 2)
    for item in unresolved_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (235, 64, 52), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_separation(
    pixels: PngPixels,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in objects:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 1)
    for item in visual_assets:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 200, 90), 3)
    for item in shape_candidates:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 122, 255), 2)
    for item in text_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (238, 190, 40), 2)
    for item in unresolved_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (235, 64, 52), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: M2905DebugArtifacts,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    options: M2905Options,
) -> bytes:
    overlays = [decode_png_pixels((output_dir / path).read_bytes()) for path in debug.to_dict().values()]
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.26, (sheet_width - margin * 2 - gap * 5) / max(1, pixels.width * 6))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    previews = crop_previews(output_dir, objects, visual_assets, shape_candidates, text_members, unresolved_members, options.output_preview_max_thumb)
    grid_h = grid_height(previews, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, *overlays]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, previews, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews(
    output_dir: Path,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    max_edge: int,
) -> list[tuple[str, list[int], str, PngPixels, int, int]]:
    items: list[tuple[str, list[int], str | None, str]] = []
    items.extend((f"combined:{item.id}", item.bbox, item.combined_asset_path, color_key_for_decision(item.decision)) for item in objects[:80])
    items.extend((f"visual:{item.id}", item.bbox, item.asset_path, "visual") for item in visual_assets)
    items.extend((f"shape:{item.id}", item.bbox, item.preview_asset_path, "shape") for item in shape_candidates)
    items.extend((f"text:{item.id}", item.bbox, item.preview_asset_path, "text") for item in text_members[:120])
    unresolved_by_id = {item.id: item for item in unresolved_members}
    for item in unresolved_members[:120]:
        path = export_existing_preview(output_dir, "unresolved_objects", item.id, item.bbox)
        items.append((f"unresolved:{item.id}", item.bbox, path, "unresolved"))
        unresolved_by_id[item.id] = item
    previews: list[tuple[str, list[int], str, PngPixels, int, int]] = []
    for label, bbox, path, color_key in items:
        if not path:
            continue
        try:
            crop = decode_png_pixels((output_dir / path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, crop.width, crop.height))
        previews.append((label, bbox, color_key, crop, max(1, round(crop.width * scale)), max(1, round(crop.height * scale))))
    return previews


def export_existing_preview(output_dir: Path, folder: str, id: str, bbox: list[int]) -> str | None:
    # Unresolved member previews are optional in the schema; this helper only reuses
    # already-written object crops when present and otherwise leaves the preview out.
    candidates = sorted((output_dir / "assets" / folder).glob("*.png")) if (output_dir / "assets" / folder).exists() else []
    return str(candidates[0].relative_to(output_dir)) if candidates else None


def write_outputs(document: M2905Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "refined_visual_objects.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_visual_separation_audit.json").write_text(json.dumps([item.to_dict() for item in document.audit], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "refined_visual_objects.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: M2905Document) -> str:
    lines = [
        "# M29.0.5 Text-Aware Visual Object Refinement",
        "",
        f"- Source M29.0.4: `{document.source_m2904_visual_object_candidates_json}`",
        f"- Source M29.0.3: `{document.source_m2903_visual_evidence_json}`",
        f"- Source M29.0.2: `{document.source_m2902_audit_json}`",
        f"- Objects: {len(document.objects)}",
        f"- Visual assets: {len(document.visual_assets)}",
        f"- Shape candidates: {len(document.shape_candidates)}",
        f"- Text members: {len(document.text_members)}",
        f"- Unresolved members: {len(document.unresolved_members)}",
        f"- Decisions: `{document.meta.get('objectDecisionCounts', {})}`",
        "",
        "## Objects",
        "",
    ]
    text_by_id = {item.id: item for item in document.text_members}
    for item in document.objects[:180]:
        text_preview = ", ".join(text_by_id[text_id].text_preview for text_id in item.text_member_ids[:4] if text_id in text_by_id)
        lines.append(
            f"- `{item.id}` source=`{item.source_object_id}` `{item.decision}` "
            f"visual={len(item.visual_asset_ids)} shape={len(item.shape_candidate_ids)} "
            f"text={len(item.text_member_ids)} unresolved={len(item.unresolved_member_ids)} "
            f"risks={item.risks} textPreview=`{text_preview}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_text_aware_visual_object_refinement_document(document: M2905Document, output_dir: Path, width: int, height: int, m2904_document: dict[str, Any], m2902_document: dict[str, Any]) -> None:
    if document.schema_name != "M2905TextAwareVisualObjectRefinementDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.5 document schema")
    source_objects = {str(item.get("id")): item for item in m2904_document.get("objects", []) if isinstance(item, dict) and item.get("id")}
    source_nodes = {str(item.get("id")) for item in m2904_document.get("evidenceNodes", []) if isinstance(item, dict) and item.get("id")}
    source_text_boxes = {str(item.get("id")) for item in m2902_document.get("textBoxes", []) if isinstance(item, dict) and item.get("id")}
    object_ids = assert_unique([item.id for item in document.objects], "object")
    visual_asset_ids = assert_unique([item.id for item in document.visual_assets], "visual asset")
    shape_ids = assert_unique([item.id for item in document.shape_candidates], "shape candidate")
    text_ids = assert_unique([item.id for item in document.text_members], "text member")
    unresolved_ids = assert_unique([item.id for item in document.unresolved_members], "unresolved member")
    audit_ids = assert_unique([item.id for item in document.audit], "audit item")
    _ = audit_ids
    source_object_ids = [item.source_object_id for item in document.objects]
    if set(source_object_ids) != set(source_objects):
        raise ValueError("M29.0.5 must refine exactly the M29.0.4 source objects")
    assert_unique(source_object_ids, "source object reference")
    for item in document.objects:
        if item.source_object_id not in source_objects:
            raise ValueError(f"M29.0.5 object references missing source object: {item.id}")
        if item.combined_asset_use != "audit_only":
            raise ValueError(f"M29.0.5 combinedAssetUse must be audit_only: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 object bbox out of bounds: {item.id}")
        assert_png_size(output_dir, item.combined_asset_path, item.bbox)
        if item.decision == "text_only" and item.visual_asset_ids:
            raise ValueError(f"M29.0.5 text_only object cannot have visual assets: {item.id}")
        if item.decision == "visual_only" and item.text_member_ids:
            raise ValueError(f"M29.0.5 visual_only object cannot have text members: {item.id}")
        if item.decision == "separated" and (not item.visual_asset_ids or not item.text_member_ids):
            raise ValueError(f"M29.0.5 separated object requires visual and text members: {item.id}")
        if item.decision == "split_needed" and item.visual_asset_ids:
            raise ValueError(f"M29.0.5 split_needed object cannot have child visual assets: {item.id}")
        for asset_id in item.visual_asset_ids:
            if asset_id not in visual_asset_ids:
                raise ValueError(f"M29.0.5 object references missing visual asset: {item.id}")
        for shape_id in item.shape_candidate_ids:
            if shape_id not in shape_ids:
                raise ValueError(f"M29.0.5 object references missing shape candidate: {item.id}")
        for text_id in item.text_member_ids:
            if text_id not in text_ids:
                raise ValueError(f"M29.0.5 object references missing text member: {item.id}")
        for unresolved_id in item.unresolved_member_ids:
            if unresolved_id not in unresolved_ids:
                raise ValueError(f"M29.0.5 object references missing unresolved member: {item.id}")
    for item in document.visual_assets:
        if item.source_object_id not in source_objects:
            raise ValueError(f"M29.0.5 visual asset references missing source object: {item.id}")
        if item.asset_use not in {"image_asset", "icon_asset"}:
            raise ValueError(f"M29.0.5 formal visual asset has invalid assetUse: {item.id}")
        if not item.asset_path or not item.asset_path.startswith("assets/visual_assets/"):
            raise ValueError(f"M29.0.5 visual asset must live under assets/visual_assets: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 visual asset bbox out of bounds: {item.id}")
        assert_png_size(output_dir, item.asset_path, item.bbox)
        for node_id in item.source_evidence_node_ids:
            if node_id not in source_nodes:
                raise ValueError(f"M29.0.5 visual asset references missing evidence node: {item.id}")
    for item in document.shape_candidates:
        if item.asset_use != "shape_candidate":
            raise ValueError(f"M29.0.5 shape candidate assetUse must be shape_candidate: {item.id}")
        if item.preview_asset_path and item.preview_asset_path.startswith("assets/visual_assets/"):
            raise ValueError(f"M29.0.5 shape candidate cannot live under visual_assets: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 shape candidate bbox out of bounds: {item.id}")
        if item.preview_asset_path:
            assert_png_size(output_dir, item.preview_asset_path, item.bbox)
        for node_id in item.source_evidence_node_ids:
            if node_id not in source_nodes:
                raise ValueError(f"M29.0.5 shape candidate references missing evidence node: {item.id}")
    for item in document.text_members:
        if not item.text_preview:
            raise ValueError(f"M29.0.5 textPreview is required: {item.id}")
        if item.source_evidence_node_id and item.source_evidence_node_id not in source_nodes:
            raise ValueError(f"M29.0.5 text member references missing evidence node: {item.id}")
        if item.source_text_box_id and item.source_text_box_id not in source_text_boxes:
            raise ValueError(f"M29.0.5 text member references missing text box: {item.id}")
        if not item.source_evidence_node_id and not item.source_text_box_id:
            raise ValueError(f"M29.0.5 text member requires source ref: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 text member bbox out of bounds: {item.id}")
        if item.preview_asset_path:
            assert_png_size(output_dir, item.preview_asset_path, item.bbox)
    for item in document.unresolved_members:
        if item.source_evidence_node_id and item.source_evidence_node_id not in source_nodes:
            raise ValueError(f"M29.0.5 unresolved member references missing evidence node: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 unresolved member bbox out of bounds: {item.id}")
    audited = {item.refined_object_id for item in document.audit}
    if audited != object_ids:
        raise ValueError("M29.0.5 audit must cover all refined objects")
    for item in document.audit:
        if item.source_object_id not in source_objects:
            raise ValueError(f"M29.0.5 audit references missing source object: {item.id}")
    for path in document.debug.to_dict().values():
        metadata = assert_readable_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.0.5 overlay dimensions do not match source image: {path}")
    assert_readable_png(output_dir, "preview_text_aware_refinement.png")


def assert_png_size(output_dir: Path, path: str, bbox: list[int]) -> None:
    metadata = assert_readable_png(output_dir, path)
    if metadata.width != bbox[2] or metadata.height != bbox[3]:
        raise ValueError(f"M29.0.5 asset dimensions do not match bbox: {path}")


def assert_readable_png(output_dir: Path, path: str):
    resolved = output_dir / path
    if not resolved.exists():
        raise ValueError(f"M29.0.5 PNG output missing or unreadable: {path}")
    metadata = read_png_metadata(resolved.read_bytes())
    if metadata is None:
        raise ValueError(f"M29.0.5 PNG output missing or unreadable: {path}")
    return metadata


def build_meta(
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    audit: list[TextVisualSeparationAuditItem],
) -> dict[str, Any]:
    return {
        "notes": "m29_0_5_text_aware_visual_object_refinement",
        "objectCount": len(objects),
        "visualAssetCount": len(visual_assets),
        "shapeCandidateCount": len(shape_candidates),
        "textMemberCount": len(text_members),
        "unresolvedMemberCount": len(unresolved_members),
        "auditCount": len(audit),
        "objectDecisionCounts": count_by(objects, lambda item: item.decision),
        "visualAssetUseCounts": count_by(visual_assets, lambda item: item.asset_use),
        "shapeDecisionCounts": count_by(shape_candidates, lambda item: item.decision),
        "unresolvedReasonCounts": count_by(unresolved_members, lambda item: item.reason),
    }


def count_by(items: list[Any], key_fn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def assert_unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate M29.0.5 {label} id: {value}")
        seen.add(value)
    return seen


def bbox_union(bboxes: list[list[int]]) -> list[int]:
    if not bboxes:
        return [0, 0, 1, 1]
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def truncate_text(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def metrics_color(metrics: M29PrimitiveMetrics | None) -> str | None:
    if metrics is None:
        return None
    return "#" + "".join(f"{max(0, min(255, value)):02X}" for value in metrics.mean_rgb)


def object_color(item: RefinedVisualObject) -> tuple[int, int, int]:
    return {
        "separated": (0, 200, 90),
        "visual_only": (0, 180, 210),
        "text_only": (238, 190, 40),
        "partially_separated": (238, 140, 40),
        "unresolved": (235, 64, 52),
        "split_needed": (180, 60, 220),
        "rejected": (170, 170, 170),
    }[item.decision]


def color_key_for_decision(decision: RefinedObjectDecision) -> str:
    return {
        "separated": "visual",
        "visual_only": "visual",
        "text_only": "text",
        "partially_separated": "partial",
        "unresolved": "unresolved",
        "split_needed": "split",
        "rejected": "rejected",
    }[decision]


def frame_color(key: str) -> tuple[int, int, int]:
    return {
        "visual": (0, 200, 90),
        "shape": (0, 122, 255),
        "text": (238, 190, 40),
        "partial": (238, 140, 40),
        "unresolved": (235, 64, 52),
        "split": (180, 60, 220),
        "rejected": (170, 170, 170),
    }.get(key, (170, 170, 170))


def grid_height(previews: list[tuple[str, list[int], str, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _label, _bbox, _key, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[str, list[int], str, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for _label, _bbox, key, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, frame_color(key))
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


def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
