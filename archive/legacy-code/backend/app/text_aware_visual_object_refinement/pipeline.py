from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import decode_png_pixels
from ..visual_evidence_normalization import parse_bbox
from ..visual_primitive_graph import bbox_in_bounds
from .artifacts import build_preview_sheet, write_debug_artifacts
from .refinement import refine_objects
from .report import build_meta, write_outputs
from .types import M2905DebugArtifacts, M2905Document, M2905Options, M2905SourceExpansionRefs
from .validation import validate_text_aware_visual_object_refinement_document


def extract_text_aware_visual_object_refinement(
    *,
    png_data: bytes,
    source_image: str,
    m2904_document: dict[str, Any],
    m2904_visual_object_candidates_json_path: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    source_expansion_refs: M2905SourceExpansionRefs | None = None,
    options: M2905Options | None = None,
    warnings: list[str] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> M2905Document:
    options = options or M2905Options()
    source_expansion_refs = source_expansion_refs or M2905SourceExpansionRefs()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    lookups = build_lookup_maps(m2904_document, m2903_document, m2902_document, pixels.width, pixels.height, options)
    objects, visual_assets, shape_candidates, text_members, unresolved_members, audit = refine_objects(
        pixels=pixels,
        output_dir=output_dir,
        lookups=lookups,
        options=options,
    )
    debug = M2905DebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_artifacts(pixels, output_dir, objects, visual_assets, shape_candidates, text_members, unresolved_members)
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_text_aware_refinement.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, objects, visual_assets, shape_candidates, text_members, unresolved_members, options))
    document = M2905Document(
        schema_name="M2905TextAwareVisualObjectRefinementDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2904_visual_object_candidates_json=m2904_visual_object_candidates_json_path,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        source_expansion_refs=source_expansion_refs,
        options=options,
        objects=objects,
        visual_assets=visual_assets,
        shape_candidates=shape_candidates,
        text_members=text_members,
        unresolved_members=unresolved_members,
        audit=audit,
        debug=debug,
        warnings=warnings or [],
        meta=build_meta(objects, visual_assets, shape_candidates, text_members, unresolved_members, audit),
    )
    validate_text_aware_visual_object_refinement_document(
        document,
        output_dir,
        pixels.width,
        pixels.height,
        m2904_document,
        m2902_document,
        require_preview_artifacts=emit_preview_artifacts,
    )
    write_outputs(document, output_dir)
    return document

def build_lookup_maps(
    m2904_document: dict[str, Any],
    m2903_document: dict[str, Any],
    m2902_document: dict[str, Any],
    width: int,
    height: int,
    options: M2905Options,
) -> dict[str, Any]:
    objects = [item for item in m2904_document.get("objects", []) if isinstance(item, dict)]
    evidence_nodes = [item for item in m2904_document.get("evidenceNodes", []) if isinstance(item, dict)]
    text_boxes = [item for item in m2902_document.get("textBoxes", []) if isinstance(item, dict)]
    m2903_items = [item for item in m2903_document.get("items", []) if isinstance(item, dict)]
    valid_text_boxes: list[dict[str, Any]] = []
    text_bboxes: list[list[int]] = []
    for raw in text_boxes:
        bbox = parse_bbox(raw.get("bbox"))
        source_id = str(raw.get("id") or "")
        if bbox is not None and source_id and bbox_in_bounds(bbox, width, height):
            item = dict(raw)
            item["bbox"] = bbox
            item["id"] = source_id
            valid_text_boxes.append(item)
            text_bboxes.append(bbox)
    for raw in evidence_nodes:
        if raw.get("nodeKind") == "text":
            bbox = parse_bbox(raw.get("bbox"))
            if bbox is not None and bbox_in_bounds(bbox, width, height):
                text_bboxes.append(bbox)
    return {
        "objects": objects,
        "objectById": {str(item.get("id")): item for item in objects if item.get("id")},
        "evidenceNodeById": {str(item.get("id")): item for item in evidence_nodes if item.get("id")},
        "m2903ById": {str(item.get("id")): item for item in m2903_items if item.get("id")},
        "m2903BySourceEvidenceId": {str(item.get("sourceEvidenceId")): item for item in m2903_items if item.get("sourceEvidenceId")},
        "textBoxById": {str(item.get("id")): item for item in valid_text_boxes if item.get("id")},
        "textBboxes": text_bboxes,
        "options": options,
    }
