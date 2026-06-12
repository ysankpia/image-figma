from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import decode_png_pixels, encode_rgb_png
from ..visual_primitive_graph import (
    M29TextBox,
    M29VisualPrimitiveOptions,
    build_text_exclusion_mask,
    extract_m29_visual_primitive_graph,
    mask_from_bboxes,
)
from .artifacts import build_preview_sheet, write_debug_artifacts
from .evidence import collect_media_evidence
from .regions import build_text_suppressed_pixels, default_media_regions, extract_counts, parse_bbox
from .report import build_meta, write_outputs
from .types import MediaAuditRegion, TextMaskedDebugArtifacts, TextMaskedMediaAuditDocument, TextMaskedMediaAuditOptions
from .validation import validate_text_masked_media_audit


def extract_text_masked_media_audit(
    *,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    text_boxes: list[M29TextBox],
    text_source: str,
    m29_document: dict[str, Any] | None = None,
    m29_nodes_json_path: str | None = None,
    m291_document: dict[str, Any] | None = None,
    m291_group_nodes_json_path: str | None = None,
    regions: list[MediaAuditRegion] | None = None,
    options: TextMaskedMediaAuditOptions | None = None,
    warnings: list[str] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> TextMaskedMediaAuditDocument:
    options = options or TextMaskedMediaAuditOptions()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    regions = regions or default_media_regions(pixels.width, pixels.height)

    text_mask = build_text_exclusion_mask(pixels.width, pixels.height, text_boxes, options.text_padding)
    suppressed_pixels = build_text_suppressed_pixels(pixels, text_boxes, options)
    suppressed_png = encode_rgb_png(suppressed_pixels.width, suppressed_pixels.height, suppressed_pixels.rows)

    before_document = m29_document or extract_m29_visual_primitive_graph(
        png_data=png_data,
        source_image=source_image,
        output_dir=output_dir / "m29_original",
        options=M29VisualPrimitiveOptions(),
        text_boxes=[],
        emit_debug_artifacts=emit_debug_artifacts,
        emit_preview_artifacts=emit_preview_artifacts,
    ).to_dict()
    after_document = extract_m29_visual_primitive_graph(
        png_data=suppressed_png,
        source_image=f"{source_image}#text_suppressed",
        output_dir=output_dir / "m29_text_suppressed",
        options=M29VisualPrimitiveOptions(),
        text_boxes=text_boxes,
        emit_debug_artifacts=emit_debug_artifacts,
        emit_preview_artifacts=emit_preview_artifacts,
    ).to_dict()

    image_mask = mask_from_bboxes(
        pixels.width,
        pixels.height,
        [parse_bbox(node.get("bbox")) or [0, 0, 0, 0] for node in before_document.get("nodes", []) if node.get("type") == "image"],
    )
    media_evidence = collect_media_evidence(
        pixels=pixels,
        output_dir=output_dir,
        text_mask=text_mask,
        image_mask=image_mask,
        regions=regions,
        before_document=before_document,
        after_document=after_document,
        m291_document=m291_document,
        options=options,
    )

    debug = TextMaskedDebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_artifacts(
            pixels=pixels,
            output_dir=output_dir,
            text_mask=text_mask,
            suppressed_pixels=suppressed_pixels,
            before_document=before_document,
            after_document=after_document,
            evidence=media_evidence,
        )
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_text_masked_media_audit.png"
        preview_path.write_bytes(build_preview_sheet(pixels, suppressed_pixels, output_dir, debug, media_evidence, options))

    document = TextMaskedMediaAuditDocument(
        schema_name="M2902TextMaskedMediaAuditDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m29_nodes_json=m29_nodes_json_path,
        source_m291_group_nodes_json=m291_group_nodes_json_path,
        text_source=text_source,
        options=options,
        text_boxes=text_boxes,
        regions=regions,
        before_counts=extract_counts(before_document),
        after_counts=extract_counts(after_document),
        media_evidence=media_evidence,
        warnings=warnings or [],
        debug=debug,
        meta=build_meta(text_boxes, media_evidence),
    )
    validate_text_masked_media_audit(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document
