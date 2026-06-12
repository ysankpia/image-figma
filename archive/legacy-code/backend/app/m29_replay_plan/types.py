from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


ReplayAction = Literal[
    "text_replay",
    "image_replay",
    "icon_replay",
    "shape_replay",
    "preserve_in_parent_raster",
    "suppress_duplicate",
    "fallback_only",
    "diagnostic_only",
]
TargetRole = Literal["m29_text", "m29_image", "m29_symbol", "m29_shape"]


@dataclass(frozen=True)
class M295ReplayPlanOptions:
    max_visible_nodes: int = 260

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M295ReplayPlanResult:
    report: dict[str, Any]
    output_dir: Path
