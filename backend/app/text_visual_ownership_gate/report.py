from __future__ import annotations

import json
from pathlib import Path

from .types import M2907Document


def write_outputs(document: M2907Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "text_visual_ownership_gate.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_visual_ownership_audit.json").write_text(json.dumps(document.audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_owned_evidence.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.ownership == "text_owned"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "visual_forming_evidence.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.allowed_for_object_forming_visual_side], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "audit_only_evidence.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.ownership == "audit_only"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_overlay_on_visual.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.ownership_reason_kind == "image_with_text_overlay"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_visual_ownership_gate.md").write_text(build_markdown_report(document), encoding="utf-8")

def build_markdown_report(document: M2907Document) -> str:
    lines = [
        "# M29.0.7 Text Visual Ownership Gate",
        "",
        f"- Source M29.0.3: `{document.source_m2903_visual_evidence_json}`",
        f"- Source M29.0.2: `{document.source_m2902_audit_json}`",
        f"- Decisions: {len(document.ownership_decisions)}",
        f"- Ownership counts: `{document.meta.get('ownershipCounts', {})}`",
        f"- Reason counts: `{document.meta.get('ownershipReasonKindCounts', {})}`",
        "",
        "## Top Decisions",
        "",
    ]
    for item in document.ownership_decisions[:120]:
        lines.append(f"- `{item.id}` `{item.ownership}` `{item.decision}` source=`{item.source}` sourceId=`{item.source_visual_evidence_item_id or item.source_text_box_id}` bbox={item.bbox} reason=`{item.ownership_reason_kind}` visualSide={item.allowed_for_object_forming_visual_side} textSide={item.allowed_for_text_side}")
    return "\n".join(lines).rstrip() + "\n"
