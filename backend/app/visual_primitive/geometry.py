from __future__ import annotations

from typing import Any

from ..png_tools import PngMetadata, PngPixels, sample_rect_edges_dominant_background
from .bbox import bbox_area, bbox_intersects, bbox_x2, bbox_y2
from .metrics import color_distance, measure_region
from .types import M29ConnectedComponent, M29LayerHint, M29PrimitiveMetrics, M29VisualPrimitiveOptions


def is_line_like(bbox: list[int], metrics: M29PrimitiveMetrics, options: M29VisualPrimitiveOptions) -> bool:
    texture_limit = 0.18 if min(bbox[2], bbox[3]) <= 2 else 0.10
    return (
        (bbox[2] >= options.line_min_length and bbox[3] <= options.line_max_thickness)
        or (bbox[3] >= options.line_min_length and bbox[2] <= options.line_max_thickness)
    ) and metrics.color_count <= 6 and metrics.texture_score <= texture_limit and metrics.fill_ratio >= 0.60


def is_rect_like(component: M29ConnectedComponent, options: M29VisualPrimitiveOptions) -> bool:
    return (
        component.area >= options.min_shape_area
        and component.fill_ratio >= 0.80
        and component.metrics.color_count <= options.shape_color_threshold
        and component.metrics.texture_score <= options.shape_texture_threshold
    )


def fit_connected_component_geometry(
    component: M29ConnectedComponent,
    options: M29VisualPrimitiveOptions,
) -> dict[str, Any]:
    bbox = component.bbox
    if is_line_like(bbox, component.metrics, options):
        return shape_geometry(
            "line",
            "high",
            metrics={"fitError": 0.0, "centerFillRatio": component.fill_ratio, "cornerMissingRatio": 0.0, "edgeFillRatio": component.fill_ratio},
            evidence=["mask_fit", "line_like"],
        )
    if component.mask_data is None or len(component.mask_data) != bbox[2] * bbox[3]:
        return shape_geometry("unknown", "low", evidence=["missing_mask"])

    width, height = bbox[2], bbox[3]
    center = local_mask_occupancy(component.mask_data, width, height, [round(width * 0.25), round(height * 0.25), max(1, round(width * 0.50)), max(1, round(height * 0.50))])
    corner_size = max(2, round(min(width, height) * 0.22))
    corners = [
        local_mask_occupancy(component.mask_data, width, height, [0, 0, corner_size, corner_size]),
        local_mask_occupancy(component.mask_data, width, height, [width - corner_size, 0, corner_size, corner_size]),
        local_mask_occupancy(component.mask_data, width, height, [0, height - corner_size, corner_size, corner_size]),
        local_mask_occupancy(component.mask_data, width, height, [width - corner_size, height - corner_size, corner_size, corner_size]),
    ]
    corner_missing = sum(1 for value in corners if value <= 0.45) / 4
    edge = local_mask_edge_occupancy(component.mask_data, width, height, thickness=max(1, min(3, min(width, height) // 8)))
    ratio = width / max(1, height)
    ellipse_fill = 3.14159 / 4
    ellipse_error = abs(component.fill_ratio - ellipse_fill)
    metrics = {
        "fitError": round(min(abs(1 - component.fill_ratio), ellipse_error), 4),
        "centerFillRatio": round(center, 4),
        "cornerMissingRatio": round(corner_missing, 4),
        "edgeFillRatio": round(edge, 4),
    }

    if is_rect_like(component, options) and center >= 0.90 and corner_missing <= 0.25:
        return shape_geometry("rect", "high", metrics=metrics, evidence=["mask_fit", "corner_occupancy", "stable_fill"])
    if (
        component.area >= options.min_shape_area
        and component.area < 10000
        and 0.45 <= component.fill_ratio <= 0.90
        and 0.35 <= ratio <= 2.80
        and center >= 0.75
        and corner_missing >= 0.50
        and ellipse_error <= 0.20
    ):
        kind = "circle" if 0.85 <= ratio <= 1.18 else "ellipse"
        confidence = "high" if ellipse_error <= 0.12 and corner_missing >= 0.75 else "medium"
        radius = round(min(width, height) / 2) if kind == "circle" else None
        return shape_geometry(kind, confidence, radius=radius, metrics=metrics, evidence=["mask_fit", "corner_occupancy"])
    return shape_geometry("unknown", "low", metrics=metrics, evidence=["mask_fit"])


def fit_low_contrast_support_geometry(pixels: PngPixels, bbox: list[int], ignored_bboxes: list[list[int]]) -> dict[str, Any]:
    width, height = bbox[2], bbox[3]
    if width <= 0 or height <= 0:
        return shape_geometry("unknown", "low", evidence=["invalid_bbox"])
    fill = support_region_metrics(pixels, bbox).mean_rgb
    ignored = [
        local_intersection_bbox(bbox, item)
        for item in ignored_bboxes
        if bbox_intersects(bbox, item)
    ]

    def occupancy(region: list[int]) -> float:
        return support_fill_occupancy(pixels, bbox, region, fill, ignored)

    corner_size = max(3, round(min(width, height) * 0.28))
    corners = [
        occupancy([0, 0, corner_size, corner_size]),
        occupancy([width - corner_size, 0, corner_size, corner_size]),
        occupancy([0, height - corner_size, corner_size, corner_size]),
        occupancy([width - corner_size, height - corner_size, corner_size, corner_size]),
    ]
    corner_missing = sum(1 for value in corners if value <= 0.55) / 4
    center = occupancy([round(width * 0.22), round(height * 0.22), max(1, round(width * 0.56)), max(1, round(height * 0.56))])
    top_edge = occupancy([round(width * 0.22), 0, max(1, round(width * 0.56)), max(1, round(height * 0.18))])
    bottom_edge = occupancy([round(width * 0.22), height - max(1, round(height * 0.18)), max(1, round(width * 0.56)), max(1, round(height * 0.18))])
    left_edge = occupancy([0, round(height * 0.28), max(1, round(width * 0.12)), max(1, round(height * 0.44))])
    right_edge = occupancy([width - max(1, round(width * 0.12)), round(height * 0.28), max(1, round(width * 0.12)), max(1, round(height * 0.44))])
    edge = min(top_edge, bottom_edge, max(left_edge, right_edge))
    metrics = {
        "fitError": round(1 - min(center, edge), 4),
        "centerFillRatio": round(center, 4),
        "cornerMissingRatio": round(corner_missing, 4),
        "edgeFillRatio": round(edge, 4),
    }

    if center >= 0.82 and edge >= 0.72 and corner_missing >= 0.75:
        radius = estimate_support_radius_from_occupancy(pixels, bbox, fill, ignored)
        half_short_edge = max(1, round(min(width, height) / 2))
        if radius >= round(half_short_edge * 0.75):
            return shape_geometry("pill", "high", radius=half_short_edge, metrics=metrics, evidence=["occupancy_fit", "corner_occupancy", "stable_fill"])
        if radius > 0:
            return shape_geometry("rounded_rect", "medium", radius=radius, metrics=metrics, evidence=["occupancy_fit", "corner_occupancy", "stable_fill"])
    if center >= 0.82 and min(corners) >= 0.62:
        return shape_geometry("rect", "medium", metrics=metrics, evidence=["occupancy_fit", "corner_occupancy", "stable_fill"])
    return shape_geometry("unknown", "low", metrics=metrics, evidence=["occupancy_fit"])


def support_region_metrics(pixels: PngPixels, bbox: list[int]) -> M29PrimitiveMetrics:
    try:
        sample = sample_rect_edges_dominant_background(
            pixels,
            bbox,
            sides={"top", "bottom", "left", "right"},
            inset=2,
            thickness=2,
            tolerance=18,
            min_fraction=0.50,
        )
        mean = tuple(int(value) for value in sample.mean_rgb)
        return M29PrimitiveMetrics(
            color_count=1 if sample.max_channel_delta <= 18 else 2,
            texture_score=round(sample.max_channel_delta / 255, 4),
            edge_score=0.0,
            fill_ratio=sample.confidence,
            aspect_ratio=round(bbox[2] / max(1, bbox[3]), 4),
            brightness=sample.brightness,
            mean_rgb=mean,
        )
    except Exception:
        return measure_region(pixels, bbox)


def shape_geometry(
    kind: str,
    confidence: str,
    *,
    radius: int | None = None,
    metrics: dict[str, float] | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if radius is not None:
        params["radius"] = max(0, round(radius))
    return {
        "kind": kind,
        "confidence": confidence,
        "params": params,
        "metrics": {
            "fitError": 1.0,
            "centerFillRatio": 0.0,
            "cornerMissingRatio": 0.0,
            "edgeFillRatio": 0.0,
            **(metrics or {}),
        },
        "evidence": evidence or [],
    }


def geometry_radius(geometry: dict[str, Any], bbox: list[int]) -> int | None:
    if geometry.get("confidence") == "low":
        return None
    if geometry.get("kind") not in {"rounded_rect", "pill", "circle", "ellipse"}:
        return None
    params = geometry.get("params") if isinstance(geometry.get("params"), dict) else {}
    value = params.get("radius")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, min(round(value), min(bbox[2], bbox[3]) // 2))


def local_mask_occupancy(mask_data: bytes, width: int, height: int, bbox: list[int]) -> float:
    x, y, box_width, box_height = clamp_local_bbox(bbox, width, height)
    if box_width <= 0 or box_height <= 0:
        return 0.0
    hits = 0
    for row_index in range(y, y + box_height):
        start = row_index * width + x
        hits += sum(1 for value in mask_data[start : start + box_width] if value)
    return hits / max(1, box_width * box_height)


def local_mask_edge_occupancy(mask_data: bytes, width: int, height: int, *, thickness: int) -> float:
    areas = [
        [0, 0, width, thickness],
        [0, height - thickness, width, thickness],
        [0, 0, thickness, height],
        [width - thickness, 0, thickness, height],
    ]
    return sum(local_mask_occupancy(mask_data, width, height, area) for area in areas) / 4


def support_fill_occupancy(
    pixels: PngPixels,
    outer_bbox: list[int],
    local_region: list[int],
    fill: tuple[int, int, int],
    ignored_local_bboxes: list[list[int]],
) -> float:
    x, y, width, height = clamp_local_bbox(local_region, outer_bbox[2], outer_bbox[3])
    if width <= 0 or height <= 0:
        return 0.0
    hits = 0
    samples = 0
    for local_y in range(y, y + height):
        row = pixels.rows[outer_bbox[1] + local_y]
        for local_x in range(x, x + width):
            if any(local_bbox_contains(item, local_x, local_y) for item in ignored_local_bboxes):
                continue
            offset = (outer_bbox[0] + local_x) * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            samples += 1
            if color_distance(rgb, fill) <= 24:
                hits += 1
    return hits / max(1, samples)


def estimate_support_radius_from_occupancy(
    pixels: PngPixels,
    bbox: list[int],
    fill: tuple[int, int, int],
    ignored_local_bboxes: list[list[int]],
) -> int:
    width, height = bbox[2], bbox[3]
    limit = max(1, min(width, height) // 2)
    probes: list[int] = []
    for row_offset in range(0, limit):
        y_values = [row_offset, height - row_offset - 1]
        for local_y in y_values:
            run = 0
            row = pixels.rows[bbox[1] + local_y]
            for local_x in range(width):
                if any(local_bbox_contains(item, local_x, local_y) for item in ignored_local_bboxes):
                    continue
                offset = (bbox[0] + local_x) * 3
                rgb = (row[offset], row[offset + 1], row[offset + 2])
                if color_distance(rgb, fill) <= 24:
                    run += 1
                elif run == 0:
                    continue
                else:
                    break
            if run > 0:
                probes.append(max(0, (width - run) // 2))
    if not probes:
        return 0
    probes = sorted(probes)
    return max(0, min(limit, probes[len(probes) // 2]))


def clamp_local_bbox(bbox: list[int], width: int, height: int) -> list[int]:
    x1 = max(0, min(width, round(bbox[0])))
    y1 = max(0, min(height, round(bbox[1])))
    x2 = max(0, min(width, round(bbox[0] + bbox[2])))
    y2 = max(0, min(height, round(bbox[1] + bbox[3])))
    return [x1, y1, max(0, x2 - x1), max(0, y2 - y1)]


def local_bbox_contains(bbox: list[int], x: int, y: int) -> bool:
    return bbox[0] <= x < bbox[0] + bbox[2] and bbox[1] <= y < bbox[1] + bbox[3]


def local_intersection_bbox(outer: list[int], item: list[int]) -> list[int]:
    x1 = max(outer[0], item[0])
    y1 = max(outer[1], item[1])
    x2 = min(bbox_x2(outer), bbox_x2(item))
    y2 = min(bbox_y2(outer), bbox_y2(item))
    return [x1 - outer[0], y1 - outer[1], max(0, x2 - x1), max(0, y2 - y1)]


def rect_subtype(bbox: list[int], image: PngMetadata) -> str:
    area_ratio = bbox_area(bbox) / max(1, image.width * image.height)
    if area_ratio > 0.45:
        return "background"
    if bbox[2] > image.width * 0.55 and bbox[3] > 32:
        return "large_container"
    return "card_background"


def shape_layer_hint(subtype: str) -> M29LayerHint:
    if subtype == "background":
        return "background"
    if subtype in {"low_contrast_support", "text_support_background"}:
        return "container"
    if subtype in {"badge_background", "small_ellipse", "small_rounded_rect", "icon_button_background"}:
        return "overlay"
    return "container"
