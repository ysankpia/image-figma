from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

try:
    import onnxruntime
except ImportError:
    onnxruntime = None


def load_onnx_model(model_path: Path) -> Any | None:
    if onnxruntime is None:
        logger.info("onnxruntime is not installed. Falling back to rule-based classification.")
        return None
    if not model_path.exists():
        logger.warning(f"ONNX model file not found at {model_path}. Falling back to rule-based classification.")
        return None
    try:
        session = onnxruntime.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        return session
    except Exception as e:
        logger.exception(f"Failed to load ONNX model from {model_path}: {e}")
        return None


def preprocess_image(img: Image.Image, target_size: tuple[int, int] = (640, 640)) -> tuple[np.ndarray, float, float, float]:
    orig_w, orig_h = img.size
    r = min(target_size[0] / orig_w, target_size[1] / orig_h)
    new_unpad_w = int(round(orig_w * r))
    new_unpad_h = int(round(orig_h * r))
    dw = (target_size[0] - new_unpad_w) / 2.0
    dh = (target_size[1] - new_unpad_h) / 2.0
    
    img_resized = img.resize((new_unpad_w, new_unpad_h), Image.Resampling.BILINEAR)
    new_img = Image.new("RGB", target_size, (114, 114, 114))
    new_img.paste(img_resized, (int(round(dw)), int(round(dh))))
    
    img_data = np.array(new_img, dtype=np.float32)
    img_data /= 255.0
    img_data = img_data.transpose(2, 0, 1)  # HWC to CHW
    img_data = np.expand_dims(img_data, axis=0)  # CHW to BCHW
    
    return img_data, r, dw, dh


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.45) -> list[int]:
    if len(boxes) == 0:
        return []
    
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    
    order = scores.argsort()[::-1]
    keep = []
    
    while order.size > 0:
        i = order[0]
        keep.append(i)
        
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        
        union = areas[i] + areas[order[1:]] - inter
        ovr = np.where(union > 0, inter / union, 0.0)
        
        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]
        
    return keep


def run_model_inference(session: Any, img_path: Path) -> list[dict[str, Any]]:
    try:
        img = Image.open(img_path).convert("RGB")
    except Exception as e:
        logger.error(f"Failed to open image {img_path} for ONNX inference: {e}")
        return []
    
    orig_w, orig_h = img.size
    input_tensor, r, dw, dh = preprocess_image(img)
    
    try:
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: input_tensor})
        output_data = outputs[0]  # shape: [1, 5, 8400]
    except Exception as e:
        logger.exception(f"ONNX model inference failed: {e}")
        return []
    
    if len(output_data.shape) != 3 or output_data.shape[1] < 5:
        logger.error(f"Unexpected ONNX output shape: {output_data.shape}")
        return []
        
    output_data = output_data[0]  # [5, 8400]
    cx = output_data[0]
    cy = output_data[1]
    w = output_data[2]
    h = output_data[3]
    scores = output_data[4]
    
    keep_idx = np.where(scores >= 0.25)[0]
    if len(keep_idx) == 0:
        return []
        
    filtered_boxes = []
    filtered_scores = []
    
    for idx in keep_idx:
        bcx, bcy, bw, bh = cx[idx], cy[idx], w[idx], h[idx]
        x1 = bcx - bw / 2.0
        y1 = bcy - bh / 2.0
        x2 = bcx + bw / 2.0
        y2 = bcy + bh / 2.0
        filtered_boxes.append([x1, y1, x2, y2])
        filtered_scores.append(scores[idx])
        
    keep = nms(np.array(filtered_boxes), np.array(filtered_scores), iou_threshold=0.45)
    
    proposed_chrome_boxes = []
    for idx in keep:
        x1, y1, x2, y2 = filtered_boxes[idx]
        score = float(filtered_scores[idx])
        
        # map back
        x1_orig = (x1 - dw) / r
        y1_orig = (y1 - dh) / r
        x2_orig = (x2 - dw) / r
        y2_orig = (y2 - dh) / r
        
        # clip
        x1_orig = max(0.0, min(float(orig_w), x1_orig))
        y1_orig = max(0.0, min(float(orig_h), y1_orig))
        x2_orig = max(0.0, min(float(orig_w), x2_orig))
        y2_orig = max(0.0, min(float(orig_h), y2_orig))
        
        proposed_chrome_boxes.append({
            "bbox": [round(x1_orig), round(y1_orig), round(x2_orig - x1_orig), round(y2_orig - y1_orig)],
            "score": score
        })
        
    return proposed_chrome_boxes


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def bbox_intersection_area(left: list[int], right: list[int]) -> int:
    left_x2 = left[0] + left[2]
    left_y2 = left[1] + left[3]
    right_x2 = right[0] + right[2]
    right_y2 = right[1] + right[3]
    w = max(0, min(left_x2, right_x2) - max(left[0], right[0]))
    h = max(0, min(left_y2, right_y2) - max(left[1], right[1]))
    return w * h


def compute_overlap_ratio(node_bbox: list[int], chrome_bbox: list[int]) -> float:
    node_a = bbox_area(node_bbox)
    if node_a == 0:
        return 0.0
    return bbox_intersection_area(node_bbox, chrome_bbox) / node_a


def classify_content_chrome(
    dsl: dict[str, Any],
    task_id: str,
    output_dir: Path,
    source_image_path: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    page = dsl.get("page", {})
    page_width = int(page.get("width") or 0)
    page_height = int(page.get("height") or 0)
    
    # 1. Try to load ONNX model and run inference
    model_path = Path("/Volumes/WorkDrive/Models/model_fp16.onnx")
    proposed_chrome_boxes = []
    onnx_loaded = False
    
    if source_image_path and source_image_path.exists() and onnxruntime is not None:
        session = load_onnx_model(model_path)
        if session is not None:
            proposed_chrome_boxes = run_model_inference(session, source_image_path)
            onnx_loaded = True
            
    # 2. Traverse nodes and classify
    classified_nodes = []
    
    # Helper to traverse
    def classify_node(node: dict[str, Any]) -> None:
        role = node.get("role")
        meta = node.setdefault("meta", {})
        
        is_m30_node = meta.get("m30Materialized") is True and role in {"m30_text_member", "m30_shape_candidate", "m30_visual_asset"}
        
        if is_m30_node:
            layout = node.get("layout", {})
            try:
                nx = float(layout.get("x", 0))
                ny = float(layout.get("y", 0))
                nw = float(layout.get("width", 0))
                nh = float(layout.get("height", 0))
                node_bbox = [round(nx), round(ny), round(nw), round(nh)]
            except (ValueError, TypeError):
                node_bbox = None
                
            if node_bbox and page_width > 0 and page_height > 0:
                classification = "content"
                matched_rules = []
                matched_model_box = None
                overlap_ratio = 0.0
                
                # Rule A: Top 12% vertical bounds
                if (node_bbox[1] + node_bbox[3]) <= 0.12 * page_height and node_bbox[2] >= 0.6 * page_width:
                    classification = "chrome"
                    matched_rules.append("top_12_percent_vertical_bounds")
                    
                # Rule B: Bottom 12% vertical bounds
                if node_bbox[1] >= 0.88 * page_height and node_bbox[2] >= 0.6 * page_width:
                    classification = "chrome"
                    matched_rules.append("bottom_12_percent_vertical_bounds")
                    
                # Rule C: Floating items on right-edge
                if (
                    node_bbox[0] > 0.8 * page_width
                    and node_bbox[1] > 0.12 * page_height
                    and (node_bbox[1] + node_bbox[3]) < 0.88 * page_height
                    and node_bbox[2] < 0.2 * page_width
                    and node_bbox[3] < 0.2 * page_height
                ):
                    classification = "chrome"
                    matched_rules.append("right_edge_floating_item")
                    
                # Model match check
                model_proposed = False
                for box_info in proposed_chrome_boxes:
                    c_box = box_info["bbox"]
                    ratio = compute_overlap_ratio(node_bbox, c_box)
                    if ratio > 0.8:
                        model_proposed = True
                        matched_model_box = c_box
                        overlap_ratio = ratio
                        break
                        
                if model_proposed and classification != "chrome":
                    classification = "chrome"
                    matched_rules.append("onnx_model_proposal")
                    
                # Safety rule override: center 60% horizontally and vertically cannot be chrome
                if classification == "chrome":
                    cx = node_bbox[0] + node_bbox[2] / 2.0
                    cy = node_bbox[1] + node_bbox[3] / 2.0
                    in_center_horiz = (0.2 * page_width) <= cx <= (0.8 * page_width)
                    in_center_vert = (0.2 * page_height) <= cy <= (0.8 * page_height)
                    if in_center_horiz and in_center_vert:
                        classification = "content"
                        matched_rules.append("override_safety_center_60_percent")
                        
                meta["boundaryClassification"] = classification
                classified_nodes.append({
                    "nodeId": node.get("id"),
                    "role": role,
                    "bbox": node_bbox,
                    "classification": classification,
                    "matchedRules": matched_rules,
                    "onnxOverlap": {
                        "proposedBox": matched_model_box,
                        "ratio": overlap_ratio,
                    } if matched_model_box else None,
                })
            else:
                meta["boundaryClassification"] = "content"
                
        for child in node.get("children", []):
            if isinstance(child, dict):
                classify_node(child)
                
    root = dsl.get("root", {})
    classify_node(root)
    
    # 3. Write report
    report = {
        "schemaName": "M39BoundaryClassificationReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "onnxEnabled": onnx_loaded,
        "pageWidth": page_width,
        "pageHeight": page_height,
        "proposedChromeBoxes": proposed_chrome_boxes,
        "summary": {
            "totalClassifiedNodes": len(classified_nodes),
            "chromeCount": sum(1 for n in classified_nodes if n["classification"] == "chrome"),
            "contentCount": sum(1 for n in classified_nodes if n["classification"] == "content"),
        },
        "classifiedNodes": classified_nodes,
    }
    
    report_file = output_dir / "m39_boundary_classification_report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return report
