from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class M29DesignTokenResult:
    report: dict[str, Any]
    output_dir: Path

