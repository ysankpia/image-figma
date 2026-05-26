from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..image_math import build_scale_profile
from ..png_tools import UnsupportedPngCropError, decode_png_pixels
from .candidates import build_composite_media_items
from .normalization import normalize_ocr_blocks, normalize_plan_items, normalize_raw_nodes, normalize_source_objects
from .report import build_summary
from .types import M29MediaInternalDecompositionResult, REPORT_ONLY_META
from .validation import validate_media_internal_decomposition_report


def extract_m29_media_internal_decomposition_report(
    *,
    task_id: str,
    source_png: bytes | None = None,
    m29_document: dict[str, Any],
    ocr_document: dict[str, Any],
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any] | None,
    m295_report: dict[str, Any],
    output_dir: Path,
) -> M29MediaInternalDecompositionResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    source_objects, source_warnings = normalize_source_objects(m292_document.get("sourceObjects", []))
    raw_nodes, raw_warnings = normalize_raw_nodes(m29_document.get("nodes", []), m29_document.get("blocked", []))
    ocr_blocks, ocr_warnings = normalize_ocr_blocks(ocr_document.get("blocks", []))
    plan_items, plan_warnings = normalize_plan_items(m295_report.get("planItems", []))
    pixels = None
    pixel_warnings: list[str] = []
    if source_png is not None:
        try:
            pixels = decode_png_pixels(source_png)
        except UnsupportedPngCropError as error:
            pixel_warnings.append(f"source_png_decode_failed:{error}")
    image_size = image_size_from(m29_document, ocr_document, m292_document)
    scale_profile = build_scale_profile(image_size=image_size, ocr_blocks=ocr_blocks, source_objects=source_objects)
    composite_media_items, text_masks, internal_candidates, matched_internal_groups, rejected_fragments = build_composite_media_items(
        source_objects=source_objects,
        raw_nodes=raw_nodes,
        ocr_blocks=ocr_blocks,
        image_size=image_size,
        pixels=pixels,
        scale_profile=scale_profile,
    )
    warnings = source_warnings + raw_warnings + ocr_warnings + plan_warnings + pixel_warnings
    report_path = output_dir / "media_internal_decomposition_report.json"
    report = {
        "schemaName": "M29MediaInternalDecompositionReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "rawM29Version": m29_document.get("version"),
        "ocrVersion": ocr_document.get("version"),
        "relationSchemaName": (m2931_report or {}).get("schemaName"),
        "relationSchemaVersion": (m2931_report or {}).get("schemaVersion"),
        "planSchemaName": m295_report.get("schemaName"),
        "planSchemaVersion": m295_report.get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            source_objects=source_objects,
            raw_nodes=raw_nodes,
            ocr_blocks=ocr_blocks,
            plan_items=plan_items,
            composite_media_items=composite_media_items,
            text_masks=text_masks,
            internal_candidates=internal_candidates,
            matched_internal_groups=matched_internal_groups,
            rejected_fragments=rejected_fragments,
            warnings=warnings,
        ),
        "compositeMediaItems": composite_media_items,
        "textMasks": text_masks,
        "internalCandidates": internal_candidates,
        "matchedInternalGroups": matched_internal_groups,
        "rejectedFragments": rejected_fragments,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "source_png_plus_ocr_plus_raw_m29_plus_m29_2_plus_m29_3_1_plus_m29_5",
            "scaleProfile": scale_profile.to_dict(),
            **REPORT_ONLY_META,
        },
    }
    validate_media_internal_decomposition_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29MediaInternalDecompositionResult(report=report, output_dir=output_dir)


def image_size_from(*documents: dict[str, Any]) -> dict[str, int]:
    for document in documents:
        value = document.get("imageSize")
        if not isinstance(value, dict):
            continue
        width = int(value.get("width") or 0)
        height = int(value.get("height") or 0)
        if width > 0 and height > 0:
            return {"width": width, "height": height}
    return {}
