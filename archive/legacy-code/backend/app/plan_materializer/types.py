from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PlanMaterializerOptions:
    enable_text_replay: bool = True
    enable_image_replay: bool = True
    enable_symbol_replay: bool = True
    enable_simple_shape_replay: bool = True
    enable_controlled_structure_materialization: bool = True
    erase_replayed_bboxes_from_fallback: bool = True
    max_total_visible_nodes: int = 260
    max_controlled_groups: int = 24
    controlled_group_min_members: int = 2
    controlled_group_max_members: int = 16
    controlled_group_min_score: float = 0.74
    controlled_group_max_area_ratio: float = 0.55

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanMaterializerResult:
    dsl: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True)
class ReplayNode:
    id: str
    kind: str
    source_id: str
    bbox: list[int]
    role: str | None = None
    asset_id: str | None = None
    asset_url: str | None = None
    replay_decision: str | None = None
