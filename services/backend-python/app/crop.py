from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from .merge import MergedElement


def crop_elements(
    image: Image.Image,
    elements: list[MergedElement],
    output_dir: str,
) -> dict[str, str]:
    """Crop image regions for non-text elements. Returns {element_index: asset_filename}."""
    assets_dir = Path(output_dir) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    asset_map: dict[str, str] = {}
    for i, el in enumerate(elements):
        if el.type == "text":
            continue
        x1 = max(0, el.x)
        y1 = max(0, el.y)
        x2 = min(image.width, el.x + el.width)
        y2 = min(image.height, el.y + el.height)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        cropped = image.crop((x1, y1, x2, y2))
        filename = f"element_{i:04d}.png"
        cropped.save(assets_dir / filename)
        asset_map[str(i)] = filename

    return asset_map
