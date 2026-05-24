from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


VISIBLE_REPLAY_ACTIONS = {"text_replay", "image_replay", "icon_replay", "shape_replay"}
LAYOUT_MODELS = {"row", "column", "grid", "overlay", "absolute"}


@dataclass(frozen=True)
class M29LayoutEnergyResult:
    report: dict[str, Any]
    output_dir: Path
