from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngMetadata, PngPixels, PngRegion
from .png_tools import UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata


M29PrimitiveType = Literal["text", "shape", "image", "symbol", "unknown"]
M29LayerHint = Literal["background", "container", "content", "overlay", "unknown"]
M29TextSource = Literal["ocr", "manual", "detector", "test"]
M29TextKind = Literal["line", "word", "block", "unknown"]
M29RelationType = Literal["contains", "overlaps", "protects", "near", "aligned"]

LAYER_ORDER: dict[str, int] = {"background": 0, "container": 1, "content": 2, "overlay": 3, "unknown": 4}
OVERLAY_COLORS: dict[str, tuple[int, int, int]] = {
    "text": (160, 80, 220),
    "shape": (0, 122, 255),
    "image": (0, 180, 210),
    "symbol": (0, 200, 90),
    "unknown": (238, 190, 40),
    "blocked": (235, 64, 52),
    "protected": (140, 140, 140),
}


@dataclass(frozen=True)
class M29TextBox:
    id: str
    bbox: list[int]
    text: str | None = None
    confidence: float = 1.0
    source: M29TextSource = "ocr"
    kind: M29TextKind = "unknown"


@dataclass(frozen=True)
class M29BinaryMask:
    width: int
    height: int
    data: bytes


@dataclass(frozen=True)
class M29PrimitiveMetrics:
    color_count: int
    texture_score: float
    edge_score: float
    fill_ratio: float
    aspect_ratio: float
    brightness: float
    mean_rgb: tuple[int, int, int]


@dataclass(frozen=True)
class M29PrimitiveNode:
    id: str
    type: M29PrimitiveType
    subtype: str
    bbox: list[int]
    confidence: float
    source: str
    source_order: int
    layer_hint: M29LayerHint
    reasons: list[str]
    metrics: M29PrimitiveMetrics
    style: dict[str, object] | None = None
    text: str | None = None
    asset_path: str | None = None
    mask_path: str | None = None
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "type": self.type,
            "subtype": self.subtype,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "sourceOrder": self.source_order,
            "layerHint": self.layer_hint,
            "reasons": self.reasons,
            "metrics": metrics_to_dict(self.metrics),
        }
        optional = {
            "style": self.style,
            "text": self.text,
            "assetPath": self.asset_path,
            "maskPath": self.mask_path,
            "parentId": self.parent_id,
            "childIds": self.child_ids or None,
        }
        data.update({key: value for key, value in optional.items() if value is not None})
        return data


@dataclass(frozen=True)
class M29BlockedPrimitive:
    id: str
    bbox: list[int]
    source: str
    reasons: list[str]
    metrics: M29PrimitiveMetrics | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "bbox": self.bbox,
            "source": self.source,
            "reasons": self.reasons,
        }
        if self.metrics is not None:
            data["metrics"] = metrics_to_dict(self.metrics)
        return data


@dataclass(frozen=True)
class M29PrimitiveRelation:
    parent_id: str
    child_id: str
    type: M29RelationType
    confidence: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parentId": self.parent_id,
            "childId": self.child_id,
            "type": self.type,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class M29VisualPrimitiveOptions:
    min_component_area: int = 16
    max_component_area_ratio: float = 0.25
    min_shape_area: int = 64
    shape_texture_threshold: float = 0.12
    shape_color_threshold: int = 10
    line_max_thickness: int = 4
    line_min_length: int = 20
    min_image_area: int = 1200
    image_color_threshold: int = 32
    image_texture_threshold: float = 0.18
    image_accept_threshold: float = 0.78
    image_protection_padding: int = 2
    symbol_min_area: int = 16
    symbol_max_area: int = 12000
    symbol_texture_threshold: float = 0.20
    symbol_color_threshold: int = 24
    text_padding: int = 2
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M29ConnectedComponent:
    id: str
    bbox: list[int]
    area: int
    centroid: tuple[float, float]
    fill_ratio: float
    metrics: M29PrimitiveMetrics
    source: str


@dataclass(frozen=True)
class M29DebugArtifacts:
    text_exclusion: str | None = None
    initial_components: str | None = None
    shapes: str | None = None
    images: str | None = None
    image_protection: str | None = None
    foreground_mask: str | None = None
    symbols: str | None = None
    final_nodes: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "textExclusion": self.text_exclusion,
                "initialComponents": self.initial_components,
                "shapes": self.shapes,
                "images": self.images,
                "imageProtection": self.image_protection,
                "foregroundMask": self.foreground_mask,
                "symbols": self.symbols,
                "finalNodes": self.final_nodes,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class M29VisualPrimitiveGraphDocument:
    version: str
    source_image: str
    image_size: dict[str, int]
    nodes: list[M29PrimitiveNode]
    relations: list[M29PrimitiveRelation]
    blocked: list[M29BlockedPrimitive]
    debug: M29DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sourceImage": self.source_image,
            "imageSize": self.image_size,
            "nodes": [node.to_dict() for node in self.nodes],
            "relations": [relation.to_dict() for relation in self.relations],
            "blocked": [item.to_dict() for item in self.blocked],
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def metrics_to_dict(metrics: M29PrimitiveMetrics) -> dict[str, Any]:
    return {
        "colorCount": metrics.color_count,
        "textureScore": round(metrics.texture_score, 4),
        "edgeScore": round(metrics.edge_score, 4),
        "fillRatio": round(metrics.fill_ratio, 4),
        "aspectRatio": round(metrics.aspect_ratio, 4),
        "brightness": round(metrics.brightness, 3),
        "meanRgb": list(metrics.mean_rgb),
    }


def bbox_x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def bbox_y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]


def bbox_area(bbox: list[int]) -> int:
    if len(bbox) != 4:
        return 0
    return max(0, bbox[2]) * max(0, bbox[3])


def bbox_intersects(left: list[int], right: list[int]) -> bool:
    return min(bbox_x2(left), bbox_x2(right)) > max(left[0], right[0]) and min(bbox_y2(left), bbox_y2(right)) > max(left[1], right[1])


def bbox_contains(outer: list[int], inner: list[int]) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and bbox_x2(outer) >= bbox_x2(inner) and bbox_y2(outer) >= bbox_y2(inner)


def bbox_iou(left: list[int], right: list[int]) -> float:
    if not bbox_intersects(left, right):
        return 0.0
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(bbox_x2(left), bbox_x2(right))
    y2 = min(bbox_y2(left), bbox_y2(right))
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = bbox_area(left) + bbox_area(right) - intersection
    return intersection / max(1, union)


def bbox_clamp(bbox: list[int], image_width: int, image_height: int) -> list[int] | None:
    if len(bbox) != 4:
        return None
    x1 = max(0, min(image_width, round(bbox[0])))
    y1 = max(0, min(image_height, round(bbox[1])))
    x2 = max(0, min(image_width, round(bbox[0] + bbox[2])))
    y2 = max(0, min(image_height, round(bbox[1] + bbox[3])))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2 - x1, y2 - y1]


def bbox_in_bounds(bbox: list[int], image_width: int, image_height: int) -> bool:
    return len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0 and bbox[0] >= 0 and bbox[1] >= 0 and bbox_x2(bbox) <= image_width and bbox_y2(bbox) <= image_height


def mask_empty(width: int, height: int) -> M29BinaryMask:
    return M29BinaryMask(width=width, height=height, data=bytes(width * height))


def mask_from_bboxes(width: int, height: int, bboxes: list[list[int]]) -> M29BinaryMask:
    data = bytearray(width * height)
    for bbox in bboxes:
        clamped = bbox_clamp(bbox, width, height)
        if clamped is None:
            continue
        x, y, box_width, box_height = clamped
        for row_index in range(y, y + box_height):
            start = row_index * width + x
            data[start : start + box_width] = b"\xff" * box_width
    return M29BinaryMask(width=width, height=height, data=bytes(data))


def mask_get(mask: M29BinaryMask, x: int, y: int) -> bool:
    if x < 0 or y < 0 or x >= mask.width or y >= mask.height:
        return False
    return mask.data[y * mask.width + x] != 0


def mask_union(left: M29BinaryMask, right: M29BinaryMask) -> M29BinaryMask:
    require_same_mask_size(left, right)
    return M29BinaryMask(left.width, left.height, bytes(255 if a or b else 0 for a, b in zip(left.data, right.data, strict=True)))


def mask_subtract(left: M29BinaryMask, right: M29BinaryMask) -> M29BinaryMask:
    require_same_mask_size(left, right)
    return M29BinaryMask(left.width, left.height, bytes(255 if a and not b else 0 for a, b in zip(left.data, right.data, strict=True)))


def mask_intersects_bbox(mask: M29BinaryMask, bbox: list[int]) -> bool:
    clamped = bbox_clamp(bbox, mask.width, mask.height)
    if clamped is None:
        return False
    x, y, width, height = clamped
    for row_index in range(y, y + height):
        start = row_index * mask.width + x
        if any(mask.data[start : start + width]):
            return True
    return False


def mask_to_png(mask: M29BinaryMask) -> bytes:
    validate_mask(mask)
    row = bytes((0, 0, 0))
    rows = []
    for row_index in range(mask.height):
        output = bytearray()
        for value in mask.data[row_index * mask.width : (row_index + 1) * mask.width]:
            output.extend((255, 255, 255) if value else row)
        rows.append(bytes(output))
    return encode_rgb_png(mask.width, mask.height, rows)


def validate_mask(mask: M29BinaryMask) -> None:
    if mask.width <= 0 or mask.height <= 0 or len(mask.data) != mask.width * mask.height:
        raise ValueError("M29 binary mask dimensions do not match data length")


def require_same_mask_size(left: M29BinaryMask, right: M29BinaryMask) -> None:
    validate_mask(left)
    validate_mask(right)
    if left.width != right.width or left.height != right.height:
        raise ValueError("M29 binary mask size mismatch")


def extract_m29_visual_primitive_graph(
    *,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    options: M29VisualPrimitiveOptions | None = None,
    text_boxes: list[M29TextBox] | None = None,
) -> M29VisualPrimitiveGraphDocument:
    options = options or M29VisualPrimitiveOptions()
    image = read_png_metadata(png_data)
    if image is None:
        raise UnsupportedPngCropError("M29 source image is not a readable PNG.")
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    texts = build_text_nodes(text_boxes or [], pixels, options)
    text_mask = build_text_exclusion_mask(pixels.width, pixels.height, text_boxes or [], options.text_padding)
    base_foreground = build_global_foreground_mask(pixels, text_mask)
    initial_components = connected_components(
        base_foreground,
        pixels,
        min_area=options.min_component_area,
        max_area_ratio=max(options.max_component_area_ratio, 0.80),
    )
    shapes = detect_shapes(initial_components, pixels, image, options)
    images, unknown_images = detect_images(initial_components, pixels, text_mask, shapes, options)
    image_mask = build_image_protection_mask(pixels.width, pixels.height, images, options.image_protection_padding)
    foreground = build_remaining_foreground_mask(pixels, text_mask, image_mask, shapes)
    remaining_components = connected_components(
        foreground,
        pixels,
        min_area=options.min_component_area,
        max_area_ratio=options.max_component_area_ratio,
    )
    symbols, blocked = detect_symbols(remaining_components, pixels, text_mask, image_mask, shapes, options)
    blocked.extend(blocked_inside_images([*initial_components, *remaining_components], images))

    nodes = stable_sort_nodes([*texts, *shapes, *images, *symbols, *unknown_images])
    nodes = export_node_assets(nodes, pixels, output_dir)
    relations = build_containment_relations(nodes)
    nodes = attach_relation_children(nodes, relations)
    debug = write_debug_overlays(
        pixels=pixels,
        output_dir=output_dir,
        text_mask=text_mask,
        initial_components=initial_components,
        shapes=shapes,
        images=images,
        image_mask=image_mask,
        foreground=foreground,
        symbols=symbols,
        nodes=nodes,
        blocked=blocked,
    )
    preview_path = output_dir / "preview_sheet.png"
    preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug))

    document = M29VisualPrimitiveGraphDocument(
        version="0.1",
        source_image=source_image,
        image_size={"width": image.width, "height": image.height},
        nodes=nodes,
        relations=relations,
        blocked=blocked,
        debug=debug,
        warnings=[],
        meta=build_meta(nodes, blocked, options),
    )
    validate_m29_document(document, output_dir)
    (output_dir / "nodes.json").write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return document


def build_text_nodes(text_boxes: list[M29TextBox], pixels: PngPixels, options: M29VisualPrimitiveOptions) -> list[M29PrimitiveNode]:
    nodes: list[M29PrimitiveNode] = []
    for index, item in enumerate(text_boxes):
        bbox = bbox_clamp(pad_bbox(item.bbox, options.text_padding), pixels.width, pixels.height)
        if bbox is None:
            continue
        nodes.append(
            M29PrimitiveNode(
                id=f"text_{index + 1:03d}",
                type="text",
                subtype=item.kind,
                bbox=bbox,
                confidence=clamp_float(item.confidence, 0, 1),
                source=item.source,
                source_order=index,
                layer_hint="content",
                reasons=["text_box"],
                metrics=measure_region(pixels, bbox),
                text=item.text,
            )
        )
    return nodes


def build_text_exclusion_mask(width: int, height: int, text_boxes: list[M29TextBox], padding: int) -> M29BinaryMask:
    return mask_from_bboxes(width, height, [pad_bbox(item.bbox, padding) for item in text_boxes])


def build_global_foreground_mask(pixels: PngPixels, exclusion: M29BinaryMask) -> M29BinaryMask:
    background = estimate_global_background(pixels)
    data = bytearray(pixels.width * pixels.height)
    for row_index, row in enumerate(pixels.rows):
        for column in range(pixels.width):
            index = row_index * pixels.width + column
            if exclusion.data[index]:
                continue
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            if color_distance(rgb, background) > 42 and not near_white(rgb):
                data[index] = 255
    return M29BinaryMask(pixels.width, pixels.height, bytes(data))


def estimate_global_background(pixels: PngPixels) -> tuple[int, int, int]:
    samples: list[tuple[int, int, int]] = []
    points = [
        (0, 0),
        (pixels.width - 1, 0),
        (0, pixels.height - 1),
        (pixels.width - 1, pixels.height - 1),
        (pixels.width // 2, 0),
        (pixels.width // 2, pixels.height - 1),
    ]
    for x, y in points:
        row = pixels.rows[max(0, min(pixels.height - 1, y))]
        offset = max(0, min(pixels.width - 1, x)) * 3
        samples.append((row[offset], row[offset + 1], row[offset + 2]))
    return tuple(round(sum(sample[channel] for sample in samples) / len(samples)) for channel in range(3))


def connected_components(mask: M29BinaryMask, pixels: PngPixels, *, min_area: int, max_area_ratio: float) -> list[M29ConnectedComponent]:
    validate_mask(mask)
    visited = bytearray(len(mask.data))
    components: list[M29ConnectedComponent] = []
    max_area = max(1, round(mask.width * mask.height * max_area_ratio))
    for index, value in enumerate(mask.data):
        if not value or visited[index]:
            continue
        stack = [index]
        visited[index] = 1
        area = 0
        x_sum = 0
        y_sum = 0
        min_x = mask.width
        min_y = mask.height
        max_x = 0
        max_y = 0
        while stack:
            current = stack.pop()
            y, x = divmod(current, mask.width)
            area += 1
            x_sum += x
            y_sum += y
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            for ny in range(max(0, y - 1), min(mask.height, y + 2)):
                for nx in range(max(0, x - 1), min(mask.width, x + 2)):
                    neighbor = ny * mask.width + nx
                    if not visited[neighbor] and mask.data[neighbor]:
                        visited[neighbor] = 1
                        stack.append(neighbor)
        if area < min_area or area > max_area:
            continue
        bbox = [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]
        metrics = measure_region(pixels, bbox, fill_ratio=area / max(1, bbox_area(bbox)))
        components.append(
            M29ConnectedComponent(
                id=f"component_{len(components) + 1:03d}",
                bbox=bbox,
                area=area,
                centroid=(round(x_sum / area, 3), round(y_sum / area, 3)),
                fill_ratio=round(area / max(1, bbox_area(bbox)), 4),
                metrics=metrics,
                source="connected_component",
            )
        )
    return components


def measure_region(pixels: PngPixels, bbox: list[int], *, fill_ratio: float | None = None) -> M29PrimitiveMetrics:
    clamped = bbox_clamp(bbox, pixels.width, pixels.height)
    if clamped is None:
        return M29PrimitiveMetrics(0, 0, 0, 0, 0, 0, (0, 0, 0))
    x, y, width, height = clamped
    step = max(1, round((width * height / 4096) ** 0.5))
    buckets: dict[tuple[int, int, int], int] = {}
    samples = 0
    red_sum = green_sum = blue_sum = 0
    texture_total = 0
    edge_hits = 0
    edge_checks = 0
    for row_index in range(y, y + height, step):
        row = pixels.rows[row_index]
        next_row = pixels.rows[min(pixels.height - 1, row_index + step)]
        for column in range(x, x + width, step):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            red_sum += rgb[0]
            green_sum += rgb[1]
            blue_sum += rgb[2]
            buckets[(rgb[0] // 16, rgb[1] // 16, rgb[2] // 16)] = buckets.get((rgb[0] // 16, rgb[1] // 16, rgb[2] // 16), 0) + 1
            samples += 1
            if column + step < pixels.width:
                neighbor_offset = (column + step) * 3
                diff = color_distance(rgb, (row[neighbor_offset], row[neighbor_offset + 1], row[neighbor_offset + 2]))
                texture_total += diff
                edge_checks += 1
                edge_hits += 1 if diff > 48 else 0
            if row_index + step < pixels.height:
                diff = color_distance(rgb, (next_row[offset], next_row[offset + 1], next_row[offset + 2]))
                texture_total += diff
                edge_checks += 1
                edge_hits += 1 if diff > 48 else 0
    samples = max(1, samples)
    mean_rgb = (round(red_sum / samples), round(green_sum / samples), round(blue_sum / samples))
    dominant = max(buckets.values()) if buckets else 0
    dominant_ratio = dominant / samples
    return M29PrimitiveMetrics(
        color_count=len(buckets),
        texture_score=round((texture_total / max(1, edge_checks)) / 255, 4),
        edge_score=round(edge_hits / max(1, edge_checks), 4),
        fill_ratio=round(fill_ratio if fill_ratio is not None else dominant_ratio, 4),
        aspect_ratio=round(width / max(1, height), 4),
        brightness=round(mean_rgb[0] * 0.299 + mean_rgb[1] * 0.587 + mean_rgb[2] * 0.114, 3),
        mean_rgb=mean_rgb,
    )


def detect_shapes(
    components: list[M29ConnectedComponent],
    pixels: PngPixels,
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> list[M29PrimitiveNode]:
    nodes: list[M29PrimitiveNode] = []
    for component in components:
        bbox = component.bbox
        metrics = component.metrics
        area = bbox_area(bbox)
        subtype: str | None = None
        confidence = 0.0
        reasons: list[str] = []
        if is_line_like(bbox, metrics, options):
            subtype = "separator"
            confidence = 0.86
            reasons = ["line_like", "low_texture"]
        elif is_ellipse_like(component, pixels, options):
            subtype = "badge_background" if area < 3200 else "small_ellipse"
            confidence = 0.78
            reasons = ["ellipse_like", "corner_background_like"]
        elif is_rect_like(component, options):
            subtype = rect_subtype(bbox, image)
            confidence = 0.82
            reasons = ["solid_fill", "low_texture", "rect_like"]
        if subtype is None:
            continue
        nodes.append(
            M29PrimitiveNode(
                id=f"shape_{len(nodes) + 1:03d}",
                type="shape",
                subtype=subtype,
                bbox=bbox,
                confidence=confidence,
                source="shape_detector",
                source_order=len(nodes),
                layer_hint=shape_layer_hint(subtype),
                reasons=reasons,
                metrics=metrics,
                style={"fill": rgb_to_hex(metrics.mean_rgb), **({"radius": rough_radius(bbox)} if subtype not in {"separator"} else {})},
            )
        )
    return nodes


def detect_images(
    components: list[M29ConnectedComponent],
    pixels: PngPixels,
    text_mask: M29BinaryMask,
    shapes: list[M29PrimitiveNode],
    options: M29VisualPrimitiveOptions,
) -> tuple[list[M29PrimitiveNode], list[M29PrimitiveNode]]:
    images: list[M29PrimitiveNode] = []
    unknowns: list[M29PrimitiveNode] = []
    protective = [node for node in shapes if is_protective_shape(node)]
    for component in components:
        if any(bbox_iou(component.bbox, shape.bbox) > 0.72 for shape in shapes):
            continue
        text_overlap = mask_bbox_overlap_ratio(text_mask, component.bbox)
        shape_overlap = max((bbox_iou(component.bbox, shape.bbox) for shape in protective), default=0.0)
        candidate_confidence = score_image_candidate(component, text_overlap, shape_overlap, options)
        if candidate_confidence >= options.image_accept_threshold:
            images.append(
                M29PrimitiveNode(
                    id=f"image_{len(images) + 1:03d}",
                    type="image",
                    subtype="bitmap_candidate",
                    bbox=component.bbox,
                    confidence=candidate_confidence,
                    source="image_detector",
                    source_order=len(images),
                    layer_hint="content",
                    reasons=["high_color_count", "texture_rich", "conservative_image_accept"],
                    metrics=component.metrics,
                )
            )
        elif component.area >= options.min_image_area and component.metrics.color_count >= options.image_color_threshold:
            unknowns.append(
                M29PrimitiveNode(
                    id=f"unknown_{len(unknowns) + 1:03d}",
                    type="unknown",
                    subtype="image_like_low_confidence",
                    bbox=component.bbox,
                    confidence=round(candidate_confidence, 3),
                    source="image_detector",
                    source_order=len(unknowns),
                    layer_hint="unknown",
                    reasons=["image_confidence_below_threshold"],
                    metrics=component.metrics,
                )
            )
    return images, unknowns


def build_image_protection_mask(width: int, height: int, images: list[M29PrimitiveNode], padding: int) -> M29BinaryMask:
    return mask_from_bboxes(width, height, [pad_bbox(node.bbox, padding) for node in images])


def build_remaining_foreground_mask(
    pixels: PngPixels,
    text_mask: M29BinaryMask,
    image_mask: M29BinaryMask,
    shapes: list[M29PrimitiveNode],
) -> M29BinaryMask:
    exclusion = mask_union(text_mask, image_mask)
    protective = mask_from_bboxes(pixels.width, pixels.height, [node.bbox for node in shapes if is_protective_shape(node)])
    exclusion = mask_union(exclusion, protective)
    foreground = mask_subtract(build_global_foreground_mask(pixels, mask_empty(pixels.width, pixels.height)), exclusion)
    data = bytearray(foreground.data)
    for shape in shapes:
        if is_protective_shape(shape):
            continue
        add_internal_contrast_pixels(data, pixels, shape, text_mask, image_mask)
    return M29BinaryMask(pixels.width, pixels.height, bytes(data))


def detect_symbols(
    components: list[M29ConnectedComponent],
    pixels: PngPixels,
    text_mask: M29BinaryMask,
    image_mask: M29BinaryMask,
    shapes: list[M29PrimitiveNode],
    options: M29VisualPrimitiveOptions,
) -> tuple[list[M29PrimitiveNode], list[M29BlockedPrimitive]]:
    symbols: list[M29PrimitiveNode] = []
    blocked: list[M29BlockedPrimitive] = []
    for component in components:
        reasons: list[str] = []
        if mask_intersects_bbox(text_mask, component.bbox):
            reasons.append("text_overlap")
        if mask_intersects_bbox(image_mask, component.bbox):
            reasons.append("inside_image_primitive")
        if any(bbox_iou(component.bbox, shape.bbox) > 0.70 and is_protective_shape(shape) for shape in shapes):
            reasons.append("protective_shape_overlap")
        if component.area < options.symbol_min_area or bbox_area(component.bbox) > options.symbol_max_area:
            reasons.append("symbol_area_out_of_range")
        if is_line_like(component.bbox, component.metrics, options):
            reasons.append("line_like")
        if reasons:
            blocked.append(M29BlockedPrimitive(f"blocked_{len(blocked) + 1:03d}", component.bbox, "symbol_detector", reasons, component.metrics))
            continue
        if component.metrics.color_count <= options.symbol_color_threshold or component.metrics.texture_score <= options.symbol_texture_threshold:
            symbols.append(
                M29PrimitiveNode(
                    id=f"symbol_{len(symbols) + 1:03d}",
                    type="symbol",
                    subtype="icon_candidate",
                    bbox=component.bbox,
                    confidence=score_symbol_candidate(component, options),
                    source="symbol_detector",
                    source_order=len(symbols),
                    layer_hint="overlay" if is_overlay_sized(component.bbox) else "content",
                    reasons=["small_visual", "non_text", "non_image"],
                    metrics=component.metrics,
                )
            )
        else:
            blocked.append(M29BlockedPrimitive(f"blocked_{len(blocked) + 1:03d}", component.bbox, "symbol_detector", ["symbol_metrics_rejected"], component.metrics))
    return symbols, blocked


def blocked_inside_images(components: list[M29ConnectedComponent], images: list[M29PrimitiveNode]) -> list[M29BlockedPrimitive]:
    blocked: list[M29BlockedPrimitive] = []
    for component in components:
        if any(bbox_contains(image.bbox, component.bbox) and bbox_iou(image.bbox, component.bbox) < 0.95 for image in images):
            if any(existing.bbox == component.bbox for existing in blocked):
                continue
            blocked.append(M29BlockedPrimitive(f"blocked_image_internal_{len(blocked) + 1:03d}", component.bbox, "image_protection", ["inside_image_primitive"], component.metrics))
    return blocked


def build_containment_relations(nodes: list[M29PrimitiveNode]) -> list[M29PrimitiveRelation]:
    relations: list[M29PrimitiveRelation] = []
    containers = [node for node in nodes if node.type == "shape" and node.layer_hint in {"background", "container"}]
    children = [node for node in nodes if node.type in {"text", "image", "symbol"}]
    for child in children:
        parents = [container for container in containers if bbox_contains(container.bbox, child.bbox) and container.id != child.id]
        if not parents:
            continue
        parent = min(parents, key=lambda item: bbox_area(item.bbox))
        relations.append(M29PrimitiveRelation(parent.id, child.id, "contains", 0.72, ["bbox_contains"]))
    return relations


def attach_relation_children(nodes: list[M29PrimitiveNode], relations: list[M29PrimitiveRelation]) -> list[M29PrimitiveNode]:
    by_id = {node.id: node for node in nodes}
    children: dict[str, list[str]] = {}
    parent: dict[str, str] = {}
    for relation in relations:
        if relation.type == "contains":
            children.setdefault(relation.parent_id, []).append(relation.child_id)
            parent[relation.child_id] = relation.parent_id
    return [replace(node, parent_id=parent.get(node.id), child_ids=sorted(children.get(node.id, []))) for node in nodes]


def stable_sort_nodes(nodes: list[M29PrimitiveNode]) -> list[M29PrimitiveNode]:
    sorted_nodes = sorted(nodes, key=lambda item: (LAYER_ORDER[item.layer_hint], item.bbox[1], item.bbox[0], bbox_area(item.bbox)))
    return [replace(node, source_order=index) for index, node in enumerate(sorted_nodes)]


def export_node_assets(nodes: list[M29PrimitiveNode], pixels: PngPixels, output_dir: Path) -> list[M29PrimitiveNode]:
    image_dir = output_dir / "assets" / "images"
    symbol_dir = output_dir / "assets" / "symbols"
    image_dir.mkdir(parents=True, exist_ok=True)
    symbol_dir.mkdir(parents=True, exist_ok=True)
    image_count = 0
    symbol_count = 0
    exported: list[M29PrimitiveNode] = []
    for node in nodes:
        if node.type == "image":
            image_count += 1
            path = image_dir / f"image_{image_count:03d}.png"
            path.write_bytes(crop_pixels(pixels, node.bbox))
            exported.append(replace(node, asset_path=str(path.relative_to(output_dir))))
        elif node.type == "symbol":
            symbol_count += 1
            path = symbol_dir / f"symbol_{symbol_count:03d}.png"
            path.write_bytes(crop_pixels(pixels, node.bbox))
            exported.append(replace(node, asset_path=str(path.relative_to(output_dir))))
        else:
            exported.append(node)
    return exported


def crop_pixels(pixels: PngPixels, bbox: list[int]) -> bytes:
    clamped = bbox_clamp(bbox, pixels.width, pixels.height)
    if clamped is None:
        raise UnsupportedPngCropError("M29 crop bbox is invalid.")
    x, y, width, height = clamped
    rows = [pixels.rows[row_index][x * 3 : (x + width) * 3] for row_index in range(y, y + height)]
    return encode_rgb_png(width, height, rows)


def write_debug_overlays(
    *,
    pixels: PngPixels,
    output_dir: Path,
    text_mask: M29BinaryMask,
    initial_components: list[M29ConnectedComponent],
    shapes: list[M29PrimitiveNode],
    images: list[M29PrimitiveNode],
    image_mask: M29BinaryMask,
    foreground: M29BinaryMask,
    symbols: list[M29PrimitiveNode],
    nodes: list[M29PrimitiveNode],
    blocked: list[M29BlockedPrimitive],
) -> M29DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "text_exclusion": overlay_dir / "01_text_exclusion.png",
        "initial_components": overlay_dir / "02_initial_components.png",
        "shapes": overlay_dir / "03_shapes.png",
        "images": overlay_dir / "04_images.png",
        "image_protection": overlay_dir / "05_image_protection.png",
        "foreground_mask": overlay_dir / "06_foreground_mask.png",
        "symbols": overlay_dir / "07_symbols.png",
        "final_nodes": overlay_dir / "08_final_nodes.png",
    }
    paths["text_exclusion"].write_bytes(mask_to_png(text_mask))
    paths["initial_components"].write_bytes(overlay_components(pixels, initial_components))
    paths["shapes"].write_bytes(overlay_nodes(pixels, shapes, []))
    paths["images"].write_bytes(overlay_nodes(pixels, images, []))
    paths["image_protection"].write_bytes(mask_to_png(image_mask))
    paths["foreground_mask"].write_bytes(mask_to_png(foreground))
    paths["symbols"].write_bytes(overlay_nodes(pixels, symbols, blocked))
    paths["final_nodes"].write_bytes(overlay_nodes(pixels, nodes, blocked))
    return M29DebugArtifacts(**{key: str(path.relative_to(output_dir)) for key, path in paths.items()})


def overlay_components(pixels: PngPixels, components: list[M29ConnectedComponent]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for component in components:
        draw_rect(rows, pixels.width, pixels.height, component.bbox, (238, 190, 40), 1)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_nodes(pixels: PngPixels, nodes: list[M29PrimitiveNode], blocked: list[M29BlockedPrimitive]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in blocked:
        color = OVERLAY_COLORS["protected"] if "inside_image_primitive" in item.reasons else OVERLAY_COLORS["blocked"]
        draw_rect(rows, pixels.width, pixels.height, item.bbox, color, 1)
    for node in nodes:
        draw_rect(rows, pixels.width, pixels.height, node.bbox, OVERLAY_COLORS[node.type], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(pixels: PngPixels, output_dir: Path, debug: M29DebugArtifacts) -> bytes:
    final_overlay = decode_png_pixels((output_dir / (debug.final_nodes or "overlays/08_final_nodes.png")).read_bytes())
    image_previews = crop_previews(output_dir / "assets" / "images", 160)
    symbol_previews = crop_previews(output_dir / "assets" / "symbols", 96)
    sheet_width = 1400
    margin = 24
    gap = 18
    source_scale = min(0.55, (sheet_width - margin * 2 - gap) / max(1, pixels.width * 2))
    source_w = max(1, round(pixels.width * source_scale))
    source_h = max(1, round(pixels.height * source_scale))
    sheet_height = source_h + grid_height(image_previews, sheet_width, margin, gap) + grid_height(symbol_previews, sheet_width, margin, gap) + margin * 6
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    y = margin
    paste_scaled(canvas, sheet_width, pixels, margin, y, source_w, source_h)
    paste_scaled(canvas, sheet_width, final_overlay, margin + source_w + gap, y, source_w, source_h)
    y += source_h + margin
    y = paste_grid(canvas, sheet_width, image_previews, margin, y, gap) + margin
    paste_grid(canvas, sheet_width, symbol_previews, margin, y, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews(path: Path, max_edge: int) -> list[tuple[PngPixels, int, int]]:
    previews: list[tuple[PngPixels, int, int]] = []
    if not path.exists():
        return previews
    for item in sorted(path.glob("*.png")):
        try:
            pixels = decode_png_pixels(item.read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews


def grid_height(previews: list[tuple[PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 70
    x = margin
    row_h = 0
    total = 0
    for _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[PngPixels, int, int]], margin: int, y: int, gap: int) -> int:
    if not previews:
        fill_rect(canvas, sheet_width, y, margin, sheet_width - margin * 2, 48, (232, 232, 232))
        return y + 48
    x = margin
    row_h = 0
    for preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, y - 3, x - 3, width + 6, height + 6, (232, 232, 232))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]


def fill_rect(canvas: list[bytearray], sheet_width: int, y: int, x: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def validate_m29_document(document: M29VisualPrimitiveGraphDocument, output_dir: Path) -> None:
    if document.version != "0.1":
        raise ValueError("M29 document version must be 0.1")
    width = int(document.image_size.get("width", 0))
    height = int(document.image_size.get("height", 0))
    seen: set[str] = set()
    orders: set[int] = set()
    for node in document.nodes:
        if node.id in seen:
            raise ValueError(f"duplicate M29 node id: {node.id}")
        seen.add(node.id)
        if node.source_order in orders:
            raise ValueError(f"duplicate M29 source_order: {node.source_order}")
        orders.add(node.source_order)
        if not bbox_in_bounds(node.bbox, width, height):
            raise ValueError(f"M29 node bbox out of bounds: {node.id}")
        if node.asset_path is not None:
            assert_readable_relative_png(output_dir, node.asset_path)
        if node.mask_path is not None:
            assert_readable_relative_png(output_dir, node.mask_path)
    for relation in document.relations:
        if relation.parent_id not in seen or relation.child_id not in seen:
            raise ValueError("M29 relation references a missing node")
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29 PNG output missing or unreadable: {path}")


def build_meta(nodes: list[M29PrimitiveNode], blocked: list[M29BlockedPrimitive], options: M29VisualPrimitiveOptions) -> dict[str, Any]:
    counts = {"text": 0, "shape": 0, "image": 0, "symbol": 0, "unknown": 0, "blocked": len(blocked)}
    for node in nodes:
        counts[node.type] += 1
    return {"notes": "m29_visual_primitive_graph_harness", "counts": counts, "options": options.to_dict()}


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


def is_ellipse_like(component: M29ConnectedComponent, pixels: PngPixels, options: M29VisualPrimitiveOptions) -> bool:
    bbox = component.bbox
    ratio = bbox[2] / max(1, bbox[3])
    if not (0.65 <= ratio <= 1.55 and 0.45 <= component.fill_ratio <= 0.90 and component.area >= options.min_shape_area and component.area < 10000):
        return False
    x, y, width, height = bbox
    corners = [(x, y), (x + width - 1, y), (x, y + height - 1), (x + width - 1, y + height - 1)]
    corner_distances = []
    for column, row_index in corners:
        row = pixels.rows[row_index]
        offset = column * 3
        corner_distances.append(color_distance((row[offset], row[offset + 1], row[offset + 2]), component.metrics.mean_rgb))
    return sum(1 for distance in corner_distances if distance > 24) >= 2


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
    if subtype in {"badge_background", "small_ellipse", "small_rounded_rect", "icon_button_background"}:
        return "overlay"
    return "container"


def is_protective_shape(node: M29PrimitiveNode) -> bool:
    return node.subtype in {"background", "card_background", "search_field_background", "large_container", "separator"}


def score_image_candidate(component: M29ConnectedComponent, text_overlap: float, shape_overlap: float, options: M29VisualPrimitiveOptions) -> float:
    if component.area < options.min_image_area or text_overlap > 0.08 or shape_overlap > 0.35:
        return 0.0
    score = 0.45
    if component.metrics.color_count >= options.image_color_threshold:
        score += 0.18
    if component.metrics.texture_score >= options.image_texture_threshold:
        score += 0.20
    if component.fill_ratio >= 0.70:
        score += 0.08
    if component.metrics.edge_score >= 0.08:
        score += 0.07
    return round(min(score, 0.98), 3)


def score_symbol_candidate(component: M29ConnectedComponent, options: M29VisualPrimitiveOptions) -> float:
    score = 0.58
    if component.area >= options.symbol_min_area:
        score += 0.08
    if component.metrics.color_count <= options.symbol_color_threshold:
        score += 0.14
    if component.metrics.texture_score <= options.symbol_texture_threshold:
        score += 0.12
    if 0.18 <= component.fill_ratio <= 1.0:
        score += 0.05
    return round(min(score, 0.96), 3)


def is_overlay_sized(bbox: list[int]) -> bool:
    return bbox_area(bbox) <= 3200 and max(bbox[2], bbox[3]) <= 80


def mask_bbox_overlap_ratio(mask: M29BinaryMask, bbox: list[int]) -> float:
    clamped = bbox_clamp(bbox, mask.width, mask.height)
    if clamped is None:
        return 0.0
    x, y, width, height = clamped
    hits = 0
    for row_index in range(y, y + height):
        start = row_index * mask.width + x
        hits += sum(1 for value in mask.data[start : start + width] if value)
    return hits / max(1, width * height)


def add_internal_contrast_pixels(data: bytearray, pixels: PngPixels, shape: M29PrimitiveNode, text_mask: M29BinaryMask, image_mask: M29BinaryMask) -> None:
    x, y, width, height = shape.bbox
    fill = tuple(int(str(shape.style.get("fill", "#000000"))[index : index + 2], 16) for index in (1, 3, 5)) if shape.style and shape.style.get("fill") else shape.metrics.mean_rgb
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        for column in range(x, x + width):
            index = row_index * pixels.width + column
            if text_mask.data[index] or image_mask.data[index]:
                continue
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            if color_distance(rgb, fill) > 80:
                data[index] = 255


def pad_bbox(bbox: list[int], padding: int) -> list[int]:
    return [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2]


def rough_radius(bbox: list[int]) -> int:
    return max(0, min(bbox[2], bbox[3]) // 8)


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1]) + abs(left[2] - right[2])


def near_white(rgb: tuple[int, int, int]) -> bool:
    return rgb[0] >= 245 and rgb[1] >= 245 and rgb[2] >= 245


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, value)):02X}" for value in rgb)


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def draw_rect(rows: list[bytearray], image_width: int, image_height: int, bbox: list[int], color: tuple[int, int, int], thickness: int) -> None:
    clamped = bbox_clamp(bbox, image_width, image_height)
    if clamped is None:
        return
    x, y, width, height = clamped
    color_bytes = bytes(color)
    for row_index in range(y, y + height):
        if row_index < y + thickness or row_index >= y + height - thickness:
            for column in range(x, x + width):
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes
        else:
            for column in list(range(x, min(x + thickness, x + width))) + list(range(max(x, x + width - thickness), x + width)):
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes
