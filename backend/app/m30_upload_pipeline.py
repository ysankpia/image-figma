from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .database import json_dumps
from .evidence_grounded_dsl_materialization import materialize_evidence_grounded_dsl, M30Options
from .hierarchy_materialization import M38Options, materialize_m38_hierarchy
from .hierarchy_readiness import extract_m37_hierarchy_readiness
from .ocr import extract_ocr
from .png_tools import PngMetadata, read_png_metadata
from .reconstruction_ui_tree import extract_m31_reconstruction_ui_tree
from .state import state
from .symbol_fragment_grouping import extract_m291_symbol_fragment_grouping
from .text_aware_visual_object_refinement import (
    M2905SourceExpansionRefs,
    extract_text_aware_visual_object_refinement,
)
from .text_masked_media_audit import extract_text_masked_media_audit, text_boxes_from_ocr_document
from .text_visual_ownership_gate import extract_text_visual_ownership_gate
from .visual_evidence_normalization import extract_visual_evidence_normalization
from .visual_object_candidate_audit import (
    M2904SourceExpansionRefs,
    extract_visual_object_candidate_audit,
)
from .visual_primitive_graph import extract_m29_visual_primitive_graph

M30PreviewProfile = Literal["production", "development"]


class M30UploadPipelineError(RuntimeError):
    def __init__(self, stage: str, code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code


@dataclass(frozen=True)
class M30PipelinePaths:
    root: Path
    ocr: Path
    m29: Path
    m291: Path
    m2902: Path
    m2903: Path
    m2907: Path
    m2904: Path
    m2905: Path
    m31: Path
    m30: Path
    m37: Path
    m38: Path
    m39: Path


@dataclass(frozen=True)
class M30ArtifactPolicy:
    profile: M30PreviewProfile
    emit_debug_artifacts: bool
    emit_preview_artifacts: bool


@dataclass
class StageTiming:
    stage: str
    started_at: str
    completed_at: str | None
    elapsed_seconds: float | None
    status: Literal["running", "completed", "failed"]
    error_code: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "elapsedSeconds": self.elapsed_seconds,
            "status": self.status,
            "errorCode": self.error_code,
            "message": self.message,
        }


def run_m30_preview_pipeline(task_id: str) -> None:
    paths = pipeline_paths(task_id)
    try:
        run_pipeline(task_id, paths)
    except M30UploadPipelineError as error:
        fail_task(task_id, error.stage, error.code, str(error))
    except Exception as error:  # noqa: BLE001 - background tasks must record failure, not crash silently.
        fail_task(task_id, "m30_pipeline", "M30_PREVIEW_PIPELINE_FAILED", str(error))


def run_pipeline(task_id: str, paths: M30PipelinePaths) -> None:
    policy = artifact_policy_from_settings()
    timings: list[StageTiming] = []
    upload_path = state.storage.upload_path(task_id)
    png_data = upload_path.read_bytes()
    image = read_png_metadata(png_data)
    if image is None:
        raise M30UploadPipelineError("upload", "INVALID_IMAGE_DIMENSIONS", "PNG image dimensions could not be read.")
    paths.root.mkdir(parents=True, exist_ok=True)

    source_image = str(upload_path)
    update_task(task_id, "ocr", 8, "Running OCR.")
    ocr_document = run_stage(paths, timings, "ocr", lambda: run_ocr(task_id, image, upload_path, paths.ocr))
    text_boxes, text_warnings = text_boxes_from_ocr_document(ocr_document.to_dict())

    update_task(task_id, "m29", 18, "Running M29 visual primitive graph.")
    m29_document = run_stage(paths, timings, "m29", lambda: extract_m29_visual_primitive_graph(
        png_data=png_data,
        source_image=source_image,
        output_dir=paths.m29,
        text_boxes=text_boxes,
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))
    m29_json = paths.m29 / "nodes.json"

    if state.settings.m31_upload_diagnostics_enabled:
        update_task(task_id, "m31_reconstruction", 24, "Building M31 reconstruction diagnostics.")
        run_m31_diagnostic_stage(
            task_id=task_id,
            paths=paths,
            timings=timings,
            upload_path=upload_path,
            png_data=png_data,
            ocr_document=ocr_document.to_dict(),
            ocr_json=paths.ocr / "ocr.json",
            m29_document=m29_document.to_dict(),
            m29_json=m29_json,
            policy=policy,
        )

    update_task(task_id, "m29_1", 30, "Running M29.1 symbol grouping.")
    m291_document = run_stage(paths, timings, "m29_1", lambda: extract_m291_symbol_fragment_grouping(
        m29_document=m29_document.to_dict(),
        m29_nodes_json_path=str(m29_json),
        png_data=png_data,
        source_image=source_image,
        output_dir=paths.m291,
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))
    m291_json = paths.m291 / "group_nodes.json"

    update_task(task_id, "m29_0_2", 42, "Running text-masked media audit.")
    m2902_document = run_stage(paths, timings, "m29_0_2", lambda: extract_text_masked_media_audit(
        png_data=png_data,
        source_image=source_image,
        output_dir=paths.m2902,
        text_boxes=text_boxes,
        text_source=f"ocr_provider:{ocr_document.provider}:{ocr_document.status}",
        m29_document=m29_document.to_dict(),
        m29_nodes_json_path=str(m29_json),
        m291_document=m291_document.to_dict(),
        m291_group_nodes_json_path=str(m291_json),
        warnings=text_warnings,
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))
    m2902_json = paths.m2902 / "text_masked_media_audit.json"

    update_task(task_id, "m29_0_3", 54, "Normalizing visual evidence.")
    m2903_document = run_stage(paths, timings, "m29_0_3", lambda: extract_visual_evidence_normalization(
        png_data=png_data,
        source_image=source_image,
        m2902_document=m2902_document.to_dict(),
        m2902_audit_json_path=str(m2902_json),
        output_dir=paths.m2903,
        m291_lineage_document=m291_document.to_dict(),
        m291_lineage_json_path=str(m291_json),
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))
    m2903_json = paths.m2903 / "visual_evidence.json"

    update_task(task_id, "m29_0_7", 64, "Routing text and visual ownership.")
    m2907_document = run_stage(paths, timings, "m29_0_7", lambda: extract_text_visual_ownership_gate(
        png_data=png_data,
        source_image=source_image,
        m2903_document=m2903_document.to_dict(),
        m2903_visual_evidence_json_path=str(m2903_json),
        m2902_document=m2902_document.to_dict(),
        m2902_audit_json_path=str(m2902_json),
        output_dir=paths.m2907,
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))
    m2907_json = paths.m2907 / "text_visual_ownership_gate.json"

    update_task(task_id, "m29_0_4", 74, "Building visual object candidates.")
    m2904_document = run_stage(paths, timings, "m29_0_4", lambda: extract_visual_object_candidate_audit(
        png_data=png_data,
        source_image=source_image,
        m2903_document=m2903_document.to_dict(),
        m2903_visual_evidence_json_path=str(m2903_json),
        m2902_document=m2902_document.to_dict(),
        m2902_audit_json_path=str(m2902_json),
        output_dir=paths.m2904,
        source_expansion_refs=M2904SourceExpansionRefs(
            m29_nodes_json=str(m29_json),
            m291_group_nodes_json=str(m291_json),
            m2902_media_evidence_json=str(m2902_json),
            m2907_ownership_json=str(m2907_json),
        ),
        m2907_ownership_document=m2907_document.to_dict(),
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))
    m2904_json = paths.m2904 / "visual_object_candidates.json"

    update_task(task_id, "m29_0_5", 84, "Refining text-aware visual objects.")
    m2905_document = run_stage(paths, timings, "m29_0_5", lambda: extract_text_aware_visual_object_refinement(
        png_data=png_data,
        source_image=source_image,
        m2904_document=m2904_document.to_dict(),
        m2904_visual_object_candidates_json_path=str(m2904_json),
        m2903_document=m2903_document.to_dict(),
        m2903_visual_evidence_json_path=str(m2903_json),
        m2902_document=m2902_document.to_dict(),
        m2902_audit_json_path=str(m2902_json),
        output_dir=paths.m2905,
        source_expansion_refs=M2905SourceExpansionRefs(
            m29_nodes_json=str(m29_json),
            m291_group_nodes_json=str(m291_json),
        ),
        emit_debug_artifacts=policy.emit_debug_artifacts,
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))
    m2905_json = paths.m2905 / "refined_visual_objects.json"

    update_task(task_id, "m30_materialization", 92, "Materializing M30 DSL.")
    m30_result = run_stage(paths, timings, "m30_materialization", lambda: materialize_evidence_grounded_dsl(
        source_image_path=str(upload_path),
        m2905_document=m2905_document.to_dict(),
        m2905_json_path=str(m2905_json),
        m2902_document=m2902_document.to_dict(),
        output_dir=paths.m30,
        mode="bootstrap-dsl-from-m29",
        options=M30Options(
            text_cover_enabled=False,
            text_editability_enabled=state.settings.ocr_text_editability_enabled,
            preserve_graphic_text_in_media_units=state.settings.ocr_graphic_text_preserve_enabled,
            max_editable_text_rotation_angle=state.settings.ocr_max_rotation_angle,
            max_editable_background_texture=state.settings.ocr_max_background_texture,
            max_editable_background_color_count=state.settings.ocr_max_background_color_count,
            text_symbol_leakage_cleanup_enabled=state.settings.ocr_text_symbol_leakage_cleanup_enabled,
            shape_erasure_enabled=state.settings.m30_shape_erasure_enabled,
            image_erasure_enabled=state.settings.m30_image_erasure_enabled,
            accepted_image_materialization_enabled=state.settings.m30_accepted_image_materialization_enabled,
            accepted_image_max_text_overlap=state.settings.m30_accepted_image_max_text_overlap,
            accepted_image_min_area=state.settings.m30_accepted_image_min_area,
            image_asset_text_erasure_enabled=state.settings.m30_image_asset_text_erasure_enabled,
            composite_media_materialization_enabled=state.settings.m30_composite_media_materialization_enabled,
            composite_media_min_area=state.settings.m30_composite_media_min_area,
        ),
        emit_preview_artifacts=policy.emit_preview_artifacts,
    ))

    update_task(task_id, "m30_asset_publish", 96, "Publishing M30 assets.")
    run_stage(paths, timings, "m30_asset_publish", lambda: publish_m30_assets(task_id, paths.m30, m30_result.dsl, image))

    update_task(task_id, "m39_boundary_classification", 97, "Running M39 boundary classification.")
    from .content_chrome_classification import classify_content_chrome
    run_stage(
        paths,
        timings,
        "m39_boundary_classification",
        lambda: classify_content_chrome(
            dsl=m30_result.dsl,
            task_id=task_id,
            output_dir=paths.m39,
            source_image_path=upload_path,
        ),
    )

    output_dsl = paths.m30 / "m30_materialized_dsl.json"
    output_dsl.write_text(json.dumps(m30_result.dsl, ensure_ascii=False, indent=2), encoding="utf-8")

    m31_tree = paths.m31 / "m31_reconstruction_tree.json"
    m31_report = paths.m31 / "m31_reconstruction_tree_report.json"
    m30_report = paths.m30 / "m30_materialization_report.json"
    m37_report = paths.m37 / "m37_hierarchy_readiness_report.json"
    if m31_tree.exists() and m31_report.exists() and m30_report.exists():
        update_task(task_id, "m37_hierarchy_readiness", 98, "Auditing M37 hierarchy readiness.")
        run_optional_stage(
            paths,
            timings,
            "m37_hierarchy_readiness",
            lambda: extract_m37_hierarchy_readiness(
                m31_tree_path=str(m31_tree),
                m31_report_path=str(m31_report),
                m30_dsl_path=str(output_dsl),
                m30_report_path=str(m30_report),
                output_dir=paths.m37,
            ),
            task_id=task_id,
        )

    if state.settings.m38_hierarchy_materialization_enabled and m37_report.exists():
        update_task(task_id, "m38_hierarchy_materialization", 99, "Materializing M38 hierarchy containers.")
        run_m38_hierarchy_materialization_stage(
            task_id=task_id,
            paths=paths,
            timings=timings,
            output_dsl=output_dsl,
            m37_report=m37_report,
        )

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
    state.database.update_task(
        task_id,
        status="completed",
        stage="m30_completed",
        progress=100,
        message="M30 materialized DSL is ready.",
        updated_at=now,
        completed_at=now,
    )
    write_stage_timings(paths, timings)


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
        raise M30UploadPipelineError("ocr", code, message)
    return document


def run_m31_diagnostic_stage(
    *,
    task_id: str,
    paths: M30PipelinePaths,
    timings: list[StageTiming],
    upload_path: Path,
    png_data: bytes,
    ocr_document: dict[str, Any],
    ocr_json: Path,
    m29_document: dict[str, Any],
    m29_json: Path,
    policy: M30ArtifactPolicy,
) -> None:
    action = lambda: extract_m31_reconstruction_ui_tree(
        source_image_path=str(upload_path),
        ocr_document=ocr_document,
        ocr_json_path=str(ocr_json),
        m29_document=m29_document,
        m29_nodes_json_path=str(m29_json),
        output_dir=paths.m31,
        profile=policy.profile,
        png_data=png_data,
    )
    if state.settings.m31_upload_diagnostics_strict:
        try:
            run_stage(paths, timings, "m31_reconstruction", action)
        except M30UploadPipelineError:
            raise
        except Exception as error:
            raise M30UploadPipelineError("m31_reconstruction", error.__class__.__name__, str(error)) from error
        return
    run_optional_stage(paths, timings, "m31_reconstruction", action, task_id=task_id)


def run_m38_hierarchy_materialization_stage(
    *,
    task_id: str,
    paths: M30PipelinePaths,
    timings: list[StageTiming],
    output_dsl: Path,
    m37_report: Path,
) -> None:
    action = lambda: materialize_m38_hierarchy(
        m30_dsl_path=str(output_dsl),
        m37_report_path=str(m37_report),
        output_dir=paths.m38,
        flat_dsl_output_path=str(paths.m30 / "m30_materialized_dsl_flat.json"),
        final_dsl_output_path=str(output_dsl),
        options=M38Options(max_containers=state.settings.m38_hierarchy_max_containers),
    )
    if state.settings.m38_hierarchy_materialization_strict:
        try:
            run_stage(paths, timings, "m38_hierarchy_materialization", action)
        except M30UploadPipelineError:
            raise
        except Exception as error:
            raise M30UploadPipelineError("m38_hierarchy_materialization", error.__class__.__name__, str(error)) from error
        return
    run_optional_stage(paths, timings, "m38_hierarchy_materialization", action, task_id=task_id)


def publish_m30_assets(task_id: str, m30_dir: Path, dsl: dict[str, Any], image: PngMetadata) -> None:
    public_dir = state.storage.assets_dir / task_id / "m30"
    public_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    seen_names: set[str] = set()
    for asset in dsl.get("assets", []):
        if not isinstance(asset, dict):
            continue
        url = str(asset.get("url") or "")
        if not url or url.startswith(("http://", "https://")):
            continue
        source = resolve_m30_asset_path(m30_dir, url)
        if source is None or not source.exists():
            continue
        filename = unique_filename(source.name, seen_names)
        target = public_dir / filename
        shutil.copy2(source, target)
        asset["url"] = state.storage.m30_asset_url(task_id, filename)
        asset["storage"] = "local"
        state.database.insert_asset(
            {
                "asset_id": str(asset.get("assetId") or filename),
                "task_id": task_id,
                "role": str(asset.get("role") or "m30_asset"),
                "path": str(target),
                "url": asset["url"],
                "mime_type": "image/png",
                "width": int(asset.get("width") or image.width),
                "height": int(asset.get("height") or image.height),
                "created_at": now,
            }
        )


def resolve_m30_asset_path(m30_dir: Path, url: str) -> Path | None:
    candidate = Path(url)
    if candidate.is_absolute():
        return candidate
    try:
        return (m30_dir / candidate).resolve()
    except OSError:
        return None


def unique_filename(filename: str, seen: set[str]) -> str:
    clean = "".join(char if char.isalnum() or char in "._-" else "_" for char in filename) or "asset.png"
    stem = Path(clean).stem or "asset"
    suffix = Path(clean).suffix or ".png"
    candidate = f"{stem}{suffix}"
    index = 2
    while candidate in seen:
        candidate = f"{stem}_{index}{suffix}"
        index += 1
    seen.add(candidate)
    return candidate


def artifact_policy_from_settings() -> M30ArtifactPolicy:
    profile = state.settings.m30_preview_profile
    if profile == "development":
        return M30ArtifactPolicy(profile="development", emit_debug_artifacts=True, emit_preview_artifacts=True)
    return M30ArtifactPolicy(profile="production", emit_debug_artifacts=False, emit_preview_artifacts=False)


def run_stage(paths: M30PipelinePaths, timings: list[StageTiming], stage: str, action):
    started_perf = time.perf_counter()
    timing = StageTiming(
        stage=stage,
        started_at=datetime.now(UTC).isoformat(),
        completed_at=None,
        elapsed_seconds=None,
        status="running",
    )
    timings.append(timing)
    write_stage_timings(paths, timings)
    try:
        result = action()
    except M30UploadPipelineError as error:
        finish_stage_timing(timing, started_perf, "failed", error.code, str(error))
        write_stage_timings(paths, timings)
        raise
    except Exception as error:
        finish_stage_timing(timing, started_perf, "failed", error.__class__.__name__, str(error))
        write_stage_timings(paths, timings)
        raise
    finish_stage_timing(timing, started_perf, "completed", None, None)
    write_stage_timings(paths, timings)
    return result


def run_optional_stage(paths: M30PipelinePaths, timings: list[StageTiming], stage: str, action, *, task_id: str):
    started_perf = time.perf_counter()
    timing = StageTiming(
        stage=stage,
        started_at=datetime.now(UTC).isoformat(),
        completed_at=None,
        elapsed_seconds=None,
        status="running",
    )
    timings.append(timing)
    write_stage_timings(paths, timings)
    try:
        result = action()
    except Exception as error:  # noqa: BLE001 - optional diagnostics must not block M30 output.
        finish_stage_timing(timing, started_perf, "failed", error.__class__.__name__, str(error))
        write_stage_timings(paths, timings)
        state.database.insert_error(
            task_id=task_id,
            stage=stage,
            error_code=error.__class__.__name__,
            message=str(error),
        )
        return None
    finish_stage_timing(timing, started_perf, "completed", None, None)
    write_stage_timings(paths, timings)
    return result


def finish_stage_timing(
    timing: StageTiming,
    started_perf: float,
    status: Literal["completed", "failed"],
    error_code: str | None,
    message: str | None,
) -> None:
    timing.completed_at = datetime.now(UTC).isoformat()
    timing.elapsed_seconds = round(time.perf_counter() - started_perf, 3)
    timing.status = status
    timing.error_code = error_code
    timing.message = message


def write_stage_timings(paths: M30PipelinePaths, timings: list[StageTiming]) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaName": "M3011StageTimings",
        "schemaVersion": "0.1",
        "stages": [timing.to_dict() for timing in timings],
    }
    (paths.root / "stage_timings.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def pipeline_paths(task_id: str) -> M30PipelinePaths:
    root = state.settings.storage_root / "m30_1_uploads" / task_id
    return M30PipelinePaths(
        root=root,
        ocr=root / "ocr",
        m29=root / "m29",
        m291=root / "m29_1",
        m2902=root / "m29_0_2",
        m2903=root / "m29_0_3",
        m2907=root / "m29_0_7",
        m2904=root / "m29_0_4",
        m2905=root / "m29_0_5",
        m31=root / "m31",
        m30=root / "m30",
        m37=root / "m37",
        m38=root / "m38",
        m39=root / "m39",
    )


def update_task(task_id: str, stage: str, progress: int, message: str) -> None:
    state.database.update_task(
        task_id,
        status="processing",
        stage=stage,
        progress=progress,
        message=message,
        updated_at=datetime.now(UTC).isoformat(),
    )


def fail_task(task_id: str, stage: str, code: str, message: str) -> None:
    now = datetime.now(UTC).isoformat()
    state.database.insert_error(
        task_id=task_id,
        stage=stage,
        error_code=code,
        message=message,
    )
    state.database.update_task(
        task_id,
        status="failed",
        stage=stage,
        progress=100,
        message=message,
        updated_at=now,
        failed_at=now,
    )
