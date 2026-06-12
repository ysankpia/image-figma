from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, crop_pixels
from .types import M291AssetAuditItem, M291FragmentCandidate, M291FragmentEdge, M291Options, M291SymbolGroup


def export_group_assets(groups: list[M291SymbolGroup], pixels: PngPixels, output_dir: Path) -> list[M291SymbolGroup]:
    group_dir = output_dir / "assets" / "symbol_groups"
    group_dir.mkdir(parents=True, exist_ok=True)
    exported: list[M291SymbolGroup] = []
    group_count = 0
    for group in groups:
        if group.decision != "accepted":
            exported.append(group)
            continue
        group_count += 1
        path = group_dir / f"symbol_group_{group_count:03d}.png"
        path.write_bytes(crop_pixels(pixels, group.bbox))
        exported.append(replace(group, asset_path=str(path.relative_to(output_dir))))
    return exported

def build_asset_audit(
    candidates: list[M291FragmentCandidate],
    edges: list[M291FragmentEdge],
    groups: list[M291SymbolGroup],
    options: M291Options,
) -> list[M291AssetAuditItem]:
    grouped_members = {member_id for group in groups if group.decision == "accepted" for member_id in group.member_ids}
    neighbors: dict[str, list[str]] = {}
    for edge in edges:
        if edge.decision in {"accepted", "weak"}:
            neighbors.setdefault(edge.left_id, []).append(edge.right_id)
            neighbors.setdefault(edge.right_id, []).append(edge.left_id)
    audit: list[M291AssetAuditItem] = []
    for candidate in candidates:
        reasons: list[str] = []
        if candidate.id in grouped_members:
            risk = "fragmented"
            score = 0.82
            reasons.append("member_of_accepted_group")
        elif candidate.id in neighbors:
            risk = "fragmented"
            score = 0.62
            reasons.append("nearby_fragment_candidate")
        elif candidate.metrics.aspect_ratio > options.max_text_like_aspect_ratio:
            risk = "text_like"
            score = 0.74
            reasons.append("wide_text_like_bbox")
        elif bbox_area(candidate.bbox) < 24:
            risk = "overcropped"
            score = 0.68
            reasons.append("very_small_bbox")
        else:
            risk = "isolated"
            score = 0.35
            reasons.append("no_group_neighbor")
        audit.append(M291AssetAuditItem(candidate.id, candidate.bbox, risk, score, reasons, sorted(neighbors.get(candidate.id, []))))
    return audit
