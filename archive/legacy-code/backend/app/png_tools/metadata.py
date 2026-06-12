from __future__ import annotations

import struct

from .types import PngMetadata, PngRegion


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


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
