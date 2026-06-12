from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import read_png_metadata
from ..visual_primitive_graph import bbox_in_bounds
from .types import M2907Document, OwnershipDecision


def validate_text_visual_ownership_gate_document(
    document: M2907Document,
    output_dir: Path,
    width: int,
    height: int,
    m2903_document: dict[str, Any],
    m2902_document: dict[str, Any],
    *,
    require_preview_artifacts: bool = True,
) -> None:
    if document.schema_name != "M2907TextVisualOwnershipGateDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.7 document schema")
    assert_unique([item.id for item in document.ownership_decisions], "ownership decision")
    visual_ids = {str(item.get("id")) for item in m2903_document.get("items", []) if isinstance(item, dict) and item.get("id")}
    source_ids = {str(item.get("sourceEvidenceId")) for item in m2903_document.get("items", []) if isinstance(item, dict) and item.get("sourceEvidenceId")}
    text_ids = {str(item.get("id")) for item in m2902_document.get("textBoxes", []) if isinstance(item, dict) and item.get("id")}
    for item in document.ownership_decisions:
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.7 decision bbox out of bounds: {item.id}")
        if item.source == "m2903_visual_evidence":
            if item.source_visual_evidence_item_id not in visual_ids or item.source_evidence_id not in source_ids:
                raise ValueError(f"M29.0.7 decision references missing visual evidence: {item.id}")
        elif item.source == "m2902_text_box":
            if item.source_text_box_id not in text_ids:
                raise ValueError(f"M29.0.7 decision references missing text box: {item.id}")
        else:
            raise ValueError(f"M29.0.7 illegal source: {item.id}")
        if item.ownership == "text_owned" and item.allowed_for_object_forming_visual_side:
            raise ValueError(f"M29.0.7 text-owned decision cannot allow visual side: {item.id}")
        if item.suppressed_as_visual and item.allowed_for_object_forming_visual_side:
            raise ValueError(f"M29.0.7 suppressed visual cannot allow visual side: {item.id}")
    for path in document.debug.to_dict().values():
        metadata = assert_readable_relative_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.0.7 overlay dimensions do not match source image: {path}")
    if require_preview_artifacts:
        assert_readable_relative_png(output_dir, "preview_text_visual_ownership_gate.png")

def build_meta(decisions: list[OwnershipDecision], examples: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "notes": "m29_0_7_text_visual_ownership_gate",
        "decisionCount": len(decisions),
        "exampleCount": len(examples),
        "ownershipCounts": count_by(decisions, lambda item: item.ownership),
        "decisionCounts": count_by(decisions, lambda item: item.decision),
        "ownershipReasonKindCounts": count_by(decisions, lambda item: item.ownership_reason_kind),
        "objectFormingVisualAllowedCount": sum(1 for item in decisions if item.allowed_for_object_forming_visual_side),
        "textSideAllowedCount": sum(1 for item in decisions if item.allowed_for_text_side),
        "suppressedAsVisualCount": sum(1 for item in decisions if item.suppressed_as_visual),
    }

def count_by(items: list[Any], key_fn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

def assert_unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate M29.0.7 {label} id: {value}")
        seen.add(value)
    return seen

def assert_readable_relative_png(output_dir: Path, path: str):
    resolved = output_dir / path
    if not resolved.exists():
        raise ValueError(f"M29.0.7 PNG output missing or unreadable: {path}")
    metadata = read_png_metadata(resolved.read_bytes())
    if metadata is None:
        raise ValueError(f"M29.0.7 PNG output missing or unreadable: {path}")
    return metadata
