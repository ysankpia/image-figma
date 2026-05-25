from __future__ import annotations

from pathlib import Path

from app.dsl_visual_comparison.pipeline import build_diff_png
from app.dsl_visual_comparison.pipeline import compare_pixels
from app.dsl_visual_comparison.render import build_text_exclusion_mask
from app.dsl_visual_comparison.render import render_dsl_to_pixels
from app.png_tools import decode_png_pixels
from app.png_tools import PngPixels


def test_text_rendering_uses_glyph_texture_not_solid_bar(tmp_path: Path) -> None:
    pixels, warnings = render_dsl_to_pixels(
        dsl={
            "page": {"width": 72, "height": 32, "background": {"type": "color", "value": "#ffffff"}},
            "assets": [],
            "root": {
                "id": "root",
                "type": "frame",
                "layout": {"x": 0, "y": 0, "width": 72, "height": 32},
                "children": [
                    {
                        "id": "text",
                        "type": "text",
                        "layout": {"x": 8, "y": 8, "width": 48, "height": 14},
                        "style": {"color": "#000000"},
                        "content": {"text": "Diagnostic"},
                    }
                ],
            },
        },
        materialized_design_dir=tmp_path,
        public_assets_dir=tmp_path,
        task_id="task_visual_comparison",
    )

    assert warnings == []
    black = (0, 0, 0)
    text_pixels = 0
    longest_run = 0
    for row_index in range(8, 22):
        row = pixels.rows[row_index]
        run = 0
        for column in range(8, 56):
            offset = column * 3
            if tuple(row[offset : offset + 3]) == black:
                text_pixels += 1
                run += 1
                longest_run = max(longest_run, run)
            else:
                run = 0

    assert text_pixels > 0
    assert longest_run < 24


def test_text_exclusion_mask_tracks_visible_text_bboxes_with_parent_offsets(tmp_path: Path) -> None:
    mask, covered = build_text_exclusion_mask(
        {
            "page": {"width": 100, "height": 60},
            "root": {
                "id": "root",
                "type": "frame",
                "layout": {"x": 0, "y": 0, "width": 100, "height": 60},
                "children": [
                    {
                        "id": "group",
                        "type": "group",
                        "layout": {"x": 10, "y": 12, "width": 70, "height": 30},
                        "children": [
                            {
                                "id": "text",
                                "type": "text",
                                "layout": {"x": 5, "y": 4, "width": 20, "height": 8},
                                "content": {"text": "中文"},
                            },
                            {
                                "id": "hidden_text",
                                "type": "text",
                                "layout": {"x": 40, "y": 4, "width": 20, "height": 8},
                                "style": {"visible": False},
                                "content": {"text": "hidden"},
                            },
                        ],
                    }
                ],
            },
        },
        width=100,
        height=60,
        padding=0,
    )

    assert covered == 160
    assert mask[16 * 100 + 15] == 1
    assert mask[23 * 100 + 34] == 1
    assert mask[16 * 100 + 50] == 0


def test_compare_pixels_reports_gate_metrics_excluding_text_regions() -> None:
    source_rows = [bytes([255, 255, 255] * 12) for _ in range(8)]
    rendered_rows = [bytearray(row) for row in source_rows]
    for row in range(2, 5):
        for col in range(3, 9):
            offset = col * 3
            rendered_rows[row][offset : offset + 3] = b"\x00\x00\x00"

    mask = bytearray(12 * 8)
    for row in range(2, 5):
        for col in range(3, 9):
            mask[row * 12 + col] = 1

    comparison = compare_pixels(
        PngPixels(width=12, height=8, rows=source_rows),
        PngPixels(width=12, height=8, rows=[bytes(row) for row in rendered_rows]),
        exclusion_mask=bytes(mask),
    )

    assert comparison["changedPixelRatio10"] > 0
    assert comparison["normalizedMeanAbsError"] > 0
    assert comparison["nonTextPixelComparedCount"] == 78
    assert comparison["gateChangedPixelRatio10"] == 0
    assert comparison["gateNormalizedMeanAbsError"] == 0
    assert comparison["gateFallbackReason"] is None


def test_gate_diff_png_clears_text_excluded_pixels() -> None:
    source_rows = [bytes([255, 255, 255] * 4) for _ in range(3)]
    rendered_rows = [bytearray(row) for row in source_rows]
    rendered_rows[1][3:6] = b"\x00\x00\x00"
    rendered_rows[1][6:9] = b"\x00\x00\x00"
    mask = bytearray(12)
    mask[1 * 4 + 1] = 1

    pixels = decode_png_pixels(
        build_diff_png(
            PngPixels(width=4, height=3, rows=source_rows),
            PngPixels(width=4, height=3, rows=[bytes(row) for row in rendered_rows]),
            exclusion_mask=bytes(mask),
        )
    )

    text_offset = 1 * 3
    non_text_offset = 2 * 3
    assert pixels.rows[1][text_offset : text_offset + 3] == b"\x00\x00\x00"
    assert pixels.rows[1][non_text_offset : non_text_offset + 3] == b"\xff\x00\x00"


def test_compare_pixels_falls_back_to_full_metrics_when_text_mask_covers_every_pixel() -> None:
    source_rows = [bytes([255, 255, 255] * 4) for _ in range(3)]
    rendered_rows = [bytes([0, 0, 0] * 4) for _ in range(3)]
    comparison = compare_pixels(
        PngPixels(width=4, height=3, rows=source_rows),
        PngPixels(width=4, height=3, rows=rendered_rows),
        exclusion_mask=bytes([1] * 12),
    )

    assert comparison["nonTextPixelComparedCount"] == 0
    assert comparison["nonTextChangedPixelRatio10"] == 0
    assert comparison["gateChangedPixelRatio10"] == comparison["changedPixelRatio10"]
    assert comparison["gateNormalizedMeanAbsError"] == comparison["normalizedMeanAbsError"]
    assert comparison["gateFallbackReason"] == "no_non_text_pixels"
