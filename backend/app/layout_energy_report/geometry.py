from __future__ import annotations

from statistics import mean


def bbox_x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def bbox_y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]


def center_x(bbox: list[int]) -> float:
    return bbox[0] + bbox[2] / 2


def center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def bbox_union(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def intersection_area(left: list[int], right: list[int]) -> int:
    return max(0, min(bbox_x2(left), bbox_x2(right)) - max(left[0], right[0])) * max(
        0,
        min(bbox_y2(left), bbox_y2(right)) - max(left[1], right[1]),
    )


def overlap_ratio(left: list[int], right: list[int]) -> float:
    smaller_area = min(bbox_area(left), bbox_area(right))
    if smaller_area <= 0:
        return 0.0
    return intersection_area(left, right) / smaller_area


def gaps_for_row(items: list[dict]) -> list[float]:
    ordered = sorted(items, key=lambda item: (item["bbox"][0], item["bbox"][1], item["sourceObjectId"]))
    return [max(0, ordered[index + 1]["bbox"][0] - bbox_x2(ordered[index]["bbox"])) for index in range(len(ordered) - 1)]


def gaps_for_column(items: list[dict]) -> list[float]:
    ordered = sorted(items, key=lambda item: (item["bbox"][1], item["bbox"][0], item["sourceObjectId"]))
    return [max(0, ordered[index + 1]["bbox"][1] - bbox_y2(ordered[index]["bbox"])) for index in range(len(ordered) - 1)]


def normalized_variance(values: list[float], scale: float) -> float:
    if len(values) <= 1:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return min(1.0, variance**0.5 / max(1.0, scale))


def overlap_penalty(items: list[dict]) -> float:
    if len(items) <= 1:
        return 0.0
    pairs = 0
    total = 0.0
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            pairs += 1
            total += overlap_ratio(left["bbox"], right["bbox"])
    return min(1.0, total / max(1, pairs))


def distinct_tracks(values: list[float], tolerance: float) -> int:
    tracks: list[float] = []
    for value in sorted(values):
        if not tracks or abs(value - tracks[-1]) > tolerance:
            tracks.append(value)
    return len(tracks)
