from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, decode_png_pixels
from ..visual_primitive_graph import bbox_in_bounds
from .artifacts import build_preview_sheet, export_visual_evidence_asset, item_sort_key, write_debug_artifacts
from .classification import classify_evidence
from .groups import build_groups
from .lineage import build_lineage_lookup, lookup_source_lineage
from .parsing import next_item_id, parse_bbox, parse_metrics, parse_source
from .report import build_meta, write_outputs
from .text_overlap import collect_text_boxes, overlapping_text_boxes
from .types import VisualEvidenceDebugArtifacts, VisualEvidenceDocument, VisualEvidenceItem, VisualEvidenceOptions
from .validation import validate_visual_evidence_document


def extract_visual_evidence_normalization(
    *,
    png_data: bytes,
    source_image: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    options: VisualEvidenceOptions | None = None,
    m291_lineage_document: dict[str, Any] | None = None,
    m291_lineage_json_path: str | None = None,
    warnings: list[str] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> VisualEvidenceDocument:
    options = options or VisualEvidenceOptions()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    media_evidence = m2902_document.get("mediaEvidence")
    if not isinstance(media_evidence, list):
        raise ValueError("M29.0.3 requires M29.0.2 mediaEvidence list")
    text_boxes = collect_text_boxes(m2902_document, pixels.width, pixels.height) if m291_lineage_document is not None else []

    items = normalize_evidence_items(
        pixels=pixels,
        output_dir=output_dir,
        media_evidence=media_evidence,
        text_boxes=text_boxes,
        options=options,
        lineage_lookup=build_lineage_lookup(m291_lineage_document),
    )
    debug = VisualEvidenceDebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_artifacts(pixels, output_dir, items)
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_visual_evidence.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, items, options))
    document = VisualEvidenceDocument(
        schema_name="M2903VisualEvidenceDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2902_audit_json=m2902_audit_json_path,
        options=options,
        items=items,
        groups=build_groups(items),
        debug=debug,
        warnings=warnings or [],
        meta=build_meta(m2902_audit_json_path, media_evidence, items, m291_lineage_json_path),
    )
    validate_visual_evidence_document(document, output_dir, pixels.width, pixels.height, expected_count=len(media_evidence))
    write_outputs(document, output_dir)
    return document

def normalize_evidence_items(
    *,
    pixels: PngPixels,
    output_dir: Path,
    media_evidence: list[Any],
    text_boxes: list[dict[str, Any]],
    options: VisualEvidenceOptions,
    lineage_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[VisualEvidenceItem]:
    items: list[VisualEvidenceItem] = []
    counters: dict[str, int] = {}
    for raw in media_evidence:
        if not isinstance(raw, dict):
            raise ValueError("M29.0.3 mediaEvidence item must be an object")
        source_evidence_id = str(raw.get("id") or "")
        source = parse_source(raw.get("source"))
        bbox = parse_bbox(raw.get("bbox"))
        if not source_evidence_id or source is None or bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            raise ValueError(f"M29.0.3 invalid mediaEvidence item: {source_evidence_id or '<missing id>'}")
        metrics = parse_metrics(raw.get("metrics"))
        source_lineage = lookup_source_lineage(raw, bbox, lineage_lookup)
        matched_text_boxes = overlapping_text_boxes(bbox, text_boxes)
        visual_kind, decision, confidence, classification_reasons, source_lineage = classify_evidence(raw, bbox, metrics, options, source_lineage, matched_text_boxes)
        id = next_item_id(visual_kind, counters)
        asset_path = export_visual_evidence_asset(pixels, output_dir, visual_kind, id, bbox)
        items.append(
            VisualEvidenceItem(
                id=id,
                source_evidence_id=source_evidence_id,
                source=source,
                bbox=bbox,
                region_name=str(raw.get("regionName") or "unknown"),
                visual_kind=visual_kind,
                decision=decision,
                confidence=confidence,
                asset_path=asset_path,
                text_overlap_ratio=float(raw.get("textOverlapRatio", 0.0)),
                image_overlap_ratio=float(raw.get("imageOverlapRatio", 0.0)),
                metrics=metrics,
                reasons=[*classification_reasons, *[str(reason) for reason in raw.get("reasons", [])]],
                source_decision=str(raw.get("decision") or ""),
                suggested_next_action=str(raw.get("suggestedNextAction") or ""),
                source_lineage=source_lineage,
            )
        )
    return sorted(items, key=item_sort_key)
