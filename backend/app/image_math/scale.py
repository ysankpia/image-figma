from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Any


DEFAULT_TEXT_UNIT_PX = 14.0


@dataclass(frozen=True)
class ImageScaleProfile:
    text_unit_px: float
    fallback_unit_px: float
    scale_basis_px: float
    source: str
    text_sample_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("text_unit_px", "fallback_unit_px", "scale_basis_px"):
            payload[key] = round(float(payload[key]), 4)
        return payload

    @property
    def factor(self) -> float:
        return max(0.5, min(6.0, self.scale_basis_px / DEFAULT_TEXT_UNIT_PX))

    def length(self, value_1x: float, *, minimum: int = 1, maximum: int | None = None) -> int:
        value = int(round(value_1x * self.factor))
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def area(self, value_1x: float, *, minimum: int = 1, maximum: int | None = None) -> int:
        value = int(round(value_1x * self.factor * self.factor))
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value


def build_scale_profile(
    *,
    image_size: dict[str, Any] | None = None,
    ocr_blocks: list[dict[str, Any]] | None = None,
    source_objects: list[dict[str, Any]] | None = None,
) -> ImageScaleProfile:
    text_heights = regular_text_heights(ocr_blocks or [])
    fallback = fallback_unit_px(image_size or {}, source_objects or [])
    if text_heights:
        text_unit = float(median(text_heights))
        basis = robust_average(text_unit, fallback)
        source = "ocr_text_height_plus_image_fallback"
    else:
        text_unit = 0.0
        basis = fallback
        source = "image_fallback"
    return ImageScaleProfile(
        text_unit_px=text_unit,
        fallback_unit_px=fallback,
        scale_basis_px=max(8.0, min(64.0, basis)),
        source=source,
        text_sample_count=len(text_heights),
    )


def regular_text_heights(blocks: list[dict[str, Any]]) -> list[float]:
    heights: list[float] = []
    for block in blocks:
        bbox = block.get("bbox") if isinstance(block, dict) else getattr(block, "bbox", None)
        raw_confidence = block.get("confidence") if isinstance(block, dict) else getattr(block, "confidence", 1.0)
        confidence = float_value(raw_confidence, default=1.0)
        if not isinstance(bbox, list) or len(bbox) != 4 or confidence < 0.5:
            continue
        try:
            height = float(bbox[3])
            width = float(bbox[2])
        except (TypeError, ValueError):
            continue
        if height <= 0 or width <= 0:
            continue
        aspect = width / max(1.0, height)
        if height < 6 or height > 96 or aspect > 18.0:
            continue
        heights.append(height)
    return heights


def fallback_unit_px(image_size: dict[str, Any], source_objects: list[dict[str, Any]]) -> float:
    image_width = int_value(image_size.get("width"))
    image_height = int_value(image_size.get("height"))
    positive_edges = [value for value in [image_width, image_height] if value > 0]
    short_edge = min(positive_edges) if positive_edges else 0
    image_based = max(10.0, min(28.0, short_edge / 28.0)) if short_edge > 0 else DEFAULT_TEXT_UNIT_PX
    object_heights: list[float] = []
    for item in source_objects:
        bbox = item.get("bbox") if isinstance(item, dict) else getattr(item, "bbox", None)
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            height = float(bbox[3])
            width = float(bbox[2])
        except (TypeError, ValueError):
            continue
        max_object_unit = max(32.0, image_based * 4.0)
        if 6 <= height <= max_object_unit and width > 0:
            object_heights.append(height)
    if not object_heights:
        return image_based
    return robust_average(float(median(object_heights)), image_based)


def robust_average(primary: float, fallback: float) -> float:
    if primary <= 0:
        return fallback
    if fallback <= 0:
        return primary
    low = min(primary, fallback)
    high = max(primary, fallback)
    if high / max(1.0, low) > 2.2:
        return primary * 0.75 + fallback * 0.25
    return (primary + fallback) / 2.0


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def float_value(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
