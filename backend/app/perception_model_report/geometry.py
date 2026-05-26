from __future__ import annotations


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if intersection <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return intersection / max(1e-6, area_a + area_b - intersection)


def nms_candidates(candidates: list[dict], *, iou_threshold: float) -> list[dict]:
    kept: list[dict] = []
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        if all(iou(candidate["bbox"], kept_candidate["bbox"]) < iou_threshold for kept_candidate in kept):
            kept.append(candidate)
    return kept
