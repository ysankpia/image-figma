from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import api
from app.config import Settings
from app.main import app
from app.ocr_cache import ResolvedOCRArtifact, copy_uploaded_ocr_artifact, resolve_or_create_ocr_artifact
from app.ocr_provider import OCRProviderError, OCRRunResult, ocr_blocks_artifact, run_ocr_provider


def test_baidu_ppocrv5_parser_outputs_ocr_blocks_and_filters_low_confidence() -> None:
    artifact = ocr_blocks_artifact(
        [
            {
                "result": {
                    "ocrResults": [
                        {
                            "prunedResult": {
                                "rec_texts": ["Hello", "Low"],
                                "rec_scores": [0.95, 0.2],
                                "rec_boxes": [[10, 20, 50, 40], [1, 2, 10, 12]],
                            }
                        }
                    ]
                }
            }
        ],
        provider="baidu_ppocrv5",
        model="PP-OCRv5",
        min_confidence=0.7,
    )

    assert artifact["version"] == "ocr_blocks.v1"
    assert len(artifact["blocks"]) == 1
    assert artifact["blocks"][0]["text"] == "Hello"
    assert artifact["blocks"][0]["bbox"] == {"x": 10, "y": 20, "width": 40, "height": 20}
    assert artifact["blocks"][0]["confidence"] == 0.95
    assert artifact["meta"]["rawTextCount"] == 2
    assert artifact["meta"]["filteredLowConfidenceCount"] == 1
    assert [warning["code"] for warning in artifact["warnings"]] == ["OCR_LOW_CONFIDENCE"]


def test_ocr_cache_miss_calls_provider_then_hit_reuses_cache(tmp_path: Path) -> None:
    image_path = write_button_image(tmp_path / "button.png")
    settings = replace(Settings(root_dir=tmp_path), ocr_cache_dir=tmp_path / "ocr_cache")
    calls = {"count": 0}

    def fake_runner(_image_path: Path, _settings: Settings) -> OCRRunResult:
        calls["count"] += 1
        return OCRRunResult(
            artifact=ocr_artifact("OK"),
            diagnostics={
                "ocrProvider": "fake",
                "ocrPresent": True,
                "ocrTextCount": 1,
                "ocrElapsedSeconds": 0.01,
                "ocrError": "",
            },
        )

    first = resolve_or_create_ocr_artifact(
        image_path=image_path,
        task_ocr_path=tmp_path / "task1" / "input.ocr_blocks.v1.json",
        settings=settings,
        require_ocr=True,
        runner=fake_runner,
    )
    second = resolve_or_create_ocr_artifact(
        image_path=image_path,
        task_ocr_path=tmp_path / "task2" / "input.ocr_blocks.v1.json",
        settings=settings,
        require_ocr=True,
        runner=fake_runner,
    )

    assert calls["count"] == 1
    assert first.path is not None and first.path.exists()
    assert second.path is not None and second.path.exists()
    assert first.diagnostics["ocrCacheHit"] is False
    assert second.diagnostics["ocrCacheHit"] is True
    assert second.diagnostics["ocrTextCount"] == 1


def test_missing_baidu_token_fails_when_ocr_is_required(tmp_path: Path) -> None:
    image_path = write_button_image(tmp_path / "button.png")
    settings = replace(
        Settings(root_dir=tmp_path),
        ocr_provider="baidu_ppocrv5",
        baidu_paddle_ocr_token="",
    )

    with pytest.raises(OCRProviderError) as error:
        run_ocr_provider(image_path, settings)

    assert error.value.code == "BAIDU_PADDLE_OCR_TOKEN_MISSING"
    assert "BAIDU_PADDLE_OCR_TOKEN" in error.value.message


def test_uploaded_ocr_artifact_does_not_call_provider(tmp_path: Path) -> None:
    uploaded = tmp_path / "uploaded.ocr_blocks.v1.json"
    uploaded.write_text(json.dumps(ocr_artifact("OK")), encoding="utf-8")

    resolved = copy_uploaded_ocr_artifact(uploaded, tmp_path / "task" / "input.ocr_blocks.v1.json")

    assert resolved.path is not None
    assert resolved.path.exists()
    assert resolved.diagnostics["ocrProvider"] == "uploaded"
    assert resolved.diagnostics["ocrCacheHit"] is False
    assert not (tmp_path / "ocr_cache").exists()


def test_png_only_api_uses_resolver_and_generates_text_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: replace(Settings(root_dir=tmp_path), storage_dir=tmp_path / "tasks", ocr_provider="none"),
    )

    def fake_resolver(**kwargs: object) -> ResolvedOCRArtifact:
        task_ocr_path = kwargs["task_ocr_path"]
        assert isinstance(task_ocr_path, Path)
        task_ocr_path.write_text(json.dumps(ocr_artifact("OK")), encoding="utf-8")
        return ResolvedOCRArtifact(
            path=task_ocr_path,
            diagnostics={
                "ocrProvider": "fake",
                "ocrPresent": True,
                "ocrTextCount": 1,
                "ocrCacheHit": False,
                "ocrElapsedSeconds": 0.01,
                "ocrError": "",
                "ocrArtifactPath": str(task_ocr_path),
            },
        )

    monkeypatch.setattr(api, "resolve_or_create_ocr_artifact", fake_resolver)

    image_path = write_button_image(tmp_path / "button.png")
    client = TestClient(app)
    with image_path.open("rb") as image_file:
        response = client.post("/api/draft-preview", files={"image": ("button.png", image_file, "image/png")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["taskId"] == payload["taskId"]
    assert payload["diagnostics"]["ocrPresent"] is True
    assert payload["diagnostics"]["ocrProvider"] == "fake"
    assert payload["diagnostics"]["textLayerCount"] > 0


def ocr_artifact(text: str) -> dict:
    return {
        "version": "ocr_blocks.v1",
        "provider": "fake",
        "blocks": [
            {
                "id": "text_0001",
                "text": text,
                "bbox": {"x": 92, "y": 53, "width": 18, "height": 12},
                "confidence": 0.99,
                "source": "fake",
            }
        ],
        "meta": {"provider": "fake"},
    }


def write_button_image(path: Path) -> Path:
    image = Image.new("RGB", (240, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((50, 42, 190, 82), radius=18, fill=(245, 180, 40))
    draw.text((92, 53), "OK", fill=(20, 20, 20))
    image.save(path)
    return path
