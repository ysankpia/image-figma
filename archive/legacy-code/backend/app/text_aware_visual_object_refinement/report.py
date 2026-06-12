from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geometry import count_by
from .types import (
    M2905Document,
    RefinedTextMember,
    RefinedVisualAsset,
    RefinedVisualObject,
    ShapeCandidate,
    TextVisualSeparationAuditItem,
    UnresolvedMember,
)


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
