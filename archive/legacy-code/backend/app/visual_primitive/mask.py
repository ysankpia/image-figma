from __future__ import annotations

from ..png_tools import encode_rgb_png
from .bbox import bbox_clamp, pad_bbox
from .types import M29BinaryMask


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


def mask_bbox_near(mask: M29BinaryMask, bbox: list[int], padding: int) -> bool:
    return mask_intersects_bbox(mask, pad_bbox(bbox, padding))


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

