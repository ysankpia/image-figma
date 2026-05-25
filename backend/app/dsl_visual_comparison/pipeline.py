from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, decode_png_pixels, encode_rgb_png
from .render import build_text_exclusion_mask, render_dsl_to_pixels


def extract_dsl_visual_comparison(
    *,
    task_id: str,
    source_png: bytes,
    dsl: dict[str, Any],
    materialized_design_dir: Path,
    public_assets_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_pixels = decode_png_pixels(source_png)
    rendered_pixels, render_warnings = render_dsl_to_pixels(
        dsl=dsl,
        materialized_design_dir=materialized_design_dir,
        public_assets_dir=public_assets_dir,
        task_id=task_id,
    )
    text_exclusion_mask, text_excluded_pixel_count = build_text_exclusion_mask(
        dsl,
        width=rendered_pixels.width,
        height=rendered_pixels.height,
    )
    comparison = compare_pixels(source_pixels, rendered_pixels, exclusion_mask=text_exclusion_mask)
    render_path = output_dir / "dsl_render.png"
    diff_path = output_dir / "source_diff.png"
    report_path = output_dir / "dsl_visual_comparison_report.json"
    render_path.write_bytes(encode_rgb_png(rendered_pixels.width, rendered_pixels.height, rendered_pixels.rows))
    diff_path.write_bytes(build_diff_png(source_pixels, rendered_pixels))
    report = {
        "schemaName": "M29DslVisualComparisonReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "summary": {
            **comparison,
            "textExcludedPixelCount": text_excluded_pixel_count,
            "textExcludedCoverage": round(text_excluded_pixel_count / max(1, rendered_pixels.width * rendered_pixels.height), 6),
            "renderedWidth": rendered_pixels.width,
            "renderedHeight": rendered_pixels.height,
            "sourceWidth": source_pixels.width,
            "sourceHeight": source_pixels.height,
            "warningCount": len(render_warnings),
        },
        "artifacts": {
            "dslRenderPng": str(render_path),
            "sourceDiffPng": str(diff_path),
        },
        "warnings": render_warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "source_png_plus_final_materialized_dsl",
            "approximateRenderer": True,
            "dslChanged": False,
            "assetChanged": False,
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def compare_pixels(source: PngPixels, rendered: PngPixels, exclusion_mask: bytes | None = None) -> dict[str, Any]:
    width = min(source.width, rendered.width)
    height = min(source.height, rendered.height)
    if width <= 0 or height <= 0:
        return {
            "pixelComparedCount": 0,
            "meanAbsChannelError": 1.0,
            "normalizedMeanAbsError": 1.0,
            "changedPixelRatio10": 1.0,
            "nonTextPixelComparedCount": 0,
            "nonTextMeanAbsChannelError": 1.0,
            "nonTextNormalizedMeanAbsError": 1.0,
            "nonTextChangedPixelRatio10": 1.0,
            "gateNormalizedMeanAbsError": 1.0,
            "gateChangedPixelRatio10": 1.0,
            "maxChannelError": 255,
        }
    total_abs = 0
    changed = 0
    max_error = 0
    non_text_total_abs = 0
    non_text_changed = 0
    non_text_pixels = 0
    for y in range(height):
        source_row = source.rows[y]
        rendered_row = rendered.rows[y]
        for x in range(width):
            offset = x * 3
            pixel_max = 0
            pixel_abs = 0
            for channel in range(3):
                error = abs(source_row[offset + channel] - rendered_row[offset + channel])
                total_abs += error
                pixel_abs += error
                pixel_max = max(pixel_max, error)
                max_error = max(max_error, error)
            if pixel_max > 10:
                changed += 1
            if not is_excluded(exclusion_mask, y * rendered.width + x):
                non_text_total_abs += pixel_abs
                non_text_pixels += 1
                if pixel_max > 10:
                    non_text_changed += 1
    channel_count = width * height * 3
    pixel_count = width * height
    mean_abs = total_abs / max(1, channel_count)
    normalized_mean_abs = mean_abs / 255.0
    changed_ratio = changed / max(1, pixel_count)
    if non_text_pixels > 0:
        non_text_mean_abs = non_text_total_abs / (non_text_pixels * 3)
        non_text_changed_ratio = non_text_changed / non_text_pixels
        gate_mean_abs = non_text_mean_abs
        gate_changed_ratio = non_text_changed_ratio
        gate_fallback_reason = None
    else:
        non_text_mean_abs = 0.0
        non_text_changed_ratio = 0.0
        gate_mean_abs = mean_abs
        gate_changed_ratio = changed_ratio
        gate_fallback_reason = "no_non_text_pixels"
    return {
        "pixelComparedCount": pixel_count,
        "meanAbsChannelError": round(mean_abs, 4),
        "normalizedMeanAbsError": round(normalized_mean_abs, 6),
        "changedPixelRatio10": round(changed_ratio, 6),
        "nonTextPixelComparedCount": non_text_pixels,
        "nonTextMeanAbsChannelError": round(non_text_mean_abs, 4),
        "nonTextNormalizedMeanAbsError": round(non_text_mean_abs / 255.0, 6),
        "nonTextChangedPixelRatio10": round(non_text_changed_ratio, 6),
        "gateNormalizedMeanAbsError": round(gate_mean_abs / 255.0, 6),
        "gateChangedPixelRatio10": round(gate_changed_ratio, 6),
        "gateFallbackReason": gate_fallback_reason,
        "maxChannelError": max_error,
    }


def is_excluded(exclusion_mask: bytes | None, index: int) -> bool:
    return exclusion_mask is not None and index < len(exclusion_mask) and exclusion_mask[index] != 0


def build_diff_png(source: PngPixels, rendered: PngPixels) -> bytes:
    width = min(source.width, rendered.width)
    height = min(source.height, rendered.height)
    rows: list[bytes] = []
    for y in range(height):
        source_row = source.rows[y]
        rendered_row = rendered.rows[y]
        output = bytearray()
        for x in range(width):
            offset = x * 3
            diff = max(abs(source_row[offset + channel] - rendered_row[offset + channel]) for channel in range(3))
            output.extend((diff, 0, 0))
        rows.append(bytes(output))
    return encode_rgb_png(width, height, rows)
