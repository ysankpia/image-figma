from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


VISIBLE_REPLAY_ACTIONS = {"text_replay", "image_replay", "icon_replay", "shape_replay"}
PARENT_REPLAY_ACTIONS = {"image_replay", "shape_replay"}
NON_HIERARCHY_ACTIONS = {"preserve_in_parent_raster", "suppress_duplicate", "fallback_only", "diagnostic_only"}


@dataclass(frozen=True)
class M29HierarchyCandidateResult:
    report: dict[str, Any]
    output_dir: Path
