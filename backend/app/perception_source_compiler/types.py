from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PerceptionSourceCompilerOptions:
    min_control_score: float = 0.25
    min_geometry_control_score: float = 0.18
    min_icon_score: float = 0.30
    min_control_child_icon_score: float = 0.08
    duplicate_iou_threshold: float = 0.72
    media_near_equal_iou_threshold: float = 0.82
    max_control_area_ratio: float = 0.24
    max_icon_area_ratio: float = 0.045
    min_geometry_control_area_ratio: float = 0.0025
    min_text_containment: float = 0.80
    min_control_text_area_ratio: float = 0.025
    max_control_text_area_ratio: float = 0.55
    max_icon_text_overlap: float = 0.20
    min_control_child_containment: float = 0.82
    max_report_only_area_ratio: float = 0.35
    min_control_aspect_ratio: float = 2.0
    max_control_aspect_ratio: float = 8.5
    min_control_width_ratio: float = 0.18
    min_control_height_ratio: float = 0.028
    max_control_height_ratio: float = 0.12
    min_geometry_control_fill_ratio: float = 0.12
    max_geometry_control_edge_score: float = 0.32
    max_geometry_control_texture_score: float = 0.34

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerceptionSourceCompilerResult:
    report: dict[str, Any]
    m292_document: dict[str, Any]
    output_dir: Path
