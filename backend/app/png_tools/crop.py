from __future__ import annotations

import struct
import zlib

from .decode import decode_png_pixels, parse_chunks, unfilter_rows
from .encode import encode_rgb_png, encode_rgba_png, png_chunk
from .metadata import PNG_SIGNATURE, read_png_metadata
from .types import PngFillOperation, PngPixels, PngRegion, UnsupportedPngCropError


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
