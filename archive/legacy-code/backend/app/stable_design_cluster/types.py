from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


PrimaryRelation = Literal["near_equal", "contains", "contained_by", "overlaps", "disjoint"]
ClusterPattern = Literal[
    "containment_anchor_subgraph",
    "directed_row_subgraph",
    "directed_column_subgraph",
    "repeated_size_subgraph",
    "stable_local_relation_subgraph",
]
RoleHint = Literal[
    "row_like",
    "column_like",
    "repeated_item_like",
    "background_anchor_like",
    "media_text_group_like",
]

PRIMARY_RELATIONS: set[str] = {"near_equal", "contains", "contained_by", "overlaps", "disjoint"}
SECONDARY_RELATIONS: set[str] = {
    "near",
    "left_of",
    "right_of",
    "above",
    "below",
    "aligned_left",
    "aligned_center_x",
    "aligned_right",
    "aligned_top",
    "aligned_center_y",
    "aligned_bottom",
    "same_width",
    "same_height",
    "same_size",
}


@dataclass(frozen=True)
class M294Options:
    max_cluster_members: int = 12
    min_stability_score: float = 0.55
    duplicate_bbox_iou_threshold: float = 0.92
    duplicate_member_overlap_threshold: float = 0.85

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M294Result:
    report: dict[str, Any]
    output_dir: Path
