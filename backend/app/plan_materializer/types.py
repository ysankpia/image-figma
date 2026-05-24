from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PlanMaterializerOptions:
    enable_text_replay: bool = True
    enable_image_replay: bool = True
    enable_symbol_replay: bool = True
    enable_simple_shape_replay: bool = True
    erase_replayed_bboxes_from_fallback: bool = True
    max_total_visible_nodes: int = 260

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
