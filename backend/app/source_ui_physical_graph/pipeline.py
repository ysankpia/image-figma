from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..image_math import build_scale_profile
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
    image = read_png_metadata(source_png)
    if image is None:
        raise UnsupportedPngCropError("M29.2 source image is not a readable PNG.")
    pixels = decode_png_pixels(source_png)
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_boxes, warnings = text_boxes_from_ocr_document(ocr_document or {"blocks": []})
    image_size = {"width": image.width, "height": image.height}
    scale_profile = build_scale_profile(image_size=image_size, ocr_blocks=ocr_boxes, source_objects=[])
    options_scale_profile = build_scale_profile(image_size=image_size, ocr_blocks=[], source_objects=[])
    options = options or scale_options(M292SourcePhysicalOptions(), options_scale_profile)
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
            "scaleProfile": scale_profile.to_dict(),
            "optionsScaleProfile": options_scale_profile.to_dict(),
        },
    }
    (output_dir / "source_ui_physical_graph.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def scale_options(base: M292SourcePhysicalOptions, scale_profile: Any) -> M292SourcePhysicalOptions:
    return M292SourcePhysicalOptions(
        min_text_confidence=base.min_text_confidence,
        editable_text_max_media_overlap=base.editable_text_max_media_overlap,
        media_display_text_min_height=scale_profile.length(base.media_display_text_min_height, minimum=24, maximum=160),
        media_display_text_min_width_ratio=base.media_display_text_min_width_ratio,
        min_media_area=scale_profile.area(base.min_media_area, minimum=base.min_media_area),
        media_color_threshold=base.media_color_threshold,
        media_texture_threshold=base.media_texture_threshold,
        media_text_overlap_preserve_threshold=base.media_text_overlap_preserve_threshold,
        media_min_color_or_texture_area=scale_profile.area(base.media_min_color_or_texture_area, minimum=base.media_min_color_or_texture_area),
        icon_max_area=scale_profile.area(base.icon_max_area, minimum=base.icon_max_area),
        icon_cluster_gap=scale_profile.length(base.icon_cluster_gap, minimum=4, maximum=40),
        raster_foreground_max_edge=scale_profile.length(base.raster_foreground_max_edge, minimum=base.raster_foreground_max_edge),
        shape_replay_color_threshold=base.shape_replay_color_threshold,
        shape_replay_texture_threshold=base.shape_replay_texture_threshold,
        shape_replay_edge_threshold=base.shape_replay_edge_threshold,
        textured_foreground_color_threshold=base.textured_foreground_color_threshold,
        textured_foreground_texture_threshold=base.textured_foreground_texture_threshold,
        textured_foreground_edge_threshold=base.textured_foreground_edge_threshold,
        control_unknown_min_width=scale_profile.length(base.control_unknown_min_width, minimum=28, maximum=180),
        control_unknown_min_height=scale_profile.length(base.control_unknown_min_height, minimum=16, maximum=120),
        control_unknown_max_height=scale_profile.length(base.control_unknown_max_height, minimum=base.control_unknown_max_height),
        control_unknown_min_aspect_ratio=base.control_unknown_min_aspect_ratio,
        control_unknown_max_aspect_ratio=base.control_unknown_max_aspect_ratio,
        control_unknown_max_area_ratio=base.control_unknown_max_area_ratio,
        control_unknown_min_text_containment=base.control_unknown_min_text_containment,
        control_unknown_min_text_area_ratio=base.control_unknown_min_text_area_ratio,
        control_unknown_max_text_area_ratio=base.control_unknown_max_text_area_ratio,
        control_unknown_max_color_count=base.control_unknown_max_color_count,
        control_unknown_max_texture_score=base.control_unknown_max_texture_score,
        control_unknown_max_edge_score=base.control_unknown_max_edge_score,
        control_unknown_min_fill_ratio=base.control_unknown_min_fill_ratio,
        duplicate_iou_threshold=base.duplicate_iou_threshold,
        scale_factor=round(scale_profile.factor, 4),
    )
