from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass


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


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum & 0xFFFFFFFF)
