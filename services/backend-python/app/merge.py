from __future__ import annotations

from dataclasses import dataclass

from .ocr import TextBlock
from .omniparser import Detection
from .vlm import VLMElement


@dataclass
class MergedElement:
    type: str  # "text", "image", "shape"
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    text: str = ""


def iou(a_x: int, a_y: int, a_w: int, a_h: int,
         b_x: int, b_y: int, b_w: int, b_h: int) -> float:
    x1 = max(a_x, b_x)
    y1 = max(a_y, b_y)
    x2 = min(a_x + a_w, b_x + b_w)
    y2 = min(a_y + a_h, b_y + b_h)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = a_w * a_h
    area_b = b_w * b_h
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def merge_results(
    texts: list[TextBlock],
    detections: list[Detection],
    vlm_elements: list[VLMElement],
    page_width: int,
    page_height: int,
    iou_threshold: float = 0.5,
) -> list[MergedElement]:
    elements: list[MergedElement] = []
    page_area = page_width * page_height

    # 1. OCR text → text nodes directly
    for t in texts:
        elements.append(MergedElement(
            type="text", role="TextView", label=t.text,
            x=t.x, y=t.y, width=t.width, height=t.height,
            confidence=t.confidence, text=t.text,
        ))

    # 2. VLM elements → map role to type
    vlm_merged: list[MergedElement] = []
    for v in vlm_elements:
        # Skip VLM TextViews that overlap with OCR (OCR is more accurate for text)
        if v.role == "TextView":
            overlaps_text = any(
                iou(v.x, v.y, v.width, v.height, t.x, t.y, t.width, t.height) > 0.4
                for t in texts
            )
            if overlaps_text:
                continue

        area_ratio = (v.width * v.height) / page_area if page_area > 0 else 0
        node_type = _role_to_type(v.role)

        # Large areas (>10% of page) that are "image" → demote to shape
        # They are containers, not actual images
        if node_type == "image" and area_ratio > 0.10:
            node_type = "shape"

        # Skip backgrounds that cover >85% of page
        if v.role == "Background" and area_ratio > 0.85:
            continue

        vlm_merged.append(MergedElement(
            type=node_type, role=v.role, label=v.label,
            x=v.x, y=v.y, width=v.width, height=v.height,
            confidence=v.confidence,
        ))

    # 3. OmniParser detections — keep only those NOT covered by VLM
    for d in detections:
        # Skip OmniParser boxes that are too large (>5% page area = not an icon)
        det_area_ratio = (d.width * d.height) / page_area if page_area > 0 else 0
        if det_area_ratio > 0.05:
            continue

        covered = any(
            iou(d.x, d.y, d.width, d.height, v.x, v.y, v.width, v.height) > iou_threshold
            for v in vlm_merged
        )
        if covered:
            continue
        # Also skip if fully covered by a text block
        text_covered = any(
            iou(d.x, d.y, d.width, d.height, t.x, t.y, t.width, t.height) > 0.6
            for t in texts
        )
        if text_covered:
            continue
        vlm_merged.append(MergedElement(
            type="image", role="Icon", label="icon",
            x=d.x, y=d.y, width=d.width, height=d.height,
            confidence=d.confidence,
        ))

    # 4. Container suppression: if an image/shape contains 3+ other elements inside, skip it
    all_elements = elements + vlm_merged
    final_vlm: list[MergedElement] = []
    for el in vlm_merged:
        if el.type == "image":
            contained = sum(
                1 for other in all_elements
                if other is not el
                and other.x >= el.x and other.y >= el.y
                and other.x + other.width <= el.x + el.width
                and other.y + other.height <= el.y + el.height
            )
            if contained >= 3:
                el.type = "shape"
        final_vlm.append(el)

    elements.extend(final_vlm)
    return elements


def _role_to_type(role: str) -> str:
    if role in ("ImageView", "Icon"):
        return "image"
    if role in ("Background", "ViewGroup", "ListView", "ActionBar", "StatusBar", "BottomNavigation"):
        return "shape"
    if role in ("TextView",):
        return "text"
    if role in ("Button", "EditText"):
        return "shape"
    return "shape"
