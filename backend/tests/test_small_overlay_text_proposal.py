from __future__ import annotations

from pathlib import Path

from app.png_tools import PngPixels, encode_rgb_png
from app.small_overlay_text_proposal import M292Options, extract_small_overlay_text_proposals


def test_detects_small_counter_like_overlay_inside_accepted_image(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_counter_like_overlay(canvas, 152, 18)

    document = run_extract(tmp_path, canvas)

    assert document.summary["candidateCount"] == 1
    candidate = document.candidates[0]
    assert candidate.decision == "proposal_only"
    assert candidate.materialization_eligible is False
    assert candidate.recognized_text is None
    assert candidate.bbox[0] >= 150
    assert "ocr_missing" in candidate.reasons


def test_dedupes_existing_ocr_for_small_overlay_candidate(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_counter_like_overlay(canvas, 152, 18)
    ocr = {"blocks": [{"id": "ocr_text_001", "text": "1/9", "bbox": [150, 16, 28, 18], "confidence": 0.99}]}

    document = run_extract(tmp_path, canvas, ocr_document=ocr)

    assert document.summary["candidateCount"] == 1
    candidate = document.candidates[0]
    assert candidate.decision == "covered_by_existing_ocr"
    assert candidate.overlaps_existing_ocr is True
    assert candidate.matched_ocr_box_id == "ocr_text_001"


def test_rejects_texture_like_lines(tmp_path: Path) -> None:
    canvas = make_canvas()
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(18, 24):
        rows[row_index][145 * 3 : 190 * 3] = b"\xff\xff\xff" * 45
    canvas.rows[:] = [bytes(row) for row in rows]

    document = run_extract(tmp_path, canvas)

    assert all(candidate.decision != "proposal_only" for candidate in document.candidates)


def test_rejects_center_photo_noise(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_counter_like_overlay(canvas, 88, 78)

    document = run_extract(tmp_path, canvas)

    assert document.summary["candidateCount"] == 0


def test_limits_candidate_count(tmp_path: Path) -> None:
    canvas = make_canvas()
    for x in (18, 55, 92, 129, 166):
        draw_counter_like_overlay(canvas, x, 18)

    document = run_extract(tmp_path, canvas, options=M292Options(max_candidates=2))

    assert document.summary["candidateCount"] == 2
    assert document.warnings


def test_fair_selection_keeps_later_image_from_starvation(tmp_path: Path) -> None:
    image_bboxes = [[10, 10, 100, 100], [130, 10, 100, 100], [250, 10, 100, 100]]
    canvas = make_multi_image_canvas(image_bboxes)
    for x, y in [(18, 18), (58, 18), (18, 52), (58, 52), (18, 84)]:
        draw_counter_like_overlay(canvas, x, y)
    draw_counter_like_overlay(canvas, 258, 18)

    document = run_extract(
        tmp_path,
        canvas,
        options=M292Options(max_candidates=4, max_candidates_per_image=4),
        m29_doc=m29_document_with_images(image_bboxes),
        m2902_doc=m2902_document_with_images(image_bboxes),
    )

    assert document.summary["candidateCount"] == 4
    assert any(candidate.source_image_evidence_id == "m29_image_003" for candidate in document.candidates)
    assert all("remaining accepted images were not scanned" not in warning for warning in document.warnings)


def test_tiny_overlay_baseline_spread_is_penalty_not_rejection(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_baseline_spread_tiny_overlay(canvas, 152, 10)

    document = run_extract(tmp_path, canvas)

    assert document.summary["candidateCount"] == 1
    candidate = document.candidates[0]
    assert candidate.decision == "proposal_only"
    assert "baseline_spread_penalty" in candidate.reasons
    assert "baseline_spread_too_high" not in candidate.reasons
    assert candidate.metrics["baselinePenaltyApplied"] is True


def test_reprobe_recognizes_counter_without_mutating_ocr(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_counter_like_overlay(canvas, 152, 18)
    ocr = {"blocks": []}

    document = run_extract(
        tmp_path,
        canvas,
        ocr_document=ocr,
        options=M292Options(reprobe_enabled=True),
        reprobe_fn=lambda _png, _bbox: {"text": "1/6", "confidence": 0.91},
    )

    candidate = document.candidates[0]
    assert candidate.decision == "reprobe_recognized"
    assert candidate.recognized_text == "1/6"
    assert candidate.recognition_source == "local_crop_ocr"
    assert candidate.materialization_eligible is False
    assert ocr["blocks"] == []


def test_reprobe_rejects_non_counter_text(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_counter_like_overlay(canvas, 152, 18)

    document = run_extract(
        tmp_path,
        canvas,
        options=M292Options(reprobe_enabled=True),
        reprobe_fn=lambda _png, _bbox: {"text": "abc", "confidence": 0.9},
    )

    candidate = document.candidates[0]
    assert candidate.decision == "reprobe_unrecognized"
    assert "recognition_pattern_rejected" in candidate.reasons


def test_reprobe_failure_is_recorded_on_candidate(tmp_path: Path) -> None:
    canvas = make_canvas()
    draw_counter_like_overlay(canvas, 152, 18)

    def fail(_png: bytes, _bbox: list[int]) -> dict[str, object]:
        raise RuntimeError("forced reprobe failure")

    document = run_extract(tmp_path, canvas, options=M292Options(reprobe_enabled=True), reprobe_fn=fail)

    candidate = document.candidates[0]
    assert candidate.decision == "reprobe_failed"
    assert "forced reprobe failure" in str(candidate.reprobe_error)


def run_extract(
    tmp_path: Path,
    canvas: PngPixels,
    *,
    ocr_document: dict | None = None,
    options: M292Options | None = None,
    reprobe_fn=None,
    m29_doc: dict | None = None,
    m2902_doc: dict | None = None,
):
    output_dir = tmp_path / "m29_2"
    return extract_small_overlay_text_proposals(
        png_data=encode_rgb_png(canvas.width, canvas.height, canvas.rows),
        source_image="/tmp/source.png",
        output_dir=output_dir,
        ocr_document=ocr_document or {"blocks": []},
        ocr_json_path="/tmp/ocr/ocr.json",
        m29_document=m29_doc or m29_document(),
        m29_nodes_json_path="/tmp/m29/nodes.json",
        m2902_document=m2902_doc or m2902_document(),
        m2902_audit_json_path="/tmp/m29_0_2/text_masked_media_audit.json",
        options=options or M292Options(),
        emit_debug_artifacts=True,
        reprobe_fn=reprobe_fn,
    )


def make_canvas() -> PngPixels:
    rows = [bytearray(bytes((148, 168, 190)) * 220) for _ in range(140)]
    # Accepted image region.
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
    # Dark translucent-like badge.
    for row_index in range(y, y + 18):
        for column in range(x, x + 30):
            rows[row_index][column * 3 : column * 3 + 3] = bytes((42, 48, 54))
    # Three separated white glyph-like groups.
    draw_rect(rows, x + 4, y + 4, 3, 10, (250, 250, 250))
    draw_slash(rows, x + 11, y + 4, (250, 250, 250))
    draw_rect(rows, x + 18, y + 4, 7, 3, (250, 250, 250))
    draw_rect(rows, x + 18, y + 8, 7, 3, (250, 250, 250))
    draw_rect(rows, x + 18, y + 12, 7, 3, (250, 250, 250))
    canvas.rows[:] = [bytes(row) for row in rows]


def draw_baseline_spread_tiny_overlay(canvas: PngPixels, x: int, y: int) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(y, y + 32):
        for column in range(x, x + 30):
            rows[row_index][column * 3 : column * 3 + 3] = bytes((42, 48, 54))
    draw_rect(rows, x + 4, y + 4, 3, 13, (250, 250, 250))
    draw_rect(rows, x + 18, y + 18, 3, 13, (250, 250, 250))
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
    return {"nodes": [{"id": "m29_image_001", "type": "image", "bbox": [10, 10, 200, 120]}]}


def m29_document_with_images(image_bboxes: list[list[int]]) -> dict:
    return {
        "nodes": [
            {"id": f"m29_image_{index:03d}", "type": "image", "bbox": bbox}
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
