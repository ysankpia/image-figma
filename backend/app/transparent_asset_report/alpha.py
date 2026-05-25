from __future__ import annotations

from collections import Counter, deque
from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, PngRegion, UnsupportedPngCropError, crop_mask_pixels_to_rgba_png


def analyze_transparent_asset_candidate(
    *,
    pixels: PngPixels,
    bbox: list[int],
    output_path: str | None = None,
    write_asset: bool = False,
) -> dict[str, Any]:
    edge_pixels = sample_edge_pixels(pixels, bbox)
    if not edge_pixels:
        return reject("empty_edge_samples")
    background = dominant_rgb(edge_pixels)
    bg_variance = channel_variance(edge_pixels, background)
    if bg_variance > 38:
        return reject("unstable_background", background, bg_variance)
    distances = pixel_distances(pixels, bbox, background)
    foreground = [value for value in distances if value >= 72]
    foreground_ratio = len(foreground) / max(1, len(distances))
    if foreground_ratio < 0.04:
        return reject("weak_foreground_contrast", background, bg_variance, foreground_ratio=foreground_ratio)
    if foreground_ratio > 0.88:
        return reject("foreground_fills_crop", background, bg_variance, foreground_ratio=foreground_ratio)
    mask_data, alpha_coverage = build_alpha_mask(pixels, bbox, background)
    edge_alpha = edge_alpha_metrics(mask_data, bbox[2], bbox[3])
    if edge_alpha["edgeAlphaCoverageGt32"] > 0.12 or edge_alpha["edgeAlphaMean"] > 28:
        return reject(
            "edge_alpha_risk",
            background,
            bg_variance,
            foreground_ratio=foreground_ratio,
            alpha_coverage=alpha_coverage,
            edge_alpha=edge_alpha,
        )
    largest_ratio = largest_component_ratio(mask_data, bbox[2], bbox[3])
    if largest_ratio < 0.35:
        return reject(
            "fragmented_foreground_mask",
            background,
            bg_variance,
            foreground_ratio=foreground_ratio,
            alpha_coverage=alpha_coverage,
            largest_component_ratio=largest_ratio,
            edge_alpha=edge_alpha,
        )
    asset_path = None
    if write_asset and output_path:
        region = PngRegion("transparent_asset", bbox[0], bbox[1], bbox[2], bbox[3])
        asset_path = output_path
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(crop_mask_pixels_to_rgba_png(pixels, mask_data, region))
        except UnsupportedPngCropError:
            return reject(
                "asset_crop_failed",
                background,
                bg_variance,
                foreground_ratio=foreground_ratio,
                alpha_coverage=alpha_coverage,
                largest_component_ratio=largest_ratio,
                edge_alpha=edge_alpha,
            )
    return {
        "decision": "allow",
        "backgroundRgb": list(background),
        "bgVariance": round(bg_variance, 3),
        "foregroundAreaRatio": round(foreground_ratio, 4),
        "alphaCoverage": round(alpha_coverage, 4),
        "largestComponentRatio": round(largest_ratio, 4),
        "edgeAlphaMean": edge_alpha["edgeAlphaMean"],
        "edgeAlphaCoverageGt32": edge_alpha["edgeAlphaCoverageGt32"],
        "assetPath": asset_path,
        "reasons": ["stable_background", "foreground_contrast", "connected_foreground"],
        "risks": [],
    }


def reject(
    reason: str,
    background: tuple[int, int, int] | None = None,
    bg_variance: float = 0.0,
    *,
    foreground_ratio: float = 0.0,
    alpha_coverage: float = 0.0,
    largest_component_ratio: float = 0.0,
    edge_alpha: dict[str, Any] | None = None,
) -> dict[str, Any]:
    edge_alpha = edge_alpha or {"edgeAlphaMean": 0.0, "edgeAlphaCoverageGt32": 0.0}
    return {
        "decision": "reject",
        "backgroundRgb": list(background or (0, 0, 0)),
        "bgVariance": round(bg_variance, 3),
        "foregroundAreaRatio": round(foreground_ratio, 4),
        "alphaCoverage": round(alpha_coverage, 4),
        "largestComponentRatio": round(largest_component_ratio, 4),
        "edgeAlphaMean": edge_alpha["edgeAlphaMean"],
        "edgeAlphaCoverageGt32": edge_alpha["edgeAlphaCoverageGt32"],
        "assetPath": None,
        "reasons": [reason],
        "risks": ["transparent_asset_rejected"],
    }


def sample_edge_pixels(pixels: PngPixels, bbox: list[int]) -> list[tuple[int, int, int]]:
    x, y, width, height = bbox
    samples: list[tuple[int, int, int]] = []
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for col in range(x, x + width):
            if row_index not in {y, y + height - 1} and col not in {x, x + width - 1}:
                continue
            offset = col * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    return samples


def dominant_rgb(samples: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    buckets: Counter[tuple[int, int, int]] = Counter((r // 16, g // 16, b // 16) for r, g, b in samples)
    bucket = buckets.most_common(1)[0][0]
    members = [sample for sample in samples if (sample[0] // 16, sample[1] // 16, sample[2] // 16) == bucket]
    return tuple(round(sum(sample[channel] for sample in members) / len(members)) for channel in range(3))


def channel_variance(samples: list[tuple[int, int, int]], background: tuple[int, int, int]) -> float:
    distances = [color_distance(sample, background) for sample in samples]
    return sum(distances) / max(1, len(distances))


def pixel_distances(pixels: PngPixels, bbox: list[int], background: tuple[int, int, int]) -> list[int]:
    x, y, width, height = bbox
    distances: list[int] = []
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for col in range(x, x + width):
            offset = col * 3
            distances.append(color_distance((row[offset], row[offset + 1], row[offset + 2]), background))
    return distances


def build_alpha_mask(pixels: PngPixels, bbox: list[int], background: tuple[int, int, int]) -> tuple[bytes, float]:
    x, y, width, height = bbox
    mask = bytearray(width * height)
    alpha_sum = 0
    for row in range(height):
        pixel_row = pixels.rows[y + row]
        for col in range(width):
            offset = (x + col) * 3
            distance = color_distance((pixel_row[offset], pixel_row[offset + 1], pixel_row[offset + 2]), background)
            if distance <= 24:
                alpha = 0
            elif distance >= 72:
                alpha = 255
            else:
                alpha = round(255 * (distance - 24) / 48)
            mask[row * width + col] = alpha
            alpha_sum += alpha
    return bytes(mask), alpha_sum / max(1, width * height * 255)


def edge_alpha_metrics(mask_data: bytes, width: int, height: int) -> dict[str, float]:
    values: list[int] = []
    for row in range(height):
        for col in range(width):
            if row not in {0, height - 1} and col not in {0, width - 1}:
                continue
            values.append(mask_data[row * width + col])
    if not values:
        return {"edgeAlphaMean": 0.0, "edgeAlphaCoverageGt32": 0.0}
    return {
        "edgeAlphaMean": round(sum(values) / len(values), 4),
        "edgeAlphaCoverageGt32": round(sum(1 for value in values if value > 32) / len(values), 4),
    }


def largest_component_ratio(mask_data: bytes, width: int, height: int) -> float:
    seen = bytearray(width * height)
    largest = 0
    total = sum(1 for value in mask_data if value >= 128)
    if total == 0:
        return 0.0
    for index, value in enumerate(mask_data):
        if value < 128 or seen[index]:
            continue
        size = 0
        queue: deque[int] = deque([index])
        seen[index] = 1
        while queue:
            current = queue.popleft()
            size += 1
            row = current // width
            col = current % width
            for nr, nc in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if nr < 0 or nr >= height or nc < 0 or nc >= width:
                    continue
                nxt = nr * width + nc
                if seen[nxt] or mask_data[nxt] < 128:
                    continue
                seen[nxt] = 1
                queue.append(nxt)
        largest = max(largest, size)
    return largest / max(1, total)


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1]) + abs(left[2] - right[2])
