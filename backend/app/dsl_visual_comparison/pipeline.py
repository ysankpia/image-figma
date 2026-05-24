from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, decode_png_pixels, encode_rgb_png
from .render import render_dsl_to_pixels


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
    comparison = compare_pixels(source_pixels, rendered_pixels)
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


def compare_pixels(source: PngPixels, rendered: PngPixels) -> dict[str, Any]:
    width = min(source.width, rendered.width)
    height = min(source.height, rendered.height)
    if width <= 0 or height <= 0:
        return {
            "pixelComparedCount": 0,
            "meanAbsChannelError": 1.0,
            "normalizedMeanAbsError": 1.0,
            "changedPixelRatio10": 1.0,
            "maxChannelError": 255,
        }
    total_abs = 0
    changed = 0
    max_error = 0
    for y in range(height):
        source_row = source.rows[y]
        rendered_row = rendered.rows[y]
        for x in range(width):
            offset = x * 3
            pixel_max = 0
            for channel in range(3):
                error = abs(source_row[offset + channel] - rendered_row[offset + channel])
                total_abs += error
                pixel_max = max(pixel_max, error)
                max_error = max(max_error, error)
            if pixel_max > 10:
                changed += 1
    channel_count = width * height * 3
    pixel_count = width * height
    mean_abs = total_abs / max(1, channel_count)
    return {
        "pixelComparedCount": pixel_count,
        "meanAbsChannelError": round(mean_abs, 4),
        "normalizedMeanAbsError": round(mean_abs / 255.0, 6),
        "changedPixelRatio10": round(changed / max(1, pixel_count), 6),
        "maxChannelError": max_error,
    }


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
