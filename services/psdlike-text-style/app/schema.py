from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


def bbox_from_dict(value: Any) -> BBox | None:
    if not isinstance(value, dict):
        return None
    try:
        box = BBox(int(value["x"]), int(value["y"]), int(value["width"]), int(value["height"]))
    except (KeyError, TypeError, ValueError):
        return None
    if box.width <= 0 or box.height <= 0:
        return None
    return box


def clamp_box(box: BBox, width: int, height: int) -> BBox | None:
    x1 = max(0, min(width, box.x))
    y1 = max(0, min(height, box.y))
    x2 = max(0, min(width, box.x2))
    y2 = max(0, min(height, box.y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x1, y1, x2 - x1, y2 - y1)
