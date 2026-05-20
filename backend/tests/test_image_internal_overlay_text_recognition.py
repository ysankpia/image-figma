from __future__ import annotations

from pathlib import Path

from app.image_internal_overlay_text_recognition import (
    M294Options,
    extract_image_internal_overlay_text_recognition,
)
from app.png_tools import PngPixels, encode_rgb_png


def test_promotion_ready_for_counter_overlay(tmp_path: Path) -> None:
    document = run_extract(
        tmp_path,
        options=M294Options(reprobe_enabled=True),
        reprobe_fn=lambda _png, _bbox: {"text": "1/6", "confidence": 0.91},
    )

    item = document.items[0]
    assert item.decision == "promotion_ready"
    assert item.recognized_text == "1/6"
    assert item.source_m293_overlay_id == "m293_overlay_003"
    assert item.source_m292_candidate_id == "m292_overlay_text_003"
    assert item.source_image_node_id == "m29_image_003"
    assert item.source_m29_node_id == "image_003"
    assert item.overlay_bbox == [72, 18, 30, 18]
    assert item.local_overlay_bbox == [62, 8, 30, 18]
    assert item.materialization_eligible is False
    assert item.asset_path
    assert item.upscaled_asset_path
    assert (tmp_path / "m29_4" / item.asset_path).exists()
    assert (tmp_path / "m29_4" / item.upscaled_asset_path).exists()
    assert "local_crop_ocr_counter_pattern" in item.reasons
    assert document.summary["promotionReadyCount"] == 1
    assert document.summary["materializedTextCount"] == 0
    assert document.summary["createdNewBBoxCount"] == 0
    assert document.summary["dslChanged"] is False


def test_pattern_rejected_for_non_counter_text(tmp_path: Path) -> None:
    document = run_extract(
        tmp_path,
        options=M294Options(reprobe_enabled=True),
        reprobe_fn=lambda _png, _bbox: {"text": "abc", "confidence": 0.88},
    )

    item = document.items[0]
    assert item.decision == "pattern_rejected"
    assert item.raw_recognized_text == "abc"
    assert item.recognized_text is None
    assert "recognition_pattern_rejected" in item.reasons
    assert document.summary["patternRejectedCount"] == 1


def test_ocr_unrecognized_for_empty_text(tmp_path: Path) -> None:
    document = run_extract(
        tmp_path,
        options=M294Options(reprobe_enabled=True),
        reprobe_fn=lambda _png, _bbox: {"text": "", "confidence": 0.0},
    )

    item = document.items[0]
    assert item.decision == "ocr_unrecognized"
    assert item.recognized_text is None
    assert "ocr_empty_text" in item.reasons


def test_ocr_failed_is_recorded(tmp_path: Path) -> None:
    def fail(_png: bytes, _bbox: list[int]) -> dict[str, object]:
        raise RuntimeError("forced m29.4 reprobe failure")

    document = run_extract(tmp_path, options=M294Options(reprobe_enabled=True), reprobe_fn=fail)

    item = document.items[0]
    assert item.decision == "ocr_failed"
    assert "forced m29.4 reprobe failure" in str(item.recognition_error)
    assert document.summary["recognitionFailedCount"] == 1


def test_covered_by_existing_ocr_does_not_reprobe(tmp_path: Path) -> None:
    calls = {"count": 0}

    def reprobe(_png: bytes, _bbox: list[int]) -> dict[str, object]:
        calls["count"] += 1
        return {"text": "1/6", "confidence": 0.99}

    overlay = dict(base_overlay(), decision="covered_by_existing_ocr", overlapsExistingOcr=True)
    document = run_extract(tmp_path, m293_doc=m293_document([overlay]), options=M294Options(reprobe_enabled=True), reprobe_fn=reprobe)

    item = document.items[0]
    assert item.decision == "covered_by_existing_ocr"
    assert calls["count"] == 0
    assert document.summary["ocrCoveredOverlayCount"] == 1


def test_missing_m292_match_is_not_attempted(tmp_path: Path) -> None:
    document = run_extract(tmp_path, m292_doc=m292_document([]), options=M294Options(reprobe_enabled=True))

    item = document.items[0]
    assert item.decision == "not_attempted"
    assert "missing_m292_candidate_match" in item.reasons
    assert item.recognition_source is None


def test_reprobe_disabled_is_not_attempted(tmp_path: Path) -> None:
    document = run_extract(tmp_path, options=M294Options(reprobe_enabled=False))

    item = document.items[0]
    assert item.decision == "not_attempted"
    assert "recognition_reprobe_disabled" in item.reasons
    assert document.summary["recognitionAttemptCount"] == 0


def test_local_ocr_bbox_maps_back_to_page_coordinates(tmp_path: Path) -> None:
    document = run_extract(
        tmp_path,
        options=M294Options(reprobe_enabled=True),
        reprobe_fn=lambda _png, _bbox: {"text": "1/6", "confidence": 0.91, "bbox": [12, 12, 60, 24]},
    )

    item = document.items[0]
    assert item.decision == "promotion_ready"
    assert item.recognized_text_bbox == [72, 18, 20, 8]
    assert item.local_recognized_text_bbox == [62, 8, 20, 8]
    assert "recognized_bbox_from_local_ocr" in item.reasons


def run_extract(
    tmp_path: Path,
    *,
    m292_doc: dict | None = None,
    m293_doc: dict | None = None,
    options: M294Options | None = None,
    reprobe_fn=None,
):
    canvas = make_canvas()
    return extract_image_internal_overlay_text_recognition(
        png_data=encode_rgb_png(canvas.width, canvas.height, canvas.rows),
        source_image="/tmp/source.png",
        output_dir=tmp_path / "m29_4",
        ocr_json_path="/tmp/ocr/ocr.json",
        m292_document=m292_doc or m292_document([base_candidate()]),
        m292_candidates_json_path="/tmp/m29_2/small_overlay_text_candidates.json",
        m293_document=m293_doc or m293_document([base_overlay()]),
        m293_overlays_json_path="/tmp/m29_3/image_internal_overlays.json",
        options=options or M294Options(),
        emit_debug_artifacts=True,
        reprobe_fn=reprobe_fn,
    )


def make_canvas() -> PngPixels:
    rows = [bytearray(bytes((148, 168, 190)) * 140) for _ in range(80)]
    for row_index in range(10, 70):
        for column in range(10, 120):
            rows[row_index][column * 3 : column * 3 + 3] = bytes((48, 54, 60))
    return PngPixels(width=140, height=80, rows=[bytes(row) for row in rows])


def base_overlay() -> dict:
    return {
        "id": "m293_overlay_003",
        "sourceImageNodeId": "m29_image_003",
        "sourceM29NodeId": "image_003",
        "sourceImageBBox": [10, 10, 100, 60],
        "bbox": [72, 18, 30, 18],
        "anchor": "top_right",
        "overlayKind": "text_like_overlay_candidate",
        "decision": "proposal_only",
        "materializationEligible": False,
        "overlapsExistingOcr": False,
        "matchedOcrBoxId": None,
        "reasons": [],
        "metrics": {},
    }


def base_candidate() -> dict:
    return {
        "candidateId": "m292_overlay_text_003",
        "sourceImageEvidenceId": "m29_image_003",
        "sourceImageBBox": [10, 10, 100, 60],
        "bbox": [72, 18, 30, 18],
        "decision": "proposal_only",
        "recognizedText": None,
        "materializationEligible": False,
        "reasons": [],
        "metrics": {},
    }


def m292_document(candidates: list[dict]) -> dict:
    return {
        "schemaName": "M292SmallOverlayTextProposalDocument",
        "schemaVersion": "0.1",
        "candidates": candidates,
    }


def m293_document(overlays: list[dict]) -> dict:
    return {
        "schemaName": "M293ImageInternalOverlayDocument",
        "schemaVersion": "0.1",
        "overlays": overlays,
    }
