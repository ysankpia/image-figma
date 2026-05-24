from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..state import state


@dataclass(frozen=True)
class UploadPreviewPaths:
    root: Path
    ocr: Path
    m29: Path
    m29_2: Path
    m29_3: Path
    m29_4: Path
    m29_5: Path
    m29_ownership_conservation: Path
    m29_hierarchy_candidates: Path
    m29_sibling_groups: Path
    materialized_design: Path


def pipeline_paths(task_id: str) -> UploadPreviewPaths:
    root = state.settings.storage_root / "upload_previews" / task_id
    return UploadPreviewPaths(
        root=root,
        ocr=root / "ocr",
        m29=root / "m29",
        m29_2=root / "m29_2",
        m29_3=root / "m29_3",
        m29_4=root / "m29_4",
        m29_5=root / "m29_5",
        m29_ownership_conservation=root / "m29_ownership_conservation",
        m29_hierarchy_candidates=root / "m29_hierarchy_candidates",
        m29_sibling_groups=root / "m29_sibling_groups",
        materialized_design=root / "materialized_design",
    )
