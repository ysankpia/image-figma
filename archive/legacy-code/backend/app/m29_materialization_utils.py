from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def list_dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def layout_from_bbox(bbox: list[int]) -> dict[str, int]:
    return {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]}


def next_unique_id(existing_ids: set[str], base: str) -> str:
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    existing_ids.add(candidate)
    return candidate


def next_unique_asset_id(existing_ids: set[str], base: str) -> str:
    return next_unique_id(existing_ids, base)


def bbox_area(bbox: list[int]) -> int:
    if len(bbox) != 4:
        return 0
    return max(0, bbox[2]) * max(0, bbox[3])


def bbox_intersection_area(left: list[int], right: list[int]) -> int:
    if len(left) != 4 or len(right) != 4:
        return 0
    width = max(0, min(left[0] + left[2], right[0] + right[2]) - max(left[0], right[0]))
    height = max(0, min(left[1] + left[3], right[1] + right[3]) - max(left[1], right[1]))
    return width * height


def bbox_overlap_ratio(left: list[int], right: list[int]) -> float:
    area = bbox_area(left)
    if area <= 0:
        return 0.0
    return bbox_intersection_area(left, right) / area


def map_page_bbox_to_asset_pixels(
    text_bbox: list[int],
    image_bbox: list[int],
    asset_width: int,
    asset_height: int,
    scale_x: float,
    scale_y: float,
) -> list[int] | None:
    local_x = (text_bbox[0] - image_bbox[0]) * scale_x
    local_y = (text_bbox[1] - image_bbox[1]) * scale_y
    local_w = text_bbox[2] * scale_x
    local_h = text_bbox[3] * scale_y
    x1 = max(0, math.floor(local_x))
    y1 = max(0, math.floor(local_y))
    x2 = min(asset_width, math.ceil(local_x + local_w))
    y2 = min(asset_height, math.ceil(local_y + local_h))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2 - x1, y2 - y1]


def sample_outer_bbox_ring_rgb(pixels: Any, bbox: list[int]) -> list[int]:
    x, y, width, height = bbox
    samples: list[tuple[int, int, int]] = []
    margin = 3
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(pixels.width, x + width + margin)
    y2 = min(pixels.height, y + height + margin)
    for row_idx in range(y1, y2):
        row = pixels.rows[row_idx]
        for col_idx in range(x1, x2):
            inside = x <= col_idx < x + width and y <= row_idx < y + height
            if inside:
                continue
            near_x_edge = abs(col_idx - x) <= margin or abs(col_idx - (x + width - 1)) <= margin
            near_y_edge = abs(row_idx - y) <= margin or abs(row_idx - (y + height - 1)) <= margin
            if not near_x_edge and not near_y_edge:
                continue
            offset = col_idx * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    if not samples:
        raise ValueError("outer bbox ring has no samples")
    return median_rgb(samples)


def median_rgb(samples: list[tuple[int, int, int]]) -> list[int]:
    return [
        sorted(sample[channel] for sample in samples)[len(samples) // 2]
        for channel in range(3)
    ]


def relative_posix(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
