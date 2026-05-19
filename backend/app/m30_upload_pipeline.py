from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import json_dumps
from .evidence_grounded_dsl_materialization import materialize_evidence_grounded_dsl
from .ocr import extract_ocr
from .png_tools import PngMetadata, read_png_metadata
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
from .visual_primitive_graph import M29TextBox, extract_m29_visual_primitive_graph


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
    m30: Path


def run_m30_preview_pipeline(task_id: str) -> None:
    paths = pipeline_paths(task_id)
    try:
        run_pipeline(task_id, paths)
    except M30UploadPipelineError as error:
        fail_task(task_id, error.stage, error.code, str(error))
    except Exception as error:  # noqa: BLE001 - background tasks must record failure, not crash silently.
        fail_task(task_id, "m30_pipeline", "M30_PREVIEW_PIPELINE_FAILED", str(error))


def run_pipeline(task_id: str, paths: M30PipelinePaths) -> None:
    upload_path = state.storage.upload_path(task_id)
    png_data = upload_path.read_bytes()
    image = read_png_metadata(png_data)
    if image is None:
        raise M30UploadPipelineError("upload", "INVALID_IMAGE_DIMENSIONS", "PNG image dimensions could not be read.")
    paths.root.mkdir(parents=True, exist_ok=True)

    source_image = str(upload_path)
    update_task(task_id, "ocr", 8, "Running OCR.")
    ocr_document = run_ocr(task_id, image, upload_path, paths.ocr)
    text_boxes, text_warnings = text_boxes_from_ocr_document(ocr_document.to_dict())

    update_task(task_id, "m29", 18, "Running M29 visual primitive graph.")
    m29_document = extract_m29_visual_primitive_graph(
        png_data=png_data,
        source_image=source_image,
        output_dir=paths.m29,
        text_boxes=text_boxes,
    )
    m29_json = paths.m29 / "nodes.json"

    update_task(task_id, "m29_1", 30, "Running M29.1 symbol grouping.")
    m291_document = extract_m291_symbol_fragment_grouping(
        m29_document=m29_document.to_dict(),
        m29_nodes_json_path=str(m29_json),
        png_data=png_data,
        source_image=source_image,
        output_dir=paths.m291,
    )
    m291_json = paths.m291 / "group_nodes.json"

    update_task(task_id, "m29_0_2", 42, "Running text-masked media audit.")
    m2902_document = extract_text_masked_media_audit(
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
    )
    m2902_json = paths.m2902 / "text_masked_media_audit.json"

    update_task(task_id, "m29_0_3", 54, "Normalizing visual evidence.")
    m2903_document = extract_visual_evidence_normalization(
        png_data=png_data,
        source_image=source_image,
        m2902_document=m2902_document.to_dict(),
        m2902_audit_json_path=str(m2902_json),
        output_dir=paths.m2903,
        m291_lineage_document=m291_document.to_dict(),
        m291_lineage_json_path=str(m291_json),
    )
    m2903_json = paths.m2903 / "visual_evidence.json"

    update_task(task_id, "m29_0_7", 64, "Routing text and visual ownership.")
    m2907_document = extract_text_visual_ownership_gate(
        png_data=png_data,
        source_image=source_image,
        m2903_document=m2903_document.to_dict(),
        m2903_visual_evidence_json_path=str(m2903_json),
        m2902_document=m2902_document.to_dict(),
        m2902_audit_json_path=str(m2902_json),
        output_dir=paths.m2907,
    )
    m2907_json = paths.m2907 / "text_visual_ownership_gate.json"

    update_task(task_id, "m29_0_4", 74, "Building visual object candidates.")
    m2904_document = extract_visual_object_candidate_audit(
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
    )
    m2904_json = paths.m2904 / "visual_object_candidates.json"

    update_task(task_id, "m29_0_5", 84, "Refining text-aware visual objects.")
    m2905_document = extract_text_aware_visual_object_refinement(
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
    )
    m2905_json = paths.m2905 / "refined_visual_objects.json"

    update_task(task_id, "m30_materialization", 92, "Materializing M30 DSL.")
    m30_result = materialize_evidence_grounded_dsl(
        source_image_path=str(upload_path),
        m2905_document=m2905_document.to_dict(),
        m2905_json_path=str(m2905_json),
        output_dir=paths.m30,
        mode="bootstrap-dsl-from-m29",
    )

    update_task(task_id, "m30_asset_publish", 96, "Publishing M30 assets.")
    publish_m30_assets(task_id, paths.m30, m30_result.dsl, image)
    output_dsl = paths.m30 / "m30_materialized_dsl.json"
    output_dsl.write_text(json.dumps(m30_result.dsl, ensure_ascii=False, indent=2), encoding="utf-8")

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
        m30=root / "m30",
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
