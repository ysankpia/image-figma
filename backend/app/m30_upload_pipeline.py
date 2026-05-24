from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .database import json_dumps
from .m29_plan_materializer import build_m29_plan_materialized_dsl
from .m29_replay_plan import build_m295_replay_plan
from .ocr import extract_ocr
from .png_tools import PngMetadata, read_png_metadata
from .region_relation_graph_report import extract_m2931_region_relation_graph_report
from .stable_design_cluster import extract_m294_stable_design_cluster_report
from .source_ui_physical_graph import extract_source_ui_physical_graph
from .state import state
from .text_masked_media_audit import text_boxes_from_ocr_document
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
    m29_2: Path
    m29_3: Path
    m29_4: Path
    m29_5: Path
    m29_materialized: Path


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
        fail_task(task_id, "m29_pipeline", "M29_MAINLINE_PIPELINE_FAILED", str(error))


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

    update_task(task_id, "m29_2_source_ui_physical_graph", 21, "Classifying M29.2 source pixel ownership.")
    m292_document = run_stage(
        paths,
        timings,
        "m29_2_source_ui_physical_graph",
        lambda: extract_source_ui_physical_graph(
            source_png=png_data,
            m29_document=m29_document.to_dict(),
            ocr_document=ocr_document.to_dict(),
            output_dir=paths.m29_2,
        ),
    )

    update_task(task_id, "m29_3_relation_graph_report", 22, "Building M29.3.1 source relation graph report.")
    m2931_result = run_stage(
        paths,
        timings,
        "m29_3_relation_graph_report",
        lambda: extract_m2931_region_relation_graph_report(
            task_id=task_id,
            m292_document=m292_document,
            output_dir=paths.m29_3,
        ),
    )

    update_task(task_id, "m29_4_stable_design_cluster", 24, "Building M29.4 stable design cluster report.")
    m294_result = run_stage(
        paths,
        timings,
        "m29_4_stable_design_cluster",
        lambda: extract_m294_stable_design_cluster_report(
            task_id=task_id,
            m2931_report=m2931_result.report,
            output_dir=paths.m29_4,
        ),
    )

    update_task(task_id, "m29_5_replay_plan", 25, "Building M29.5 replay quality plan.")
    m295_result = run_stage(
        paths,
        timings,
        "m29_5_replay_plan",
        lambda: build_m295_replay_plan(
            task_id=task_id,
            m292_document=m292_document,
            m2931_report=m2931_result.report,
            m294_report=m294_result.report,
            output_dir=paths.m29_5,
        ),
    )

    update_task(task_id, "m29_materialization", 92, "Materializing M29 plan-driven DSL.")
    m29_materialized_result = run_stage(paths, timings, "m29_materialization", lambda: build_m29_plan_materialized_dsl(
        source_png=png_data,
        source_image_path=str(upload_path),
        m29_document={**m29_document.to_dict(), "sourceM29NodesJson": str(m29_json)},
        ocr_document=ocr_document.to_dict(),
        m292_document=m292_document,
        m295_replay_plan=m295_result.report,
        extra_warnings=[],
        output_dir=paths.m29_materialized,
        task_id=task_id,
    ))

    update_task(task_id, "m29_asset_publish", 96, "Publishing M29 assets.")
    run_stage(paths, timings, "m29_asset_publish", lambda: publish_m29_assets(task_id, paths.m29_materialized, m29_materialized_result.dsl, image))

    output_dsl = paths.m29_materialized / "m29_materialized_dsl.json"
    output_dsl.write_text(json.dumps(m29_materialized_result.dsl, ensure_ascii=False, indent=2), encoding="utf-8")

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
        stage="m29_completed",
        progress=100,
        message="M29 plan-driven DSL is ready.",
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


def publish_m29_assets(task_id: str, m29_dir: Path, dsl: dict[str, Any], image: PngMetadata) -> None:
    publish_variant_assets(task_id, "m29", m29_dir, dsl, image)


def publish_variant_assets(task_id: str, variant: str, source_dir: Path, dsl: dict[str, Any], image: PngMetadata) -> None:
    public_dir = state.storage.assets_dir / task_id / variant
    public_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    seen_names: set[str] = set()
    for asset in dsl.get("assets", []):
        if not isinstance(asset, dict):
            continue
        url = str(asset.get("url") or "")
        if not url or url.startswith(("http://", "https://")):
            continue
        source = resolve_materialized_asset_path(source_dir, url)
        if source is None or not source.exists():
            continue
        filename = unique_filename(source.name, seen_names)
        target = public_dir / filename
        shutil.copy2(source, target)
        asset["url"] = variant_asset_url(task_id, variant, filename)
        asset["storage"] = "local"
        state.database.insert_asset(
            {
                "asset_id": str(asset.get("assetId") or filename),
                "task_id": task_id,
                "role": str(asset.get("role") or "m29_asset"),
                "path": str(target),
                "url": asset["url"],
                "mime_type": "image/png",
                "width": int(asset.get("width") or image.width),
                "height": int(asset.get("height") or image.height),
                "created_at": now,
            }
        )


def variant_asset_url(task_id: str, variant: str, filename: str) -> str:
    return f"{state.storage.public_base_url}/files/assets/{task_id}/{variant}/{filename}"


def resolve_materialized_asset_path(source_dir: Path, url: str) -> Path | None:
    candidate = Path(url)
    if candidate.is_absolute():
        return candidate
    try:
        return (source_dir / candidate).resolve()
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
    profile = state.settings.m29_preview_profile
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
        raise M30UploadPipelineError(stage, error.__class__.__name__, str(error)) from error
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
        m29_2=root / "m29_2",
        m29_3=root / "m29_3",
        m29_4=root / "m29_4",
        m29_5=root / "m29_5",
        m29_materialized=root / "m29_materialized",
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
