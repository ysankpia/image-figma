from __future__ import annotations

import numpy as np


def dominant_cluster_stats(pixels: np.ndarray, bucket_size: int = 24) -> tuple[np.ndarray, float]:
    if pixels.size == 0:
        return np.array([255, 255, 255], dtype=np.uint8), 1.0
    buckets = np.clip(pixels.astype(np.int16) // bucket_size, 0, 255 // bucket_size)
    codes = buckets[:, 0] * 1024 + buckets[:, 1] * 32 + buckets[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    dominant_index = int(np.argmax(counts))
    dominant_code = values[dominant_index]
    cluster = pixels[codes == dominant_code]
    color = np.median(cluster if cluster.size else pixels, axis=0)
    return np.clip(color, 0, 255).astype(np.uint8), float(counts[dominant_index]) / max(1, int(counts.sum()))


def dominant_cluster_color(pixels: np.ndarray, bucket_size: int = 24) -> np.ndarray:
    color, _ = dominant_cluster_stats(pixels, bucket_size)
    return color


def color_hex(color: tuple[int, int, int] | np.ndarray) -> str:
    r, g, b = [int(item) for item in color]
    return f"#{r:02x}{g:02x}{b:02x}"


def color_distance(a: tuple[int, int, int] | np.ndarray, b: tuple[int, int, int] | np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=np.float32) - np.asarray(b, dtype=np.float32)))
