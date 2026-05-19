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
