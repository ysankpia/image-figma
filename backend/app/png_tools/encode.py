from __future__ import annotations

import struct
import zlib

from .metadata import PNG_SIGNATURE
from .types import UnsupportedPngCropError


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


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum & 0xFFFFFFFF)
