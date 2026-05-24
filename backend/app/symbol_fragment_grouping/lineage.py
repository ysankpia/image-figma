from __future__ import annotations

from typing import Any, Literal

from .types import M291FragmentCandidate, M291SourceKind


def build_candidate_lineage(candidate_id: str, source_kind: M291SourceKind, source_node_id: str, reasons: list[str]) -> dict[str, Any]:
    lineage_source = "m29_symbol" if source_kind == "symbol" else "eligible_blocked"
    lineage_strength = "medium" if source_kind == "symbol" else "weak"
    lineage_reasons = ["m29_symbol_candidate"] if source_kind == "symbol" else ["eligible_blocked_symbol_metrics"]
    risks = [reason for reason in reasons if reason in {"weak_symbol_metrics", "symbol_color_too_high", "symbol_texture_too_high", "symbol_edge_too_high", "symbol_area_too_small"}]
    return {
        "preOcrSymbolCandidate": True,
        "lineageStrength": lineage_strength,
        "lineageSource": lineage_source,
        "m29NodeIds": [source_node_id] if source_kind == "symbol" else [],
        "m29BlockedIds": [source_node_id] if source_kind == "blocked" else [],
        "m291CandidateIds": [candidate_id],
        "m291GroupId": None,
        "ownershipHint": "visual_or_mixed",
        "risks": sorted(set(risks)),
        "reasons": lineage_reasons,
    }

def build_group_lineage(
    group_id: str,
    decision: Literal["accepted", "uncertain", "rejected"],
    candidates: list[M291FragmentCandidate],
    reasons: list[str],
) -> dict[str, Any] | None:
    if decision == "rejected":
        return None
    if "text_like_sequence" in reasons or "image_like_merged_result" in reasons:
        return None
    strength = "strong" if decision == "accepted" and any(candidate.source_kind == "symbol" for candidate in candidates) else "medium"
    if decision == "uncertain":
        strength = "medium" if any(candidate.source_kind == "symbol" for candidate in candidates) else "weak"
    risks: list[str] = []
    if decision == "uncertain":
        risks.append("lineage_conflict")
    if "too_many_members" in reasons:
        risks.append("anchorless_fragment")
    if any(candidate.source_kind == "blocked" for candidate in candidates):
        risks.append("eligible_blocked_member")
    return {
        "preOcrSymbolCandidate": True,
        "lineageStrength": strength,
        "lineageSource": "m291_group",
        "m29NodeIds": [candidate.source_node_id for candidate in candidates if candidate.source_kind == "symbol"],
        "m29BlockedIds": [candidate.source_node_id for candidate in candidates if candidate.source_kind == "blocked"],
        "m291CandidateIds": [candidate.id for candidate in candidates],
        "m291GroupId": group_id,
        "ownershipHint": "visual_or_mixed",
        "risks": sorted(set(risks)),
        "reasons": ["symbol_group_lineage_preserved", *[reason for reason in reasons if reason]],
    }

def build_interactive_shape_lineage(group_id: str, foreground_candidate_id: str, foreground_source_id: str) -> dict[str, Any]:
    return {
        "preOcrSymbolCandidate": True,
        "lineageStrength": "strong",
        "lineageSource": "m291_group",
        "m29NodeIds": [foreground_source_id],
        "m29BlockedIds": [],
        "m291CandidateIds": [foreground_candidate_id],
        "m291GroupId": group_id,
        "ownershipHint": "visual_or_mixed",
        "risks": [],
        "reasons": ["symbol_group_lineage_preserved", "interactive_shape_contains_symbol"],
    }
