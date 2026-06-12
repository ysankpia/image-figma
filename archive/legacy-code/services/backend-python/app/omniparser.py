from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import onnxruntime as ort
from PIL import Image

from .config import OmniParserConfig


@dataclass
class Detection:
    x: int
    y: int
    width: int
    height: int
    confidence: float


def letterbox(image: Image.Image, target_size: int) -> tuple[np.ndarray, float, int, int]:
    """Resize with padding to target_size×target_size, return (array, scale, pad_x, pad_y)."""
    w, h = image.size
    scale = target_size / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = image.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (target_size, target_size), (114, 114, 114))
    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))
    arr = np.asarray(canvas, dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)[np.newaxis]
    return arr, scale, pad_x, pad_y


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Standard greedy NMS. boxes shape: [N, 4] as (x1, y1, x2, y2)."""
    if len(boxes) == 0:
        return []
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while len(order) > 0:
        i = order[0]
        keep.append(int(i))
        if len(order) == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_rest = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_rest - inter + 1e-6)
        order = rest[iou <= iou_threshold]
    return keep


class OmniParser:
    def __init__(self, config: OmniParserConfig) -> None:
        self.config = config
        self.session = ort.InferenceSession(
            config.model_path,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name

    def detect(self, image: Image.Image) -> list[Detection]:
        img_w, img_h = image.size
        size = self.config.input_size
        arr, scale, pad_x, pad_y = letterbox(image.convert("RGB"), size)

        outputs = self.session.run(None, {self.input_name: arr})
        # output shape: [1, 5, N] → transpose to [N, 5]
        pred = outputs[0][0].T  # [N, 5]: cx, cy, w, h, conf

        mask = pred[:, 4] > self.config.confidence
        pred = pred[mask]
        if len(pred) == 0:
            return []

        # convert cx,cy,w,h to x1,y1,x2,y2
        cx, cy, bw, bh = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
        x1 = cx - bw / 2
        y1 = cy - bh / 2
        x2 = cx + bw / 2
        y2 = cy + bh / 2
        boxes = np.stack([x1, y1, x2, y2], axis=1)
        scores = pred[:, 4]

        keep = nms(boxes, scores, self.config.nms_iou)
        boxes = boxes[keep]
        scores = scores[keep]

        detections: list[Detection] = []
        for box, score in zip(boxes, scores):
            # undo letterbox: subtract padding, then divide by scale
            rx1 = (box[0] - pad_x) / scale
            ry1 = (box[1] - pad_y) / scale
            rx2 = (box[2] - pad_x) / scale
            ry2 = (box[3] - pad_y) / scale
            # clip to image bounds
            rx1 = max(0, min(rx1, img_w))
            ry1 = max(0, min(ry1, img_h))
            rx2 = max(0, min(rx2, img_w))
            ry2 = max(0, min(ry2, img_h))
            w = int(rx2 - rx1)
            h = int(ry2 - ry1)
            if w < 4 or h < 4:
                continue
            detections.append(Detection(
                x=int(rx1), y=int(ry1), width=w, height=h,
                confidence=float(score),
            ))
        return detections
