from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import PngPixels
from ..visual_evidence_normalization import parse_bbox
from ..visual_primitive_graph import bbox_in_bounds, crop_pixels
from .artifacts import export_crop
from .decisions import (
    decide_refined_object,
    is_split_source_object,
    object_reasons,
    object_risks,
    separation_quality_for,
    source_object_requires_split,
    suggested_action,
)
from .members import refine_object_members
from .types import (
    M2905Options,
    RefinedTextMember,
    RefinedVisualAsset,
    RefinedVisualObject,
    ShapeCandidate,
    TextVisualSeparationAuditItem,
    UnresolvedMember,
)


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
