from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


VISIBLE_REPLAY_ACTIONS = {"text_replay", "image_replay", "icon_replay", "shape_replay"}
STRUCTURAL_CLUSTER_ROLE_HINTS = {"row_like", "column_like", "repeated_item_like"}


@dataclass(frozen=True)
class M29SiblingGroupCandidateResult:
    report: dict[str, Any]
    output_dir: Path
