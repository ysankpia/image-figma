from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

OUTPUT_NAME = "m29_locations.v1.json"


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    def to_json(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class Component:
    id: int
    bbox: BBox
    area: int
    pixels: tuple[tuple[int, int], ...]


def locate(input_path: Path, output_dir: Path) -> dict[str, Any]:
    if not str(input_path):
        raise ValueError("missing input path")
    if not str(output_dir):
        raise ValueError("missing output dir")

    image = Image.open(input_path).convert("RGBA")
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("invalid image size")

    crops_dir = output_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    pixels = image.load()
    background, threshold = estimate_background(image, pixels)
    foreground = build_foreground_mask(image, pixels, background, threshold)
    components = connected_components(foreground, min_component_area(width, height), 0.80)
    components.sort(key=lambda item: (item.bbox.y, item.bbox.x, item.id))

    image_area = width * height
    items: list[dict[str, Any]] = []
    for index, component in enumerate(components, start=1):
        item_id = f"loc_{index:04d}"
        measurements = measure_component(image, pixels, component, background)
        kind, hints = classify(component, measurements, image_area)
        crop_path = f"crops/{item_id}.png"
        write_crop(image, component.bbox, output_dir / crop_path)
        items.append(
            {
                "id": item_id,
                "kind": kind,
                "bbox": component.bbox.to_json(),
                "cropPath": crop_path,
                "measurements": measurements,
                "hints": hints,
            }
        )

    doc: dict[str, Any] = {
        "schemaName": "M29Locations",
        "version": "1.0",
        "generator": {"name": "go-m29", "mode": "m29.0-locator"},
        "image": {
            "width": width,
            "height": height,
            "sourcePath": str(input_path),
        },
        "items": items,
        "diagnostics": {
            "backgroundColor": hex_rgb(background),
            "foregroundThreshold": threshold,
            "foregroundPixelCount": mask_count(foreground),
            "componentCount": len(components),
            "itemCount": len(items),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / OUTPUT_NAME).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return doc


def estimate_background(image: Image.Image, pixels: Any) -> tuple[tuple[int, int, int], float]:
    width, height = image.size
    samples: list[tuple[int, int, int]] = []
    step = max(1, min(width, height) // 160)
    for x in range(0, width, step):
        samples.append(rgb_at(pixels, x, 0))
        samples.append(rgb_at(pixels, x, height - 1))
    for y in range(0, height, step):
        samples.append(rgb_at(pixels, 0, y))
        samples.append(rgb_at(pixels, width - 1, y))
    background = median_rgb(samples)
    distances = sorted(color_distance(sample, background) for sample in samples)
    p95 = percentile(distances, 0.95)
    threshold = clamp_float(max(18.0, p95 * 2.2), 18.0, 52.0)
    return background, threshold


def build_foreground_mask(image: Image.Image, pixels: Any, background: tuple[int, int, int], threshold: float) -> "MaskData":
    width, height = image.size
    data = [False] * (width * height)
    for y in range(height):
        row = y * width
        for x in range(width):
            if color_distance(rgb_at(pixels, x, y), background) > threshold:
                data[row + x] = True
    return MaskData(width, height, data)


class MaskData(list[bool]):
    def __init__(self, width: int, height: int, data: list[bool]) -> None:
        super().__init__(data)
        self.width = width
        self.height = height


def connected_components(mask: MaskData, min_area: int, max_area_ratio: float) -> list[Component]:
    width = mask.width
    height = mask.height
    visited = [False] * len(mask)
    components: list[Component] = []
    max_area = int(float(width * height) * max_area_ratio)
    next_id = 1
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or not mask[index]:
                continue
            component = flood(next_id, mask, visited, width, height, x, y)
            if component.area >= min_area and (max_area <= 0 or component.area <= max_area):
                components.append(component)
                next_id += 1
    return components


def flood(id_value: int, mask: list[bool], visited: list[bool], width: int, height: int, start_x: int, start_y: int) -> Component:
    queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
    visited[start_y * width + start_x] = True
    min_x = max_x = start_x
    min_y = max_y = start_y
    pixels: list[tuple[int, int]] = []
    while queue:
        x, y = queue.popleft()
        pixels.append((x, y))
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            index = ny * width + nx
            if visited[index] or not mask[index]:
                continue
            visited[index] = True
            queue.append((nx, ny))
    return Component(
        id=id_value,
        area=len(pixels),
        pixels=tuple(pixels),
        bbox=BBox(x=min_x, y=min_y, width=max_x - min_x + 1, height=max_y - min_y + 1),
    )


def measure_component(image: Image.Image, pixels: Any, component: Component, background: tuple[int, int, int]) -> dict[str, Any]:
    bbox_area = component.bbox.width * component.bbox.height
    fill = 0.0
    if bbox_area > 0:
        fill = component.area / bbox_area
    sum_r = sum_g = sum_b = 0
    colors: set[tuple[int, int, int]] = set()
    for x, y in component.pixels:
        rgb = rgb_at(pixels, x, y)
        sum_r += rgb[0]
        sum_g += rgb[1]
        sum_b += rgb[2]
        colors.add((rgb[0] >> 4, rgb[1] >> 4, rgb[2] >> 4))
    mean = (0, 0, 0)
    if component.area > 0:
        mean = (sum_r // component.area, sum_g // component.area, sum_b // component.area)
    edge_density = edge_density_in_bbox(pixels, component.bbox)
    color_count = len(colors)
    texture = clamp_float(edge_density + color_count / 96.0, 0.0, 1.0)
    return {
        "area": component.area,
        "fillRatio": round_go(fill, 4),
        "meanColor": hex_rgb(mean),
        "colorCount": color_count,
        "edgeDensity": round_go(edge_density, 4),
        "textureScore": round_go(texture, 4),
        "localContrast": round_go(color_distance(mean, background), 2),
        "cornerRadiusEstimate": 0,
    }


def edge_density_in_bbox(pixels: Any, bbox: BBox) -> float:
    if bbox.width <= 2 or bbox.height <= 2:
        return 0.0
    total = 0
    edge = 0
    for y in range(bbox.y + 1, bbox.y + bbox.height - 1):
        for x in range(bbox.x + 1, bbox.x + bbox.width - 1):
            gx = abs(gray_at(pixels, x + 1, y) - gray_at(pixels, x - 1, y))
            gy = abs(gray_at(pixels, x, y + 1) - gray_at(pixels, x, y - 1))
            total += 1
            if gx + gy > 48:
                edge += 1
    if total == 0:
        return 0.0
    return edge / total


def classify(component: Component, measurements: dict[str, Any], image_area: int) -> tuple[str, dict[str, Any]]:
    bbox = component.bbox
    min_dim = min(bbox.width, bbox.height)
    max_dim = max(bbox.width, bbox.height)
    area_ratio = component.area / max(1, image_area)
    aspect = max_dim / max(1, min_dim)

    if min_dim <= 2 and max_dim >= 12:
        return "line", {
            "canBeLayerBackground": False,
            "canContainForeground": False,
            "canBeImage": False,
            "canBeIcon": False,
            "hasStableRectGeometry": True,
            "confidence": 0.86,
            "reasons": ["thin_component", "long_axis"],
        }

    if measurements["fillRatio"] >= 0.72 and measurements["colorCount"] <= 10 and measurements["edgeDensity"] <= 0.18:
        return "rect", {
            "canBeLayerBackground": area_ratio >= 0.0015,
            "canContainForeground": area_ratio >= 0.003,
            "canBeImage": False,
            "canBeIcon": False,
            "hasStableRectGeometry": True,
            "confidence": clamp_float(0.72 + measurements["fillRatio"] * 0.2, 0.0, 0.95),
            "reasons": ["stable_rect", "low_texture"],
        }

    if measurements["colorCount"] <= 12 and measurements["edgeDensity"] <= 0.22 and area_ratio >= 0.0008 and min_dim >= 18 and max_dim <= 220:
        return "surface_region", {
            "canBeLayerBackground": True,
            "canContainForeground": True,
            "canBeImage": False,
            "canBeIcon": False,
            "hasStableRectGeometry": True,
            "confidence": 0.74,
            "reasons": ["control_surface_component", "low_texture_control_surface"],
        }

    if area_ratio >= 0.004 and (
        measurements["colorCount"] >= 24 or measurements["edgeDensity"] >= 0.22 or measurements["textureScore"] >= 0.45
    ):
        return "image_region", {
            "canBeLayerBackground": False,
            "canContainForeground": False,
            "canBeImage": True,
            "canBeIcon": False,
            "hasStableRectGeometry": False,
            "confidence": clamp_float(0.55 + min(measurements["textureScore"], 0.4), 0.0, 0.92),
            "reasons": ["high_texture_or_color_variance"],
        }

    if area_ratio <= 0.01 and max_dim <= 128 and measurements["fillRatio"] >= 0.05:
        return "symbol_region", {
            "canBeLayerBackground": False,
            "canContainForeground": False,
            "canBeImage": False,
            "canBeIcon": True,
            "hasStableRectGeometry": False,
            "confidence": 0.62,
            "reasons": ["compact_foreground_component"],
        }

    if aspect >= 8 and min_dim <= 6:
        return "line", {
            "canBeLayerBackground": False,
            "canContainForeground": False,
            "canBeImage": False,
            "canBeIcon": False,
            "hasStableRectGeometry": True,
            "confidence": 0.7,
            "reasons": ["line_like_aspect"],
        }

    return "unknown_region", {
        "canBeLayerBackground": False,
        "canContainForeground": False,
        "canBeImage": False,
        "canBeIcon": False,
        "hasStableRectGeometry": False,
        "confidence": 0.35,
        "reasons": ["unclassified_physical_component"],
    }


def write_crop(image: Image.Image, bbox: BBox, path: Path) -> None:
    if bbox.width <= 0 or bbox.height <= 0:
        raise ValueError("invalid crop bbox")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.crop((bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)).save(path)


def rgb_at(pixels: Any, x: int, y: int) -> tuple[int, int, int]:
    r, g, b, a = pixels[x, y]
    if a == 255:
        return int(r), int(g), int(b)
    return (int(r) * int(a) // 255, int(g) * int(a) // 255, int(b) * int(a) // 255)


def gray_at(pixels: Any, x: int, y: int) -> float:
    r, g, b = rgb_at(pixels, x, y)
    return 0.299 * r + 0.587 * g + 0.114 * b


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    dr = float(a[0] - b[0])
    dg = float(a[1] - b[1])
    db = float(a[2] - b[2])
    return math.sqrt(dr * dr + dg * dg + db * db)


def median_rgb(samples: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    if not samples:
        return (255, 255, 255)
    rs = sorted(sample[0] for sample in samples)
    gs = sorted(sample[1] for sample in samples)
    bs = sorted(sample[2] for sample in samples)
    mid = len(samples) // 2
    return rs[mid], gs[mid], bs[mid]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    index = int(math.floor(float(len(values) - 1) * p + 0.5))
    index = max(0, min(index, len(values) - 1))
    return values[index]


def clamp_float(value: float, lower: float, upper: float) -> float:
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def round_go(value: float, digits: int) -> float:
    scale = 10**digits
    return math.floor(value * scale + 0.5) / scale


def hex_rgb(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def min_component_area(width: int, height: int) -> int:
    area = (width * height) // 90000
    if area < 8:
        return 8
    return area


def mask_count(mask: list[bool]) -> int:
    return sum(1 for value in mask if value)
