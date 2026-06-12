from __future__ import annotations

from ..png_tools import PngPixels, UnsupportedPngCropError, encode_rgb_png
from .bbox import bbox_clamp, bbox_x2, bbox_y2, pad_bbox
from .metrics import color_distance, measure_region


def crop_pixels(pixels: PngPixels, bbox: list[int]) -> bytes:
    clamped = bbox_clamp(bbox, pixels.width, pixels.height)
    if clamped is None:
        raise UnsupportedPngCropError("M29 crop bbox is invalid.")
    x, y, width, height = clamped
    rows = [pixels.rows[row_index][x * 3 : (x + width) * 3] for row_index in range(y, y + height)]
    return encode_rgb_png(width, height, rows)


def sample_region_mean_rgb(pixels: PngPixels, bbox: list[int]) -> tuple[int, int, int]:
    clamped = bbox_clamp(bbox, pixels.width, pixels.height)
    if clamped is None:
        return measure_region(pixels, [0, 0, pixels.width, pixels.height]).mean_rgb
    x, y, width, height = clamped
    red = green = blue = count = 0
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for column in range(x, x + width):
            offset = column * 3
            red += row[offset]
            green += row[offset + 1]
            blue += row[offset + 2]
            count += 1
    if count == 0:
        return measure_region(pixels, clamped).mean_rgb
    return (round(red / count), round(green / count), round(blue / count))


def sample_outer_ring_mean_rgb(pixels: PngPixels, bbox: list[int], *, padding: int, thickness: int) -> tuple[int, int, int]:
    outer = bbox_clamp(pad_bbox(bbox, padding), pixels.width, pixels.height)
    if outer is None:
        return measure_region(pixels, bbox).mean_rgb
    x, y, width, height = outer
    inner_x1, inner_y1 = bbox[0], bbox[1]
    inner_x2, inner_y2 = bbox_x2(bbox), bbox_y2(bbox)
    red = green = blue = count = 0
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for column in range(x, x + width):
            in_inner = inner_x1 <= column < inner_x2 and inner_y1 <= row_index < inner_y2
            near_outer_edge = (
                column < x + thickness
                or column >= x + width - thickness
                or row_index < y + thickness
                or row_index >= y + height - thickness
            )
            if in_inner or not near_outer_edge:
                continue
            offset = column * 3
            red += row[offset]
            green += row[offset + 1]
            blue += row[offset + 2]
            count += 1
    if count == 0:
        return measure_region(pixels, bbox).mean_rgb
    return (round(red / count), round(green / count), round(blue / count))


def draw_rect(rows: list[bytearray], image_width: int, image_height: int, bbox: list[int], color: tuple[int, int, int], thickness: int) -> None:
    clamped = bbox_clamp(bbox, image_width, image_height)
    if clamped is None:
        return
    x, y, width, height = clamped
    color_bytes = bytes(color)
    for row_index in range(y, y + height):
        if row_index < y + thickness or row_index >= y + height - thickness:
            for column in range(x, x + width):
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes
        else:
            for column in list(range(x, min(x + thickness, x + width))) + list(range(max(x, x + width - thickness), x + width)):
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes

