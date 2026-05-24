from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

VISIBLE_REPLAY_ACTIONS = {"text_replay", "image_replay", "icon_replay", "shape_replay"}
NON_VISIBLE_REPLAY_ACTIONS = {"preserve_in_parent_raster", "fallback_only", "diagnostic_only", "suppress_duplicate"}


@dataclass(frozen=True)
class M29OwnershipConservationResult:
    report: dict[str, Any]
    output_dir: Path

