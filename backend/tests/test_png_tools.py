from __future__ import annotations

import struct
import zlib

import pytest

from app.png_tools import (
    PngFillOperation,
    PngMetadata,
    PngRegion,
    UnsupportedPngCropError,
    crop_and_fill_png,
    crop_pixels_to_png,
    crop_png,
    decode_png_pixels,
    encode_rgb_png,
    plan_regions,
    read_png_metadata,
    sample_rect_edges,
    sample_region_background,
    sample_text_foreground_rgb,
    find_leading_symbol_gap,
    upscale_pixels_nearest,
)
from conftest import make_png, png_chunk


def test_read_png_metadata_includes_crop_relevant_fields() -> None:
    png = make_png(941, 1672)

    metadata = read_png_metadata(png)

    assert metadata == PngMetadata(
        width=941,
        height=1672,
        bit_depth=8,
        color_type=2,
        compression=0,
        filter_method=0,
        interlace=0,
    )


def test_plan_regions_splits_portrait_mobile_image_into_three_contiguous_regions() -> None:
    metadata = PngMetadata(
        width=941,
        height=1672,
        bit_depth=8,
        color_type=2,
        compression=0,
        filter_method=0,
        interlace=0,
    )

    regions = plan_regions(metadata)

    assert regions == [
        PngRegion("header", 0, 0, 941, 234),
        PngRegion("content", 0, 234, 941, 1237),
        PngRegion("bottom", 0, 1471, 941, 201),
    ]


def test_crop_png_writes_valid_png_with_region_dimensions() -> None:
    png = make_png(20, 30)

    cropped = crop_png(png, PngRegion("header", 0, 0, 20, 7))

    metadata = read_png_metadata(cropped)
    assert metadata is not None
    assert metadata.width == 20
    assert metadata.height == 7
    assert metadata.bit_depth == 8
    assert metadata.color_type == 2
    assert metadata.interlace == 0


def test_crop_pixels_to_png_preserves_decoded_pixel_region() -> None:
    rows = []
    for row_index in range(6):
        row = bytearray()
        for column in range(8):
            row.extend((column * 10, row_index * 20, 100 + column + row_index))
        rows.append(bytes(row))
    source = make_png_from_rows(8, 6, rows)
    pixels = decode_png_pixels(source)

    cropped = crop_pixels_to_png(pixels, PngRegion("unit", 2, 1, 4, 3))

    metadata = read_png_metadata(cropped)
    cropped_pixels = decode_png_pixels(cropped)
    assert metadata is not None
    assert metadata.width == 4
    assert metadata.height == 3
    assert cropped_pixels.rows == [row[2 * 3 : 6 * 3] for row in rows[1:4]]


def test_crop_pixels_to_png_rejects_invalid_regions() -> None:
    pixels = decode_png_pixels(make_rgb_png(8, 6, (247, 248, 250)))

    invalid_regions = [
        PngRegion("negative", -1, 0, 4, 4),
        PngRegion("empty", 0, 0, 0, 4),
        PngRegion("overflow", 6, 0, 3, 4),
        PngRegion("overflow_y", 0, 5, 4, 2),
    ]
    for region in invalid_regions:
        with pytest.raises(UnsupportedPngCropError):
            crop_pixels_to_png(pixels, region)


def test_upscale_pixels_nearest_triples_dimensions_and_preserves_colors() -> None:
    rows = [
        bytes((10, 20, 30)) + bytes((40, 50, 60)),
        bytes((70, 80, 90)) + bytes((100, 110, 120)),
    ]
    pixels = decode_png_pixels(make_png_from_rows(2, 2, rows))

    scaled = upscale_pixels_nearest(pixels, 3)

    assert scaled.width == 6
    assert scaled.height == 6
    assert scaled.rows[:3] == [bytes((10, 20, 30)) * 3 + bytes((40, 50, 60)) * 3] * 3
    assert scaled.rows[3:] == [bytes((70, 80, 90)) * 3 + bytes((100, 110, 120)) * 3] * 3


def test_upscale_pixels_nearest_rejects_invalid_factor() -> None:
    pixels = decode_png_pixels(make_rgb_png(2, 2, (10, 20, 30)))

    with pytest.raises(UnsupportedPngCropError):
        upscale_pixels_nearest(pixels, 0)


def test_sample_text_foreground_rgb_isolates_high_contrast_stroke_color() -> None:
    rows = [bytearray(bytes((22, 119, 255)) * 8) for _ in range(8)]
    for row_index in range(3, 5):
        for column in range(3, 5):
            rows[row_index][column * 3 : column * 3 + 3] = b"\xff\xff\xff"
    pixels = decode_png_pixels(make_png_from_rows(8, 8, [bytes(row) for row in rows]))

    foreground = sample_text_foreground_rgb(pixels, [2, 2, 4, 4], [22, 119, 255])

    assert foreground == (255, 255, 255)


def test_sample_text_foreground_rgb_prefers_high_contrast_over_high_count() -> None:
    rows = [bytearray(bytes((76, 60, 35)) * 12) for _ in range(12)]
    for row_index in range(2, 10):
        for column in range(2, 10):
            rows[row_index][column * 3 : column * 3 + 3] = bytes((105, 83, 52))
    rows[5][5 * 3 : 7 * 3] = b"\xff\xff\xff\xff\xff\xff"
    pixels = decode_png_pixels(make_png_from_rows(12, 12, [bytes(row) for row in rows]))

    foreground = sample_text_foreground_rgb(pixels, [1, 1, 10, 10], [76, 60, 35])

    assert foreground == (255, 255, 255)


def test_sample_text_foreground_rgb_preserves_dark_text_on_light_background() -> None:
    rows = [bytearray(bytes((248, 248, 246)) * 8) for _ in range(8)]
    for row_index in range(3, 5):
        for column in range(3, 5):
            rows[row_index][column * 3 : column * 3 + 3] = bytes((24, 31, 42))
    pixels = decode_png_pixels(make_png_from_rows(8, 8, [bytes(row) for row in rows]))

    foreground = sample_text_foreground_rgb(pixels, [2, 2, 4, 4], [248, 248, 246])

    assert foreground == (24, 31, 42)


def test_sample_text_foreground_rgb_preserves_chromatic_text() -> None:
    rows = [bytearray(bytes((255, 238, 238)) * 8) for _ in range(8)]
    for row_index in range(3, 5):
        for column in range(3, 5):
            rows[row_index][column * 3 : column * 3 + 3] = bytes((226, 24, 56))
    pixels = decode_png_pixels(make_png_from_rows(8, 8, [bytes(row) for row in rows]))

    foreground = sample_text_foreground_rgb(pixels, [2, 2, 4, 4], [255, 238, 238])

    assert foreground == (226, 24, 56)


def test_sample_text_foreground_rgb_returns_default_contrast_when_no_foreground_pixels() -> None:
    pixels = decode_png_pixels(make_rgb_png(8, 8, (18, 28, 46)))

    foreground = sample_text_foreground_rgb(pixels, [2, 2, 4, 4], [18, 28, 46])

    assert foreground == (255, 255, 255)


def test_sample_text_foreground_rgb_clamps_bbox_to_bounds() -> None:
    rows = [bytearray(bytes((255, 255, 255)) * 8) for _ in range(8)]
    for row_index in range(1, 3):
        for column in range(1, 3):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x11\x18\x27"
    pixels = decode_png_pixels(make_png_from_rows(8, 8, [bytes(row) for row in rows]))

    foreground = sample_text_foreground_rgb(pixels, [-2, -2, 6, 6], [255, 255, 255])

    assert foreground == (17, 24, 39)


def test_find_leading_symbol_gap_detects_projection_gap() -> None:
    rows = [bytearray(bytes((255, 255, 255)) * 96) for _ in range(32)]
    for row_index in range(12, 24):
        for column in range(10, 22):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x00\x00\x00"
    for row_index in range(12, 24):
        for column in range(30, 70):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x00\x00\x00"
    pixels = decode_png_pixels(make_png_from_rows(96, 32, [bytes(row) for row in rows]))

    result = find_leading_symbol_gap(pixels, [8, 8, 80, 20], [255, 255, 255])

    assert result is not None
    assert result["protectedSymbolBBox"] == [8, 8, 14, 20]
    assert result["gapBBox"] == [22, 8, 8, 20]
    assert result["cleanedBBox"] == [30, 8, 58, 20]
    assert result["metrics"]["leftInkColumnCount"] >= 2
    assert result["metrics"]["rightInkColumnCount"] >= 2


def test_find_leading_symbol_gap_rejects_left_padding_without_symbol_ink() -> None:
    rows = [bytearray(bytes((255, 255, 255)) * 96) for _ in range(32)]
    for row_index in range(12, 24):
        for column in range(30, 70):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x00\x00\x00"
    pixels = decode_png_pixels(make_png_from_rows(96, 32, [bytes(row) for row in rows]))

    result = find_leading_symbol_gap(pixels, [8, 8, 80, 20], [255, 255, 255])

    assert result is None


def test_find_leading_symbol_gap_rejects_touching_text_without_gap() -> None:
    rows = [bytearray(bytes((255, 255, 255)) * 96) for _ in range(32)]
    for row_index in range(12, 24):
        for column in range(10, 70):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x00\x00\x00"
    pixels = decode_png_pixels(make_png_from_rows(96, 32, [bytes(row) for row in rows]))

    result = find_leading_symbol_gap(pixels, [8, 8, 80, 20], [255, 255, 255])

    assert result is None


def test_find_leading_symbol_gap_rejects_small_candidate_span() -> None:
    pixels = decode_png_pixels(make_rgb_png(30, 12, (255, 255, 255)))

    result = find_leading_symbol_gap(pixels, [1, 1, 24, 8], [255, 255, 255])

    assert result is None


def test_crop_png_rejects_unsupported_color_type_after_metadata_is_readable() -> None:
    png = bytearray(make_png(20, 30))
    png[25] = 3

    metadata = read_png_metadata(bytes(png))
    assert metadata is not None
    assert metadata.color_type == 3

    with pytest.raises(UnsupportedPngCropError):
        crop_png(bytes(png), PngRegion("header", 0, 0, 20, 7))


def test_encode_rgb_png_writes_readable_png() -> None:
    rows = [bytes((12, 34, 56)) * 5 for _ in range(4)]

    png = encode_rgb_png(5, 4, rows)

    metadata = read_png_metadata(png)
    pixels = decode_png_pixels(png)
    assert metadata == PngMetadata(5, 4, 8, 2, 0, 0, 0)
    assert pixels.rows == rows


def test_crop_and_fill_png_fills_crop_local_bbox() -> None:
    rows = [bytearray(bytes((247, 248, 250)) * 8) for _ in range(8)]
    png = make_png_from_rows(8, 8, [bytes(row) for row in rows])

    filled = crop_and_fill_png(
        png,
        PngRegion("slice", 2, 2, 4, 4),
        [PngFillOperation(1, 1, 2, 2, (22, 119, 255))],
    )

    pixels = decode_png_pixels(filled)
    assert pixels.width == 4
    assert pixels.height == 4
    for row_index in range(4):
        for column in range(4):
            offset = column * 3
            rgb = tuple(pixels.rows[row_index][offset : offset + 3])
            if 1 <= row_index < 3 and 1 <= column < 3:
                assert rgb == (22, 119, 255)
            else:
                assert rgb == (247, 248, 250)


def test_crop_and_fill_png_rejects_fill_outside_crop() -> None:
    png = make_rgb_png(8, 8, (247, 248, 250))

    with pytest.raises(UnsupportedPngCropError):
        crop_and_fill_png(
            png,
            PngRegion("slice", 2, 2, 4, 4),
            [PngFillOperation(3, 3, 2, 2, (22, 119, 255))],
        )


def test_decode_png_pixels_and_sample_rgb_background() -> None:
    png = make_rgb_png(12, 8, (247, 248, 250))

    pixels = decode_png_pixels(png)
    sample = sample_region_background(pixels, [0, 0, 12, 8], tolerance=18)

    assert sample.color == "#F7F8FA"
    assert sample.mean_rgb == [247, 248, 250]
    assert sample.max_channel_delta == 0
    assert sample.brightness > 180


def test_decode_png_pixels_composites_rgba_on_white() -> None:
    png = make_rgba_png(2, 1, (0, 0, 0, 128))

    pixels = decode_png_pixels(png)
    sample = sample_region_background(pixels, [0, 0, 2, 1], tolerance=18)

    assert sample.mean_rgb == [127, 127, 127]


def test_sample_region_background_clamps_bbox_to_bounds() -> None:
    png = make_rgb_png(12, 8, (255, 255, 255))
    pixels = decode_png_pixels(png)

    sample = sample_region_background(pixels, [-4, -4, 8, 8], tolerance=18)

    assert sample.bbox == [0, 0, 4, 4]


def test_sample_rect_edges_can_ignore_one_side() -> None:
    rows = []
    for _row_index in range(8):
        row = bytearray(bytes((247, 248, 250)) * 12)
        for column in range(0, 2):
            offset = column * 3
            row[offset : offset + 3] = bytes((38, 132, 255))
        rows.append(bytes(row))
    png = make_png_from_rows(12, 8, rows)
    pixels = decode_png_pixels(png)

    all_edges = sample_region_background(pixels, [0, 0, 12, 8], tolerance=18)
    side_edges = sample_rect_edges(pixels, [0, 0, 12, 8], sides={"top", "bottom", "right"}, inset=2, thickness=1, tolerance=18)

    assert all_edges.max_channel_delta > 18
    assert side_edges.max_channel_delta == 0
    assert side_edges.color == "#F7F8FA"


def make_rgb_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * width
    idat_data = zlib.compress(row * height)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", ihdr_data),
            png_chunk(b"IDAT", idat_data),
            png_chunk(b"IEND", b""),
        ]
    )


def make_rgba_png(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + bytes(rgba) * width
    idat_data = zlib.compress(row * height)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", ihdr_data),
            png_chunk(b"IDAT", idat_data),
            png_chunk(b"IEND", b""),
        ]
    )


def make_png_from_rows(width: int, height: int, rows: list[bytes]) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat_data = zlib.compress(b"".join(b"\x00" + row for row in rows))
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", ihdr_data),
            png_chunk(b"IDAT", idat_data),
            png_chunk(b"IEND", b""),
        ]
    )


def test_encode_rgba_png_writes_readable_rgba_png() -> None:
    from app.png_tools import encode_rgba_png, decode_png_pixels
    rows = [bytes((12, 34, 56, 128)) * 5 for _ in range(4)]

    png = encode_rgba_png(5, 4, rows)

    metadata = read_png_metadata(png)
    pixels = decode_png_pixels(png)
    assert metadata == PngMetadata(5, 4, 8, 6, 0, 0, 0)
    # 12 * 128/255 + 255 * (1 - 128/255) = 6 + 127 = 133
    # 34 * 128/255 + 255 * (1 - 128/255) = 17 + 127 = 144
    # 56 * 128/255 + 255 * (1 - 128/255) = 28 + 127 = 155
    expected_row = bytes((133, 144, 155)) * 5
    assert pixels.rows == [expected_row] * 4


def test_crop_mask_pixels_to_rgba_png_correctly_masks_region() -> None:
    from app.png_tools import crop_mask_pixels_to_rgba_png, decode_png_pixels
    # Create 4x4 RGB pixels
    rows = [bytes((100, 150, 200)) * 4 for _ in range(4)]
    png = make_png_from_rows(4, 4, rows)
    pixels = decode_png_pixels(png)

    # Define a 4x4 mask, where center 2x2 are 255 (opaque) and outer are 0 (transparent)
    mask = bytes([
        0,   0,   0, 0,
        0, 255, 255, 0,
        0, 255, 255, 0,
        0,   0,   0, 0,
    ])

    # Crop to region [1, 1, 2, 2]
    region = PngRegion("icon", 1, 1, 2, 2)
    rgba_png = crop_mask_pixels_to_rgba_png(pixels, mask, region)

    metadata = read_png_metadata(rgba_png)
    assert metadata == PngMetadata(2, 2, 8, 6, 0, 0, 0)

    # Let's decode it back. Since the mask at (1,1)-(2,2) was 255, alpha is 255.
    # Blended on white should just be the original RGB (100, 150, 200).
    pixels_out = decode_png_pixels(rgba_png)
    assert pixels_out.rows == [bytes((100, 150, 200)) * 2] * 2
