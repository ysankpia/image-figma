from __future__ import annotations

from pathlib import Path

from app.dsl_visual_comparison.render import render_dsl_to_pixels


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

