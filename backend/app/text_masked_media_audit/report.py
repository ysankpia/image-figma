from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..visual_primitive_graph import M29TextBox
from .types import MediaEvidenceItem, TextMaskedMediaAuditDocument


def write_outputs(document: TextMaskedMediaAuditDocument, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "text_masked_media_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_masked_media_audit.md").write_text(build_markdown_report(document), encoding="utf-8")

def build_markdown_report(document: TextMaskedMediaAuditDocument) -> str:
    lines = [
        "# M29.0.2 Text-Masked Visual Media Audit",
        "",
        f"- Text source: `{document.text_source}`",
        f"- Text boxes: {len(document.text_boxes)}",
        f"- Media evidence: {len(document.media_evidence)}",
        f"- Before counts: `{document.before_counts}`",
        f"- After counts: `{document.after_counts}`",
        "",
        "## Evidence By Region",
        "",
    ]
    for region in document.regions:
        items = [item for item in document.media_evidence if item.region_name == region.name]
        if not items:
            continue
        lines.append(f"### {region.name}")
        for item in items[:80]:
            lines.append(
                f"- `{item.id}` `{item.source}` `{item.decision}` bbox={item.bbox} "
                f"textOverlap={item.text_overlap_ratio:.3f} action=`{item.suggested_next_action}`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def build_meta(text_boxes: list[M29TextBox], evidence: list[MediaEvidenceItem]) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for item in evidence:
        by_source[item.source] = by_source.get(item.source, 0) + 1
        by_action[item.suggested_next_action] = by_action.get(item.suggested_next_action, 0) + 1
    return {
        "notes": "m29_0_2_text_masked_media_audit",
        "textBoxCount": len(text_boxes),
        "evidenceCount": len(evidence),
        "evidenceBySource": dict(sorted(by_source.items())),
        "suggestedActionSummary": dict(sorted(by_action.items())),
    }
