from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from app.text_masked_media_audit import (
    MediaEvidenceItem,
    TextMaskedMediaAuditOptions,
    build_text_suppressed_pixels,
    extract_text_masked_media_audit,
    text_boxes_from_ocr_document,
    validate_text_masked_media_audit,
)
from app.visual_primitive_graph import M29TextBox


def test_ocr_document_blocks_convert_to_m29_text_boxes() -> None:
    boxes, warnings = text_boxes_from_ocr_document(
        {
            "blocks": [
                {"id": "ocr_1", "text": "蔬菜", "bbox": [10, 20, 30, 12], "confidence": 0.91},
                {"id": "bad", "bbox": [1, 2, 0, 3]},
            ]
        }
    )

    assert warnings == ["ocr_block_bad_invalid_bbox"]
    assert len(boxes) == 1
    assert boxes[0].id == "ocr_1"
    assert boxes[0].bbox == [10, 20, 30, 12]
    assert boxes[0].source == "ocr"


def test_text_suppressed_analysis_changes_only_text_mask_area() -> None:
    canvas = make_canvas(50, 40, (255, 255, 255))
    draw_rect(canvas, 10, 10, 12, 8, (20, 20, 20))
    draw_rect(canvas, 34, 12, 6, 6, (240, 0, 0))

    suppressed = build_text_suppressed_pixels(
        canvas,
        [M29TextBox("text_1", [10, 10, 12, 8], text="A", source="test", kind="line")],
        TextMaskedMediaAuditOptions(text_padding=0),
    )

    assert pixel_at(suppressed, 10, 10) != (20, 20, 20)
    assert pixel_at(suppressed, 34, 12) == (240, 0, 0)
    assert pixel_at(canvas, 10, 10) == (20, 20, 20)


def test_extract_audit_writes_masks_preview_and_original_crops(tmp_path: Path) -> None:
    canvas = make_canvas(120, 90, (255, 255, 255))
    draw_noise_patch(canvas, 12, 12, 34, 30)
    draw_rect(canvas, 60, 16, 24, 12, (20, 20, 20))
    draw_rect(canvas, 92, 18, 10, 10, (245, 0, 0))

    m29 = {
        "nodes": [
            node("image_001", "image", [12, 12, 34, 30], asset_path="assets/images/image_001.png"),
            node("unknown_001", "unknown", [12, 52, 34, 24]),
            node("symbol_001", "symbol", [92, 18, 10, 10]),
        ],
        "blocked": [
            blocked("blocked_001", [60, 16, 24, 12], ["text_overlap", "symbol_color_too_high"]),
            blocked("blocked_002", [92, 52, 16, 16], ["weak_symbol_metrics", "symbol_texture_too_high"]),
        ],
        "meta": {"counts": {"text": 0, "shape": 0, "image": 1, "symbol": 1, "unknown": 1, "blocked": 2}},
    }
    m291 = {"groups": [{"id": "group_001", "decision": "accepted", "bbox": [90, 16, 14, 14], "reasons": ["group_confidence_accepted"]}]}

    document = extract_text_masked_media_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        text_boxes=[M29TextBox("text_1", [60, 16, 24, 12], text="Label", source="test", kind="line")],
        text_source="test",
        m29_document=m29,
        m291_document=m291,
        options=TextMaskedMediaAuditOptions(text_padding=0, min_media_like_area=80),
    )

    assert document.schema_name == "M2902TextMaskedMediaAuditDocument"
    assert read_png_metadata((tmp_path / "overlays" / "09_text_mask.png").read_bytes()) is not None
    assert read_png_metadata((tmp_path / "overlays" / "10_text_suppressed_analysis.png").read_bytes()) is not None
    assert read_png_metadata((tmp_path / "preview_text_masked_media_audit.png").read_bytes()) is not None
    assert (tmp_path / "text_masked_media_audit.json").exists()
    assert (tmp_path / "text_masked_media_audit.md").exists()
    sources = {item.source for item in document.media_evidence}
    assert {"m29_image", "m29_unknown", "m29_symbol", "m29_blocked", "m291_group"} <= sources
    assert any(item.suggested_next_action == "likely_text_noise" for item in document.media_evidence)
    unknown_asset = next(item for item in document.media_evidence if item.source == "m29_unknown").asset_path
    assert unknown_asset is not None
    cropped = decode_png_pixels((tmp_path / unknown_asset).read_bytes())
    assert cropped.width == 34 and cropped.height == 24


def test_text_mask_prevents_text_from_becoming_symbol_in_after_run(tmp_path: Path) -> None:
    canvas = make_canvas(96, 80, (255, 255, 255))
    draw_rect(canvas, 10, 10, 20, 14, (20, 20, 20))
    draw_noise_patch(canvas, 48, 12, 30, 30)

    document = extract_text_masked_media_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        text_boxes=[M29TextBox("text_1", [10, 10, 20, 14], text="Text", source="test", kind="line")],
        text_source="test",
        m29_document=None,
        m291_document=None,
        options=TextMaskedMediaAuditOptions(text_padding=0, min_media_like_area=40),
    )

    assert document.after_counts["text"] == 1
    assert document.after_counts["symbol"] <= document.before_counts["symbol"]


def test_validation_rejects_missing_asset(tmp_path: Path) -> None:
    canvas = make_canvas(40, 40, (255, 255, 255))
    document = extract_text_masked_media_audit(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        text_boxes=[],
        text_source="none",
        m29_document={"nodes": [], "blocked": [], "meta": {"counts": {"text": 0, "shape": 0, "image": 0, "symbol": 0, "unknown": 0, "blocked": 0}}},
        options=TextMaskedMediaAuditOptions(),
    )
    bad = MediaEvidenceItem(
        id="bad",
        source="m29_unknown",
        bbox=[1, 1, 8, 8],
        region_name="full",
        decision="image_like_unknown",
        asset_path="missing.png",
        text_overlap_ratio=0,
        image_overlap_ratio=0,
        metrics=document.media_evidence[0].metrics if document.media_evidence else zero_metrics(),
        reasons=[],
        suggested_next_action="review_image_threshold",
    )
    broken = document.__class__(
        schema_name=document.schema_name,
        schema_version=document.schema_version,
        source_image=document.source_image,
        source_m29_nodes_json=document.source_m29_nodes_json,
        source_m291_group_nodes_json=document.source_m291_group_nodes_json,
        text_source=document.text_source,
        options=document.options,
        text_boxes=document.text_boxes,
        regions=document.regions,
        before_counts=document.before_counts,
        after_counts=document.after_counts,
        media_evidence=[bad],
        warnings=document.warnings,
        debug=document.debug,
        meta=document.meta,
    )

    with pytest.raises(ValueError, match="missing or unreadable"):
        validate_text_masked_media_audit(broken, tmp_path, 40, 40)


def make_canvas(width: int, height: int, fill: tuple[int, int, int]) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def node(id: str, node_type: str, bbox: list[int], *, asset_path: str | None = None) -> dict:
    data = {
        "id": id,
        "type": node_type,
        "subtype": "test",
        "bbox": bbox,
        "reasons": ["test"],
        "metrics": metrics_dict(),
    }
    if asset_path:
        data["assetPath"] = asset_path
    return data


def blocked(id: str, bbox: list[int], reasons: list[str]) -> dict:
    return {"id": id, "bbox": bbox, "reasons": reasons, "metrics": metrics_dict(), "context": {}}


def metrics_dict() -> dict:
    return {
        "colorCount": 48,
        "textureScore": 0.22,
        "edgeScore": 0.12,
        "fillRatio": 0.8,
        "aspectRatio": 1.0,
        "brightness": 120,
        "meanRgb": [100, 100, 100],
    }


def zero_metrics():
    from app.visual_primitive_graph import M29PrimitiveMetrics

    return M29PrimitiveMetrics(0, 0, 0, 0, 0, 0, (0, 0, 0))


def draw_rect(canvas: PngPixels, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    color_bytes = bytes(color)
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            rows[row_index][column * 3 : column * 3 + 3] = color_bytes
    canvas.rows[:] = [bytes(row) for row in rows]


def draw_noise_patch(canvas: PngPixels, x: int, y: int, width: int, height: int) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            rows[row_index][column * 3 : column * 3 + 3] = bytes(
                (
                    (column * 31 + row_index * 17) % 220,
                    (column * 13 + row_index * 29) % 220,
                    (column * 7 + row_index * 11) % 220,
                )
            )
    canvas.rows[:] = [bytes(row) for row in rows]


def pixel_at(canvas: PngPixels, x: int, y: int) -> tuple[int, int, int]:
    row = canvas.rows[y]
    offset = x * 3
    return row[offset], row[offset + 1], row[offset + 2]


def pixels_to_png(canvas: PngPixels) -> bytes:
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)
