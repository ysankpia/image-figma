from __future__ import annotations

from dataclasses import dataclass


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
