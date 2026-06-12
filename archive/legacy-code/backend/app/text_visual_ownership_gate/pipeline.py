from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import decode_png_pixels
from .artifacts import build_preview_sheet, export_examples, write_debug_artifacts
from .decision import build_ownership_decisions, valid_text_boxes
from .report import write_outputs
from .routing import build_audit, build_routing_views
from .types import M2907DebugArtifacts, M2907Document, M2907Options
from .validation import build_meta, validate_text_visual_ownership_gate_document


def extract_text_visual_ownership_gate(
    *,
    png_data: bytes,
    source_image: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    options: M2907Options | None = None,
    warnings: list[str] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> M2907Document:
    options = options or M2907Options()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    text_boxes = valid_text_boxes(m2902_document, pixels.width, pixels.height, options)
    decisions = build_ownership_decisions(m2903_document, text_boxes, pixels.width, pixels.height, options)
    examples: list[dict[str, Any]] = []
    if emit_preview_artifacts:
        export_examples(pixels, output_dir, decisions, options, examples)
    debug = M2907DebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_artifacts(pixels, output_dir, decisions)
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_text_visual_ownership_gate.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, examples, options))
    document = M2907Document(
        schema_name="M2907TextVisualOwnershipGateDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        options=options,
        ownership_decisions=decisions,
        routing_views=build_routing_views(decisions),
        audit=build_audit(decisions),
        debug=debug,
        warnings=warnings or [],
        meta=build_meta(decisions, examples),
    )
    validate_text_visual_ownership_gate_document(
        document,
        output_dir,
        pixels.width,
        pixels.height,
        m2903_document,
        m2902_document,
        require_preview_artifacts=emit_preview_artifacts,
    )
    write_outputs(document, output_dir)
    return document
