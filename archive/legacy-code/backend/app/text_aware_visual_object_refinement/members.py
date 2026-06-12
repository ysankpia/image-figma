from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import PngPixels
from ..visual_evidence_normalization import parse_bbox
from ..visual_primitive_graph import bbox_area, bbox_gap_distance, bbox_in_bounds
from .artifacts import export_crop
from .classification import classify_visual_kind, parse_node_metrics, shape_source_reasons, shape_source_subtype
from .geometry import bbox_union, dedupe_strings, metrics_color, truncate_text, visual_text_overlap_ratio
from .types import (
    M2905Options,
    RefinedTextMember,
    RefinedVisualAsset,
    ShapeCandidate,
    UnresolvedMember,
    UnresolvedReason,
    VisualAssetUse,
)


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
        source_subtype = shape_source_subtype(node, lookups)
        source_reasons = shape_source_reasons(node, lookups)
        source_proven_support = source_subtype in {"low_contrast_support", "text_support_background"} or bool(
            set(source_reasons) & {"low_contrast_support_region", "text_support_background_region"}
        )
        if overlap > options.visual_asset_text_overlap_max and not source_proven_support:
            risks.extend(["contains_text", "text_overlay_shape"])
        return ShapeCandidate(
            id=f"shape_{shape_index:04d}",
            source_object_id=object_id,
            source_evidence_node_ids=[node_id],
            source_subtype=source_subtype,
            source_reasons=source_reasons,
            bbox=bbox,
            asset_use="shape_candidate",
            decision="candidate" if not risks else "uncertain",
            metrics=metrics,
            color=metrics_color(metrics),
            text_overlap_ratio=overlap,
            reasons=dedupe_strings(["shape_like_member", *source_reasons]),
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
