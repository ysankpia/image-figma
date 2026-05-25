from __future__ import annotations

from collections import Counter, deque
from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, PngRegion, UnsupportedPngCropError, crop_mask_pixels_to_rgba_png
from ..region_relation_kernel import x2, y2

MIN_DOMINANT_BACKGROUND_COVERAGE = 0.36
MAX_BACKGROUND_CLUSTER_VARIANCE = 18.0
MAX_EDGE_VARIANCE_FALLBACK = 38.0


def analyze_transparent_asset_candidate(
    *,
    pixels: PngPixels,
    bbox: list[int],
    output_path: str | None = None,
    write_asset: bool = False,
    expand_context: bool = False,
    container_bbox: list[int] | None = None,
) -> dict[str, Any]:
    analysis_bbox = expanded_analysis_bbox(bbox, pixels, container_bbox) if expand_context else bbox
    edge_pixels = sample_edge_pixels(pixels, analysis_bbox)
    if not edge_pixels:
        return reject("empty_edge_samples")
    background_sample = dominant_background_sample(edge_pixels) if expand_context else edge_background_sample(edge_pixels)
    background = background_sample["rgb"]
    bg_variance = background_sample["variance"]
    if not background_sample["stable"]:
        return reject("unstable_background", background, bg_variance, background_sample=background_sample)
    distances = pixel_distances(pixels, analysis_bbox, background)
    foreground = [value for value in distances if value >= 72]
    foreground_ratio = len(foreground) / max(1, len(distances))
    if foreground_ratio < 0.04:
        return reject("weak_foreground_contrast", background, bg_variance, foreground_ratio=foreground_ratio, background_sample=background_sample)
    if foreground_ratio > 0.88:
        return reject("foreground_fills_crop", background, bg_variance, foreground_ratio=foreground_ratio, background_sample=background_sample)
    mask_data, alpha_coverage = build_alpha_mask(pixels, analysis_bbox, background)
    edge_alpha = edge_alpha_metrics(mask_data, analysis_bbox[2], analysis_bbox[3])
    if edge_alpha["edgeAlphaCoverageGt32"] > 0.12 or edge_alpha["edgeAlphaMean"] > 28:
        return reject(
            "edge_alpha_risk",
            background,
            bg_variance,
            foreground_ratio=foreground_ratio,
            alpha_coverage=alpha_coverage,
            edge_alpha=edge_alpha,
            background_sample=background_sample,
            analysis_bbox=analysis_bbox,
        )
    largest_ratio = largest_component_ratio(mask_data, analysis_bbox[2], analysis_bbox[3])
    if largest_ratio < 0.35:
        return reject(
            "fragmented_foreground_mask",
            background,
            bg_variance,
            foreground_ratio=foreground_ratio,
            alpha_coverage=alpha_coverage,
            largest_component_ratio=largest_ratio,
            edge_alpha=edge_alpha,
            background_sample=background_sample,
            analysis_bbox=analysis_bbox,
        )
    asset_path = None
    if write_asset and output_path:
        region = PngRegion("transparent_asset", analysis_bbox[0], analysis_bbox[1], analysis_bbox[2], analysis_bbox[3])
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
                background_sample=background_sample,
                analysis_bbox=analysis_bbox,
            )
    return {
        "decision": "allow",
        "analysisBbox": analysis_bbox,
        "sourceBbox": bbox,
        "backgroundRgb": list(background),
        "bgVariance": round(bg_variance, 3),
        "backgroundCoverage": background_sample["coverage"],
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
    background_sample: dict[str, Any] | None = None,
    analysis_bbox: list[int] | None = None,
) -> dict[str, Any]:
    edge_alpha = edge_alpha or {"edgeAlphaMean": 0.0, "edgeAlphaCoverageGt32": 0.0}
    return {
        "decision": "reject",
        "analysisBbox": analysis_bbox,
        "sourceBbox": None,
        "backgroundRgb": list(background or (0, 0, 0)),
        "bgVariance": round(bg_variance, 3),
        "backgroundCoverage": round(float((background_sample or {}).get("coverage") or 0.0), 4),
        "foregroundAreaRatio": round(foreground_ratio, 4),
        "alphaCoverage": round(alpha_coverage, 4),
        "largestComponentRatio": round(largest_component_ratio, 4),
        "edgeAlphaMean": edge_alpha["edgeAlphaMean"],
        "edgeAlphaCoverageGt32": edge_alpha["edgeAlphaCoverageGt32"],
        "assetPath": None,
        "reasons": [reason],
        "risks": ["transparent_asset_rejected"],
    }


def expanded_analysis_bbox(bbox: list[int], pixels: PngPixels, container_bbox: list[int] | None = None) -> list[int]:
    x, y, width, height = bbox
    container = container_bbox or [0, 0, pixels.width, pixels.height]
    short_edge = max(1, min(width, height))
    padding = max(4, min(12, round(short_edge * 0.45)))
    left = max(0, container[0], x - padding)
    top = max(0, container[1], y - padding)
    right = min(pixels.width, x2(container), x + width + padding)
    bottom = min(pixels.height, y2(container), y + height + padding)
    if right <= left or bottom <= top:
        return bbox
    return [left, top, right - left, bottom - top]


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


def edge_background_sample(samples: list[tuple[int, int, int]]) -> dict[str, Any]:
    rgb = dominant_rgb(samples)
    variance = channel_variance(samples, rgb)
    return {
        "rgb": rgb,
        "variance": round(variance, 3),
        "coverage": 1.0,
        "clusterVariance": round(variance, 3),
        "edgeVariance": round(variance, 3),
        "stable": variance <= MAX_EDGE_VARIANCE_FALLBACK,
    }


def dominant_background_sample(samples: list[tuple[int, int, int]]) -> dict[str, Any]:
    buckets: Counter[tuple[int, int, int]] = Counter((r // 16, g // 16, b // 16) for r, g, b in samples)
    bucket, count = buckets.most_common(1)[0]
    members = [sample for sample in samples if (sample[0] // 16, sample[1] // 16, sample[2] // 16) == bucket]
    rgb = tuple(round(sum(sample[channel] for sample in members) / len(members)) for channel in range(3))
    cluster_variance = channel_variance(members, rgb)
    all_edge_variance = channel_variance(samples, rgb)
    coverage = count / max(1, len(samples))
    stable = (coverage >= MIN_DOMINANT_BACKGROUND_COVERAGE and cluster_variance <= MAX_BACKGROUND_CLUSTER_VARIANCE) or (
        all_edge_variance <= MAX_EDGE_VARIANCE_FALLBACK
    )
    return {
        "rgb": rgb,
        "variance": round(cluster_variance if coverage >= MIN_DOMINANT_BACKGROUND_COVERAGE else all_edge_variance, 3),
        "coverage": round(coverage, 4),
        "clusterVariance": round(cluster_variance, 3),
        "edgeVariance": round(all_edge_variance, 3),
        "stable": stable,
    }


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
