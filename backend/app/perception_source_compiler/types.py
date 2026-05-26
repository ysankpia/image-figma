from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PerceptionSourceCompilerOptions:
    min_control_score: float = 0.25
    min_icon_score: float = 0.30
    duplicate_iou_threshold: float = 0.72
    media_near_equal_iou_threshold: float = 0.82
    max_control_area_ratio: float = 0.24
    max_icon_area_ratio: float = 0.045
    min_text_containment: float = 0.80
    min_control_text_area_ratio: float = 0.025
    max_control_text_area_ratio: float = 0.55
    max_icon_text_overlap: float = 0.20
    max_report_only_area_ratio: float = 0.35

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerceptionSourceCompilerResult:
    report: dict[str, Any]
    m292_document: dict[str, Any]
    output_dir: Path
