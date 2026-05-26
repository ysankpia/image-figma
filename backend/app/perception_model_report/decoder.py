from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from .geometry import clamp, nms_candidates


def preprocess_image(image: Any, *, input_size: int) -> tuple[np.ndarray, dict[str, float]]:
    width, height = image.size
    scale = min(input_size / width, input_size / height)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    pad_x = (input_size - resized_width) / 2.0
    pad_y = (input_size - resized_height) / 2.0

    canvas = Image.new("RGB", (input_size, input_size), (114, 114, 114))
    resized = image.resize((resized_width, resized_height))
    canvas.paste(resized, (round(pad_x), round(pad_y)))
    array = np.asarray(canvas).astype("float32") / 255.0
    tensor = np.transpose(array, (2, 0, 1))[None, :, :, :]
    return tensor, {
        "scale": float(scale),
        "padX": float(pad_x),
        "padY": float(pad_y),
        "imageWidth": float(width),
        "imageHeight": float(height),
    }


def decode_yolo_like_output(
    raw_output: Any,
    *,
    transform: dict[str, float],
    score_threshold: float,
    min_box_px: float,
    nms_threshold: float,
    top_k: int,
) -> list[dict[str, Any]]:
    data = np.asarray(raw_output)
    rows = rows_from_output(data)
    scale = transform["scale"]
    pad_x = transform["padX"]
    pad_y = transform["padY"]
    image_width = transform["imageWidth"]
    image_height = transform["imageHeight"]
    scores = rows[:, 4]
    if float(scores.min(initial=0.0)) < 0.0 or float(scores.max(initial=0.0)) > 1.0:
        scores = 1.0 / (1.0 + np.exp(-scores))

    candidates: list[dict[str, Any]] = []
    for anchor_index, (row, score_value) in enumerate(zip(rows, scores, strict=False)):
        score = float(score_value)
        if score < score_threshold:
            continue
        cx, cy, width, height = [float(value) for value in row[:4]]
        x1 = (cx - width / 2.0 - pad_x) / scale
        y1 = (cy - height / 2.0 - pad_y) / scale
        x2 = (cx + width / 2.0 - pad_x) / scale
        y2 = (cy + height / 2.0 - pad_y) / scale
        x1 = clamp(x1, 0.0, image_width)
        y1 = clamp(y1, 0.0, image_height)
        x2 = clamp(x2, 0.0, image_width)
        y2 = clamp(y2, 0.0, image_height)
        box_width = x2 - x1
        box_height = y2 - y1
        if box_width < min_box_px or box_height < min_box_px:
            continue
        area_ratio = (box_width * box_height) / max(1.0, image_width * image_height)
        candidates.append(
            {
                "rawAnchorIndex": anchor_index,
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                "score": round(score, 6),
                "areaRatio": round(area_ratio, 6),
            }
        )
    return nms_candidates(candidates, iou_threshold=nms_threshold)[:top_k]


def rows_from_output(data: np.ndarray) -> np.ndarray:
    if data.ndim != 3 or data.shape[0] != 1:
        raise ValueError(f"unsupported perception model output shape {list(data.shape)}; expected [1, 5, anchors] or [1, anchors, 5]")
    if data.shape[1] == 5:
        return data[0].T
    if data.shape[2] == 5:
        return data[0]
    raise ValueError(f"unsupported perception model output shape {list(data.shape)}; expected one dimension of size 5")
