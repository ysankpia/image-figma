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


def raster_ownership(candidate: Candidate, ocr_blocks: list[OCRBlock], text_mask: np.ndarray) -> dict[str, Any]:
    covered_blocks: list[dict[str, Any]] = []
    for block in ocr_blocks:
        overlap = intersection_area(candidate.bbox, block.bbox)
        if overlap <= 0 or block.bbox.area <= 0:
            continue
        block_coverage = overlap / block.bbox.area
        if block_coverage < 0.25:
            continue
        covered_blocks.append(
            {
                "id": block.id,
                "coverage": round(block_coverage, 4),
                "textLength": len(block.text),
            }
        )

    knockout_pixel_ratio = 0.0
    if candidate.bbox.area > 0 and text_mask.size:
        knockout_pixel_ratio = float(text_mask[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2].mean())

    return {
        "textKnockout": bool(covered_blocks),
        "knockoutPixelRatio": round(knockout_pixel_ratio, 4),
        "coveredTextBlockCount": len(covered_blocks),
        "coveredTextBlocks": covered_blocks,
        "visibleTextOwnershipConflict": False,
    }


def build_raster_ownership(candidates: list[Candidate], ocr_blocks: list[OCRBlock], text_mask: np.ndarray) -> dict[str, dict[str, Any]]:
    return {candidate.id: raster_ownership(candidate, ocr_blocks, text_mask) for candidate in candidates}
