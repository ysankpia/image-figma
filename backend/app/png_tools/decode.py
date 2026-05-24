from __future__ import annotations

import struct
import zlib

from .metadata import PNG_SIGNATURE, is_png, read_png_metadata
from .types import PngPixels, UnsupportedPngCropError


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
