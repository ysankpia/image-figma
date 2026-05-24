from __future__ import annotations

import json
from datetime import UTC, datetime

from ..database import json_dumps
from ..png_tools import read_png_metadata
from ..state import state
from ..text_masked_media_audit import text_boxes_from_ocr_document
from .assets import publish_m29_assets
from .paths import UploadPreviewPaths, pipeline_paths
from .stages import (
    run_m292_source_ui_physical_stage,
    run_m2931_relation_stage,
    run_m294_cluster_stage,
    run_m295_replay_plan_stage,
    run_m29_hierarchy_candidate_stage,
    run_m29_layout_energy_stage,
    run_m29_ownership_conservation_stage,
    run_m29_sibling_group_candidate_stage,
    run_m29_visual_primitive_stage,
    run_materialization_stage,
    run_ocr,
)
from .task_state import complete_task, fail_task, update_task
from .timings import StageTiming, run_stage, write_stage_timings
from .types import UploadPreviewArtifactPolicy, UploadPreviewPipelineError


def run_upload_preview_pipeline(task_id: str) -> None:
    paths = pipeline_paths(task_id)
    try:
        run_pipeline(task_id, paths)
    except UploadPreviewPipelineError as error:
        fail_task(task_id, error.stage, error.code, str(error))
    except Exception as error:  # noqa: BLE001 - background tasks must record failure, not crash silently.
        fail_task(task_id, "m29_pipeline", "M29_MAINLINE_PIPELINE_FAILED", str(error))


def run_pipeline(task_id: str, paths: UploadPreviewPaths) -> None:
    policy = artifact_policy_from_settings()
    timings: list[StageTiming] = []
    upload_path = state.storage.upload_path(task_id)
    png_data = upload_path.read_bytes()
    image = read_png_metadata(png_data)
    if image is None:
        raise UploadPreviewPipelineError("upload", "INVALID_IMAGE_DIMENSIONS", "PNG image dimensions could not be read.")
    paths.root.mkdir(parents=True, exist_ok=True)

    source_image = str(upload_path)
    update_task(task_id, "ocr", 8, "Running OCR.")
    ocr_document = run_stage(paths, timings, "ocr", lambda: run_ocr(task_id, image, upload_path, paths.ocr))
    text_boxes, text_warnings = text_boxes_from_ocr_document(ocr_document.to_dict())

    update_task(task_id, "m29", 18, "Running M29 visual primitive graph.")
    m29_document = run_stage(
        paths,
        timings,
        "m29",
        lambda: run_m29_visual_primitive_stage(
            png_data=png_data,
            source_image=source_image,
            paths=paths,
            text_boxes=text_boxes,
            policy=policy,
        ),
    )
    m29_json = paths.m29 / "nodes.json"

    update_task(task_id, "m29_2_source_ui_physical_graph", 21, "Classifying M29.2 source pixel ownership.")
    m292_document = run_stage(
        paths,
        timings,
        "m29_2_source_ui_physical_graph",
        lambda: run_m292_source_ui_physical_stage(
            png_data=png_data,
            paths=paths,
            m29_document=m29_document,
            ocr_document=ocr_document,
        ),
    )

    update_task(task_id, "m29_3_relation_graph_report", 22, "Building M29.3.1 source relation graph report.")
    m2931_result = run_stage(
        paths,
        timings,
        "m29_3_relation_graph_report",
        lambda: run_m2931_relation_stage(
            task_id=task_id,
            paths=paths,
            m292_document=m292_document,
        ),
    )

    update_task(task_id, "m29_4_stable_design_cluster", 24, "Building M29.4 stable design cluster report.")
    m294_result = run_stage(
        paths,
        timings,
        "m29_4_stable_design_cluster",
        lambda: run_m294_cluster_stage(
            task_id=task_id,
            paths=paths,
            m2931_report=m2931_result.report,
        ),
    )

    update_task(task_id, "m29_5_replay_plan", 25, "Building M29.5 replay quality plan.")
    m295_result = run_stage(
        paths,
        timings,
        "m29_5_replay_plan",
        lambda: run_m295_replay_plan_stage(
            task_id=task_id,
            paths=paths,
            m292_document=m292_document,
            m2931_report=m2931_result.report,
            m294_report=m294_result.report,
        ),
    )

    update_task(task_id, "m29_ownership_conservation", 28, "Checking M29 ownership conservation.")
    run_stage(
        paths,
        timings,
        "m29_ownership_conservation",
        lambda: run_m29_ownership_conservation_stage(
            task_id=task_id,
            paths=paths,
            m292_document=m292_document,
            m2931_report=m2931_result.report,
            m295_report=m295_result.report,
        ),
    )

    update_task(task_id, "m29_hierarchy_candidates", 31, "Building M29 hierarchy candidate report.")
    hierarchy_result = run_stage(
        paths,
        timings,
        "m29_hierarchy_candidates",
        lambda: run_m29_hierarchy_candidate_stage(
            task_id=task_id,
            paths=paths,
            m292_document=m292_document,
            m2931_report=m2931_result.report,
            m295_report=m295_result.report,
        ),
    )

    update_task(task_id, "m29_sibling_groups", 34, "Building M29 sibling group candidate report.")
    sibling_group_result = run_stage(
        paths,
        timings,
        "m29_sibling_groups",
        lambda: run_m29_sibling_group_candidate_stage(
            task_id=task_id,
            paths=paths,
            m2931_report=m2931_result.report,
            m294_report=m294_result.report,
            m295_report=m295_result.report,
            hierarchy_report=hierarchy_result.report,
        ),
    )

    update_task(task_id, "m29_layout_energy", 37, "Computing M29 layout energy report.")
    run_stage(
        paths,
        timings,
        "m29_layout_energy",
        lambda: run_m29_layout_energy_stage(
            task_id=task_id,
            paths=paths,
            m295_report=m295_result.report,
            hierarchy_report=hierarchy_result.report,
            sibling_group_report=sibling_group_result.report,
        ),
    )

    update_task(task_id, "m29_materialization", 92, "Materializing M29 plan-driven DSL.")
    materialized_design_result = run_stage(
        paths,
        timings,
        "m29_materialization",
        lambda: run_materialization_stage(
            task_id=task_id,
            png_data=png_data,
            upload_path=upload_path,
            paths=paths,
            m29_document=m29_document,
            m29_json=m29_json,
            ocr_document=ocr_document,
            m292_document=m292_document,
            m295_report=m295_result.report,
        ),
    )

    update_task(task_id, "m29_asset_publish", 96, "Publishing M29 assets.")
    run_stage(paths, timings, "m29_asset_publish", lambda: publish_m29_assets(task_id, paths.materialized_design, materialized_design_result.dsl, image))

    output_dsl = paths.materialized_design / "design.dsl.json"
    output_dsl.write_text(json.dumps(materialized_design_result.dsl, ensure_ascii=False, indent=2), encoding="utf-8")

    now = datetime.now(UTC).isoformat()
    state.database.insert_dsl_result(
        {
            "task_id": task_id,
            "dsl_path": str(output_dsl),
            "version": "0.1",
            "validation_status": "valid",
            "validation_errors": json_dumps([]),
            "created_at": now,
        }
    )
    complete_task(task_id)
    write_stage_timings(paths, timings)


def artifact_policy_from_settings() -> UploadPreviewArtifactPolicy:
    profile = state.settings.upload_preview_profile
    if profile == "development":
        return UploadPreviewArtifactPolicy(profile="development", emit_debug_artifacts=True, emit_preview_artifacts=True)
    return UploadPreviewArtifactPolicy(profile="production", emit_debug_artifacts=False, emit_preview_artifacts=False)
