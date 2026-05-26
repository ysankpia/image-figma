from __future__ import annotations

import builtins
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.perception_model_report import PerceptionModelOptions, extract_perception_model_report, validate_perception_model_report
from app.perception_model_report.decoder import decode_yolo_like_output, preprocess_image
from app.perception_model_report.pipeline import run_onnx_model


def test_perception_model_decodes_yolo_like_output_with_letterbox_transform() -> None:
    image = Image.new("RGB", (200, 100), (0, 0, 0))
    _, transform = preprocess_image(image, input_size=100)
    raw_output = np.array(
        [
            [
                [50.0, 51.0],
                [50.0, 50.0],
                [20.0, 20.0],
                [10.0, 10.0],
                [0.90, 0.40],
            ]
        ],
        dtype=np.float32,
    )

    candidates = decode_yolo_like_output(
        raw_output,
        transform=transform,
        score_threshold=0.50,
        min_box_px=2.0,
        nms_threshold=0.45,
        top_k=10,
    )

    assert len(candidates) == 1
    assert candidates[0]["bbox"] == [80.0, 40.0, 120.0, 60.0]
    assert candidates[0]["score"] == pytest.approx(0.9)
    assert candidates[0]["areaRatio"] == pytest.approx(0.04)


def test_perception_model_report_is_report_only(tmp_path: Path) -> None:
    raw_output = np.array(
        [
            [
                [50.0, 20.0],
                [50.0, 50.0],
                [20.0, 8.0],
                [10.0, 8.0],
                [0.90, 0.80],
            ]
        ],
        dtype=np.float32,
    )

    result = extract_perception_model_report(
        task_id="task_probe",
        source_png=png_bytes(200, 100),
        output_dir=tmp_path / "m29_perception_model",
        raw_output=raw_output,
        model_metadata={
            "provider": "synthetic_onnx",
            "inputName": "images",
            "inputShape": ["batch", 3, "height", "width"],
            "outputName": "output0",
            "outputShape": ["batch", 5, "anchors"],
        },
        options=PerceptionModelOptions(input_size=100, score_threshold=0.5, top_k=10),
    )

    report = result.report
    validate_perception_model_report(report)
    assert report["schemaName"] == "M29PerceptionModelReport"
    assert report["summary"]["candidateCount"] == 2
    assert report["summary"]["reportOnly"] is True
    assert report["summary"]["sourceOwnershipChanged"] is False
    assert report["summary"]["materializationChanged"] is False
    assert report["summary"]["createdVisibleNodeCount"] == 0
    assert report["candidates"][0]["candidateId"] == "perception_candidate_0001"
    assert report["candidates"][0]["roleHint"] == "unknown_ui_object"
    assert report["candidates"][0]["decision"] == "report_only"
    assert report["candidates"][0]["replayAuthorized"] is False
    assert report["candidates"][0]["cleanupAuthorized"] is False
    assert (tmp_path / "m29_perception_model" / "perception_model_report.json").exists()


def test_perception_model_report_requires_model_path_or_raw_output(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="model_path or raw_output"):
        extract_perception_model_report(
            task_id="task_probe",
            source_png=png_bytes(20, 20),
            output_dir=tmp_path / "m29_perception_model",
        )


def test_onnx_runtime_dependency_error_mentions_backend_sync(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "onnxruntime":
            raise ImportError("blocked by test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(RuntimeError, match="uv sync"):
        run_onnx_model(
            model_path=tmp_path / "missing.onnx",
            tensor=np.zeros((1, 3, 8, 8), dtype=np.float32),
            provider="CPUExecutionProvider",
        )


def png_bytes(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), (255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
