from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class OCRBlock:
    id: str
    text: str
    bbox: BBox
    confidence: float


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    bbox: BBox
    score: float
    scores: dict[str, float]
    reason: str


@dataclass(frozen=True)
class ControlSuppressionResult:
    rasters: list[Candidate]
    suppressed: list[dict[str, Any]]
    residual_suppressed_count: int


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def clamp_box(box: BBox, width: int, height: int) -> BBox | None:
    x1 = max(0, min(width, box.x))
    y1 = max(0, min(height, box.y))
    x2 = max(0, min(width, box.x2))
    y2 = max(0, min(height, box.y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x1, y1, x2 - x1, y2 - y1)


def intersection_area(a: BBox, b: BBox) -> int:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    return max(0, x2 - x1) * max(0, y2 - y1)


def iou(a: BBox, b: BBox) -> float:
    inter = intersection_area(a, b)
    union = a.area + b.area - inter
    if union <= 0:
        return 0.0
    return inter / union


def ioa(inner: BBox, outer: BBox) -> float:
    if inner.area <= 0:
        return 0.0
    return intersection_area(inner, outer) / inner.area
