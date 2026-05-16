from __future__ import annotations

import pytest

from app.png_tools import PngMetadata, PngRegion, UnsupportedPngCropError, crop_png, plan_regions, read_png_metadata
from conftest import make_png


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


def test_crop_png_rejects_unsupported_color_type_after_metadata_is_readable() -> None:
    png = bytearray(make_png(20, 30))
    png[25] = 3

    metadata = read_png_metadata(bytes(png))
    assert metadata is not None
    assert metadata.color_type == 3

    with pytest.raises(UnsupportedPngCropError):
        crop_png(bytes(png), PngRegion("header", 0, 0, 20, 7))
