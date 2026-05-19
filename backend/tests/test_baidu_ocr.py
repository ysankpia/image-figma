from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self) -> dict[str, Any]:
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)
