from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..auto_layout_permission_report import extract_m29_auto_layout_permission_report
from ..b_stage_quality_report import extract_m29_b_stage_quality_report
from ..design_token_report import extract_m29_design_token_report
from ..dsl_visual_comparison import extract_dsl_visual_comparison
from ..m29_replay_plan import build_m295_replay_plan
from ..hierarchy_candidate_report import extract_m29_hierarchy_candidate_report
from ..internal_source_promotion import extract_m29_internal_source_promotion_report
from ..layout_energy_report import extract_m29_layout_energy_report
from ..media_internal_decomposition import extract_m29_media_internal_decomposition_report
from ..ownership_conservation import extract_m29_ownership_conservation_report
from ..ocr import extract_ocr
from ..plan_materializer import build_plan_driven_dsl
from ..png_tools import PngMetadata
from ..region_relation_graph_report import extract_m2931_region_relation_graph_report
from ..sibling_group_candidate_report import extract_m29_sibling_group_candidate_report
from ..source_ui_physical_graph import extract_source_ui_physical_graph
from ..stable_design_cluster import extract_m294_stable_design_cluster_report
from ..state import state
from ..transparent_asset_report import extract_m29_transparent_asset_report
from ..visual_primitive_graph import extract_m29_visual_primitive_graph
from .paths import UploadPreviewPaths
from .types import UploadPreviewArtifactPolicy, UploadPreviewPipelineError


def run_ocr(task_id: str, image: PngMetadata, upload_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    document = extract_ocr(task_id=task_id, image=image, settings=state.settings, source_path=upload_path)
    ocr_json = output_dir / "ocr.json"
    ocr_json.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    now = datetime.now(UTC).isoformat()
    state.database.insert_ocr_result(
        {
            "task_id": task_id,
            "provider": document.provider,
            "model": document.model,
            "status": document.status,
            "ocr_path": str(ocr_json),
            "block_count": len(document.blocks),
            "error_code": document.error["code"] if document.error else None,
            "error_message": document.error["message"] if document.error else None,
            "created_at": now,
        }
    )
    if document.status == "failed":
        code = document.error["code"] if document.error else "OCR_EXTRACTION_FAILED"
        message = document.error["message"] if document.error else "OCR extraction failed."
        raise UploadPreviewPipelineError("ocr", code, message)
    return document


def run_m29_visual_primitive_stage(
    *,
    png_data: bytes,
    source_image: str,
    paths: UploadPreviewPaths,
    text_boxes: list[Any],
    policy: UploadPreviewArtifactPolicy,
):
    return extract_m29_visual_primitive_graph(
        png_data=png_data,
        source_image=source_image,
        output_dir=paths.m29,
        text_boxes=text_boxes,
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    )


def run_m292_source_ui_physical_stage(*, png_data: bytes, paths: UploadPreviewPaths, m29_document: Any, ocr_document: Any) -> dict[str, Any]:
    return extract_source_ui_physical_graph(
        source_png=png_data,
        m29_document=m29_document.to_dict(),
        ocr_document=ocr_document.to_dict(),
        output_dir=paths.m29_2,
    )


def run_m2931_relation_stage(*, task_id: str, paths: UploadPreviewPaths, m292_document: dict[str, Any]):
    return extract_m2931_region_relation_graph_report(
        task_id=task_id,
        m292_document=m292_document,
        output_dir=paths.m29_3,
    )


def run_m294_cluster_stage(*, task_id: str, paths: UploadPreviewPaths, m2931_report: dict[str, Any]):
    return extract_m294_stable_design_cluster_report(
        task_id=task_id,
        m2931_report=m2931_report,
        output_dir=paths.m29_4,
    )


def run_m295_replay_plan_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any],
    m294_report: dict[str, Any],
):
    return build_m295_replay_plan(
        task_id=task_id,
        m292_document=m292_document,
        m2931_report=m2931_report,
        m294_report=m294_report,
        output_dir=paths.m29_5,
    )


def run_m29_ownership_conservation_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any],
    m295_report: dict[str, Any],
):
    return extract_m29_ownership_conservation_report(
        task_id=task_id,
        m292_document=m292_document,
        m2931_report=m2931_report,
        m295_report=m295_report,
        output_dir=paths.m29_ownership_conservation,
    )


def run_m29_media_internal_decomposition_stage(
    *,
    task_id: str,
    png_data: bytes,
    paths: UploadPreviewPaths,
    m29_document: Any,
    ocr_document: Any,
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any],
    m295_report: dict[str, Any],
):
    return extract_m29_media_internal_decomposition_report(
        task_id=task_id,
        source_png=png_data,
        m29_document=m29_document.to_dict(),
        ocr_document=ocr_document.to_dict(),
        m292_document=m292_document,
        m2931_report=m2931_report,
        m295_report=m295_report,
        output_dir=paths.m29_media_internal_decomposition,
    )


def run_m29_transparent_asset_stage(
    *,
    task_id: str,
    png_data: bytes,
    paths: UploadPreviewPaths,
    ocr_document: Any,
    m292_document: dict[str, Any],
    media_internal_report: dict[str, Any],
):
    return extract_m29_transparent_asset_report(
        task_id=task_id,
        source_png=png_data,
        ocr_document=ocr_document.to_dict(),
        m292_document=m292_document,
        media_internal_report=media_internal_report,
        output_dir=paths.m29_transparent_assets,
    )


def run_m29_internal_source_promotion_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    m292_document: dict[str, Any],
    media_internal_report: dict[str, Any],
    transparent_asset_report: dict[str, Any],
):
    return extract_m29_internal_source_promotion_report(
        task_id=task_id,
        m292_document=m292_document,
        media_internal_report=media_internal_report,
        transparent_asset_report=transparent_asset_report,
        output_dir=paths.m29_internal_source_promotion,
    )


def run_m29_hierarchy_candidate_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any],
    m295_report: dict[str, Any],
):
    return extract_m29_hierarchy_candidate_report(
        task_id=task_id,
        m292_document=m292_document,
        m2931_report=m2931_report,
        m295_report=m295_report,
        output_dir=paths.m29_hierarchy_candidates,
    )


def run_m29_sibling_group_candidate_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    m2931_report: dict[str, Any],
    m294_report: dict[str, Any],
    m295_report: dict[str, Any],
    hierarchy_report: dict[str, Any],
):
    return extract_m29_sibling_group_candidate_report(
        task_id=task_id,
        m2931_report=m2931_report,
        m294_report=m294_report,
        m295_report=m295_report,
        hierarchy_report=hierarchy_report,
        output_dir=paths.m29_sibling_groups,
    )


def run_m29_layout_energy_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    m295_report: dict[str, Any],
    hierarchy_report: dict[str, Any],
    sibling_group_report: dict[str, Any],
):
    return extract_m29_layout_energy_report(
        task_id=task_id,
        m295_report=m295_report,
        hierarchy_report=hierarchy_report,
        sibling_group_report=sibling_group_report,
        output_dir=paths.m29_layout_energy,
    )


def run_m29_auto_layout_permission_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    layout_energy_report: dict[str, Any],
):
    return extract_m29_auto_layout_permission_report(
        task_id=task_id,
        layout_energy_report=layout_energy_report,
        output_dir=paths.m29_auto_layout_permission,
    )


def run_materialization_stage(
    *,
    task_id: str,
    png_data: bytes,
    upload_path: Path,
    paths: UploadPreviewPaths,
    m29_document: Any,
    m29_json: Path,
    ocr_document: Any,
    m292_document: dict[str, Any],
    m295_report: dict[str, Any],
    hierarchy_report: dict[str, Any] | None = None,
    sibling_group_report: dict[str, Any] | None = None,
    layout_energy_report: dict[str, Any] | None = None,
    auto_layout_permission_report: dict[str, Any] | None = None,
):
    return build_plan_driven_dsl(
        source_png=png_data,
        source_image_path=str(upload_path),
        m29_document={**m29_document.to_dict(), "sourceM29NodesJson": str(m29_json)},
        ocr_document=ocr_document.to_dict(),
        m292_document=m292_document,
        m295_replay_plan=m295_report,
        hierarchy_report=hierarchy_report,
        sibling_group_report=sibling_group_report,
        layout_energy_report=layout_energy_report,
        auto_layout_permission_report=auto_layout_permission_report,
        extra_warnings=[],
        output_dir=paths.materialized_design,
        task_id=task_id,
    )


def run_m29_design_token_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    dsl: dict[str, Any],
    materialization_report: dict[str, Any],
    m295_report: dict[str, Any],
):
    return extract_m29_design_token_report(
        task_id=task_id,
        dsl=dsl,
        materialization_report=materialization_report,
        m295_report=m295_report,
        output_dir=paths.m29_design_tokens,
    )


def run_m29_b_stage_quality_stage(
    *,
    task_id: str,
    paths: UploadPreviewPaths,
    ownership_report: dict[str, Any],
    hierarchy_report: dict[str, Any],
    sibling_group_report: dict[str, Any],
    layout_energy_report: dict[str, Any],
    auto_layout_permission_report: dict[str, Any],
    design_token_report: dict[str, Any],
    materialization_report: dict[str, Any],
):
    return extract_m29_b_stage_quality_report(
        task_id=task_id,
        ownership_report=ownership_report,
        hierarchy_report=hierarchy_report,
        sibling_group_report=sibling_group_report,
        layout_energy_report=layout_energy_report,
        auto_layout_permission_report=auto_layout_permission_report,
        design_token_report=design_token_report,
        materialization_report=materialization_report,
        output_dir=paths.m29_b_stage_quality,
    )


def run_m29_dsl_visual_comparison_stage(
    *,
    task_id: str,
    png_data: bytes,
    paths: UploadPreviewPaths,
    dsl: dict[str, Any],
):
    return extract_dsl_visual_comparison(
        task_id=task_id,
        source_png=png_data,
        dsl=dsl,
        materialized_design_dir=paths.materialized_design,
        public_assets_dir=state.storage.assets_dir,
        output_dir=paths.m29_dsl_visual_comparison,
    )
