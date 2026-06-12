from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .groups import build_groups
from .types import VisualEvidenceDocument, VisualEvidenceItem


def write_outputs(document: VisualEvidenceDocument, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "visual_evidence.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "visual_evidence.md").write_text(build_markdown_report(document), encoding="utf-8")

def build_markdown_report(document: VisualEvidenceDocument) -> str:
    lines = [
        "# M29.0.3 Visual Evidence Normalization",
        "",
        f"- Source M29.0.2 audit: `{document.source_m2902_audit_json}`",
        f"- Items: {len(document.items)}",
        f"- Buckets: `{document.groups.get('byVisualKind', {})}`",
        f"- Decisions: `{document.groups.get('byDecision', {})}`",
        "",
        "## Evidence By Region",
        "",
    ]
    by_region = document.groups.get("byRegion", {})
    if isinstance(by_region, dict):
        for region, counts in by_region.items():
            lines.append(f"- `{region}`: `{counts}`")
    lines.extend(["", "## Items", ""])
    for item in document.items[:160]:
        lines.append(
            f"- `{item.id}` `{item.visual_kind}` `{item.decision}` source=`{item.source}` "
            f"sourceId=`{item.source_evidence_id}` bbox={item.bbox} textOverlap={item.text_overlap_ratio:.3f}"
        )
    return "\n".join(lines).rstrip() + "\n"

def build_meta(m2902_audit_json_path: str, media_evidence: list[Any], items: list[VisualEvidenceItem], m291_lineage_json_path: str | None = None) -> dict[str, Any]:
    return {
        "notes": "m29_0_3_visual_evidence_normalization",
        "sourceM2902AuditJson": m2902_audit_json_path,
        "sourceM291LineageJson": m291_lineage_json_path,
        "sourceEvidenceCount": len(media_evidence),
        "itemCount": len(items),
        "bucketCounts": build_groups(items)["byVisualKind"],
        "lineageAwareItemCount": sum(1 for item in items if item.source_lineage is not None),
    }
