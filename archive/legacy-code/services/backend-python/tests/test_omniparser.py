import numpy as np
from PIL import Image

from app.omniparser import letterbox, nms, OmniParser, Detection
from app.config import OmniParserConfig


def test_letterbox_square():
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    arr, scale, pad_x, pad_y = letterbox(img, 640)
    assert arr.shape == (1, 3, 640, 640)
    assert scale == 6.4
    assert pad_x == 0
    assert pad_y == 0


def test_letterbox_landscape():
    img = Image.new("RGB", (200, 100), (0, 255, 0))
    arr, scale, pad_x, pad_y = letterbox(img, 640)
    assert arr.shape == (1, 3, 640, 640)
    assert scale == 3.2
    assert pad_x == 0
    assert pad_y == 160


def test_nms_basic():
    boxes = np.array([
        [0, 0, 10, 10],
        [1, 1, 11, 11],
        [50, 50, 60, 60],
    ], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    keep = nms(boxes, scores, 0.5)
    assert 0 in keep
    assert 2 in keep
    assert 1 not in keep


def test_nms_empty():
    boxes = np.zeros((0, 4), dtype=np.float32)
    scores = np.zeros(0, dtype=np.float32)
    assert nms(boxes, scores, 0.5) == []


def test_omniparser_detect():
    """Integration test — requires model file."""
    import os
    model_path = os.getenv("OMNIPARSER_MODEL_PATH", "/Volumes/WorkDrive/Models/model_fp16.onnx")
    if not os.path.exists(model_path):
        import pytest
        pytest.skip("OmniParser model not found")

    config = OmniParserConfig(model_path=model_path, confidence=0.3, nms_iou=0.5, input_size=640)
    parser = OmniParser(config)
    # Create a simple test image
    img = Image.new("RGB", (375, 812), (240, 240, 240))
    detections = parser.detect(img)
    # Blank image should have few or no detections
    assert isinstance(detections, list)
    for d in detections:
        assert isinstance(d, Detection)
        assert d.width > 0 and d.height > 0
