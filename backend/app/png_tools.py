from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class PngMetadata:
    width: int
    height: int
    bit_depth: int
    color_type: int
    compression: int
    filter_method: int
    interlace: int


@dataclass(frozen=True)
class PngRegion:
    name: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class PngPixels:
    width: int
    height: int
    rows: list[bytes]


@dataclass(frozen=True)
class PngFillOperation:
    x: int
    y: int
    width: int
    height: int
    rgb: tuple[int, int, int]


@dataclass(frozen=True)
class BackgroundSample:
    bbox: list[int]
    color: str
    mean_rgb: list[int]
    max_channel_delta: int
    brightness: float
    confidence: float


class UnsupportedPngCropError(ValueError):
    pass


def is_png(data: bytes) -> bool:
    return data.startswith(PNG_SIGNATURE)


def read_png_metadata(data: bytes) -> PngMetadata | None:
    if not is_png(data) or len(data) < 33:
        return None

    ihdr_length = struct.unpack(">I", data[8:12])[0]
    chunk_type = data[12:16]
    if ihdr_length != 13 or chunk_type != b"IHDR":
        return None

    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        return None

    return PngMetadata(
        width=width,
        height=height,
        bit_depth=data[24],
        color_type=data[25],
        compression=data[26],
        filter_method=data[27],
        interlace=data[28],
    )


def plan_regions(image: PngMetadata) -> list[PngRegion]:
    if not is_portrait_mobile_like(image):
        return [PngRegion("full_image", 0, 0, image.width, image.height)]

    header_height = min(max(round(image.height * 0.14), 120), 260)
    bottom_height = min(max(round(image.height * 0.12), 100), 220)
    content_height = image.height - header_height - bottom_height
    if content_height < 160:
        return [PngRegion("full_image", 0, 0, image.width, image.height)]

    return [
        PngRegion("header", 0, 0, image.width, header_height),
        PngRegion("content", 0, header_height, image.width, content_height),
        PngRegion("bottom", 0, header_height + content_height, image.width, bottom_height),
    ]


def is_portrait_mobile_like(image: PngMetadata) -> bool:
    return image.height >= image.width * 1.2 and image.width <= 1200


def crop_png(data: bytes, region: PngRegion) -> bytes:
    metadata = read_png_metadata(data)
    if metadata is None:
        raise UnsupportedPngCropError("PNG metadata could not be read.")
    if metadata.bit_depth != 8 or metadata.color_type not in {2, 6} or metadata.interlace != 0:
        raise UnsupportedPngCropError("PNG format is not supported by the standard-library cropper.")
    if metadata.compression != 0 or metadata.filter_method != 0:
        raise UnsupportedPngCropError("PNG compression or filter method is not supported.")
    if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0:
        raise UnsupportedPngCropError("Crop region is invalid.")
    if region.x + region.width > metadata.width or region.y + region.height > metadata.height:
        raise UnsupportedPngCropError("Crop region exceeds image bounds.")

    chunks = parse_chunks(data)
    idat_data = b"".join(chunk_data for chunk_type, chunk_data in chunks if chunk_type == b"IDAT")
    try:
        raw = zlib.decompress(idat_data)
    except zlib.error as error:
        raise UnsupportedPngCropError("PNG IDAT data could not be decompressed.") from error
    channels = 3 if metadata.color_type == 2 else 4
    bytes_per_pixel = channels
    stride = metadata.width * bytes_per_pixel
    rows = unfilter_rows(raw, metadata.width, metadata.height, bytes_per_pixel)

    cropped_rows: list[bytes] = []
    for y in range(region.y, region.y + region.height):
        row = rows[y]
        start = region.x * bytes_per_pixel
        end = start + region.width * bytes_per_pixel
        cropped_rows.append(b"\x00" + row[start:end])

    ihdr = struct.pack(">IIBBBBB", region.width, region.height, metadata.bit_depth, metadata.color_type, 0, 0, 0)
    compressed = zlib.compress(b"".join(cropped_rows))
    return b"".join(
        [
            PNG_SIGNATURE,
            png_chunk(b"IHDR", ihdr),
            png_chunk(b"IDAT", compressed),
            png_chunk(b"IEND", b""),
        ]
    )


def crop_pixels_to_png(pixels: PngPixels, region: PngRegion) -> bytes:
    if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0:
        raise UnsupportedPngCropError("Crop region is invalid.")
    if region.x + region.width > pixels.width or region.y + region.height > pixels.height:
        raise UnsupportedPngCropError("Crop region exceeds image bounds.")

    cropped_rows: list[bytes] = []
    for row_index in range(region.y, region.y + region.height):
        row = pixels.rows[row_index]
        start = region.x * 3
        end = start + region.width * 3
        cropped_rows.append(row[start:end])
    return encode_rgb_png(region.width, region.height, cropped_rows)


def crop_mask_pixels_to_rgba_png(
    pixels: PngPixels,
    mask_data: bytes,
    region: PngRegion,
) -> bytes:
    if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0:
        raise UnsupportedPngCropError("Crop region is invalid.")
    if region.x + region.width > pixels.width or region.y + region.height > pixels.height:
        raise UnsupportedPngCropError("Crop region exceeds image bounds.")

    is_full_size = len(mask_data) == pixels.width * pixels.height
    is_region_size = len(mask_data) == region.width * region.height

    if not (is_full_size or is_region_size):
        raise UnsupportedPngCropError("Mask data size does not match pixels or region size.")

    cropped_rows: list[bytes] = []
    for r in range(region.height):
        row_index = region.y + r
        pixel_row = pixels.rows[row_index]

        row_bytes = bytearray()
        for col in range(region.width):
            px_offset = (region.x + col) * 3
            r_val = pixel_row[px_offset]
            g_val = pixel_row[px_offset + 1]
            b_val = pixel_row[px_offset + 2]

            if is_full_size:
                mask_index = row_index * pixels.width + (region.x + col)
            else:
                mask_index = r * region.width + col

            a_val = mask_data[mask_index]
            row_bytes.extend([r_val, g_val, b_val, a_val])
        cropped_rows.append(bytes(row_bytes))

    return encode_rgba_png(region.width, region.height, cropped_rows)


def encode_rgb_png(width: int, height: int, rows: list[bytes]) -> bytes:
    if width <= 0 or height <= 0:
        raise UnsupportedPngCropError("PNG dimensions must be positive.")
    if len(rows) != height:
        raise UnsupportedPngCropError("PNG row count does not match height.")
    stride = width * 3
    for row in rows:
        if len(row) != stride:
            raise UnsupportedPngCropError("PNG row length does not match width.")

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    compressed = zlib.compress(b"".join(b"\x00" + row for row in rows))
    return b"".join(
        [
            PNG_SIGNATURE,
            png_chunk(b"IHDR", ihdr),
            png_chunk(b"IDAT", compressed),
            png_chunk(b"IEND", b""),
        ]
    )


def encode_rgba_png(width: int, height: int, rows: list[bytes]) -> bytes:
    if width <= 0 or height <= 0:
        raise UnsupportedPngCropError("PNG dimensions must be positive.")
    if len(rows) != height:
        raise UnsupportedPngCropError("PNG row count does not match height.")
    stride = width * 4
    for row in rows:
        if len(row) != stride:
            raise UnsupportedPngCropError("PNG row length does not match width.")

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    compressed = zlib.compress(b"".join(b"\x00" + row for row in rows))
    return b"".join(
        [
            PNG_SIGNATURE,
            png_chunk(b"IHDR", ihdr),
            png_chunk(b"IDAT", compressed),
            png_chunk(b"IEND", b""),
        ]
    )


def crop_and_fill_png(data: bytes, region: PngRegion, fill_operations: list[PngFillOperation]) -> bytes:
    pixels = decode_png_pixels(data)
    if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0:
        raise UnsupportedPngCropError("Crop region is invalid.")
    if region.x + region.width > pixels.width or region.y + region.height > pixels.height:
        raise UnsupportedPngCropError("Crop region exceeds image bounds.")

    cropped_rows: list[bytearray] = []
    for row_index in range(region.y, region.y + region.height):
        row = pixels.rows[row_index]
        start = region.x * 3
        end = start + region.width * 3
        cropped_rows.append(bytearray(row[start:end]))

    for operation in fill_operations:
        if operation.x < 0 or operation.y < 0 or operation.width <= 0 or operation.height <= 0:
            raise UnsupportedPngCropError("Fill region is invalid.")
        if operation.x + operation.width > region.width or operation.y + operation.height > region.height:
            raise UnsupportedPngCropError("Fill region exceeds crop bounds.")
        if any(channel < 0 or channel > 255 for channel in operation.rgb):
            raise UnsupportedPngCropError("Fill color channel is out of range.")
        fill_bytes = bytes(operation.rgb)
        for row_index in range(operation.y, operation.y + operation.height):
            row = cropped_rows[row_index]
            for column in range(operation.x, operation.x + operation.width):
                offset = column * 3
                row[offset : offset + 3] = fill_bytes

    return encode_rgb_png(region.width, region.height, [bytes(row) for row in cropped_rows])


def decode_png_pixels(data: bytes) -> PngPixels:
    metadata = read_png_metadata(data)
    if metadata is None:
        raise UnsupportedPngCropError("PNG metadata could not be read.")
    if metadata.bit_depth != 8 or metadata.color_type not in {2, 6} or metadata.interlace != 0:
        raise UnsupportedPngCropError("PNG format is not supported by the standard-library pixel decoder.")
    if metadata.compression != 0 or metadata.filter_method != 0:
        raise UnsupportedPngCropError("PNG compression or filter method is not supported.")

    chunks = parse_chunks(data)
    idat_data = b"".join(chunk_data for chunk_type, chunk_data in chunks if chunk_type == b"IDAT")
    try:
        raw = zlib.decompress(idat_data)
    except zlib.error as error:
        raise UnsupportedPngCropError("PNG IDAT data could not be decompressed.") from error

    bytes_per_pixel = 3 if metadata.color_type == 2 else 4
    rows = unfilter_rows(raw, metadata.width, metadata.height, bytes_per_pixel)
    if metadata.color_type == 6:
        rows = [rgba_row_to_rgb(row) for row in rows]
    return PngPixels(width=metadata.width, height=metadata.height, rows=rows)


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


def find_leading_symbol_gap(
    pixels: PngPixels,
    bbox: list[int],
    bg_rgb: tuple[int, int, int] | list[int],
) -> dict[str, Any] | None:
    if len(bbox) != 4:
        return None
    if len(bg_rgb) != 3:
        return None

    x, y, width, height = [round(value) for value in bbox]
    if width <= 0 or height <= 0:
        return None

    max_search_width = round(min(width * 0.28, height * 1.4))
    if max_search_width < 12 or width <= max_search_width:
        return None

    x1 = clamp_int(x, 0, pixels.width)
    y1 = clamp_int(y + 1, 0, pixels.height)
    x2 = clamp_int(x + max_search_width, 0, pixels.width)
    y2 = clamp_int(y + height - 1, 0, pixels.height)
    if x2 <= x1 or y2 <= y1:
        return None

    bg = tuple(clamp_int(round(channel), 0, 255) for channel in bg_rgb)
    bg_r, bg_g, bg_b = bg
    column_height = y2 - y1
    ink_densities: list[float] = []
    for column in range(x1, x2):
        ink_count = 0
        for row_index in range(y1, y2):
            row = pixels.rows[row_index]
            offset = column * 3
            red = row[offset]
            green = row[offset + 1]
            blue = row[offset + 2]
            if abs(red - bg_r) + abs(green - bg_g) + abs(blue - bg_b) > 64:
                ink_count += 1
        ink_densities.append(ink_count / column_height)

    def count_ink_columns(start_x: int, end_x: int, min_density: float) -> int:
        probe_x1 = clamp_int(start_x, 0, pixels.width)
        probe_x2 = clamp_int(end_x, 0, pixels.width)
        if probe_x2 <= probe_x1:
            return 0
        count = 0
        for column in range(probe_x1, probe_x2):
            ink_count = 0
            for row_index in range(y1, y2):
                row = pixels.rows[row_index]
                offset = column * 3
                red = row[offset]
                green = row[offset + 1]
                blue = row[offset + 2]
                if abs(red - bg_r) + abs(green - bg_g) + abs(blue - bg_b) > 64:
                    ink_count += 1
            if ink_count / column_height >= min_density:
                count += 1
        return count

    low_ink_threshold = 0.10
    min_gap_width = max(2, round(height * 0.08))
    min_ink_density = 0.12
    min_ink_columns = 2
    candidate_count = len(ink_densities)
    best: dict[str, Any] | None = None

    run_start: int | None = None
    for index, density in enumerate([*ink_densities, 1.0]):
        if index < candidate_count and density <= low_ink_threshold:
            if run_start is None:
                run_start = index
            continue

        if run_start is not None:
            run_end = index
            gap_width = run_end - run_start
            if gap_width >= min_gap_width:
                left_columns = ink_densities[:run_start]
                left_ink_columns = sum(1 for item in left_columns if item >= min_ink_density)
                gap_end_x = x1 + run_end
                right_probe_end = min(x + width, gap_end_x + max_search_width)
                right_ink_columns = count_ink_columns(gap_end_x, right_probe_end, min_ink_density)
                if left_ink_columns >= min_ink_columns and right_ink_columns >= min_ink_columns:
                    gap_density = sum(ink_densities[run_start:run_end]) / gap_width
                    score = gap_width - gap_density
                    if best is None or score > best["score"]:
                        best = {
                            "start": run_start,
                            "width": gap_width,
                            "density": gap_density,
                            "leftInkColumnCount": left_ink_columns,
                            "rightInkColumnCount": right_ink_columns,
                            "score": score,
                        }
            run_start = None

    if best is None:
        return None

    gap_x = x1 + int(best["start"])
    gap_width = int(best["width"])
    cleaned_x = gap_x + gap_width
    cleaned_width = x + width - cleaned_x
    protected_width = gap_x - x
    if protected_width <= 0 or cleaned_width <= 0:
        return None

    return {
        "protectedSymbolBBox": [x, y, protected_width, height],
        "gapBBox": [gap_x, y, gap_width, height],
        "cleanedBBox": [cleaned_x, y, cleaned_width, height],
        "metrics": {
            "maxSearchWidth": max_search_width,
            "minGapWidth": min_gap_width,
            "gapInkDensity": round(float(best["density"]), 4),
            "leftInkColumnCount": int(best["leftInkColumnCount"]),
            "rightInkColumnCount": int(best["rightInkColumnCount"]),
        },
    }


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


def rect_edge_points(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    sides: set[str],
    thickness: int,
) -> list[tuple[int, int]]:
    edge_thickness = max(1, min(thickness, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2)))
    points: list[tuple[int, int]] = []
    normalized_sides = {side.lower() for side in sides}
    for row_index in range(y1, y2):
        for column in range(x1, x2):
            near_top = row_index < y1 + edge_thickness
            near_bottom = row_index >= y2 - edge_thickness
            near_left = column < x1 + edge_thickness
            near_right = column >= x2 - edge_thickness
            on_top = near_top and ("left" in normalized_sides or not near_left) and ("right" in normalized_sides or not near_right)
            on_bottom = near_bottom and ("left" in normalized_sides or not near_left) and ("right" in normalized_sides or not near_right)
            on_left = near_left and ("top" in normalized_sides or not near_top) and ("bottom" in normalized_sides or not near_bottom)
            on_right = near_right and ("top" in normalized_sides or not near_top) and ("bottom" in normalized_sides or not near_bottom)
            if (
                ("top" in normalized_sides and on_top)
                or ("bottom" in normalized_sides and on_bottom)
                or ("left" in normalized_sides and on_left)
                or ("right" in normalized_sides and on_right)
            ):
                points.append((row_index, column))
    return points


def rgba_row_to_rgb(row: bytes) -> bytes:
    rgb = bytearray()
    for offset in range(0, len(row), 4):
        red = row[offset]
        green = row[offset + 1]
        blue = row[offset + 2]
        alpha = row[offset + 3] / 255
        rgb.extend(
            [
                round(red * alpha + 255 * (1 - alpha)),
                round(green * alpha + 255 * (1 - alpha)),
                round(blue * alpha + 255 * (1 - alpha)),
            ]
        )
    return bytes(rgb)


def perimeter_points(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    border = min(2, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2))
    for row_index in range(y1, y2):
        for column in range(x1, x2):
            if row_index < y1 + border or row_index >= y2 - border or column < x1 + border or column >= x2 - border:
                points.append((row_index, column))
    return points


def points_bbox(points: list[tuple[int, int]]) -> list[int]:
    min_y = min(row_index for row_index, _column in points)
    max_y = max(row_index for row_index, _column in points)
    min_x = min(column for _row_index, column in points)
    max_x = max(column for _row_index, column in points)
    return [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]


def rgb_to_hex(rgb: list[int]) -> str:
    return "#" + "".join(f"{clamp_int(value, 0, 255):02X}" for value in rgb)


def parse_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not is_png(data):
        raise UnsupportedPngCropError("Invalid PNG signature.")

    chunks: list[tuple[bytes, bytes]] = []
    offset = len(PNG_SIGNATURE)
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        crc_end = chunk_data_end + 4
        if crc_end > len(data):
            raise UnsupportedPngCropError("PNG chunk is truncated.")
        chunks.append((chunk_type, data[chunk_data_start:chunk_data_end]))
        offset = crc_end
        if chunk_type == b"IEND":
            break
    return chunks


def unfilter_rows(raw: bytes, width: int, height: int, bytes_per_pixel: int) -> list[bytes]:
    stride = width * bytes_per_pixel
    expected = (stride + 1) * height
    if len(raw) != expected:
        raise UnsupportedPngCropError("PNG decompressed data has unexpected length.")

    rows: list[bytes] = []
    offset = 0
    previous = bytes(stride)
    for _y in range(height):
        filter_type = raw[offset]
        scanline = raw[offset + 1 : offset + 1 + stride]
        offset += stride + 1
        row = unfilter_scanline(filter_type, scanline, previous, bytes_per_pixel)
        rows.append(row)
        previous = row
    return rows


def unfilter_scanline(filter_type: int, scanline: bytes, previous: bytes, bytes_per_pixel: int) -> bytes:
    out = bytearray(len(scanline))
    for index, value in enumerate(scanline):
        left = out[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index]
        upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            predictor = paeth(left, up, upper_left)
        else:
            raise UnsupportedPngCropError(f"Unsupported PNG filter type: {filter_type}.")
        out[index] = (value + predictor) & 0xFF
    return bytes(out)


def paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum & 0xFFFFFFFF)
