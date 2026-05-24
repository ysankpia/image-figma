from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..m29_replay_plan import build_m295_replay_plan
from ..hierarchy_candidate_report import extract_m29_hierarchy_candidate_report
from ..ownership_conservation import extract_m29_ownership_conservation_report
from ..ocr import extract_ocr
from ..plan_materializer import build_plan_driven_dsl
from ..png_tools import PngMetadata
from ..region_relation_graph_report import extract_m2931_region_relation_graph_report
from ..source_ui_physical_graph import extract_source_ui_physical_graph
from ..stable_design_cluster import extract_m294_stable_design_cluster_report
from ..state import state
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
):
    return build_plan_driven_dsl(
        source_png=png_data,
        source_image_path=str(upload_path),
        m29_document={**m29_document.to_dict(), "sourceM29NodesJson": str(m29_json)},
        ocr_document=ocr_document.to_dict(),
        m292_document=m292_document,
        m295_replay_plan=m295_report,
        extra_warnings=[],
        output_dir=paths.materialized_design,
        task_id=task_id,
    )
