from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import sample_outer_bbox_ring_rgb
from ..png_tools import PngPixels, rgb_to_hex
from ..visual_primitive_graph import measure_region


def apply_source_background(dsl: dict[str, Any], pixels: PngPixels) -> None:
    background = rgb_to_hex(sample_canvas_background(pixels))
    page = dsl.get("page") if isinstance(dsl.get("page"), dict) else {}
    page["background"] = {"type": "color", "value": background}
    dsl["page"] = page
    root = dsl.get("root") if isinstance(dsl.get("root"), dict) else {}
    style = root.get("style") if isinstance(root.get("style"), dict) else {}
    style["fill"] = background
    root["style"] = style
    dsl["root"] = root


def sample_canvas_background(pixels: PngPixels) -> list[int]:
    samples: list[tuple[int, int, int]] = []
    for x in range(0, pixels.width, max(1, pixels.width // 24)):
        samples.append(pixel_at(pixels, x, 0))
        samples.append(pixel_at(pixels, x, pixels.height - 1))
    for y in range(0, pixels.height, max(1, pixels.height // 24)):
        samples.append(pixel_at(pixels, 0, y))
        samples.append(pixel_at(pixels, pixels.width - 1, y))
    if not samples:
        raise ValueError("source image has no edge samples for M29 background materialization.")
    return median_rgb(samples)


def pixel_at(pixels: PngPixels, x: int, y: int) -> tuple[int, int, int]:
    row = pixels.rows[max(0, min(pixels.height - 1, y))]
    col = max(0, min(pixels.width - 1, x))
    offset = col * 3
    return row[offset], row[offset + 1], row[offset + 2]


def median_rgb(samples: list[tuple[int, int, int]]) -> list[int]:
    return [
        sorted(sample[channel] for sample in samples)[len(samples) // 2]
        for channel in range(3)
    ]


def sample_text_background(pixels: PngPixels, bbox: list[int]) -> list[int]:
    try:
        return sample_outer_bbox_ring_rgb(pixels, bbox)
    except Exception:
        metrics = measure_region(pixels, bbox)
        return list(metrics.mean_rgb)


def sample_text_foreground(pixels: PngPixels, bbox: list[int], bg_rgb: list[int]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    best = (32, 32, 32)
    best_distance = -1
    for row_idx in range(max(0, y), min(pixels.height, y + height)):
        row = pixels.rows[row_idx]
        for col_idx in range(max(0, x), min(pixels.width, x + width)):
            offset = col_idx * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            distance = abs(rgb[0] - bg_rgb[0]) + abs(rgb[1] - bg_rgb[1]) + abs(rgb[2] - bg_rgb[2])
            if distance > best_distance:
                best_distance = distance
                best = rgb
    return best


def estimate_font_size(bbox: list[int]) -> int:
    return max(8, min(64, round(bbox[3] * 0.82)))


def sampled_shape_fill(pixels: PngPixels, bbox: list[int]) -> str:
    metrics = measure_region(pixels, bbox)
    return rgb_to_hex(list(metrics.mean_rgb))


def build_shape_replay_style(
    pixels: PngPixels,
    bbox: list[int],
    source_node: dict[str, Any] | None,
    m292_object: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = m292_object.get("sourceEvidence") if isinstance(m292_object, dict) and isinstance(m292_object.get("sourceEvidence"), dict) else {}
    fill_override = str(evidence.get("shapeFillOverride") or "").strip()
    source_fill = source_shape_fill(source_node)
    if fill_override.startswith("#"):
        fill = fill_override
        style_source = "source_shape_inference"
    elif source_fill is not None:
        fill = source_fill
        style_source = "source_shape_style"
    else:
        fill = sampled_shape_fill(pixels, bbox)
        style_source = "sampled_fill_only"
    style: dict[str, Any] = {"fill": fill}
    radius: int | None = None
    geometry = source_node.get("geometry") if isinstance(source_node, dict) and isinstance(source_node.get("geometry"), dict) else {}
    geometry_kind = str(geometry.get("kind") or "")
    geometry_confidence = str(geometry.get("confidence") or "")
    geometry_params = geometry.get("params") if isinstance(geometry.get("params"), dict) else {}
    geometry_radius = numeric_radius(geometry_params.get("radius"))

    if geometry_kind in {"rounded_rect", "pill", "circle", "ellipse"} and geometry_confidence != "low" and geometry_radius is not None:
        radius = clamp_radius(geometry_radius, bbox)
        style_source = "shape_geometry_fit"

    radius_override = numeric_radius(evidence.get("shapeRadiusOverride"))
    if radius_override is not None:
        radius = clamp_radius(radius_override, bbox)
        style_source = "source_shape_inference"

    if radius is not None:
        style["radius"] = radius
    style["meta"] = {
        "m29ShapeStyleSource": style_source,
        **({"m29ShapeRadius": radius} if radius is not None else {}),
    }
    return style


def source_shape_fill(source_node: dict[str, Any] | None) -> str | None:
    style = source_node.get("style") if isinstance(source_node, dict) and isinstance(source_node.get("style"), dict) else {}
    fill = str(style.get("fill") or "").strip()
    if not fill.startswith("#"):
        return None
    text = fill[1:]
    if len(text) == 3:
        text = "".join(char + char for char in text)
    if len(text) != 6:
        return None
    try:
        int(text, 16)
    except ValueError:
        return None
    return f"#{text.upper()}"


def numeric_radius(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return round(value)


def clamp_radius(radius: int, bbox: list[int]) -> int:
    return max(0, min(radius, min(bbox[2], bbox[3]) // 2))
