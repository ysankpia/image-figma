from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class UnexpectedOnnxOutputShape(ValueError):
    pass


def propose_boxes_with_onnx(
    *,
    source_image_path: Path | None,
    model_path: Path,
    warning_prefix: str,
) -> tuple[list[dict[str, Any]], str | None, bool, list[str]]:
    warnings: list[str] = []
    if source_image_path is None or not source_image_path.exists():
        return [], "inference_failed", False, [f"{warning_prefix} skipped: source image missing."]
    if not model_path.exists():
        return [], "missing_model", False, [f"{warning_prefix} skipped: model not found at {model_path}."]

    numpy_module, reason = import_optional_module("numpy", reason_name="numpy")
    if reason is not None:
        return [], reason, False, [f"{warning_prefix} skipped: {reason}."]
    image_module, reason = import_optional_module("PIL.Image", reason_name="PIL")
    if reason is not None:
        return [], reason, False, [f"{warning_prefix} skipped: {reason}."]
    onnxruntime_module, reason = import_optional_module("onnxruntime", reason_name="onnxruntime")
    if reason is not None:
        return [], reason, False, [f"{warning_prefix} skipped: {reason}."]

    try:
        session = onnxruntime_module.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    except Exception as error:  # noqa: BLE001 - optional proposer must not block upload.
        logger.warning("%s model load failed: %s", warning_prefix, error)
        return [], "inference_failed", False, [f"{warning_prefix} model load failed: {error}."]

    try:
        boxes = run_model_inference(
            session=session,
            img_path=source_image_path,
            np_module=numpy_module,
            image_module=image_module,
            warning_prefix=warning_prefix,
        )
    except UnexpectedOnnxOutputShape as error:
        return [], "unexpected_output_shape", True, [str(error)]
    except Exception as error:  # noqa: BLE001 - optional proposer must not block upload.
        logger.warning("%s inference failed: %s", warning_prefix, error)
        return [], "inference_failed", True, [f"{warning_prefix} inference failed: {error}."]

    return boxes, None, True, warnings


def import_optional_module(module_name: str, *, reason_name: str) -> tuple[Any | None, str | None]:
    try:
        return importlib.import_module(module_name), None
    except ImportError:
        return None, f"missing_dependency:{reason_name}"


def run_model_inference(
    *,
    session: Any,
    img_path: Path,
    np_module: Any,
    image_module: Any,
    warning_prefix: str = "ONNX proposer",
) -> list[dict[str, Any]]:
    img = image_module.open(img_path).convert("RGB")
    orig_w, orig_h = img.size
    input_tensor, scale, pad_x, pad_y = preprocess_image(img, np_module=np_module, image_module=image_module)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_tensor})
    if not outputs:
        raise UnexpectedOnnxOutputShape(f"{warning_prefix} unexpected output shape: no outputs.")
    output_data = outputs[0]
    shape = getattr(output_data, "shape", None)
    if shape is None or len(shape) != 3:
        raise UnexpectedOnnxOutputShape(f"{warning_prefix} unexpected output shape: {shape}.")
    if shape[1] >= 5 and shape[1] <= shape[2]:
        output_data = output_data[0]
    elif shape[2] >= 5:
        output_data = output_data[0].transpose(1, 0)
    else:
        raise UnexpectedOnnxOutputShape(f"{warning_prefix} unexpected output shape: {shape}.")

    cx = output_data[0]
    cy = output_data[1]
    width = output_data[2]
    height = output_data[3]
    scores = output_data[4]

    keep_idx = np_module.where(scores >= 0.25)[0]
    if len(keep_idx) == 0:
        return []

    filtered_boxes = []
    filtered_scores = []
    for idx in keep_idx:
        bcx = cx[idx]
        bcy = cy[idx]
        box_w = width[idx]
        box_h = height[idx]
        filtered_boxes.append([bcx - box_w / 2.0, bcy - box_h / 2.0, bcx + box_w / 2.0, bcy + box_h / 2.0])
        filtered_scores.append(scores[idx])

    keep = nms(np_module.array(filtered_boxes), np_module.array(filtered_scores), np_module=np_module, iou_threshold=0.45)
    proposed_boxes = []
    for idx in keep:
        x1, y1, x2, y2 = filtered_boxes[idx]
        score = float(filtered_scores[idx])
        x1_orig = (x1 - pad_x) / scale
        y1_orig = (y1 - pad_y) / scale
        x2_orig = (x2 - pad_x) / scale
        y2_orig = (y2 - pad_y) / scale
        x1_orig = max(0.0, min(float(orig_w), x1_orig))
        y1_orig = max(0.0, min(float(orig_h), y1_orig))
        x2_orig = max(0.0, min(float(orig_w), x2_orig))
        y2_orig = max(0.0, min(float(orig_h), y2_orig))
        proposed_boxes.append(
            {
                "bbox": [round(x1_orig), round(y1_orig), round(x2_orig - x1_orig), round(y2_orig - y1_orig)],
                "score": score,
            }
        )
    return proposed_boxes


def preprocess_image(
    img: Any,
    *,
    np_module: Any,
    image_module: Any,
    target_size: tuple[int, int] = (640, 640),
) -> tuple[Any, float, float, float]:
    orig_w, orig_h = img.size
    scale = min(target_size[0] / orig_w, target_size[1] / orig_h)
    new_unpad_w = int(round(orig_w * scale))
    new_unpad_h = int(round(orig_h * scale))
    pad_x = (target_size[0] - new_unpad_w) / 2.0
    pad_y = (target_size[1] - new_unpad_h) / 2.0

    img_resized = img.resize((new_unpad_w, new_unpad_h), image_module.Resampling.BILINEAR)
    new_img = image_module.new("RGB", target_size, (114, 114, 114))
    new_img.paste(img_resized, (int(round(pad_x)), int(round(pad_y))))

    img_data = np_module.array(new_img, dtype=np_module.float32)
    img_data /= 255.0
    img_data = img_data.transpose(2, 0, 1)
    img_data = np_module.expand_dims(img_data, axis=0)
    return img_data, scale, pad_x, pad_y


def nms(boxes: Any, scores: Any, *, np_module: Any, iou_threshold: float = 0.45) -> list[int]:
    if len(boxes) == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np_module.maximum(x1[i], x1[order[1:]])
        yy1 = np_module.maximum(y1[i], y1[order[1:]])
        xx2 = np_module.minimum(x2[i], x2[order[1:]])
        yy2 = np_module.minimum(y2[i], y2[order[1:]])
        width = np_module.maximum(0.0, xx2 - xx1)
        height = np_module.maximum(0.0, yy2 - yy1)
        inter = width * height
        union = areas[i] + areas[order[1:]] - inter
        overlap = np_module.where(union > 0, inter / union, 0.0)
        indexes = np_module.where(overlap <= iou_threshold)[0]
        order = order[indexes + 1]

    return keep
