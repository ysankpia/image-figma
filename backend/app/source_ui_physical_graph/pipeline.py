from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..png_tools import UnsupportedPngCropError, decode_png_pixels, read_png_metadata
from ..text_masked_media_audit import text_boxes_from_ocr_document
from .artifacts import build_summary, render_overlay
from .blocked import classify_blocked_objects
from .dedupe import dedupe_objects
from .icons import cluster_icon_objects
from .media import detect_media_objects
from .shapes import classify_shape_objects
from .text import classify_ocr_text_objects
from .types import M292SourceObject, M292SourcePhysicalOptions
from .unknowns import classify_unknown_objects


def extract_source_ui_physical_graph(
    *,
    source_png: bytes,
    m29_document: dict[str, Any],
    ocr_document: dict[str, Any] | None,
    output_dir: Path,
    options: M292SourcePhysicalOptions | None = None,
) -> dict[str, Any]:
    options = options or M292SourcePhysicalOptions()
    image = read_png_metadata(source_png)
    if image is None:
        raise UnsupportedPngCropError("M29.2 source image is not a readable PNG.")
    pixels = decode_png_pixels(source_png)
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_boxes, warnings = text_boxes_from_ocr_document(ocr_document or {"blocks": []})
    m29_nodes = [item for item in m29_document.get("nodes", []) if isinstance(item, dict)]
    blocked_nodes = [item for item in m29_document.get("blocked", []) if isinstance(item, dict)]
    media_nodes = detect_media_objects(m29_nodes, ocr_boxes, pixels, image.width, image.height, options)
    objects: list[M292SourceObject] = []
    objects.extend(media_nodes)
    objects.extend(classify_ocr_text_objects(ocr_boxes, m29_nodes, media_nodes, pixels, image.width, image.height, options))
    objects.extend(cluster_icon_objects(m29_nodes, media_nodes, ocr_boxes, pixels, image.width, image.height, options))
    objects.extend(classify_shape_objects(m29_nodes, media_nodes, ocr_boxes, pixels, image.width, image.height, options))
    objects.extend(classify_unknown_objects(m29_nodes, media_nodes, ocr_boxes, pixels, image.width, image.height, options))
    objects.extend(classify_blocked_objects(blocked_nodes, media_nodes, ocr_boxes, pixels, image.width, image.height, options))
    objects = dedupe_objects(objects, options.duplicate_iou_threshold)

    summary = build_summary(objects, m29_nodes, ocr_boxes)
    overlay_path = output_dir / "source_ui_physical_graph_overlay.png"
    overlay_path.write_bytes(render_overlay(pixels, objects))
    payload = {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "sourceImage": str(m29_document.get("sourceImage") or ""),
        "imageSize": {"width": image.width, "height": image.height},
        "summary": summary,
        "options": options.to_dict(),
        "sourceObjects": [item.to_dict() for item in objects],
        "warnings": warnings,
        "debug": {"overlay": overlay_path.name},
        "meta": {
            "dslChanged": False,
            "assetChanged": False,
            "truthSource": "source_png_plus_ocr_plus_m29_primitives",
        },
    }
    (output_dir / "source_ui_physical_graph.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
