from __future__ import annotations

from .geometry import clamp_int, perimeter_points, points_bbox, rect_edge_points, rgb_to_hex
from .types import BackgroundSample, PngPixels, UnsupportedPngCropError


def sample_region_background(pixels: PngPixels, bbox: list[int], tolerance: int) -> BackgroundSample:
    if len(bbox) != 4:
        raise UnsupportedPngCropError("Background sample bbox must be [x, y, width, height].")
    x, y, width, height = [round(value) for value in bbox]
    x1 = clamp_int(x, 0, pixels.width)
    y1 = clamp_int(y, 0, pixels.height)
    x2 = clamp_int(x + width, 0, pixels.width)
    y2 = clamp_int(y + height, 0, pixels.height)
    if x2 <= x1 or y2 <= y1:
        raise UnsupportedPngCropError("Background sample bbox does not intersect image bounds.")

    return sample_points_background(pixels, perimeter_points(x1, y1, x2, y2), tolerance, [x1, y1, x2 - x1, y2 - y1])


def sample_rect_edges(
    pixels: PngPixels,
    bbox: list[int],
    *,
    sides: set[str],
    inset: int,
    thickness: int,
    tolerance: int,
) -> BackgroundSample:
    if len(bbox) != 4:
        raise UnsupportedPngCropError("Edge sample bbox must be [x, y, width, height].")
    x, y, width, height = [round(value) for value in bbox]
    x1 = clamp_int(x + inset, 0, pixels.width)
    y1 = clamp_int(y + inset, 0, pixels.height)
    x2 = clamp_int(x + width - inset, 0, pixels.width)
    y2 = clamp_int(y + height - inset, 0, pixels.height)
    if x2 <= x1 or y2 <= y1:
        raise UnsupportedPngCropError("Edge sample bbox does not intersect image bounds.")

    points = rect_edge_points(x1, y1, x2, y2, sides=sides, thickness=thickness)
    return sample_points_background(pixels, points, tolerance, [x1, y1, x2 - x1, y2 - y1])


def sample_rect_edges_dominant_background(
    pixels: PngPixels,
    bbox: list[int],
    *,
    sides: set[str],
    inset: int,
    thickness: int,
    tolerance: int,
    min_fraction: float = 0.58,
) -> BackgroundSample:
    if len(bbox) != 4:
        raise UnsupportedPngCropError("Dominant edge sample bbox must be [x, y, width, height].")
    x, y, width, height = [round(value) for value in bbox]
    x1 = clamp_int(x + inset, 0, pixels.width)
    y1 = clamp_int(y + inset, 0, pixels.height)
    x2 = clamp_int(x + width - inset, 0, pixels.width)
    y2 = clamp_int(y + height - inset, 0, pixels.height)
    if x2 <= x1 or y2 <= y1:
        raise UnsupportedPngCropError("Dominant edge sample bbox does not intersect image bounds.")
    points = rect_edge_points(x1, y1, x2, y2, sides=sides, thickness=thickness)
    return sample_points_dominant_background(
        pixels,
        points,
        tolerance,
        [x1, y1, x2 - x1, y2 - y1],
        min_fraction=min_fraction,
    )


def sample_text_foreground_rgb(pixels: PngPixels, bbox: list[int], bg_rgb: tuple[int, int, int] | list[int]) -> tuple[int, int, int]:
    return sample_text_foreground_rgb_with_source(pixels, bbox, bg_rgb)[0]


def _relative_brightness(rgb: tuple[int, int, int]) -> float:
    return (rgb[0] * 0.299) + (rgb[1] * 0.587) + (rgb[2] * 0.114)


def sample_text_foreground_rgb_with_source(
    pixels: PngPixels,
    bbox: list[int],
    bg_rgb: tuple[int, int, int] | list[int],
) -> tuple[tuple[int, int, int], str]:
    if len(bbox) != 4:
        raise UnsupportedPngCropError("Text foreground sample bbox must be [x, y, width, height].")
    x, y, width, height = [round(value) for value in bbox]
    bg = tuple(clamp_int(round(channel), 0, 255) for channel in bg_rgb)
    if len(bg) != 3:
        raise UnsupportedPngCropError("Text foreground background color must be RGB.")

    x1 = clamp_int(x + 1, 0, pixels.width)
    y1 = clamp_int(y + 1, 0, pixels.height)
    x2 = clamp_int(x + width - 1, 0, pixels.width)
    y2 = clamp_int(y + height - 1, 0, pixels.height)
    if x2 <= x1 or y2 <= y1:
        return default_contrast_rgb(bg), "default_contrast"

    bg_r, bg_g, bg_b = bg
    bg_luma = _relative_brightness(bg)
    foreground_pixels: list[tuple[int, int, int]] = []
    for row_index in range(y1, y2):
        row = pixels.rows[row_index]
        for column in range(x1, x2):
            offset = column * 3
            red = row[offset]
            green = row[offset + 1]
            blue = row[offset + 2]
            if abs(red - bg_r) + abs(green - bg_g) + abs(blue - bg_b) > 64:
                foreground_pixels.append((red, green, blue))

    if not foreground_pixels:
        return default_contrast_rgb(bg), "default_contrast"

    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for red, green, blue in foreground_pixels:
        key = (red // 16, green // 16, blue // 16)
        buckets.setdefault(key, []).append((red, green, blue))

    best_bucket: list[tuple[int, int, int]] | None = None
    best_score = -1.0
    for pixel_list in buckets.values():
        count = len(pixel_list)
        avg_red = round(sum(pixel[0] for pixel in pixel_list) / count)
        avg_green = round(sum(pixel[1] for pixel in pixel_list) / count)
        avg_blue = round(sum(pixel[2] for pixel in pixel_list) / count)
        avg_rgb = (avg_red, avg_green, avg_blue)

        contrast = abs(avg_red - bg_r) + abs(avg_green - bg_g) + abs(avg_blue - bg_b)
        contrast_factor = contrast / 765.0
        foreground_luma = _relative_brightness(avg_rgb)
        if bg_luma < 128:
            polarity_factor = foreground_luma / 255.0
        else:
            polarity_factor = (255.0 - foreground_luma) / 255.0
        luma_delta_factor = abs(foreground_luma - bg_luma) / 255.0
        count_factor = min(count**0.5, 6.0)
        score = count_factor * contrast_factor * polarity_factor * luma_delta_factor

        if score > best_score:
            best_score = score
            best_bucket = pixel_list

    if best_bucket is None:
        return default_contrast_rgb(bg), "default_contrast"

    return (
        (
            round(sum(pixel[0] for pixel in best_bucket) / len(best_bucket)),
            round(sum(pixel[1] for pixel in best_bucket) / len(best_bucket)),
            round(sum(pixel[2] for pixel in best_bucket) / len(best_bucket)),
        ),
        "sampled_foreground",
    )


def default_contrast_rgb(bg_rgb: tuple[int, int, int] | list[int]) -> tuple[int, int, int]:
    bg = tuple(clamp_int(round(channel), 0, 255) for channel in bg_rgb)
    if len(bg) != 3:
        raise UnsupportedPngCropError("Default contrast background color must be RGB.")
    brightness = _relative_brightness(bg)
    return (255, 255, 255) if brightness < 128 else (17, 24, 39)


def sample_points_dominant_background(
    pixels: PngPixels,
    sample_points: list[tuple[int, int]],
    tolerance: int,
    bbox: list[int] | None = None,
    *,
    min_fraction: float = 0.58,
) -> BackgroundSample:
    valid_points = [
        (row_index, column)
        for row_index, column in sample_points
        if 0 <= row_index < pixels.height and 0 <= column < pixels.width
    ]
    if not valid_points:
        raise UnsupportedPngCropError("Dominant background sample has no valid points.")

    buckets: dict[tuple[int, int, int], list[tuple[int, int]]] = {}
    for row_index, column in valid_points:
        row = pixels.rows[row_index]
        offset = column * 3
        bucket = (row[offset] // 16, row[offset + 1] // 16, row[offset + 2] // 16)
        buckets.setdefault(bucket, []).append((row_index, column))
    dominant_points = max(buckets.values(), key=len)
    if len(dominant_points) / len(valid_points) < min_fraction:
        return sample_points_background(pixels, valid_points, tolerance, bbox)

    sample = sample_points_background(pixels, dominant_points, tolerance, bbox)
    return BackgroundSample(
        bbox=sample.bbox,
        color=sample.color,
        mean_rgb=sample.mean_rgb,
        max_channel_delta=sample.max_channel_delta,
        brightness=sample.brightness,
        confidence=round(min(1, sample.confidence * (len(dominant_points) / len(valid_points))), 3),
    )


def sample_points_background(
    pixels: PngPixels,
    sample_points: list[tuple[int, int]],
    tolerance: int,
    bbox: list[int] | None = None,
) -> BackgroundSample:
    valid_points = [
        (row_index, column)
        for row_index, column in sample_points
        if 0 <= row_index < pixels.height and 0 <= column < pixels.width
    ]
    if not valid_points:
        raise UnsupportedPngCropError("Background sample has no valid points.")

    count = len(valid_points)
    red_sum = 0
    green_sum = 0
    blue_sum = 0
    for row_index, column in valid_points:
        row = pixels.rows[row_index]
        offset = column * 3
        red_sum += row[offset]
        green_sum += row[offset + 1]
        blue_sum += row[offset + 2]

    mean_rgb = [
        round(red_sum / count),
        round(green_sum / count),
        round(blue_sum / count),
    ]
    max_delta = 0
    for row_index, column in valid_points:
        row = pixels.rows[row_index]
        offset = column * 3
        max_delta = max(
            max_delta,
            abs(row[offset] - mean_rgb[0]),
            abs(row[offset + 1] - mean_rgb[1]),
            abs(row[offset + 2] - mean_rgb[2]),
        )

    brightness = round((mean_rgb[0] * 0.299) + (mean_rgb[1] * 0.587) + (mean_rgb[2] * 0.114), 3)
    confidence = max(0, min(1, 1 - (max_delta / max(1, tolerance * 2))))
    return BackgroundSample(
        bbox=bbox or points_bbox(valid_points),
        color=rgb_to_hex(mean_rgb),
        mean_rgb=mean_rgb,
        max_channel_delta=max_delta,
        brightness=brightness,
        confidence=round(confidence, 3),
    )
