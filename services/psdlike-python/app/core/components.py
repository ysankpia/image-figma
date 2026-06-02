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


def connected_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    rows, cols = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[list[tuple[int, int]]] = []

    for row in range(rows):
        for col in range(cols):
            if not mask[row, col] or visited[row, col]:
                continue
            stack = [(row, col)]
            visited[row, col] = True
            component: list[tuple[int, int]] = []
            while stack:
                cur_row, cur_col = stack.pop()
                component.append((cur_row, cur_col))
                for next_row, next_col in (
                    (cur_row - 1, cur_col),
                    (cur_row + 1, cur_col),
                    (cur_row, cur_col - 1),
                    (cur_row, cur_col + 1),
                ):
                    if (
                        0 <= next_row < rows
                        and 0 <= next_col < cols
                        and mask[next_row, next_col]
                        and not visited[next_row, next_col]
                    ):
                        visited[next_row, next_col] = True
                        stack.append((next_row, next_col))
            components.append(component)
    return components


def component_bbox(component: list[tuple[int, int]], tile_size: int, width: int, height: int) -> BBox:
    rows = [item[0] for item in component]
    cols = [item[1] for item in component]
    x1 = min(cols) * tile_size
    y1 = min(rows) * tile_size
    x2 = min(width, (max(cols) + 1) * tile_size)
    y2 = min(height, (max(rows) + 1) * tile_size)
    return BBox(x1, y1, x2 - x1, y2 - y1)


def contiguous_ranges(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    ranges: list[tuple[int, int]] = []
    start = values[0]
    previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append((start, previous))
        start = value
        previous = value
    ranges.append((start, previous))
    return ranges


def bands_overlap_horizontally(a: dict[str, Any], b: dict[str, Any]) -> bool:
    left = max(int(a["col1"]), int(b["col1"]))
    right = min(int(a["col2"]), int(b["col2"]))
    overlap = max(0, right - left + 1)
    if overlap <= 0:
        return False
    a_width = int(a["col2"]) - int(a["col1"]) + 1
    b_width = int(b["col2"]) - int(b["col1"]) + 1
    return overlap / max(1, min(a_width, b_width)) >= 0.35
