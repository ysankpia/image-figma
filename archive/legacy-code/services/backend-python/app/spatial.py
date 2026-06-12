from __future__ import annotations

from .schema import BBox


def clamp_bbox(box: BBox, width: int, height: int) -> BBox | None:
    x1 = max(0, min(box.x, width))
    y1 = max(0, min(box.y, height))
    x2 = max(0, min(box.x2, width))
    y2 = max(0, min(box.y2, height))
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)


def intersection_area(a: BBox, b: BBox) -> int:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    return max(0, x2 - x1) * max(0, y2 - y1)


def iou(a: BBox, b: BBox) -> float:
    inter = intersection_area(a, b)
    union = a.area + b.area - inter
    if union <= 0:
        return 0.0
    return inter / union


def ioa(inner: BBox, outer: BBox) -> float:
    if inner.area <= 0:
        return 0.0
    return intersection_area(inner, outer) / inner.area


def contains(parent: BBox, child: BBox, tolerance: int = 0) -> bool:
    return (
        parent.x - tolerance <= child.x
        and parent.y - tolerance <= child.y
        and parent.x2 + tolerance >= child.x2
        and parent.y2 + tolerance >= child.y2
    )


def union_bbox(boxes: list[BBox]) -> BBox:
    if not boxes:
        return BBox(0, 0, 0, 0)
    x1 = min(box.x for box in boxes)
    y1 = min(box.y for box in boxes)
    x2 = max(box.x2 for box in boxes)
    y2 = max(box.y2 for box in boxes)
    return BBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)
