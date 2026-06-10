from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


def safe_slug(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^0-9A-Za-z_-]+", "_", value).strip("_")
    return slug or fallback


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_bbox(value: dict[str, Any]) -> dict[str, int]:
    x = value.get("x", value.get("left", value.get("xmin", 0)))
    y = value.get("y", value.get("top", value.get("ymin", 0)))
    if "width" in value or "w" in value:
        width = value.get("width", value.get("w", 0))
        height = value.get("height", value.get("h", 0))
    else:
        width = float(value.get("xmax", value.get("right", x))) - float(x)
        height = float(value.get("ymax", value.get("bottom", y))) - float(y)
    return {
        "x": int(round(float(x or 0))),
        "y": int(round(float(y or 0))),
        "width": int(round(float(width or 0))),
        "height": int(round(float(height or 0))),
    }


def normalize_xyxy(value: list[float] | tuple[float, ...]) -> dict[str, int]:
    x1, y1, x2, y2 = value[:4]
    return {
        "x": int(round(x1)),
        "y": int(round(y1)),
        "width": int(round(x2 - x1)),
        "height": int(round(y2 - y1)),
    }


def clamp_bbox(bbox: dict[str, int], width: int, height: int) -> dict[str, int]:
    x = max(0, min(int(bbox["x"]), width))
    y = max(0, min(int(bbox["y"]), height))
    right = max(x, min(int(bbox["x"]) + int(bbox["width"]), width))
    bottom = max(y, min(int(bbox["y"]) + int(bbox["height"]), height))
    return {"x": x, "y": y, "width": right - x, "height": bottom - y}


def bbox_area(bbox: dict[str, int]) -> int:
    return max(0, int(bbox["width"])) * max(0, int(bbox["height"]))


def bbox_iou(a: dict[str, int], b: dict[str, int]) -> float:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = ax1 + a["width"], ay1 + a["height"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = bx1 + b["width"], by1 + b["height"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    intersection = (ix2 - ix1) * (iy2 - iy1)
    union = bbox_area(a) + bbox_area(b) - intersection
    return intersection / union if union > 0 else 0.0


def bbox_overlap_ratio(inner: dict[str, int], outer: dict[str, int]) -> float:
    ix1 = max(inner["x"], outer["x"])
    iy1 = max(inner["y"], outer["y"])
    ix2 = min(inner["x"] + inner["width"], outer["x"] + outer["width"])
    iy2 = min(inner["y"] + inner["height"], outer["y"] + outer["height"])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    area = (ix2 - ix1) * (iy2 - iy1)
    base = bbox_area(inner)
    return area / base if base > 0 else 0.0
