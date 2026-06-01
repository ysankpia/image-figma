from __future__ import annotations

from typing import Any

from PIL import Image

from .merge import MergedElement


def build_dsl(
    elements: list[MergedElement],
    asset_map: dict[str, str],
    image: Image.Image,
    task_id: str,
) -> dict[str, Any]:
    """Build DraftRuntimeDSL v1.0 from merged elements."""
    page_w, page_h = image.size
    background = _sample_background(image)

    children: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []

    for i, el in enumerate(elements):
        node_id = f"node_{i:04d}"
        node: dict[str, Any] = {
            "id": node_id,
            "type": el.type,
            "name": el.label or f"{el.role}_{i}",
            "bbox": {"x": el.x, "y": el.y, "width": el.width, "height": el.height},
        }

        if el.type == "text":
            node["text"] = {"characters": el.text}
            node["style"] = {"fontSize": _estimate_font_size(el)}
        elif el.type == "image":
            asset_filename = asset_map.get(str(i))
            if asset_filename:
                asset_id = f"asset_{i:04d}"
                node["image"] = {"assetId": asset_id, "mode": "fill"}
                assets.append({
                    "assetId": asset_id,
                    "url": f"assets/{asset_filename}",
                    "width": el.width,
                    "height": el.height,
                })
        elif el.type == "shape":
            node["style"] = {"fill": "#E5E7EB", "opacity": 0.6}

        children.append(node)

    root: dict[str, Any] = {
        "id": "root",
        "type": "frame",
        "name": "Root",
        "bbox": {"x": 0, "y": 0, "width": page_w, "height": page_h},
        "children": children,
    }

    return {
        "version": "draft-runtime-dsl-v1.0",
        "page": {
            "width": page_w,
            "height": page_h,
            "background": background,
        },
        "root": root,
        "assets": assets,
    }


def _estimate_font_size(el: MergedElement) -> int:
    char_count = max(1, len(el.text))
    from_height = int(el.height * 0.8)
    from_width = int(el.width / char_count * 1.6)
    return max(10, min(from_height, from_width))


def _sample_background(image: Image.Image) -> str:
    """Sample background color from image corners."""
    w, h = image.size
    pixels = []
    for x, y in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]:
        pixels.append(image.getpixel((x, y))[:3])
    r = sum(p[0] for p in pixels) // 4
    g = sum(p[1] for p in pixels) // 4
    b = sum(p[2] for p in pixels) // 4
    return f"#{r:02X}{g:02X}{b:02X}"
