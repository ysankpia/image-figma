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

from .schema import BBox, OCRBlock, clamp_box


def load_ocr_blocks(path: Path | None, image_width: int, image_height: int, min_confidence: float) -> list[OCRBlock]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_blocks = data.get("blocks", data if isinstance(data, list) else [])

    blocks: list[OCRBlock] = []
    for index, item in enumerate(raw_blocks, start=1):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        confidence = float(item.get("confidence", 1.0))
        if confidence < min_confidence:
            continue
        raw_box = item.get("bbox", {})
        if isinstance(raw_box, list):
            if len(raw_box) < 4:
                continue
            box = BBox(int(raw_box[0]), int(raw_box[1]), int(raw_box[2]), int(raw_box[3]))
        else:
            box = BBox(
                int(raw_box.get("x", 0)),
                int(raw_box.get("y", 0)),
                int(raw_box.get("width", 0)),
                int(raw_box.get("height", 0)),
            )
        clamped = clamp_box(box, image_width, image_height)
        if clamped is None or clamped.width <= 1 or clamped.height < 6:
            continue
        blocks.append(
            OCRBlock(
                id=str(item.get("id") or f"text_{index:04d}"),
                text=text,
                bbox=clamped,
                confidence=confidence,
            )
        )
    return blocks
