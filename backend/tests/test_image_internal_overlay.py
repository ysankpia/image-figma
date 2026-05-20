from __future__ import annotations

from pathlib import Path

from app.image_internal_overlay import M293Options, extract_image_internal_overlays
from app.png_tools import PngPixels, encode_rgb_png


def test_binds_child_overlay_to_correct_accepted_image_parent(tmp_path: Path) -> None:
    image_bboxes = [[10, 10, 100, 100]]
    canvas = make_multi_image_canvas(image_bboxes)
    draw_counter_like_overlay(canvas, 72, 18)

    document = run_extract(tmp_path, canvas, m29_doc=m29_document_with_images(image_bboxes), m2902_doc=m2902_document_with_images(image_bboxes))

    assert document.summary["overlayCount"] == 1
    overlay = document.overlays[0]
    assert overlay.source_image_node_id == "m29_image_001"
    assert overlay.source_m29_node_id == "image_001"
    assert overlay.source_image_bbox == [10, 10, 100, 100]
    assert overlay.decision == "proposal_only"
    assert overlay.overlay_kind == "text_like_overlay_candidate"
    assert overlay.anchor == "top_right"
    assert overlay.materialization_eligible is False
    assert "parent_image_ownership_bound" in overlay.reasons


def test_dedupes_ocr_covered_overlay(tmp_path: Path) -> None:
    image_bboxes = [[10, 10, 100, 100]]
    canvas = make_multi_image_canvas(image_bboxes)
    draw_counter_like_overlay(canvas, 72, 18)
    ocr = {"blocks": [{"id": "ocr_text_001", "text": "1/9", "bbox": [72, 18, 30, 18], "confidence": 0.99}]}

    document = run_extract(
        tmp_path,
        canvas,
        ocr_document=ocr,
        m29_doc=m29_document_with_images(image_bboxes),
        m2902_doc=m2902_document_with_images(image_bboxes),
    )

    overlay = document.overlays[0]
    assert overlay.decision == "covered_by_existing_ocr"
    assert overlay.overlaps_existing_ocr is True
    assert overlay.matched_ocr_box_id == "ocr_text_001"
    assert overlay.materialization_eligible is False


def test_rejects_center_photo_noise(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_counter_like_overlay(canvas, 88, 78)

    document = run_extract(tmp_path, canvas)

    assert document.summary["overlayCount"] == 0


def test_rejects_texture_like_lines(tmp_path: Path) -> None:
    canvas = make_canvas()
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(18, 24):
        rows[row_index][145 * 3 : 190 * 3] = b"\xff\xff\xff" * 45
    canvas.rows[:] = [bytes(row) for row in rows]

    document = run_extract(tmp_path, canvas)

    assert all(overlay.decision != "proposal_only" for overlay in document.overlays)


def test_fair_selection_keeps_later_image_overlay_from_starvation(tmp_path: Path) -> None:
    image_bboxes = [[10, 10, 100, 100], [130, 10, 100, 100], [250, 10, 100, 100]]
    canvas = make_multi_image_canvas(image_bboxes)
    for x, y in [(18, 18), (58, 18), (18, 52), (58, 52), (18, 84)]:
        draw_counter_like_overlay(canvas, x, y)
    draw_counter_like_overlay(canvas, 258, 18)

    document = run_extract(
        tmp_path,
        canvas,
        options=M293Options(max_overlays=4, max_overlays_per_image=4),
        m29_doc=m29_document_with_images(image_bboxes),
        m2902_doc=m2902_document_with_images(image_bboxes),
    )

    assert document.summary["overlayCount"] == 4
    assert any(overlay.source_image_node_id == "m29_image_003" for overlay in document.overlays)
    assert document.summary["materializedTextCount"] == 0
    assert document.summary["createdNewBBoxCount"] == 0
    assert document.summary["dslChanged"] is False


def run_extract(
    tmp_path: Path,
    canvas: PngPixels,
    *,
    ocr_document: dict | None = None,
    options: M293Options | None = None,
    m29_doc: dict | None = None,
    m2902_doc: dict | None = None,
):
    output_dir = tmp_path / "m29_3"
    return extract_image_internal_overlays(
        png_data=encode_rgb_png(canvas.width, canvas.height, canvas.rows),
        source_image="/tmp/source.png",
        output_dir=output_dir,
        ocr_document=ocr_document or {"blocks": []},
        ocr_json_path="/tmp/ocr/ocr.json",
        m29_document=m29_doc or m29_document(),
        m29_nodes_json_path="/tmp/m29/nodes.json",
        m2902_document=m2902_doc or m2902_document(),
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        options=options or M293Options(),
        emit_debug_artifacts=True,
    )


def make_canvas() -> PngPixels:
    rows = [bytearray(bytes((148, 168, 190)) * 220) for _ in range(140)]
    for row_index in range(10, 130):
        for column in range(10, 210):
            shade = 90 + ((row_index + column) % 28)
            rows[row_index][column * 3 : column * 3 + 3] = bytes((shade, shade + 8, shade + 18))
    return PngPixels(width=220, height=140, rows=[bytes(row) for row in rows])


def make_multi_image_canvas(image_bboxes: list[list[int]]) -> PngPixels:
    width = max(bbox[0] + bbox[2] for bbox in image_bboxes) + 10
    height = max(bbox[1] + bbox[3] for bbox in image_bboxes) + 10
    rows = [bytearray(bytes((148, 168, 190)) * width) for _ in range(height)]
    for x, y, box_width, box_height in image_bboxes:
        for row_index in range(y, y + box_height):
            for column in range(x, x + box_width):
                shade = 90 + ((row_index + column) % 28)
                rows[row_index][column * 3 : column * 3 + 3] = bytes((shade, shade + 8, shade + 18))
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows])


def draw_counter_like_overlay(canvas: PngPixels, x: int, y: int) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(y, y + 18):
        for column in range(x, x + 30):
            rows[row_index][column * 3 : column * 3 + 3] = bytes((42, 48, 54))
    draw_rect(rows, x + 4, y + 4, 3, 10, (250, 250, 250))
    draw_slash(rows, x + 11, y + 4, (250, 250, 250))
    draw_rect(rows, x + 18, y + 4, 7, 3, (250, 250, 250))
    draw_rect(rows, x + 18, y + 8, 7, 3, (250, 250, 250))
    draw_rect(rows, x + 18, y + 12, 7, 3, (250, 250, 250))
    canvas.rows[:] = [bytes(row) for row in rows]


def draw_rect(rows: list[bytearray], x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    value = bytes(color)
    for row_index in range(y, y + height):
        for column in range(x, x + width):
            rows[row_index][column * 3 : column * 3 + 3] = value


def draw_slash(rows: list[bytearray], x: int, y: int, color: tuple[int, int, int]) -> None:
    value = bytes(color)
    for step in range(10):
        column = x + step // 2
        row_index = y + 9 - step
        rows[row_index][column * 3 : column * 3 + 3] = value


def m29_document() -> dict:
    return {"nodes": [{"id": "image_001", "type": "image", "bbox": [10, 10, 200, 120]}]}


def m29_document_with_images(image_bboxes: list[list[int]]) -> dict:
    return {
        "nodes": [
            {"id": f"image_{index:03d}", "type": "image", "bbox": bbox}
            for index, bbox in enumerate(image_bboxes, start=1)
        ]
    }


def m2902_document() -> dict:
    return {
        "schemaName": "M2902TextMaskedMediaAuditDocument",
        "schemaVersion": "0.1",
        "mediaEvidence": [
            {
                "id": "m29_image_001",
                "source": "m29_image",
                "bbox": [10, 10, 200, 120],
                "decision": "accepted_image",
                "suggestedNextAction": "keep_accepted_image",
            }
        ],
    }


def m2902_document_with_images(image_bboxes: list[list[int]]) -> dict:
    return {
        "schemaName": "M2902TextMaskedMediaAuditDocument",
        "schemaVersion": "0.1",
        "mediaEvidence": [
            {
                "id": f"m29_image_{index:03d}",
                "source": "m29_image",
                "bbox": bbox,
                "decision": "accepted_image",
                "suggestedNextAction": "keep_accepted_image",
            }
            for index, bbox in enumerate(image_bboxes, start=1)
        ],
    }
