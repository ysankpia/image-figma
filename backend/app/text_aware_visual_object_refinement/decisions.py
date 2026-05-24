from __future__ import annotations

from typing import Any

from .geometry import dedupe_strings
from .types import RefinedObjectDecision, RefinedTextMember, RefinedVisualAsset, ShapeCandidate, UnresolvedMember


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
