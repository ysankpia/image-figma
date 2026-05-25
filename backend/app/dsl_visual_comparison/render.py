from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..png_tools import PngPixels, decode_png_pixels


def render_dsl_to_pixels(
    *,
    dsl: dict[str, Any],
    materialized_design_dir: Path,
    public_assets_dir: Path,
    task_id: str,
) -> tuple[PngPixels, list[str]]:
    page = dsl.get("page") if isinstance(dsl.get("page"), dict) else {}
    width = int(page.get("width") or dsl.get("root", {}).get("layout", {}).get("width") or 1)
    height = int(page.get("height") or dsl.get("root", {}).get("layout", {}).get("height") or 1)
    background = background_rgb(dsl)
    rows = [bytearray(bytes(background) * width) for _ in range(height)]
    warnings: list[str] = []
    assets = {str(asset.get("assetId")): asset for asset in list_dicts(dsl.get("assets")) if asset.get("assetId")}
    root = dsl.get("root")
    if isinstance(root, dict):
        render_element(
            rows=rows,
            element=root,
            assets=assets,
            materialized_design_dir=materialized_design_dir,
            public_assets_dir=public_assets_dir,
            task_id=task_id,
            parent_offset=(0, 0),
            warnings=warnings,
            is_root=True,
        )
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows]), warnings


def build_text_exclusion_mask(
    dsl: dict[str, Any],
    *,
    width: int,
    height: int,
    padding: int = 1,
    source_text_bboxes: list[list[int]] | None = None,
) -> tuple[bytes, int]:
    mask = bytearray(width * height)
    root = dsl.get("root")
    if width <= 0 or height <= 0:
        return bytes(mask), 0
    if isinstance(root, dict):
        for bbox in collect_visible_text_bboxes(root, parent_offset=(0, 0), is_root=True):
            mark_bbox(mask, width, height, bbox, padding=padding)
    for bbox in source_text_bboxes or []:
        source_padding = source_text_padding(bbox, fallback_padding=padding)
        mark_bbox(mask, width, height, bbox, padding=source_padding)
    return bytes(mask), sum(1 for value in mask if value)


def source_text_padding(bbox: list[int], *, fallback_padding: int) -> int:
    if len(bbox) != 4:
        return fallback_padding
    try:
        height = int(round(float(bbox[3])))
    except (TypeError, ValueError):
        return fallback_padding
    return max(fallback_padding, min(4, round(height * 0.12)))


def collect_visible_text_bboxes(
    element: dict[str, Any],
    *,
    parent_offset: tuple[int, int],
    is_root: bool = False,
) -> list[list[int]]:
    if not is_visible(element):
        return []
    layout = parse_layout(element.get("layout"))
    if layout is None:
        return []
    x = parent_offset[0] + layout[0]
    y = parent_offset[1] + layout[1]
    bbox = [x, y, layout[2], layout[3]]
    result: list[list[int]] = []
    if not is_root and str(element.get("type") or "") == "text":
        result.append(bbox)
    for child in list_dicts(element.get("children")):
        result.extend(collect_visible_text_bboxes(child, parent_offset=(x, y)))
    return result


def mark_bbox(mask: bytearray, width: int, height: int, bbox: list[int], *, padding: int) -> None:
    left = max(0, bbox[0] - padding)
    top = max(0, bbox[1] - padding)
    right = min(width, bbox[0] + bbox[2] + padding)
    bottom = min(height, bbox[1] + bbox[3] + padding)
    if right <= left or bottom <= top:
        return
    fill = b"\x01" * (right - left)
    for row_index in range(top, bottom):
        start = row_index * width + left
        mask[start : start + right - left] = fill


def render_element(
    *,
    rows: list[bytearray],
    element: dict[str, Any],
    assets: dict[str, dict[str, Any]],
    materialized_design_dir: Path,
    public_assets_dir: Path,
    task_id: str,
    parent_offset: tuple[int, int],
    warnings: list[str],
    is_root: bool = False,
) -> None:
    if not is_visible(element):
        return
    layout = parse_layout(element.get("layout"))
    if layout is None:
        warnings.append(f"missing_layout:{element.get('id')}")
        return
    x = parent_offset[0] + layout[0]
    y = parent_offset[1] + layout[1]
    bbox = [x, y, layout[2], layout[3]]
    element_type = str(element.get("type") or "")
    if not is_root and element_type in {"frame", "group"}:
        fill = style_fill(element)
        if fill is not None:
            fill_rect(rows, bbox, fill)
    elif element_type == "shape":
        fill = style_fill(element)
        if fill is not None:
            fill_rect(rows, bbox, fill)
    elif element_type == "image":
        render_image(
            rows=rows,
            element=element,
            bbox=bbox,
            assets=assets,
            materialized_design_dir=materialized_design_dir,
            public_assets_dir=public_assets_dir,
            task_id=task_id,
            warnings=warnings,
        )
    elif element_type == "text":
        render_text_approx(rows, bbox, text_rgb(element), text_content(element))

    for child in list_dicts(element.get("children")):
        render_element(
            rows=rows,
            element=child,
            assets=assets,
            materialized_design_dir=materialized_design_dir,
            public_assets_dir=public_assets_dir,
            task_id=task_id,
            parent_offset=(x, y),
            warnings=warnings,
        )


def render_image(
    *,
    rows: list[bytearray],
    element: dict[str, Any],
    bbox: list[int],
    assets: dict[str, dict[str, Any]],
    materialized_design_dir: Path,
    public_assets_dir: Path,
    task_id: str,
    warnings: list[str],
) -> None:
    source = element.get("source") if isinstance(element.get("source"), dict) else {}
    asset_id = str(source.get("assetId") or "")
    asset = assets.get(asset_id)
    if asset is None:
        warnings.append(f"missing_asset:{element.get('id')}:{asset_id}")
        return
    path = resolve_asset_path(
        str(asset.get("url") or ""),
        materialized_design_dir=materialized_design_dir,
        public_assets_dir=public_assets_dir,
        task_id=task_id,
    )
    if path is None or not path.exists():
        warnings.append(f"missing_asset_file:{element.get('id')}:{asset.get('url')}")
        return
    try:
        image = decode_png_pixels(path.read_bytes())
    except Exception as error:  # noqa: BLE001 - report renderer should not block upload.
        warnings.append(f"asset_decode_failed:{element.get('id')}:{error.__class__.__name__}")
        return
    mode = "fill"
    image_fill = element.get("imageFill") if isinstance(element.get("imageFill"), dict) else {}
    if image_fill.get("mode") == "fit":
        mode = "fit"
    draw_scaled_image(rows, bbox, image, mode)


def draw_scaled_image(rows: list[bytearray], bbox: list[int], image: PngPixels, mode: str) -> None:
    canvas_height = len(rows)
    canvas_width = len(rows[0]) // 3 if rows else 0
    x, y, width, height = bbox
    if width <= 0 or height <= 0:
        return
    draw_x, draw_y, draw_w, draw_h = x, y, width, height
    if mode == "fit":
        scale = min(width / max(1, image.width), height / max(1, image.height))
        draw_w = max(1, round(image.width * scale))
        draw_h = max(1, round(image.height * scale))
        draw_x = x + (width - draw_w) // 2
        draw_y = y + (height - draw_h) // 2
    for row_index in range(max(0, draw_y), min(canvas_height, draw_y + draw_h)):
        src_y = min(image.height - 1, max(0, int((row_index - draw_y) * image.height / max(1, draw_h))))
        src_row = image.rows[src_y]
        row = rows[row_index]
        for col_index in range(max(0, draw_x), min(canvas_width, draw_x + draw_w)):
            src_x = min(image.width - 1, max(0, int((col_index - draw_x) * image.width / max(1, draw_w))))
            src_offset = src_x * 3
            dst_offset = col_index * 3
            row[dst_offset : dst_offset + 3] = src_row[src_offset : src_offset + 3]


def render_text_approx(rows: list[bytearray], bbox: list[int], rgb: tuple[int, int, int], text: str = "") -> None:
    x, y, width, height = bbox
    if width <= 0 or height <= 0:
        return
    content = text.strip()
    if not content:
        render_text_placeholder(rows, bbox, rgb)
        return
    canvas_height = len(rows)
    canvas_width = len(rows[0]) // 3 if rows else 0
    if canvas_width <= 0 or canvas_height <= 0:
        return
    inset_x = max(1, min(3, width // 12))
    inset_y = max(1, min(3, height // 5))
    glyph_height = max(2, height - inset_y * 2)
    drawable_width = max(1, width - inset_x * 2)
    glyph_count = max(1, min(len(content), max(1, drawable_width // 2)))
    slot_width = max(2, drawable_width // glyph_count)
    sampled_text = sample_text_for_width(content, glyph_count)
    for index, char in enumerate(sampled_text):
        if char.isspace():
            continue
        glyph_x = x + inset_x + index * slot_width
        if glyph_x >= x + width:
            break
        glyph_y = y + inset_y
        glyph_width = max(1, min(slot_width - 1, x + width - glyph_x))
        draw_approx_glyph(
            rows,
            glyph_x,
            glyph_y,
            glyph_width,
            glyph_height,
            rgb,
            seed=ord(char) + index * 17,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )


def render_text_placeholder(rows: list[bytearray], bbox: list[int], rgb: tuple[int, int, int]) -> None:
    x, y, width, height = bbox
    line_height = max(1, min(height, round(height * 0.18)))
    top = y + max(0, (height - line_height) // 2)
    dash_width = max(1, min(6, width // 5))
    gap = max(1, dash_width // 2)
    cursor = x
    while cursor < x + width:
        fill_rect(rows, [cursor, top, min(dash_width, x + width - cursor), line_height], rgb)
        cursor += dash_width + gap


def sample_text_for_width(text: str, count: int) -> str:
    if len(text) <= count:
        return text
    if count <= 1:
        return text[:1]
    last_index = len(text) - 1
    return "".join(text[round(index * last_index / (count - 1))] for index in range(count))


def draw_approx_glyph(
    rows: list[bytearray],
    x: int,
    y: int,
    width: int,
    height: int,
    rgb: tuple[int, int, int],
    *,
    seed: int,
    canvas_width: int,
    canvas_height: int,
) -> None:
    if width <= 0 or height <= 0:
        return
    stroke = max(1, min(2, width, height // 5 if height >= 5 else 1))
    mid_y = y + max(0, height // 2 - stroke // 2)
    right_x = x + max(0, width - stroke)
    bottom_y = y + max(0, height - stroke)
    draw_glyph_rect(rows, [x, y, stroke, height], rgb, canvas_width, canvas_height)
    if width >= 3 and seed % 2 == 0:
        draw_glyph_rect(rows, [right_x, y, stroke, height], rgb, canvas_width, canvas_height)
    if seed % 3 != 0:
        draw_glyph_rect(rows, [x, y, width, stroke], rgb, canvas_width, canvas_height)
    if height >= 5 and seed % 5 != 0:
        draw_glyph_rect(rows, [x, mid_y, width, stroke], rgb, canvas_width, canvas_height)
    if seed % 7 != 0:
        draw_glyph_rect(rows, [x, bottom_y, width, stroke], rgb, canvas_width, canvas_height)


def draw_glyph_rect(
    rows: list[bytearray],
    bbox: list[int],
    rgb: tuple[int, int, int],
    canvas_width: int,
    canvas_height: int,
) -> None:
    x, y, width, height = bbox
    for row_index in range(max(0, y), min(canvas_height, y + height)):
        row = rows[row_index]
        for col_index in range(max(0, x), min(canvas_width, x + width)):
            offset = col_index * 3
            row[offset : offset + 3] = bytes(rgb)


def fill_rect(rows: list[bytearray], bbox: list[int], rgb: tuple[int, int, int]) -> None:
    canvas_height = len(rows)
    canvas_width = len(rows[0]) // 3 if rows else 0
    x, y, width, height = bbox
    for row_index in range(max(0, y), min(canvas_height, y + height)):
        row = rows[row_index]
        for col_index in range(max(0, x), min(canvas_width, x + width)):
            offset = col_index * 3
            row[offset : offset + 3] = bytes(rgb)


def resolve_asset_path(url: str, *, materialized_design_dir: Path, public_assets_dir: Path, task_id: str) -> Path | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        marker = f"/files/assets/{task_id}/"
        if marker not in parsed.path:
            return None
        suffix = parsed.path.split(marker, 1)[1]
        return public_assets_dir / task_id / suffix
    candidate = Path(url).expanduser()
    if candidate.is_absolute():
        return candidate
    return (materialized_design_dir / candidate).resolve()


def background_rgb(dsl: dict[str, Any]) -> tuple[int, int, int]:
    page = dsl.get("page") if isinstance(dsl.get("page"), dict) else {}
    background = page.get("background") if isinstance(page.get("background"), dict) else {}
    if background.get("type") == "color" and isinstance(background.get("value"), str):
        return parse_hex(background["value"])
    root = dsl.get("root") if isinstance(dsl.get("root"), dict) else {}
    fill = style_fill(root)
    return fill or (247, 248, 250)


def style_fill(element: dict[str, Any]) -> tuple[int, int, int] | None:
    style = element.get("style") if isinstance(element.get("style"), dict) else {}
    fill = style.get("fill")
    if isinstance(fill, str):
        return parse_hex(fill)
    return None


def text_rgb(element: dict[str, Any]) -> tuple[int, int, int]:
    style = element.get("style") if isinstance(element.get("style"), dict) else {}
    color = style.get("color")
    if isinstance(color, str):
        return parse_hex(color)
    return (17, 24, 39)


def text_content(element: dict[str, Any]) -> str:
    content = element.get("content") if isinstance(element.get("content"), dict) else {}
    return str(content.get("text") or "")


def is_visible(element: dict[str, Any]) -> bool:
    style = element.get("style") if isinstance(element.get("style"), dict) else {}
    return style.get("visible") is not False


def parse_layout(value: Any) -> list[int] | None:
    if not isinstance(value, dict):
        return None
    try:
        layout = [int(round(float(value[key]))) for key in ["x", "y", "width", "height"]]
    except (KeyError, TypeError, ValueError):
        return None
    if layout[2] <= 0 or layout[3] <= 0:
        return None
    return layout


def parse_hex(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char + char for char in text)
    if len(text) != 6:
        return (0, 0, 0)
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return (0, 0, 0)


def list_dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
