from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.ocr_baidu import parse_ppocrv5_rows, polygon_to_bbox, rec_box_to_bbox


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


def test_baidu_provider_without_token_does_not_break_upload(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "OCR_PROVIDER": "baidu_ppocrv5",
            "BAIDU_PADDLE_OCR_TOKEN": "",
        },
    )
    from conftest import PNG_BYTES

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        ocr_response = client.get(f"/api/tasks/{task_id}/ocr")
        assert ocr_response.status_code == 200
        ocr = ocr_response.json()["data"]
        assert ocr["provider"] == "baidu_ppocrv5"
        assert ocr["model"] == "PP-OCRv5"
        assert ocr["status"] == "failed"
        assert ocr["error"]["code"] == "BAIDU_PADDLE_OCR_TOKEN_MISSING"

        dsl_response = client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl_response.status_code == 200
        child_ids = {child["id"] for child in dsl_response.json()["data"]["dsl"]["root"]["children"]}
        assert "text_ocr_text_001" not in child_ids
        assert "fallback_region_header" in child_ids


def test_baidu_provider_success_builds_hidden_text_candidates(monkeypatch, tmp_path) -> None:
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
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "OCR_PROVIDER": "baidu_ppocrv5",
            "BAIDU_PADDLE_OCR_TOKEN": "test-token",
            "BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS": "0",
        },
    )
    from conftest import PNG_BYTES

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        ocr = client.get(f"/api/tasks/{task_id}/ocr").json()["data"]
        assert ocr["status"] == "completed"
        assert ocr["provider"] == "baidu_ppocrv5"
        assert len(ocr["blocks"]) == 1
        assert ocr["blocks"][0]["text"] == "宿舍选床"
        assert ocr["blocks"][0]["bbox"] == [10, 20, 100, 40]
        assert ocr["warnings"][0]["code"] == "OCR_LOW_CONFIDENCE"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        children = {child["id"]: child for child in dsl["root"]["children"]}
        assert children["text_ocr_text_001"]["style"]["visible"] is False
        assert children["text_ocr_text_001"]["content"]["text"] == "宿舍选床"
        assert "fallback_region_header" in children

    assert ("post", "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs") in calls


def test_baidu_provider_remote_failure_keeps_upload_completed(monkeypatch, tmp_path) -> None:
    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, {"data": {"jobId": "job_failed"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse(200, {"data": {"state": "failed", "errorMsg": "quota exceeded"}})

    monkeypatch.setattr("app.ocr_baidu.requests.post", fake_post)
    monkeypatch.setattr("app.ocr_baidu.requests.get", fake_get)
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "OCR_PROVIDER": "baidu_ppocrv5",
            "BAIDU_PADDLE_OCR_TOKEN": "test-token",
            "BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS": "0",
        },
    )
    from conftest import PNG_BYTES

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        ocr = client.get(f"/api/tasks/{task_id}/ocr").json()["data"]
        assert ocr["status"] == "failed"
        assert ocr["error"]["code"] == "OCR_EXTRACTION_FAILED"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        child_ids = {child["id"] for child in dsl["root"]["children"]}
        assert "text_ocr_text_001" not in child_ids
        assert "fallback_region_header" in child_ids


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self) -> dict[str, Any]:
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("IMAGE_FIGMA_LOAD_LOCAL_ENV", "false")
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    for key, value in env.items():
        if value:
            monkeypatch.setenv(key, value)
        else:
            monkeypatch.delenv(key, raising=False)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    return TestClient(main.create_app())
