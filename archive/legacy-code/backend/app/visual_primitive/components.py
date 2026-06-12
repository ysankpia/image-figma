from __future__ import annotations

from ..png_tools import PngPixels
from .bbox import bbox_area, pad_bbox
from .mask import mask_empty, mask_from_bboxes, mask_subtract, mask_union, validate_mask
from .metrics import color_distance, measure_region, near_white
from .types import M29BinaryMask, M29ConnectedComponent, M29PrimitiveNode, M29TextBox


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
        pts = []
        while stack:
            current = stack.pop()
            y, x = divmod(current, mask.width)
            pts.append((x, y))
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
        x_start, y_start, w, h = bbox
        local_mask = bytearray(w * h)
        for px, py in pts:
            local_mask[(py - y_start) * w + (px - x_start)] = 255
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
                mask_data=bytes(local_mask),
            )
        )
    return components


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


def is_protective_shape(node: M29PrimitiveNode) -> bool:
    return node.subtype in {"background", "card_background", "search_field_background", "low_contrast_support", "text_support_background", "large_container", "separator"}


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
