from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


Mode = Literal["clean-editable", "visual-fidelity", "visual-ocr", "all"]
EXPORT_MODES: tuple[str, ...] = ("clean-editable", "visual-fidelity", "visual-ocr")
BoundarySource = Literal["m29", "psdlike", "hybrid"]
BOUNDARY_SOURCES: tuple[str, ...] = ("m29", "psdlike", "hybrid")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class PageInput:
    id: str
    path: Path
    original_name: str


@dataclass(frozen=True)
class ExportRequest:
    inputs: list[PageInput]
    out_dir: Path
    project_name: str
    mode: Mode = "all"
    columns: str = "auto"
    include_debug: bool = True
    ocr_provider: str | None = None
    boundary_source: BoundarySource = "m29"


@dataclass(frozen=True)
class M29RunResult:
    artifact_dir: Path
    source_png: Path
    stdout_path: Path
    stderr_path: Path
