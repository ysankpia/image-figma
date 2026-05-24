from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import read_png_metadata
from ..visual_primitive_graph import bbox_in_bounds
from .types import M291AssetAuditItem, M291Document, M291FragmentCandidate, M291FragmentEdge, M291SymbolGroup


def validate_m291_document(document: M291Document, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M291SymbolFragmentGroupingDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.1 document schema")
    candidate_ids = {candidate.id for candidate in document.candidates}
    if len(candidate_ids) != len(document.candidates):
        raise ValueError("duplicate M29.1 candidate id")
    for candidate in document.candidates:
        if not bbox_in_bounds(candidate.bbox, width, height):
            raise ValueError(f"M29.1 candidate bbox out of bounds: {candidate.id}")
    edge_ids = {edge.id for edge in document.edges}
    if len(edge_ids) != len(document.edges):
        raise ValueError("duplicate M29.1 edge id")
    for edge in document.edges:
        if edge.left_id not in candidate_ids or edge.right_id not in candidate_ids:
            raise ValueError("M29.1 edge references missing candidate")
    group_ids = {group.id for group in document.groups}
    if len(group_ids) != len(document.groups):
        raise ValueError("duplicate M29.1 group id")
    for group in document.groups:
        if not bbox_in_bounds(group.bbox, width, height):
            raise ValueError(f"M29.1 group bbox out of bounds: {group.id}")
        if group.decision == "accepted" and group.asset_path is None:
            raise ValueError(f"M29.1 accepted group missing asset: {group.id}")
        if group.asset_path is not None:
            assert_readable_relative_png(output_dir, group.asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)

def build_m291_meta(
    candidates: list[M291FragmentCandidate],
    edges: list[M291FragmentEdge],
    groups: list[M291SymbolGroup],
    asset_audit: list[M291AssetAuditItem],
) -> dict[str, Any]:
    return {
        "notes": "m29_1_symbol_fragment_grouping_harness",
        "counts": {
            "candidates": len(candidates),
            "edges": len(edges),
            "groups": len(groups),
            "acceptedGroups": sum(1 for group in groups if group.decision == "accepted"),
            "uncertainGroups": sum(1 for group in groups if group.decision == "uncertain"),
            "rejectedGroups": sum(1 for group in groups if group.decision == "rejected"),
            "assetAudit": len(asset_audit),
        },
    }

def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.1 PNG output missing or unreadable: {path}")
