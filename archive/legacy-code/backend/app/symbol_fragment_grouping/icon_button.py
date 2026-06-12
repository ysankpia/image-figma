from __future__ import annotations

from typing import Any

from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_contains
from .geometry import is_interactive_shape, merge_bboxes, merged_bbox_score, parse_bbox
from .lineage import build_interactive_shape_lineage
from .types import M291FragmentCandidate, M291GroupMember, M291Options, M291SymbolGroup


def add_icon_button_groups(
    groups: list[M291SymbolGroup],
    candidates: list[M291FragmentCandidate],
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[M291SymbolGroup]:
    output = list(groups)
    accepted_groups = [group for group in groups if group.decision == "accepted"]
    used_pairs: set[tuple[str, str]] = set()
    for shape in [node for node in nodes if is_interactive_shape(node)]:
        shape_bbox = parse_bbox(shape.get("bbox"))
        if shape_bbox is None:
            continue
        foreground_groups = [group for group in accepted_groups if bbox_contains(shape_bbox, group.bbox)]
        foreground_candidates = [candidate for candidate in candidates if bbox_contains(shape_bbox, candidate.bbox)]
        for group in foreground_groups[:1]:
            key = (str(shape.get("id")), group.id)
            if key in used_pairs:
                continue
            used_pairs.add(key)
            output.append(make_icon_button_group(f"group_{len(output) + 1:03d}", shape, group.bbox, group.id, group.id, shape_bbox, pixels, options))
        if foreground_groups:
            continue
        for candidate in foreground_candidates[:1]:
            key = (str(shape.get("id")), candidate.id)
            if key in used_pairs:
                continue
            used_pairs.add(key)
            output.append(make_icon_button_group(f"group_{len(output) + 1:03d}", shape, candidate.bbox, candidate.id, candidate.source_node_id, shape_bbox, pixels, options))
    return output

def make_icon_button_group(
    id: str,
    shape: dict[str, Any],
    foreground_bbox: list[int],
    foreground_candidate_id: str,
    foreground_source_id: str,
    shape_bbox: list[int],
    pixels: PngPixels,
    options: M291Options,
) -> M291SymbolGroup:
    bbox = merge_bboxes([shape_bbox, foreground_bbox])
    confidence = min(0.92, 0.72 + 0.20 * merged_bbox_score(bbox, options))
    return M291SymbolGroup(
        id=id,
        group_type="icon_button_group",
        decision="accepted",
        member_ids=[f"background_{shape.get('id')}", foreground_candidate_id],
        members=[
            M291GroupMember(f"background_{shape.get('id')}", str(shape.get("id")), "button_background"),
            M291GroupMember(foreground_candidate_id, foreground_source_id, "foreground_symbol"),
        ],
        bbox=bbox,
        confidence=confidence,
        reasons=["interactive_shape_contains_symbol", "icon_button_group_relation"],
        source_lineage=build_interactive_shape_lineage(id, foreground_candidate_id, foreground_source_id),
    )
