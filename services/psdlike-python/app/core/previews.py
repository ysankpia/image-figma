from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


def write_preview_html(output_path: Path, dsl: dict[str, Any]) -> None:
    page = dsl["page"]
    width = int(page["width"])
    height = int(page["height"])
    background = str(page.get("background") or "#ffffff")
    children = sorted(dsl["root"].get("children", []), key=lambda item: (item.get("z", 0), item["id"]))
    asset_urls = {asset["assetId"]: asset.get("url", "") for asset in dsl.get("assets", [])}

    nodes = "\n".join(render_preview_node(node, asset_urls) for node in children)
    output_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSD-like Draft Preview</title>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: #1f2328;
    font-family: Arial, Helvetica, sans-serif;
  }}
  .page {{
    position: relative;
    width: {width}px;
    height: {height}px;
    margin: 24px auto;
    overflow: hidden;
    background: {html.escape(background)};
    box-shadow: 0 0 0 1px rgba(255,255,255,.12), 0 18px 60px rgba(0,0,0,.35);
  }}
  .node {{
    position: absolute;
    box-sizing: border-box;
  }}
  .shape {{
    pointer-events: none;
  }}
  .raster {{
    object-fit: fill;
    display: block;
  }}
  .text {{
    overflow: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
  }}
</style>
</head>
<body>
<main class="page" data-width="{width}" data-height="{height}">
{nodes}
</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def render_preview_node(node: dict[str, Any], asset_urls: dict[str, str]) -> str:
    bbox = node["bbox"]
    base_style = (
        f"left:{int(bbox['x'])}px;top:{int(bbox['y'])}px;"
        f"width:{int(bbox['width'])}px;height:{int(bbox['height'])}px;"
        f"z-index:{int(node.get('z', 0))};"
    )
    node_id = html.escape(str(node["id"]))
    title = html.escape(str(node.get("name") or node["id"]))
    node_type = node["type"]

    if node_type == "image":
        asset_id = str(node.get("image", {}).get("assetId", ""))
        src = html.escape(asset_urls.get(asset_id, ""))
        return f'<img class="node raster" data-node-id="{node_id}" title="{title}" src="{src}" style="{base_style}" alt="">'

    if node_type == "shape":
        style = node.get("style", {})
        fill = html.escape(str(style.get("fill") or "transparent"))
        radius = int(style.get("cornerRadius") or style.get("radius") or 0)
        return (
            f'<div class="node shape" data-node-id="{node_id}" title="{title}" '
            f'style="{base_style}background:{fill};border-radius:{radius}px;"></div>'
        )

    if node_type == "text":
        style = node.get("style", {})
        text = html.escape(str(node.get("text", {}).get("characters", "")))
        font_size = int(style.get("fontSize") or max(8, round(float(bbox["height"]) * 0.8)))
        color = html.escape(str(style.get("color") or "#111111"))
        font_weight = int(style.get("fontWeight") or 400)
        line_height = int(style.get("lineHeight") or max(font_size, int(math.ceil(font_size * 1.12))))
        return (
            f'<div class="node text" data-node-id="{node_id}" title="{title}" '
            f'style="{base_style}font-size:{font_size}px;line-height:{line_height}px;'
            f'font-weight:{font_weight};color:{color};">{text}</div>'
        )

    return f'<div class="node" data-node-id="{node_id}" title="{title}" style="{base_style}"></div>'


def write_preview_report(output_path: Path, dsl: dict[str, Any], layer_stack: dict[str, Any]) -> None:
    children = dsl["root"].get("children", [])
    image_nodes = [node for node in children if node.get("type") == "image"]
    text_nodes = [node for node in children if node.get("type") == "text"]
    shape_nodes = [node for node in children if node.get("type") == "shape"]
    asset_ids = {asset["assetId"] for asset in dsl.get("assets", [])}
    missing_image_refs = [
        node["id"]
        for node in image_nodes
        if node.get("image", {}).get("assetId") not in asset_ids
    ]
    diagnostics = layer_stack["diagnostics"]
    lines = [
        "# PSD-like Draft Preview Report",
        "",
        f"- nodes: {len(children)}",
        f"- text nodes: {len(text_nodes)}",
        f"- image nodes: {len(image_nodes)}",
        f"- shape nodes: {len(shape_nodes)}",
        f"- surface shape nodes: {diagnostics.get('surfaceShapeLayerCount', 0)}",
        f"- control surface shape nodes: {diagnostics.get('controlSurfaceShapeLayerCount', 0)}",
        f"- page background: {diagnostics.get('pageBackground', dsl.get('page', {}).get('background', ''))}",
        f"- assets: {len(dsl.get('assets', []))}",
        f"- missing image refs: {len(missing_image_refs)}",
        f"- visible text overlap: {diagnostics['textOverlapRaster']}",
        f"- raw text overlap: {diagnostics['rawTextOverlapRaster']}",
        f"- raster text knockout: {diagnostics['rasterTextKnockoutCount']}",
        f"- text-owned raster suppressed: {diagnostics.get('textOwnedRasterSuppressedCount', 0)}",
        f"- full page visible raster: {diagnostics['fullPageVisibleRaster']}",
        f"- tiny raster fragments: {diagnostics['tinyRasterFragments']}",
        "",
    ]
    if missing_image_refs:
        lines.append("## Missing Image Refs")
        lines.extend(f"- `{item}`" for item in missing_image_refs)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_draft_preview_png(output_path: Path, dsl: dict[str, Any], output_dir: Path) -> None:
    page = dsl["page"]
    width = int(page["width"])
    height = int(page["height"])
    image = Image.new("RGBA", (width, height), css_color_to_rgba(str(page.get("background") or "#ffffff")))
    draw = ImageDraw.Draw(image)
    assets = {asset["assetId"]: asset.get("url", "") for asset in dsl.get("assets", [])}

    for node in sorted(dsl["root"].get("children", []), key=lambda item: (item.get("z", 0), item["id"])):
        bbox = node["bbox"]
        box = (
            int(bbox["x"]),
            int(bbox["y"]),
            int(bbox["x"] + bbox["width"]),
            int(bbox["y"] + bbox["height"]),
        )
        if node["type"] == "shape":
            style = node.get("style", {})
            fill = css_color_to_rgba(str(style.get("fill") or "#ffffff"))
            radius = int(style.get("cornerRadius") or style.get("radius") or 0)
            if radius > 0:
                draw.rounded_rectangle(box, radius=radius, fill=fill)
            else:
                draw.rectangle(box, fill=fill)
        elif node["type"] == "image":
            asset_id = str(node.get("image", {}).get("assetId", ""))
            asset_url = assets.get(asset_id, "")
            asset_path = output_dir / asset_url
            if asset_path.exists():
                crop = Image.open(asset_path).convert("RGBA").resize((int(bbox["width"]), int(bbox["height"])))
                image.paste(crop, (int(bbox["x"]), int(bbox["y"])), crop)
        elif node["type"] == "text":
            style = node.get("style", {})
            color = css_color_to_rgba(str(style.get("color") or "#111111"))
            text = str(node.get("text", {}).get("characters", ""))
            font_size = int(style.get("fontSize") or max(8, round(float(bbox["height"]) * 0.8)))
            draw.text((int(bbox["x"]), int(bbox["y"])), text, fill=color, font=load_preview_font(font_size))

    image.convert("RGB").save(output_path)


def css_color_to_rgba(value: str) -> tuple[int, int, int, int]:
    value = value.strip()
    if value.startswith("#") and len(value) in {4, 7}:
        if len(value) == 4:
            r = int(value[1] * 2, 16)
            g = int(value[2] * 2, 16)
            b = int(value[3] * 2, 16)
        else:
            r = int(value[1:3], 16)
            g = int(value[3:5], 16)
            b = int(value[5:7], 16)
        return (r, g, b, 255)
    return (255, 255, 255, 255)


def load_preview_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def heatmap_image(values: np.ndarray, width: int, height: int, tile_size: int, color: tuple[int, int, int]) -> Image.Image:
    clipped = np.clip(values, 0.0, 1.0)
    small = (clipped * 255).astype(np.uint8)
    image = Image.fromarray(small, mode="L").resize((width, height), Image.Resampling.NEAREST)
    rgb = Image.new("RGB", (width, height), (0, 0, 0))
    alpha = np.asarray(image).astype(np.float32) / 255.0
    out = np.zeros((height, width, 3), dtype=np.uint8)
    out[:, :, 0] = (alpha * color[0]).astype(np.uint8)
    out[:, :, 1] = (alpha * color[1]).astype(np.uint8)
    out[:, :, 2] = (alpha * color[2]).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


def draw_overlay(
    image: Image.Image,
    ocr_blocks: list[OCRBlock],
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    output_path: Path,
) -> None:
    overlay = image.convert("RGBA")
    draw = ImageDraw.Draw(overlay, "RGBA")

    for index, shape in enumerate(shape_candidates, start=1):
        box = shape.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(40, 180, 90, 255), width=3)
        draw.text((box.x + 2, box.y + 2), f"S{index}", fill=(40, 180, 90, 255))

    for index, raster in enumerate(raster_candidates, start=1):
        box = raster.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(230, 70, 70, 255), width=3)
        draw.text((box.x + 2, box.y + 2), f"R{index}", fill=(230, 70, 70, 255))

    for block in ocr_blocks:
        box = block.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(60, 120, 255, 230), width=2)

    overlay.convert("RGB").save(output_path)


def draw_reconstructed_preview(
    image: Image.Image,
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    text_mask: np.ndarray,
    output_path: Path,
) -> None:
    bg = estimate_background_color(rgb)
    preview = Image.new("RGB", image.size, bg)
    draw = ImageDraw.Draw(preview)

    for shape in shape_candidates:
        fill = median_fill(rgb, shape.bbox)
        box = shape.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), fill=fill)

    for raster in raster_candidates:
        crop = image.crop((raster.bbox.x, raster.bbox.y, raster.bbox.x2, raster.bbox.y2)).convert("RGBA")
        crop = inpaint_text_pixels_in_raster(crop, raster, rgb=rgb, ocr_blocks=ocr_blocks, text_mask=text_mask)
        preview.paste(crop, (raster.bbox.x, raster.bbox.y), crop)

    for block in ocr_blocks:
        box = block.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(20, 80, 220), width=1)
        draw.text((box.x, box.y), block.text[:32], fill=(20, 20, 20))

    preview.save(output_path)
