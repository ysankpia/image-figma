from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class M29BStageQualityResult:
    report: dict[str, Any]
    output_dir: Path

