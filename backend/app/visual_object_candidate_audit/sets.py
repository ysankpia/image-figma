from __future__ import annotations

from .geometry import bbox_union, center_x, center_y
from .types import M2904Options, SetKind, VisualObjectCandidate, VisualObjectEvidenceEdge, VisualObjectSetCandidate


def build_set_candidates(
    objects: list[VisualObjectCandidate],
    edges: list[VisualObjectEvidenceEdge],
    options: M2904Options,
) -> list[VisualObjectSetCandidate]:
    usable = [item for item in objects if item.decision in {"accepted", "candidate", "uncertain"} and item.object_kind in {"visual_text_pair", "single_visual", "compound_visual"}]
    rows = group_objects_by_row(usable, options)
    sets: list[VisualObjectSetCandidate] = []
    for row in rows:
        if len(row) < options.min_set_members:
            continue
        row = sorted(row, key=lambda item: center_x(item.bbox))
        if not regular_spacing(row):
            set_kind: SetKind = "aligned_row_set"
            confidence = 0.58
            reasons = ["aligned_row"]
        else:
            set_kind = "repeated_visual_set"
            confidence = 0.72
            reasons = ["same_row", "regular_spacing"]
        sets.append(
            VisualObjectSetCandidate(
                id=f"set_{len(sets) + 1:04d}",
                set_kind=set_kind,
                decision="candidate",
                member_object_ids=[item.id for item in row],
                bbox=bbox_union([item.bbox for item in row]),
                confidence=confidence,
                edge_ids=[],
                risks=[],
                reasons=reasons,
            )
        )
    return sets

def group_objects_by_row(objects: list[VisualObjectCandidate], options: M2904Options) -> list[list[VisualObjectCandidate]]:
    rows: list[list[VisualObjectCandidate]] = []
    for item in sorted(objects, key=lambda obj: (center_y(obj.bbox), center_x(obj.bbox))):
        for row in rows:
            if abs(sum(center_y(obj.bbox) for obj in row) / len(row) - center_y(item.bbox)) <= options.row_tolerance:
                row.append(item)
                break
        else:
            rows.append([item])
    return rows

def regular_spacing(objects: list[VisualObjectCandidate]) -> bool:
    if len(objects) < 3:
        return False
    centers = [center_x(item.bbox) for item in objects]
    gaps = [centers[index + 1] - centers[index] for index in range(len(centers) - 1)]
    avg = sum(gaps) / len(gaps)
    return avg > 0 and all(abs(gap - avg) <= max(18, avg * 0.35) for gap in gaps)
