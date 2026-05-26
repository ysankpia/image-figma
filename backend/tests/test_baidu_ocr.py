from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from app.config import Settings
from app.ocr import extract_ocr
from app.ocr_baidu import parse_ppocrv5_rows, polygon_to_bbox, rec_box_to_bbox
from app.png_tools import read_png_metadata


def test_parse_ppocrv5_rows_converts_boxes_and_filters_low_confidence() -> None:
    rows = [
        {
            "result": {
                "ocrResults": [
                    {
                        "prunedResult": {
                            "rec_texts": ["宿舍选床", "噪声", "多边形"],
                            "rec_scores": [0.99, 0.2, 0.92],
                            "rec_boxes": [[396, 82, 543, 124], [1, 1, 3, 3], None],
                            "rec_polys": [[], [], [[10, 20], [50, 20], [50, 44], [10, 44]]],
                        }
                    }
                ]
            }
        }
    ]

    blocks, warnings = parse_ppocrv5_rows(rows, min_confidence=0.7)

    assert [block.text for block in blocks] == ["宿舍选床", "多边形"]
    assert blocks[0].bbox == [396, 82, 147, 42]
    assert blocks[0].source == "baidu_ppocrv5"
    assert blocks[1].bbox == [10, 20, 40, 24]
    assert [warning.code for warning in warnings] == ["OCR_LOW_CONFIDENCE"]


def test_bbox_helpers_reject_invalid_shapes() -> None:
    assert rec_box_to_bbox([10, 20, 30, 50]) == [10, 20, 20, 30]
    assert rec_box_to_bbox([10, 20, 8, 50]) is None
    assert rec_box_to_bbox(["bad", 20, 30, 50]) is None
    assert polygon_to_bbox([[1, 2], [5, 2], [5, 8], [1, 8]]) == [1, 2, 4, 6]
    assert polygon_to_bbox([[1, 2]]) is None


def test_baidu_provider_without_token_returns_failed_document(tmp_path) -> None:
    from conftest import PNG_BYTES

    source = tmp_path / "input.png"
    source.write_bytes(PNG_BYTES)
    image = read_png_metadata(PNG_BYTES)
    assert image is not None

    document = extract_ocr(
        task_id="task_ocr_missing_token",
        image=image,
        settings=Settings(
            version="0.1.0",
            storage_root=tmp_path,
            database_path=tmp_path / "app.db",
            public_base_url="http://localhost:8000",
            max_upload_bytes=10 * 1024 * 1024,
            cors_allow_origins=["*"],
            ocr_provider="baidu_ppocrv5",
            baidu_paddle_ocr_token=None,
        ),
        source_path=source,
    )

    assert document.provider == "baidu_ppocrv5"
    assert document.model == "PP-OCRv5"
    assert document.status == "failed"
    assert document.blocks == []
    assert document.error is not None
    assert document.error["code"] == "BAIDU_PADDLE_OCR_TOKEN_MISSING"


def test_baidu_provider_success_builds_standard_ocr_document(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(("post", url))
        return FakeResponse(200, {"data": {"jobId": "job_123"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(("get", url))
        if url.endswith("/job_123"):
            return FakeResponse(
                200,
                {
                    "data": {
                        "state": "done",
                        "resultUrl": {"jsonUrl": "https://example.test/result.jsonl"},
                    }
                },
            )
        return FakeResponse(
            200,
            text=json.dumps(
                {
                    "result": {
                        "ocrResults": [
                            {
                                "prunedResult": {
                                    "rec_texts": ["宿舍选床", "低置信度"],
                                    "rec_scores": [0.99, 0.1],
                                    "rec_boxes": [[10, 20, 110, 60], [1, 1, 10, 10]],
                                    "rec_polys": [],
                                }
                            }
                        ]
                    }
                },
                ensure_ascii=False,
            ),
        )

    monkeypatch.setattr("app.ocr_baidu.requests.post", fake_post)
    monkeypatch.setattr("app.ocr_baidu.requests.get", fake_get)
    source = tmp_path / "input.png"
    from conftest import PNG_BYTES

    source.write_bytes(PNG_BYTES)
    image = read_png_metadata(PNG_BYTES)
    assert image is not None
    document = extract_ocr(
        task_id="task_ocr_success",
        image=image,
        settings=Settings(
            version="0.1.0",
            storage_root=tmp_path,
            database_path=tmp_path / "app.db",
            public_base_url="http://localhost:8000",
            max_upload_bytes=10 * 1024 * 1024,
            cors_allow_origins=["*"],
            ocr_provider="baidu_ppocrv5",
            baidu_paddle_ocr_token="test-token",
            baidu_paddle_ocr_poll_interval_seconds=0,
        ),
        source_path=source,
    )

    assert document.status == "completed"
    assert document.provider == "baidu_ppocrv5"
    assert len(document.blocks) == 1
    assert document.blocks[0].text == "宿舍选床"
    assert document.blocks[0].bbox == [10, 20, 100, 40]
    assert document.warnings[0].code == "OCR_LOW_CONFIDENCE"
    assert ("post", "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs") in calls


def test_baidu_provider_remote_failure_returns_failed_document(monkeypatch, tmp_path) -> None:
    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, {"data": {"jobId": "job_failed"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, {"data": {"state": "failed", "errorMsg": "quota exceeded"}})

    monkeypatch.setattr("app.ocr_baidu.requests.post", fake_post)
    monkeypatch.setattr("app.ocr_baidu.requests.get", fake_get)
    source = tmp_path / "input.png"
    from conftest import PNG_BYTES

    source.write_bytes(PNG_BYTES)
    image = read_png_metadata(PNG_BYTES)
    assert image is not None
    document = extract_ocr(
        task_id="task_ocr_remote_failure",
        image=image,
        settings=Settings(
            version="0.1.0",
            storage_root=tmp_path,
            database_path=tmp_path / "app.db",
            public_base_url="http://localhost:8000",
            max_upload_bytes=10 * 1024 * 1024,
            cors_allow_origins=["*"],
            ocr_provider="baidu_ppocrv5",
            baidu_paddle_ocr_token="test-token",
            baidu_paddle_ocr_poll_interval_seconds=0,
        ),
        source_path=source,
    )

    assert document.status == "failed"
    assert document.error is not None
    assert document.error["code"] == "OCR_EXTRACTION_FAILED"


def test_baidu_provider_retries_transient_submit_transport_failure(monkeypatch, tmp_path) -> None:
    post_calls = 0
    uploaded_sizes: list[int] = []

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        nonlocal post_calls
        post_calls += 1
        uploaded_sizes.append(len(kwargs["files"]["file"].read()))
        if post_calls == 1:
            raise requests.exceptions.SSLError("temporary eof")
        return FakeResponse(200, {"data": {"jobId": "job_123"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        if url.endswith("/job_123"):
            return FakeResponse(
                200,
                {
                    "data": {
                        "state": "done",
                        "resultUrl": {"jsonUrl": "https://example.test/result.jsonl"},
                    }
                },
            )
        return FakeResponse(
            200,
            text=json.dumps(
                {
                    "result": {
                        "ocrResults": [
                            {
                                "prunedResult": {
                                    "rec_texts": ["Retry OK"],
                                    "rec_scores": [0.99],
                                    "rec_boxes": [[10, 20, 110, 60]],
                                    "rec_polys": [],
                                }
                            }
                        ]
                    }
                },
                ensure_ascii=False,
            ),
        )

    monkeypatch.setattr("app.ocr_baidu.requests.post", fake_post)
    monkeypatch.setattr("app.ocr_baidu.requests.get", fake_get)
    source = tmp_path / "input.png"
    from conftest import PNG_BYTES

    source.write_bytes(PNG_BYTES)
    image = read_png_metadata(PNG_BYTES)
    assert image is not None
    document = extract_ocr(
        task_id="task_ocr_retry_submit",
        image=image,
        settings=Settings(
            version="0.1.0",
            storage_root=tmp_path,
            database_path=tmp_path / "app.db",
            public_base_url="http://localhost:8000",
            max_upload_bytes=10 * 1024 * 1024,
            cors_allow_origins=["*"],
            ocr_provider="baidu_ppocrv5",
            baidu_paddle_ocr_token="test-token",
            baidu_paddle_ocr_poll_interval_seconds=0,
        ),
        source_path=source,
    )

    assert document.status == "completed"
    assert post_calls == 2
    assert uploaded_sizes[0] > 0
    assert uploaded_sizes[1] == uploaded_sizes[0]
    assert document.blocks[0].text == "Retry OK"


def test_baidu_provider_retries_transient_jsonl_503(monkeypatch, tmp_path) -> None:
    jsonl_calls = 0

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, {"data": {"jobId": "job_123"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        nonlocal jsonl_calls
        if url.endswith("/job_123"):
            return FakeResponse(
                200,
                {
                    "data": {
                        "state": "done",
                        "resultUrl": {"jsonUrl": "https://example.test/result.jsonl"},
                    }
                },
            )
        jsonl_calls += 1
        if jsonl_calls == 1:
            return FakeResponse(503, {"message": "temporary unavailable"})
        return FakeResponse(
            200,
            text=json.dumps(
                {
                    "result": {
                        "ocrResults": [
                            {
                                "prunedResult": {
                                    "rec_texts": ["Retry JSONL"],
                                    "rec_scores": [0.99],
                                    "rec_boxes": [[10, 20, 110, 60]],
                                    "rec_polys": [],
                                }
                            }
                        ]
                    }
                },
                ensure_ascii=False,
            ),
        )

    monkeypatch.setattr("app.ocr_baidu.requests.post", fake_post)
    monkeypatch.setattr("app.ocr_baidu.requests.get", fake_get)
    source = tmp_path / "input.png"
    from conftest import PNG_BYTES

    source.write_bytes(PNG_BYTES)
    image = read_png_metadata(PNG_BYTES)
    assert image is not None
    document = extract_ocr(
        task_id="task_ocr_retry_jsonl",
        image=image,
        settings=Settings(
            version="0.1.0",
            storage_root=tmp_path,
            database_path=tmp_path / "app.db",
            public_base_url="http://localhost:8000",
            max_upload_bytes=10 * 1024 * 1024,
            cors_allow_origins=["*"],
            ocr_provider="baidu_ppocrv5",
            baidu_paddle_ocr_token="test-token",
            baidu_paddle_ocr_poll_interval_seconds=0,
        ),
        source_path=source,
    )

    assert document.status == "completed"
    assert jsonl_calls == 2
    assert document.blocks[0].text == "Retry JSONL"


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self) -> dict[str, Any]:
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


# ---------------------------------------------------------------------------
# M34: estimate_polygon_rotation tests
# ---------------------------------------------------------------------------


def test_estimate_polygon_rotation_horizontal_rect_returns_near_zero() -> None:
    from app.ocr_baidu import estimate_polygon_rotation

    # Perfectly horizontal rectangle (top-left, top-right, bottom-right, bottom-left)
    poly = [[10, 20], [110, 20], [110, 50], [10, 50]]
    angle = estimate_polygon_rotation(poly)
    assert angle is not None
    assert angle < 0.5, f"Expected near-zero for horizontal rect, got {angle}"


def test_estimate_polygon_rotation_tilted_returns_high_angle() -> None:
    from app.ocr_baidu import estimate_polygon_rotation
    import math

    # 15-degree tilted rectangle
    cx, cy = 100, 100
    w, h = 200, 40
    rad = math.radians(15)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    poly = [[cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a] for x, y in corners]
    angle = estimate_polygon_rotation(poly)
    assert angle is not None
    assert angle > 10.0, f"Expected high angle for 15° tilt, got {angle}"


def test_estimate_polygon_rotation_slightly_skewed() -> None:
    from app.ocr_baidu import estimate_polygon_rotation

    # Slightly skewed parallelogram (about 5 degrees)
    poly = [[10, 20], [110, 29], [110, 59], [10, 50]]
    angle = estimate_polygon_rotation(poly)
    assert angle is not None
    assert angle > 2.0, f"Expected > 2° for skewed quad, got {angle}"


def test_estimate_polygon_rotation_invalid_inputs() -> None:
    from app.ocr_baidu import estimate_polygon_rotation

    assert estimate_polygon_rotation(None) is None
    assert estimate_polygon_rotation([]) is None
    assert estimate_polygon_rotation([[1, 2]]) is None
    assert estimate_polygon_rotation("not a list") is None


def test_parse_ppocrv5_rows_populates_meta_with_angle_and_polygon() -> None:
    """When rec_polys is present, meta should contain angle and polygon."""
    rows = [
        {
            "result": {
                "ocrResults": [
                    {
                        "prunedResult": {
                            "rec_texts": ["Hello"],
                            "rec_scores": [0.95],
                            "rec_boxes": [[10, 20, 110, 50]],
                            "rec_polys": [[[10, 20], [110, 20], [110, 50], [10, 50]]],
                        }
                    }
                ]
            }
        }
    ]
    blocks, warnings = parse_ppocrv5_rows(rows, min_confidence=0.7)
    assert len(blocks) == 1
    assert "angle" in blocks[0].meta
    assert blocks[0].meta["angle"] < 1.0  # horizontal -> near zero
    assert "polygon" in blocks[0].meta
    assert len(blocks[0].meta["polygon"]) == 4


def test_parse_ppocrv5_rows_tilted_polygon_has_high_angle() -> None:
    """A tilted polygon should produce a high angle in meta."""
    import math

    cx, cy = 100, 100
    w, h = 200, 40
    rad = math.radians(20)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    poly = [[cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a] for x, y in corners]
    rows = [
        {
            "result": {
                "ocrResults": [
                    {
                        "prunedResult": {
                            "rec_texts": ["Art Text"],
                            "rec_scores": [0.95],
                            "rec_boxes": [],
                            "rec_polys": [poly],
                        }
                    }
                ]
            }
        }
    ]
    blocks, warnings = parse_ppocrv5_rows(rows, min_confidence=0.7)
    assert len(blocks) == 1
    assert blocks[0].meta.get("angle", 0) > 10.0


# ---------------------------------------------------------------------------
# M34.1: OCR evidence preservation tests
# ---------------------------------------------------------------------------


def test_ocr_text_box_conversion_preserves_rotation_meta() -> None:
    from app.text_masked_media_audit import text_boxes_from_ocr_document

    boxes, warnings = text_boxes_from_ocr_document(
        {
            "blocks": [
                {
                    "id": "ocr_text_001",
                    "bbox": [10, 10, 40, 20],
                    "text": "Graphic",
                    "confidence": 0.95,
                    "meta": {
                        "angle": 15.0,
                        "polygon": [[10, 10], [49, 20], [45, 39], [6, 29]],
                    },
                },
                {
                    "id": "ocr_text_002",
                    "bbox": [10, 40, 40, 20],
                    "text": "Normal",
                    "confidence": 0.95,
                    "meta": {"angle": 0.5},
                },
            ]
        }
    )

    assert warnings == []
    assert [box.id for box in boxes] == ["ocr_text_001", "ocr_text_002"]
    assert boxes[0].meta["angle"] == 15.0
    assert boxes[0].meta["polygon"] == [[10, 10], [49, 20], [45, 39], [6, 29]]
    assert boxes[1].meta["angle"] == 0.5


def test_ocr_text_box_conversion_keeps_box_without_meta() -> None:
    from app.text_masked_media_audit import text_boxes_from_ocr_document

    boxes, warnings = text_boxes_from_ocr_document(
        {
            "blocks": [
                {
                    "id": "ocr_text_001",
                    "bbox": [10, 10, 40, 20],
                    "text": "Plain",
                    "confidence": 0.95,
                }
            ]
        }
    )

    assert warnings == []
    assert len(boxes) == 1
    assert boxes[0].id == "ocr_text_001"
    assert boxes[0].meta == {}
