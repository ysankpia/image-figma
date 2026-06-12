from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import decode_png_pixels
from .artifacts import build_preview_sheet, write_debug_artifacts
from .candidates import build_object_candidates
from .edges import build_evidence_edges
from .evidence import build_evidence_nodes, build_ownership_routing
from .report import build_meta, write_outputs
from .sets import build_set_candidates
from .types import EdgeAuditItem, M2904DebugArtifacts, M2904Document, M2904Options, M2904SourceExpansionRefs
from .validation import validate_visual_object_candidate_audit_document


def extract_visual_object_candidate_audit(
    *,
    png_data: bytes,
    source_image: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    source_expansion_refs: M2904SourceExpansionRefs | None = None,
    options: M2904Options | None = None,
    m2907_ownership_document: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> M2904Document:
    options = options or M2904Options()
    source_expansion_refs = source_expansion_refs or M2904SourceExpansionRefs(m2902_media_evidence_json=m2902_audit_json_path)
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    ownership_routing, ownership_warnings = build_ownership_routing(m2907_ownership_document)
    evidence_nodes, node_warnings = build_evidence_nodes(m2903_document, m2902_document, pixels.width, pixels.height, options, ownership_routing)
    evidence_edges = build_evidence_edges(evidence_nodes, pixels.width, pixels.height, options)
    edge_audit = [EdgeAuditItem(edge.id, edge.left_id, edge.right_id, edge.decision, edge.score, edge.reasons, edge.risks, edge.metrics) for edge in evidence_edges]
    objects = build_object_candidates(pixels, output_dir, evidence_nodes, evidence_edges, options)
    sets = build_set_candidates(objects, evidence_edges, options)
    debug = M2904DebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_artifacts(pixels, output_dir, evidence_nodes, objects, sets, evidence_edges)
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_visual_objects.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, objects, sets, options))
    document = M2904Document(
        schema_name="M2904GenericVisualObjectCandidateAuditDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        source_expansion_refs=source_expansion_refs,
        options=options,
        evidence_nodes=evidence_nodes,
        evidence_edges=evidence_edges,
        objects=objects,
        sets=sets,
        edge_audit=edge_audit,
        debug=debug,
        warnings=[*(warnings or []), *ownership_warnings, *node_warnings],
        meta=build_meta(evidence_nodes, evidence_edges, objects, sets),
    )
    validate_visual_object_candidate_audit_document(
        document,
        output_dir,
        pixels.width,
        pixels.height,
        require_preview_artifacts=emit_preview_artifacts,
    )
    write_outputs(document, output_dir)
    return document
