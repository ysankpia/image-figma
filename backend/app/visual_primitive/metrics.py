from __future__ import annotations

from ..png_tools import PngPixels
from .bbox import bbox_clamp
from .types import M29PrimitiveMetrics


def metrics_to_dict(metrics: M29PrimitiveMetrics) -> dict[str, object]:
    return {
        "colorCount": metrics.color_count,
        "textureScore": round(metrics.texture_score, 4),
        "edgeScore": round(metrics.edge_score, 4),
        "fillRatio": round(metrics.fill_ratio, 4),
        "aspectRatio": round(metrics.aspect_ratio, 4),
        "brightness": round(metrics.brightness, 3),
        "meanRgb": list(metrics.mean_rgb),
    }


def measure_region(pixels: PngPixels, bbox: list[int], *, fill_ratio: float | None = None) -> M29PrimitiveMetrics:
    clamped = bbox_clamp(bbox, pixels.width, pixels.height)
    if clamped is None:
        return M29PrimitiveMetrics(0, 0, 0, 0, 0, 0, (0, 0, 0))
    x, y, width, height = clamped
    step = max(1, round((width * height / 4096) ** 0.5))
    buckets: dict[tuple[int, int, int], int] = {}
    samples = 0
    red_sum = green_sum = blue_sum = 0
    texture_total = 0
    edge_hits = 0
    edge_checks = 0
    for row_index in range(y, y + height, step):
        row = pixels.rows[row_index]
        next_row = pixels.rows[min(pixels.height - 1, row_index + step)]
        for column in range(x, x + width, step):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            red_sum += rgb[0]
            green_sum += rgb[1]
            blue_sum += rgb[2]
            buckets[(rgb[0] // 16, rgb[1] // 16, rgb[2] // 16)] = buckets.get((rgb[0] // 16, rgb[1] // 16, rgb[2] // 16), 0) + 1
            samples += 1
            if column + step < pixels.width:
                neighbor_offset = (column + step) * 3
                diff = color_distance(rgb, (row[neighbor_offset], row[neighbor_offset + 1], row[neighbor_offset + 2]))
                texture_total += diff
                edge_checks += 1
                edge_hits += 1 if diff > 48 else 0
            if row_index + step < pixels.height:
                diff = color_distance(rgb, (next_row[offset], next_row[offset + 1], next_row[offset + 2]))
                texture_total += diff
                edge_checks += 1
                edge_hits += 1 if diff > 48 else 0
    samples = max(1, samples)
    mean_rgb = (round(red_sum / samples), round(green_sum / samples), round(blue_sum / samples))
    dominant = max(buckets.values()) if buckets else 0
    dominant_ratio = dominant / samples
    return M29PrimitiveMetrics(
        color_count=len(buckets),
        texture_score=round((texture_total / max(1, edge_checks)) / 255, 4),
        edge_score=round(edge_hits / max(1, edge_checks), 4),
        fill_ratio=round(fill_ratio if fill_ratio is not None else dominant_ratio, 4),
        aspect_ratio=round(width / max(1, height), 4),
        brightness=round(mean_rgb[0] * 0.299 + mean_rgb[1] * 0.587 + mean_rgb[2] * 0.114, 3),
        mean_rgb=mean_rgb,
    )


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1]) + abs(left[2] - right[2])


def near_white(rgb: tuple[int, int, int]) -> bool:
    return rgb[0] >= 245 and rgb[1] >= 245 and rgb[2] >= 245


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, value)):02X}" for value in rgb)


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))

