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


def merge_surface_and_shape_candidates(surface_candidates: list[Candidate], shape_candidates: list[Candidate]) -> list[Candidate]:
    merged = nms_surface_candidates(surface_candidates) + shape_candidates
    accepted: list[Candidate] = []
    for candidate in sorted(merged, key=lambda item: (-surface_merge_priority(item), item.bbox.y, item.bbox.x, -item.bbox.area, item.id)):
        duplicate = False
        for kept in accepted:
            if iou(candidate.bbox, kept.bbox) >= 0.82:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def surface_merge_priority(candidate: Candidate) -> int:
    if candidate.scores.get("confirmedControlSurface", 0.0) >= 1.0:
        return 4
    if candidate.reason == "local_container_surface":
        return 3
    if candidate.reason in {"low_texture_solid_region"}:
        return 2
    if candidate.reason in {"background_surface_band", "inferred_background_plate_from_surface_bands"}:
        return 0
    return 1


def infer_background_plate_candidates(
    surface_candidates: list[Candidate],
    width: int,
    height: int,
    page_background: tuple[int, int, int],
) -> list[Candidate]:
    surfaces = [
        item
        for item in surface_candidates
        if item.reason == "background_surface_band"
        and item.bbox.width >= max(120, width * 0.18)
        and item.bbox.height >= 16
        and surface_fill_distance(item, page_background) >= 36.0
    ]
    clusters: list[dict[str, Any]] = []
    for surface in sorted(surfaces, key=lambda item: item.bbox.area, reverse=True):
        color = surface_fill_rgb(surface)
        match: dict[str, Any] | None = None
        for cluster in clusters:
            if color_distance(cluster["color"], color) <= 40.0:
                match = cluster
                break
        if match is None:
            clusters.append({"color": color.astype(np.float32), "surfaces": [surface]})
        else:
            match["surfaces"].append(surface)
            colors = np.stack([surface_fill_rgb(item).astype(np.float32) for item in match["surfaces"]])
            match["color"] = np.mean(colors, axis=0)

    plates: list[Candidate] = []
    page_area = width * height
    for index, cluster in enumerate(clusters, start=1):
        members: list[Candidate] = cluster["surfaces"]
        if len(members) < 3:
            continue
        x1 = min(item.bbox.x for item in members)
        y1 = min(item.bbox.y for item in members)
        x2 = max(item.bbox.x2 for item in members)
        y2 = max(item.bbox.y2 for item in members)
        box = BBox(x1, y1, x2 - x1, y2 - y1)
        if box.width < width * 0.50 or box.height < height * 0.42:
            continue
        wide_member_count = sum(1 for item in members if item.bbox.width >= width * 0.45)
        if wide_member_count < 3:
            continue
        member_area = sum(item.bbox.area for item in members)
        if box.area <= 0 or member_area / box.area < 0.16:
            continue
        if page_area > 0 and box.area / page_area < 0.18:
            continue
        color = np.clip(cluster["color"], 0, 255).astype(np.uint8)
        scores = {
            "fillR": round(float(color[0]), 2),
            "fillG": round(float(color[1]), 2),
            "fillB": round(float(color[2]), 2),
            "sourceSurfaceCount": float(len(members)),
            "wideSurfaceCount": float(wide_member_count),
            "sourceSurfaceAreaRatio": round(float(member_area / max(1, box.area)), 4),
            "pageBackgroundDistance": round(float(color_distance(color, page_background)), 4),
        }
        plates.append(
            Candidate(
                id=f"background_plate_{index:04d}",
                kind="shape",
                bbox=box,
                score=0.99,
                scores=scores,
                reason="inferred_background_plate_from_surface_bands",
            )
        )

    return nms_surface_candidates(plates)


def surface_fill_rgb(surface: Candidate) -> np.ndarray:
    return np.array(
        [
            surface.scores.get("fillR", 255.0),
            surface.scores.get("fillG", 255.0),
            surface.scores.get("fillB", 255.0),
        ],
        dtype=np.float32,
    )


def surface_fill_distance(surface: Candidate, color: tuple[int, int, int] | np.ndarray) -> float:
    return color_distance(surface_fill_rgb(surface), color)
