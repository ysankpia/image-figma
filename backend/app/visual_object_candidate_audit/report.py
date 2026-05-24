from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geometry import count_by
from .types import M2904Document, VisualObjectCandidate, VisualObjectEvidenceEdge, VisualObjectEvidenceNode, VisualObjectSetCandidate


def write_outputs(document: M2904Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "visual_object_candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "edge_audit.json").write_text(json.dumps([item.to_dict() for item in document.edge_audit], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "visual_object_candidates.md").write_text(build_markdown_report(document), encoding="utf-8")

def build_markdown_report(document: M2904Document) -> str:
    lines = [
        "# M29.0.4 Generic Visual Object Candidate Audit",
        "",
        f"- Source M29.0.3: `{document.source_m2903_visual_evidence_json}`",
        f"- Source M29.0.2: `{document.source_m2902_audit_json}`",
        f"- Evidence nodes: {len(document.evidence_nodes)}",
        f"- Evidence edges: {len(document.evidence_edges)}",
        f"- Objects: {len(document.objects)}",
        f"- Sets: {len(document.sets)}",
        f"- Object decisions: `{document.meta.get('objectDecisionCounts', {})}`",
        f"- Object kinds: `{document.meta.get('objectKindCounts', {})}`",
        "",
        "## Objects",
        "",
    ]
    for item in document.objects[:180]:
        member_summary = ", ".join(f"{member.member_role}:{member.source_id}" for member in item.members)
        lines.append(f"- `{item.id}` `{item.object_kind}` `{item.decision}` bbox={item.bbox} risks={item.risks} members=[{member_summary}]")
    if document.sets:
        lines.extend(["", "## Sets", ""])
        for item in document.sets:
            lines.append(f"- `{item.id}` `{item.set_kind}` `{item.decision}` members={item.member_object_ids} bbox={item.bbox}")
    return "\n".join(lines).rstrip() + "\n"

def build_meta(
    nodes: list[VisualObjectEvidenceNode],
    edges: list[VisualObjectEvidenceEdge],
    objects: list[VisualObjectCandidate],
    sets: list[VisualObjectSetCandidate],
) -> dict[str, Any]:
    return {
        "notes": "m29_0_4_generic_visual_object_candidate_audit",
        "evidenceNodeCount": len(nodes),
        "evidenceEdgeCount": len(edges),
        "objectCount": len(objects),
        "setCount": len(sets),
        "objectKindCounts": count_by(objects, lambda item: item.object_kind),
        "objectDecisionCounts": count_by(objects, lambda item: item.decision),
        "edgeDecisionCounts": count_by(edges, lambda item: item.decision),
        "setKindCounts": count_by(sets, lambda item: item.set_kind),
    }
