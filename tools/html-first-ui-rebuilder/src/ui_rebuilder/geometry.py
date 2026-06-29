from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @staticmethod
    def from_dict(value: dict[str, Any]) -> "BBox":
        return BBox(
            x=int(round(value["x"])),
            y=int(round(value["y"])),
            width=int(round(value["width"])),
            height=int(round(value["height"])),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    def clamp(self, image_width: int, image_height: int) -> "BBox":
        x = max(0, min(self.x, image_width))
        y = max(0, min(self.y, image_height))
        right = max(x, min(self.x + self.width, image_width))
        bottom = max(y, min(self.y + self.height, image_height))
        return BBox(x=x, y=y, width=right - x, height=bottom - y)

    def inset(self, value: int, image_width: int, image_height: int) -> "BBox":
        return BBox(
            self.x - value,
            self.y - value,
            self.width + value * 2,
            self.height + value * 2,
        ).clamp(image_width, image_height)

    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)
