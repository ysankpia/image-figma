from __future__ import annotations

from pathlib import Path

from PIL import Image

from .schema import DraftElement


def crop_image_assets(
    image: Image.Image,
    elements: list[DraftElement],
    output_dir: str,
) -> dict[str, str]:
    assets_dir = Path(output_dir) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    asset_map: dict[str, str] = {}
    for element in elements:
        if element.type != "image":
            continue
        x1 = max(0, element.bbox.x)
        y1 = max(0, element.bbox.y)
        x2 = min(image.width, element.bbox.x2)
        y2 = min(image.height, element.bbox.y2)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        filename = f"{element.id}.png"
        image.crop((x1, y1, x2, y2)).save(assets_dir / filename)
        asset_map[element.id] = filename
    return asset_map
