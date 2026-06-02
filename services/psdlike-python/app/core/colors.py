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


def dominant_cluster_stats(pixels: np.ndarray, bucket_size: int = 24) -> tuple[np.ndarray, float]:
    if pixels.size == 0:
        return np.array([255, 255, 255], dtype=np.uint8), 1.0
    buckets = np.clip(pixels.astype(np.int16) // bucket_size, 0, 255 // bucket_size)
    codes = buckets[:, 0] * 1024 + buckets[:, 1] * 32 + buckets[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    dominant_index = int(np.argmax(counts))
    dominant_code = values[dominant_index]
    cluster = pixels[codes == dominant_code]
    if cluster.size == 0:
        color = np.median(pixels, axis=0)
    else:
        color = np.median(cluster, axis=0)
    return np.clip(color, 0, 255).astype(np.uint8), float(counts[dominant_index]) / max(1, int(counts.sum()))


def dominant_cluster_color(pixels: np.ndarray, bucket_size: int = 24) -> np.ndarray:
    color, _ = dominant_cluster_stats(pixels, bucket_size)
    return color


def estimate_background_color(rgb: np.ndarray) -> tuple[int, int, int]:
    height, width, _ = rgb.shape
    edge = max(8, min(width, height) // 30)
    samples = np.concatenate(
        [
            rgb[:edge, :, :].reshape(-1, 3),
            rgb[height - edge :, :, :].reshape(-1, 3),
            rgb[:, :edge, :].reshape(-1, 3),
            rgb[:, width - edge :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    color, _ = dominant_cluster_stats(samples, bucket_size=16)
    return int(color[0]), int(color[1]), int(color[2])


def color_hex(color: tuple[int, int, int] | np.ndarray) -> str:
    r, g, b = [int(item) for item in color]
    return f"#{r:02x}{g:02x}{b:02x}"


def color_distance(a: tuple[int, int, int] | np.ndarray, b: tuple[int, int, int] | np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=np.float32) - np.asarray(b, dtype=np.float32)))
