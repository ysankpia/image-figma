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
    m29_media_internal_decomposition: Path
    m29_transparent_assets: Path
    m29_evidence_contract: Path
    m29_internal_source_promotion: Path
    m29_hierarchy_candidates: Path
    m29_sibling_groups: Path
    m29_layout_energy: Path
    m29_auto_layout_permission: Path
    m29_design_tokens: Path
    m29_b_stage_quality: Path
    m29_dsl_visual_comparison: Path
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
        m29_media_internal_decomposition=root / "m29_media_internal_decomposition",
        m29_transparent_assets=root / "m29_transparent_assets",
        m29_evidence_contract=root / "m29_evidence_contract",
        m29_internal_source_promotion=root / "m29_internal_source_promotion",
        m29_hierarchy_candidates=root / "m29_hierarchy_candidates",
        m29_sibling_groups=root / "m29_sibling_groups",
        m29_layout_energy=root / "m29_layout_energy",
        m29_auto_layout_permission=root / "m29_auto_layout_permission",
        m29_design_tokens=root / "m29_design_tokens",
        m29_b_stage_quality=root / "m29_b_stage_quality",
        m29_dsl_visual_comparison=root / "m29_dsl_visual_comparison",
        materialized_design=root / "materialized_design",
    )
