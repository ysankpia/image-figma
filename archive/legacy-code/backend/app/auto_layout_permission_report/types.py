from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_AUTO_LAYOUT_MODELS = {"row", "column", "grid"}


@dataclass(frozen=True)
class M29AutoLayoutPermissionResult:
    report: dict[str, Any]
    output_dir: Path


@dataclass(frozen=True)
class M29AutoLayoutPermissionOptions:
    max_row_column_energy: float = 0.32
    max_grid_energy: float = 0.28

    def threshold_for(self, model: str) -> float:
        if model == "grid":
            return self.max_grid_energy
        return self.max_row_column_energy
