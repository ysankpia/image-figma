from __future__ import annotations

from typing import Any

from ..visual_primitive_graph import M29PrimitiveMetrics, bbox_area, bbox_x2, bbox_y2


def visual_text_overlap_ratio(bbox: list[int], text_bboxes: list[list[int]]) -> float:
    area = bbox_area(bbox)
    if area <= 0:
        return 0.0
    return min(1.0, rectangle_union_intersection_area(bbox, text_bboxes) / area)

def rectangle_union_intersection_area(target: list[int], bboxes: list[list[int]]) -> int:
    rects: list[tuple[int, int, int, int]] = []
    tx1, ty1, tx2, ty2 = target[0], target[1], bbox_x2(target), bbox_y2(target)
    for bbox in bboxes:
        x1 = max(tx1, bbox[0])
        y1 = max(ty1, bbox[1])
        x2 = min(tx2, bbox_x2(bbox))
        y2 = min(ty2, bbox_y2(bbox))
        if x2 > x1 and y2 > y1:
            rects.append((x1, y1, x2, y2))
    if not rects:
        return 0
    xs = sorted({coord for rect in rects for coord in (rect[0], rect[2])})
    area = 0
    for index in range(len(xs) - 1):
        x1, x2 = xs[index], xs[index + 1]
        if x2 <= x1:
            continue
        intervals = [(rect[1], rect[3]) for rect in rects if rect[0] <= x1 and rect[2] >= x2]
        area += (x2 - x1) * union_interval_length(intervals)
    return area

def union_interval_length(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return sum(end - start for start, end in merged)

def bbox_union(bboxes: list[list[int]]) -> list[int]:
    if not bboxes:
        return [0, 0, 1, 1]
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]

def count_by(items: list[Any], key_fn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))

def assert_unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate M29.0.5 {label} id: {value}")
        seen.add(value)
    return seen

def truncate_text(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= max_chars else text[:max_chars] + "..."

def metrics_color(metrics: M29PrimitiveMetrics | None) -> str | None:
    if metrics is None:
        return None
    return "#" + "".join(f"{max(0, min(255, value)):02X}" for value in metrics.mean_rgb)

def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
