#!/usr/bin/env python3
"""Export M29 physical evidence into a Pencil .pen package.

This tool is intentionally narrow:

PNG/M29 evidence + OCR text regions
-> production Pencil package with visible clean crops and editable text
-> debug package with raw evidence for inspection

The production package must not reference the original source image, raw text
crops, masks, or any debug asset. If text becomes editable, the old text pixels
must stop being visible in the underlying crop.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter, ImageFont


PEN_VERSION = "2.11"

CJK_FONT_CANDIDATES = [
    "Noto Sans SC",
    "PingFang SC",
    "Microsoft YaHei",
    "Source Han Sans SC",
    "Arial Unicode MS",
    "Arial",
]

LATIN_FONT_CANDIDATES = [
    "Inter",
    "SF Pro Text",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
]

LOCAL_FONT_FILES = {
    "PingFang SC": [
        # macOS stores downloadable system fonts under AssetsV2 on recent releases.
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ],
    "Helvetica Neue": [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    ],
    "Arial": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
}


@dataclass(frozen=True)
class Primitive:
    id: str
    primitive_type: str
    bbox: dict[str, float]
    crop_ref: str
    mask_ref: str | None
    text: str
    source: dict[str, Any]
    measurements: dict[str, Any]
    compile_hints: dict[str, Any]


@dataclass(frozen=True)
class ExportPaths:
    input_dir: Path
    out_dir: Path
    production_dir: Path
    debug_dir: Path
    production_assets_dir: Path
    debug_assets_dir: Path


@dataclass(frozen=True)
class ExportMode:
    name: str
    dir_name: str
    visible_ocr_text: bool
    crop_text_regions: bool
    enable_text_knockout: bool
    enable_crop_dedupe: bool
    crop_policy: str
    description: str


EXPORT_MODE_NAMES = ("clean-editable", "visual-fidelity", "visual-ocr")


@dataclass(frozen=True)
class SinglePageExportOptions:
    input_dir: Path
    out: Path
    name: str = "M29 Pencil Export"
    mode: str = "clean-editable"
    page_fill: str | None = None
    disable_text_knockout: bool = False
    include_debug_pen: bool = False
    disable_art_text_gate: bool = False
    disable_crop_dedupe: bool = False
    crop_policy: str = "component"

    def to_namespace(self) -> argparse.Namespace:
        return argparse.Namespace(
            input_dir=self.input_dir,
            out=self.out,
            name=self.name,
            mode=self.mode,
            page_fill=self.page_fill,
            disable_text_knockout=self.disable_text_knockout,
            include_debug_pen=self.include_debug_pen,
            disable_art_text_gate=self.disable_art_text_gate,
            disable_crop_dedupe=self.disable_crop_dedupe,
            crop_policy=self.crop_policy,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export M29 replay artifacts to a Pencil .pen package.")
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing m29_physical_evidence.v1.json, m29-pencil-replay.v1.json, and assets/.",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output package directory.")
    parser.add_argument("--name", default="M29 Pencil Export", help="Top frame name.")
    parser.add_argument(
        "--mode",
        choices=(*EXPORT_MODE_NAMES, "all"),
        default="clean-editable",
        help=(
            "clean-editable emits cleaned crops plus editable OCR text; "
            "visual-fidelity emits crop-only visual layers; "
            "visual-ocr emits visual-friendly cleaned bitmap layers plus visible OCR text; "
            "all emits all three packages."
        ),
    )
    parser.add_argument(
        "--page-fill",
        default=None,
        help="Optional page background color. Defaults to the evidence pageBackground if present, else #FFFFFF.",
    )
    parser.add_argument(
        "--disable-text-knockout",
        action="store_true",
        help="Do not erase text pixels from underlying clean-editable crops. Intended only for debugging.",
    )
    parser.add_argument(
        "--include-debug-pen",
        action="store_true",
        help="Also emit a debug .pen with the source image reference and raw crops.",
    )
    parser.add_argument(
        "--disable-art-text-gate",
        action="store_true",
        help="Convert decorative/art text to editable text as well. Intended only for comparison.",
    )
    parser.add_argument(
        "--disable-crop-dedupe",
        action="store_true",
        help="Keep overlapping duplicate crop layers. Intended only for debugging.",
    )
    parser.add_argument(
        "--crop-policy",
        choices=("component", "editable"),
        default="component",
        help=(
            "component keeps the nearest enclosing component crop and suppresses internal fragments; "
            "editable keeps more foreground fragments for manual editing."
        ),
    )
    return parser.parse_args()


def export_single_page(options: SinglePageExportOptions) -> dict[str, Any]:
    return export_package(options.to_namespace())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def export_modes(args: argparse.Namespace) -> list[ExportMode]:
    text_knockout_enabled = not args.disable_text_knockout
    crop_dedupe_enabled = not args.disable_crop_dedupe
    modes = {
        "clean-editable": ExportMode(
            name="clean-editable",
            dir_name="production",
            visible_ocr_text=True,
            crop_text_regions=False,
            enable_text_knockout=text_knockout_enabled,
            enable_crop_dedupe=crop_dedupe_enabled,
            crop_policy=args.crop_policy,
            description="Clean handoff with text knockout crops plus visible editable OCR TextLayers.",
        ),
        "visual-fidelity": ExportMode(
            name="visual-fidelity",
            dir_name="visual-fidelity",
            visible_ocr_text=False,
            crop_text_regions=True,
            enable_text_knockout=False,
            enable_crop_dedupe=False,
            crop_policy="none",
            description="Crop-only visual handoff. OCR text stays in the bitmap; no visible OCR TextLayers.",
        ),
        "visual-ocr": ExportMode(
            name="visual-ocr",
            dir_name="visual-ocr",
            visible_ocr_text=True,
            crop_text_regions=False,
            enable_text_knockout=text_knockout_enabled,
            enable_crop_dedupe=False,
            crop_policy="none",
            description=(
                "Visual-friendly OCR handoff. Normal OCR text pixels are owned by editable TextLayers; "
                "overlapping bitmap crops are text-knockout cleaned to avoid doubled visible text."
            ),
        ),
    }
    if args.mode == "all":
        return [modes[name] for name in EXPORT_MODE_NAMES]
    return [modes[args.mode]]


def paths_for_mode(base: ExportPaths, mode: ExportMode) -> ExportPaths:
    production_dir = base.out_dir / mode.dir_name
    return replace(
        base,
        production_dir=production_dir,
        production_assets_dir=production_dir / "assets" / "visible",
    )


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def has_latin_or_digit(text: str) -> bool:
    return bool(re.search(r"[A-Za-z0-9]", text))


def font_candidates_for_text(text: str) -> list[str]:
    if has_cjk(text):
        return CJK_FONT_CANDIDATES
    return LATIN_FONT_CANDIDATES


def local_measure_family_for_text(text: str) -> str:
    if has_cjk(text):
        return "PingFang SC"
    return "Helvetica Neue"


def load_font(font_family: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = LOCAL_FONT_FILES.get(font_family, []) + LOCAL_FONT_FILES["Arial"]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def measured_text_size(text: str, font_family: str, size: int) -> tuple[int, int]:
    font = load_font(font_family, size)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def text_visual_units(text: str) -> float:
    units = 0.0
    for ch in text:
        if ch.isspace():
            units += 0.32
        elif re.match(r"[\u3400-\u9fff]", ch):
            units += 1.0
        elif ch.isdigit():
            units += 0.55
        elif ch.isalpha():
            units += 0.58 if ch.islower() else 0.66
        elif ch in "+-/|:.，。、“”《》：；（）()[]{}":
            units += 0.35
        else:
            units += 0.5
    return max(1.0, units)


def fit_font_size(text: str, bbox: dict[str, float], font_family: str) -> float:
    width = float(bbox["width"])
    height = float(bbox["height"])
    if not text.strip():
        return round(max(8.0, min(16.0, height * 0.72)), 2)

    max_w = max(1.0, width * 0.96)
    max_h = max(1.0, height * 0.82)
    upper = int(clamp(height * 0.92, 8, 96))
    lower = 6
    best = lower
    for size in range(lower, upper + 1):
        measured_w, measured_h = measured_text_size(text, font_family, size)
        heuristic_w = text_visual_units(text) * size
        if max(measured_w, heuristic_w) <= max_w and measured_h <= max_h:
            best = size
    return round(float(best), 2)


def expanded_text_bounds(
    bbox: dict[str, float],
    canvas: dict[str, Any],
    font_size: float,
    script: str,
) -> dict[str, float]:
    x = float(bbox["x"])
    y = float(bbox["y"])
    width = float(bbox["width"])
    height = float(bbox["height"])
    canvas_width = float(canvas.get("width") or x + width)
    canvas_height = float(canvas.get("height") or y + height)
    right_pad = max(2.0, font_size * (0.40 if script in {"cjk", "mixed"} else 0.20))
    vertical_pad = max(2.0, font_size * 0.22)
    expanded_x = x
    expanded_y = y - vertical_pad
    expanded_width = width + right_pad
    expanded_height = height + vertical_pad * 2

    if expanded_y < 0:
        expanded_height += expanded_y
        expanded_y = 0.0
    if expanded_x + expanded_width > canvas_width:
        expanded_width = max(1.0, canvas_width - expanded_x)
    if expanded_y + expanded_height > canvas_height:
        expanded_height = max(1.0, canvas_height - expanded_y)

    return {
        "x": round(expanded_x, 2),
        "y": round(expanded_y, 2),
        "width": round(max(1.0, expanded_width), 2),
        "height": round(max(1.0, expanded_height), 2),
    }


def area_of(bbox: dict[str, float]) -> float:
    return max(0.0, float(bbox["width"])) * max(0.0, float(bbox["height"]))


def intersection_area(a: dict[str, float], b: dict[str, float]) -> float:
    inter = bbox_intersection(a, b)
    if not inter:
        return 0.0
    return float(inter["width"] * inter["height"])


def ioa(a: dict[str, float], b: dict[str, float]) -> float:
    area = area_of(a)
    if area <= 0:
        return 0.0
    return intersection_area(a, b) / area


def iou(a: dict[str, float], b: dict[str, float]) -> float:
    inter = intersection_area(a, b)
    if inter <= 0:
        return 0.0
    union = area_of(a) + area_of(b) - inter
    return inter / union if union > 0 else 0.0


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = [value / 255.0 for value in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return abs(luminance(a) - luminance(b))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def dominant_quantized_color(pixels: np.ndarray) -> tuple[int, int, int]:
    if pixels.size == 0:
        return (255, 255, 255)
    flat = pixels.reshape(-1, 3)
    quantized = (flat // 16) * 16 + 8
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    if len(colors) == 0:
        return (255, 255, 255)
    return tuple(int(value) for value in colors[int(np.argmax(counts))])


def estimate_crop_edge_background(image: Image.Image) -> tuple[int, int, int]:
    arr = np.asarray(image.convert("RGB"), dtype=np.uint8)
    h, w = arr.shape[:2]
    if h == 0 or w == 0:
        return (255, 255, 255)
    border = max(1, min(4, h // 4, w // 4))
    samples = np.concatenate(
        [
            arr[:border, :, :].reshape(-1, 3),
            arr[h - border :, :, :].reshape(-1, 3),
            arr[:, :border, :].reshape(-1, 3),
            arr[:, w - border :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return dominant_quantized_color(samples)


def sample_text_color(crop_path: Path) -> tuple[str, str, float]:
    if not crop_path.exists():
        return "#111111", "missing_crop_fallback", 0.0
    image = Image.open(crop_path).convert("RGB")
    pixels = np.asarray(image, dtype=np.uint8).reshape(-1, 3)
    if pixels.size == 0:
        return "#111111", "empty_crop_fallback", 0.0

    quantized = (pixels // 16) * 16 + 8
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    if len(colors) == 0:
        return "#111111", "empty_quant_fallback", 0.0

    edge_background = estimate_crop_edge_background(image)
    dominant_background = tuple(int(value) for value in colors[int(np.argmax(counts))])
    background = edge_background
    total = max(1, int(counts.sum()))
    foreground_candidates: list[tuple[float, tuple[int, int, int], int]] = []
    for color, count in zip(colors, counts):
        rgb = tuple(int(value) for value in color)
        share = int(count) / total
        delta = contrast(rgb, background)
        dominant_delta = contrast(rgb, dominant_background)
        if share < 0.006 or share > 0.72:
            continue
        if delta < 0.14 and dominant_delta < 0.14:
            continue
        # Capped area reward prevents a large colored button background from beating
        # smaller but high-contrast text strokes.
        area_reward = math.sqrt(min(0.18, share))
        polarity_bonus = 1.15 if luminance(rgb) >= 0.88 or luminance(rgb) <= 0.18 else 1.0
        foreground_candidates.append((max(delta, dominant_delta) * area_reward * polarity_bonus, rgb, int(count)))
    if foreground_candidates:
        foreground_candidates.sort(reverse=True)
        rgb = foreground_candidates[0][1]
        return rgb_to_hex(rgb), "edge_contrast_foreground_bucket", float(foreground_candidates[0][0])

    scored: list[tuple[float, int, tuple[int, int, int]]] = []
    for color, count in zip(colors, counts):
        rgb = tuple(int(value) for value in color)
        delta = contrast(rgb, background)
        if delta < 0.16:
            continue
        scored.append((delta * math.sqrt(float(count)), int(count), rgb))
    if not scored:
        fallback = (255, 255, 255) if luminance(background) < 0.48 else (20, 24, 31)
        return rgb_to_hex(fallback), "contrast_fallback", contrast(fallback, background)
    scored.sort(reverse=True)
    return rgb_to_hex(scored[0][2]), "contrast_bucket", float(scored[0][0])


def bbox_intersection(a: dict[str, float], b: dict[str, float]) -> dict[str, int] | None:
    x1 = max(int(a["x"]), int(b["x"]))
    y1 = max(int(a["y"]), int(b["y"]))
    x2 = min(int(a["x"] + a["width"]), int(b["x"] + b["width"]))
    y2 = min(int(a["y"] + a["height"]), int(b["y"] + b["height"]))
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def crop_full_page_mask(mask_path: Path, bbox: dict[str, int]) -> Image.Image | None:
    if not mask_path.exists():
        return None
    x = int(bbox["x"])
    y = int(bbox["y"])
    w = int(bbox["width"])
    h = int(bbox["height"])
    return Image.open(mask_path).convert("L").crop((x, y, x + w, y + h))


def asset_path(paths: ExportPaths, ref: str) -> Path:
    rel = str(ref).removeprefix("./assets/")
    candidates = [
        paths.input_dir / "assets" / rel,
        paths.input_dir / rel,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def build_text_mask_for_layer(
    paths: ExportPaths,
    layer_bbox: dict[str, float],
    text_primitives: list[Primitive],
) -> np.ndarray | None:
    width = int(layer_bbox["width"])
    height = int(layer_bbox["height"])
    combined = np.zeros((height, width), dtype=bool)
    for text_primitive in text_primitives:
        inter = bbox_intersection(layer_bbox, text_primitive.bbox)
        if not inter or not text_primitive.mask_ref:
            continue
        mask_path = asset_path(paths, text_primitive.mask_ref)
        text_mask = crop_full_page_mask(mask_path, inter)
        if text_mask is None:
            continue
        mx = inter["x"] - int(layer_bbox["x"])
        my = inter["y"] - int(layer_bbox["y"])
        mask = np.array(text_mask) > 0
        if mask.any():
            combined[my : my + inter["height"], mx : mx + inter["width"]] |= mask
    if not combined.any():
        return None
    expanded = Image.fromarray((combined.astype(np.uint8) * 255), "L").filter(ImageFilter.MaxFilter(3))
    return np.array(expanded) > 0


def erase_masked_pixels(image: Image.Image, mask: np.ndarray) -> Image.Image:
    pixels = np.array(image.convert("RGB"))
    if pixels.shape[:2] != mask.shape:
        return image.convert("RGB")
    keep = ~mask
    if not keep.any():
        return image.convert("RGB")
    filled = pixels.copy()
    current = mask.copy()

    # Deterministic local inpaint: peel the masked region from the outside in,
    # replacing each frontier pixel by the median of already-known 8-neighbors.
    # This preserves local gradients far better than filling the whole crop with
    # one dominant color, and keeps the tool dependency-free.
    for _ in range(96):
        if not current.any():
            break
        updates: list[tuple[int, int, np.ndarray]] = []
        ys, xs = np.where(current)
        for y, x in zip(ys.tolist(), xs.tolist()):
            samples = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny = y + dy
                    nx = x + dx
                    if 0 <= ny < current.shape[0] and 0 <= nx < current.shape[1] and not current[ny, nx]:
                        samples.append(filled[ny, nx])
            if samples:
                updates.append((y, x, np.median(np.array(samples), axis=0).astype(np.uint8)))
        if not updates:
            break
        for y, x, value in updates:
            filled[y, x] = value
            current[y, x] = False

    if current.any():
        fill = np.median(filled[~current], axis=0).astype(np.uint8)
        filled[current] = fill
    pixels[mask] = filled[mask]
    return Image.fromarray(pixels)


def copy_used_crop_to_visible_assets(
    paths: ExportPaths,
    layer: dict[str, Any],
    text_primitives: list[Primitive],
    enable_text_knockout: bool,
) -> tuple[str, dict[str, Any]]:
    primitive_id = layer["sourcePrimitiveId"]
    source_rel = str(layer["fillImage"]).removeprefix("./assets/")
    source_path = asset_path(paths, source_rel)
    if not source_path.exists():
        raise FileNotFoundError(f"Missing crop asset for {primitive_id}: {source_path}")

    metadata: dict[str, Any] = {
        "visibleAssetSource": "raw_crop",
        "sourceCropRef": source_rel,
    }
    output_name = f"{primitive_id}.png"
    output_path = paths.production_assets_dir / output_name

    if enable_text_knockout and layer.get("role") not in {"art_text_region", "visual_text_region", "text_region"}:
        text_mask = build_text_mask_for_layer(paths, layer["bbox"], text_primitives)
        if text_mask is not None:
            cleaned = erase_masked_pixels(Image.open(source_path), text_mask)
            output_name = f"{primitive_id}.clean.png"
            output_path = paths.production_assets_dir / output_name
            cleaned.save(output_path)
            metadata["visibleAssetSource"] = "text_knockout_crop"
            metadata["textKnockout"] = True
            metadata["knockoutPixelCount"] = int(text_mask.sum())
        else:
            shutil.copy2(source_path, output_path)
    else:
        shutil.copy2(source_path, output_path)

    return f"./assets/visible/{output_name}", metadata


def source_image_path(paths: ExportPaths) -> Path:
    direct = paths.input_dir / "source.png"
    if direct.exists():
        return direct
    asset_source = paths.input_dir / "assets" / "source.png"
    if asset_source.exists():
        return asset_source
    raise FileNotFoundError(f"Missing source image in evidence directory: {paths.input_dir}")


def has_alpha_pixels(image_path: Path) -> bool:
    with Image.open(image_path) as image:
        if image.mode in ("RGBA", "LA"):
            alpha = image.getchannel("A")
            return alpha.getextrema()[0] < 255
        if image.mode == "P" and "transparency" in image.info:
            return True
    return False


def copy_source_to_visible_asset(paths: ExportPaths) -> tuple[str, dict[str, Any]]:
    source = source_image_path(paths)
    output_name = "source_full.png"
    output_path = paths.production_assets_dir / output_name
    with Image.open(source) as image:
        image.save(output_path)
    return f"./assets/visible/{output_name}", {
        "visibleAssetSource": "source_full_raster",
        "fallbackPolicy": "empty_evidence_source_raster.v1",
        "sourceHasAlpha": has_alpha_pixels(source),
    }


def load_primitives(evidence: dict[str, Any]) -> dict[str, Primitive]:
    primitives: dict[str, Primitive] = {}
    for item in evidence.get("primitives") or []:
        source = item.get("source") or {}
        primitives[item["id"]] = Primitive(
            id=item["id"],
            primitive_type=item["primitiveType"],
            bbox=item["bbox"],
            crop_ref=item["cropRef"],
            mask_ref=item.get("maskRef"),
            text=source.get("text") or "",
            source=source,
            measurements=item.get("measurements") or {},
            compile_hints=item.get("compileHints") or {},
        )
    return primitives


def build_replay_from_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    role_order = {
        "image_region": 0,
        "surface_region": 1,
        "unknown_region": 2,
        "rect": 3,
        "symbol_region": 4,
        "text_region": 5,
    }
    primitives = sorted(
        evidence.get("primitives") or [],
        key=lambda item: (
            role_order.get(str(item.get("primitiveType") or ""), 9),
            int((item.get("bbox") or {}).get("y", 0)),
            int((item.get("bbox") or {}).get("x", 0)),
            str(item.get("id") or ""),
        ),
    )
    layers: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for z, primitive in enumerate(primitives, start=1):
        primitive_id = str(primitive["id"])
        primitive_type = str(primitive.get("primitiveType") or "unknown_region")
        counts[primitive_type] += 1
        layers.append(
            {
                "id": primitive_id,
                "sourcePrimitiveId": primitive_id,
                "role": primitive_type,
                "nodeType": "rectangle",
                "bbox": primitive["bbox"],
                "fillImage": f"./assets/{primitive['cropRef']}",
                "maskImage": f"./assets/{primitive['maskRef']}" if primitive.get("maskRef") else None,
                "editableMode": "raster_crop",
                "z": z,
            }
        )
    return {
        "schema": "m29.pencil.replay.v1",
        "version": "1.0",
        "source": "generated_from_m29_physical_evidence",
        "policy": {
            "mode": "physical_raster_crop_replay",
            "textRegions": "imageFillFirstPass",
            "generatedBy": "m29_pencil_export.build_replay_from_evidence",
        },
        "layers": layers,
        "summary": {
            "layerCount": len(layers),
            "primitiveTypeCounts": dict(counts),
        },
    }


def infer_page_fill(evidence: dict[str, Any], explicit: str | None) -> str:
    if explicit:
        return explicit
    diagnostics = evidence.get("diagnostics") or {}
    for key in ("pageBackground", "backgroundColor", "canvasBackground"):
        value = diagnostics.get(key)
        if isinstance(value, str) and value.startswith("#"):
            return value
    return "#FFFFFF"


def infer_font_weight(text: str, bbox: dict[str, float]) -> str:
    height = float(bbox["height"])
    if height >= 56:
        return "600"
    if height >= 34 or len(text.strip()) <= 3:
        return "500"
    return "400"


def art_text_rejection_reason(primitive: Primitive) -> str | None:
    text = primitive.text.strip()
    bbox = primitive.bbox
    width = float(bbox["width"])
    height = float(bbox["height"])
    area = width * height
    aspect = width / max(1.0, height)
    alnum_len = len(re.findall(r"[\w\u3400-\u9fff]", text))

    # Decorative hero/logo glyphs are often OCR-visible text but are not normal editable UI copy.
    # Keep this intentionally conservative: regular buttons/headings/labels still become Text.
    if alnum_len <= 1 and area >= 12000 and 0.45 <= aspect <= 1.45:
        return "large_single_glyph_art_text"
    if alnum_len <= 2 and area >= 18000 and 0.55 <= aspect <= 1.75:
        return "large_short_glyph_art_text"
    if len(text) <= 8 and area >= 45000 and height >= 84:
        return "large_logo_or_display_art_text"
    return None


VISUAL_TEXT_OWNER_ROLES = {"image_region", "unknown_region", "symbol_region", "art_text_region"}


def primitive_for_layer(layer: dict[str, Any], primitives: dict[str, Primitive]) -> Primitive | None:
    return primitives.get(str(layer.get("sourcePrimitiveId") or ""))


def layer_complexity(layer: dict[str, Any], primitives: dict[str, Primitive]) -> float:
    primitive = primitive_for_layer(layer, primitives)
    measurements = primitive.measurements if primitive else {}
    texture = float(measurements.get("texture") or 0.0)
    edge = float(measurements.get("edge") or 0.0)
    entropy = float(measurements.get("entropy") or 0.0)
    unique = float(measurements.get("unique") or 0.0)
    return max(texture, edge * 1.15, entropy * 0.80, unique * 0.70)


def layer_reason(layer: dict[str, Any], primitives: dict[str, Primitive]) -> str:
    primitive = primitive_for_layer(layer, primitives)
    if primitive:
        return str(primitive.source.get("reason") or "")
    return str(layer.get("reason") or "")


def is_promo_or_price_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return False
    if re.search(r"[¥￥$€£]\s*\d", compact):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*折", compact):
        return True
    if re.search(r"满\s*\d+.*(?:减|用|使用|券)", compact):
        return True
    if re.search(r"(?:到手价|活动价|券后价|优惠券|立减|促销|特惠|秒杀)", compact):
        return True
    if compact in {"折"}:
        return True
    return False


def promo_text_rejection_reason(primitive: Primitive, canvas: dict[str, int]) -> str | None:
    text = primitive.text.strip()
    if not is_promo_or_price_text(text):
        return None
    bbox = primitive.bbox
    height = float(bbox["height"])
    area = area_of(bbox)
    canvas_area = max(1.0, float(canvas["width"]) * float(canvas["height"]))

    # Price/promo typography in screenshots is commonly designed as a graphic
    # artifact. Preserve only display-sized cases; small table/dashboard values
    # should remain normal editable OCR text.
    if height >= 24 or area >= canvas_area * 0.0025:
        return "promo_display_text_preserved_as_raster"
    return None


def looks_like_simple_control_owner(
    owner: dict[str, Any],
    text_bbox: dict[str, float],
    primitives: dict[str, Primitive],
    canvas: dict[str, int],
) -> bool:
    bbox = owner["bbox"]
    width = float(bbox["width"])
    height = float(bbox["height"])
    aspect = width / max(1.0, height)
    canvas_area = max(1.0, float(canvas["width"]) * float(canvas["height"]))
    area_ratio = area_of(bbox) / canvas_area
    complexity = layer_complexity(owner, primitives)
    text_ratio = area_of(text_bbox) / max(1.0, area_of(bbox))
    short_side = min(float(canvas["width"]), float(canvas["height"]))
    control_height_limit = max(84.0, min(112.0, short_side * 0.12))

    if height <= control_height_limit and 1.8 <= aspect <= 12.0 and area_ratio <= 0.10 and complexity < 0.58:
        return True
    if text_ratio >= 0.42 and height <= 96 and complexity < 0.48:
        return True
    return False


def can_visual_text_owner(
    owner: dict[str, Any],
    text_layer: dict[str, Any],
    primitives: dict[str, Primitive],
    canvas: dict[str, int],
) -> bool:
    if owner is text_layer:
        return False
    if owner.get("role") not in VISUAL_TEXT_OWNER_ROLES:
        return False
    if owner.get("editableMode") == "shape":
        return False
    if is_canvas_like_crop(owner, canvas):
        return False

    owner_bbox = owner["bbox"]
    text_bbox = text_layer["bbox"]
    owner_area = area_of(owner_bbox)
    text_area = area_of(text_bbox)
    if owner_area <= 0 or text_area <= 0:
        return False
    if owner_area < text_area * 1.55:
        return False
    if ioa(text_bbox, owner_bbox) < 0.70:
        return False

    canvas_area = max(1.0, float(canvas["width"]) * float(canvas["height"]))
    area_ratio = owner_area / canvas_area
    complexity = layer_complexity(owner, primitives)
    reason = layer_reason(owner, primitives)

    if area_ratio > 0.55:
        return False
    if area_ratio > 0.28 and complexity < 0.42:
        return False
    if looks_like_simple_control_owner(owner, text_bbox, primitives, canvas):
        return False

    complex_reason = any(
        token in reason
        for token in (
            "high_texture",
            "complex_visual",
            "foreground_object",
            "source_raster",
            "low_texture_solid_region",
            "m29_low_coverage_fallback_object",
        )
    )
    if owner.get("role") in {"symbol_region", "art_text_region"}:
        return area_ratio <= 0.18 or complexity >= 0.38 or complex_reason
    if owner.get("role") in {"image_region", "unknown_region"}:
        return complexity >= 0.32 or complex_reason or area_ratio <= 0.08
    return False


def visual_text_rejection_decision(
    layer: dict[str, Any],
    primitive: Primitive,
    layers: list[dict[str, Any]],
    primitives: dict[str, Primitive],
    canvas: dict[str, int],
) -> dict[str, Any] | None:
    owners = [
        candidate
        for candidate in layers
        if can_visual_text_owner(candidate, layer, primitives, canvas)
    ]
    if owners:
        owner = min(
            owners,
            key=lambda item: (
                area_of(item["bbox"]),
                -layer_complexity(item, primitives),
                str(item.get("id", "")),
            ),
        )
        return {
            "reason": "text_inside_raster_owner",
            "ownerPrimitiveId": owner.get("sourcePrimitiveId"),
            "ownerRole": owner.get("role"),
            "ownerBBox": owner.get("bbox"),
            "ownerComplexity": round(float(layer_complexity(owner, primitives)), 4),
            "ownerReason": layer_reason(owner, primitives),
        }

    promo_reason = promo_text_rejection_reason(primitive, canvas)
    if promo_reason:
        return {"reason": promo_reason}
    return None


def bbox_union(boxes: list[dict[str, float]]) -> dict[str, float]:
    x1 = min(float(box["x"]) for box in boxes)
    y1 = min(float(box["y"]) for box in boxes)
    x2 = max(float(box["x"]) + float(box["width"]) for box in boxes)
    y2 = max(float(box["y"]) + float(box["height"]) for box in boxes)
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def expanded_bbox_for_overlap(bbox: dict[str, float], px: float) -> dict[str, float]:
    return {
        "x": float(bbox["x"]) - px,
        "y": float(bbox["y"]) - px,
        "width": float(bbox["width"]) + px * 2,
        "height": float(bbox["height"]) + px * 2,
    }


def text_cluster_token(text: str) -> str:
    return re.sub(r"\s+", "", text)


def is_price_or_discount_seed(text: str) -> bool:
    compact = text_cluster_token(text)
    if not compact:
        return False
    if is_promo_or_price_text(compact):
        return True
    if re.fullmatch(r"\d+(?:\.\d+)?", compact):
        return True
    if compact in {"折", "券", "减"}:
        return True
    return False


def is_promo_cluster_signal(text: str) -> bool:
    compact = text_cluster_token(text)
    if not compact:
        return False
    if is_promo_or_price_text(compact):
        return True
    if re.search(r"(?:满|使用|领取|入会|详情|活动|时间|赠|加赠|享|直播|备注|暗号)", compact):
        return True
    return False


def can_join_visual_text_cluster(primitive: Primitive) -> bool:
    text = primitive.text
    return is_price_or_discount_seed(text) or is_promo_cluster_signal(text)


def bbox_gap(a: dict[str, float], b: dict[str, float]) -> tuple[float, float]:
    ax1 = float(a["x"])
    ay1 = float(a["y"])
    ax2 = ax1 + float(a["width"])
    ay2 = ay1 + float(a["height"])
    bx1 = float(b["x"])
    by1 = float(b["y"])
    bx2 = bx1 + float(b["width"])
    by2 = by1 + float(b["height"])
    horizontal = max(0.0, max(ax1, bx1) - min(ax2, bx2))
    vertical = max(0.0, max(ay1, by1) - min(ay2, by2))
    return horizontal, vertical


def same_text_cluster_band(a: dict[str, float], b: dict[str, float]) -> bool:
    expanded_a = expanded_bbox_for_overlap(a, max(4.0, min(float(a["height"]), float(b["height"])) * 0.35))
    if intersection_area(expanded_a, b) > 0:
        return True
    _, vertical_gap = bbox_gap(a, b)
    max_height = max(float(a["height"]), float(b["height"]))
    min_height = min(float(a["height"]), float(b["height"]))
    if vertical_gap <= max(4.0, min_height * 0.55):
        return True
    return vertical_gap <= max_height * 0.25


def text_layers_are_cluster_neighbors(
    a: tuple[dict[str, Any], Primitive],
    b: tuple[dict[str, Any], Primitive],
    canvas: dict[str, int],
) -> bool:
    layer_a, primitive_a = a
    layer_b, primitive_b = b
    bbox_a = layer_a["bbox"]
    bbox_b = layer_b["bbox"]
    if not same_text_cluster_band(bbox_a, bbox_b):
        return False

    horizontal_gap, vertical_gap = bbox_gap(bbox_a, bbox_b)
    height = max(float(bbox_a["height"]), float(bbox_b["height"]))
    width = max(float(bbox_a["width"]), float(bbox_b["width"]))
    short_side = max(1.0, float(min(canvas["width"], canvas["height"])))
    max_horizontal_gap = max(10.0, min(short_side * 0.10, height * 2.8, width * 1.4))
    max_vertical_gap = max(6.0, height * 0.85)
    if horizontal_gap <= max_horizontal_gap and vertical_gap <= max_vertical_gap:
        return True

    combined = text_cluster_token(primitive_a.text) + text_cluster_token(primitive_b.text)
    if is_promo_cluster_signal(combined) and horizontal_gap <= max_horizontal_gap * 1.6 and vertical_gap <= max_vertical_gap:
        return True
    return False


def cluster_is_layout_bar(cluster: list[tuple[dict[str, Any], Primitive]], canvas: dict[str, int]) -> bool:
    union = bbox_union([layer["bbox"] for layer, _ in cluster])
    width_ratio = float(union["width"]) / max(1.0, float(canvas["width"]))
    height_ratio = float(union["height"]) / max(1.0, float(canvas["height"]))
    if width_ratio > 0.70 and height_ratio < 0.10:
        return True
    if height_ratio > 0.42 and width_ratio < 0.12:
        return True
    return False


def build_visual_text_cluster_decisions(
    text_items: list[tuple[dict[str, Any], Primitive]],
    single_decisions: dict[str, dict[str, Any]],
    canvas: dict[str, int],
) -> dict[str, dict[str, Any]]:
    if not text_items:
        return {}

    neighbors: dict[str, set[str]] = {primitive.id: set() for _, primitive in text_items}
    by_id = {primitive.id: (layer, primitive) for layer, primitive in text_items}
    for index, item in enumerate(text_items):
        for other in text_items[index + 1 :]:
            if not (can_join_visual_text_cluster(item[1]) and can_join_visual_text_cluster(other[1])):
                continue
            if text_layers_are_cluster_neighbors(item, other, canvas):
                neighbors[item[1].id].add(other[1].id)
                neighbors[other[1].id].add(item[1].id)

    decisions: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for _, primitive in text_items:
        if primitive.id in seen:
            continue
        stack = [primitive.id]
        component_ids: list[str] = []
        seen.add(primitive.id)
        while stack:
            current = stack.pop()
            component_ids.append(current)
            for neighbor in neighbors[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)

        component = [by_id[item_id] for item_id in component_ids]
        seed_ids = {
            item_id
            for item_id in component_ids
            if item_id in single_decisions or is_price_or_discount_seed(by_id[item_id][1].text)
        }
        if not seed_ids:
            continue
        if len(component) == 1 and component_ids[0] not in single_decisions:
            continue
        if len(component) >= 4 and cluster_is_layout_bar(component, canvas):
            continue

        cluster_text = "".join(text_cluster_token(item[1].text) for item in component)
        promo_cluster = is_promo_cluster_signal(cluster_text) or any(
            is_price_or_discount_seed(by_id[item_id][1].text) for item_id in component_ids
        )
        if not promo_cluster and not any(item_id in single_decisions for item_id in component_ids):
            continue
        cluster_bbox = bbox_union([layer["bbox"] for layer, _ in component])
        cluster_id = "visual_text_cluster__" + "__".join(sorted(component_ids))
        for item_id in component_ids:
            existing = single_decisions.get(item_id, {})
            if not existing and not promo_cluster:
                continue
            decisions[item_id] = {
                **existing,
                "reason": existing.get("reason") or "promo_text_cluster_preserved_as_raster",
                "clusterId": cluster_id,
                "clusterPrimitiveIds": sorted(component_ids),
                "clusterBBox": cluster_bbox,
                "clusterText": cluster_text,
                "clusterPolicy": "visual_text_cluster.v1",
            }
    return decisions


def make_text_node(
    layer: dict[str, Any],
    primitive: Primitive,
    paths: ExportPaths,
    canvas: dict[str, Any],
) -> dict[str, Any]:
    text = primitive.text.strip()
    bbox = layer["bbox"]
    candidates = font_candidates_for_text(text)
    measure_family = local_measure_family_for_text(text)
    font_size = fit_font_size(text, bbox, measure_family)
    color, color_source, color_score = sample_text_color(asset_path(paths, primitive.crop_ref))
    font_weight = infer_font_weight(text, bbox)
    script = "mixed" if has_cjk(text) and has_latin_or_digit(text) else ("cjk" if has_cjk(text) else "latin")
    safe_bbox = expanded_text_bounds(bbox, canvas, font_size, script)

    return {
        "id": f"text_{primitive.id}",
        "type": "text",
        "name": f"{primitive.id} editable text",
        "x": safe_bbox["x"],
        "y": safe_bbox["y"],
        "width": safe_bbox["width"],
        "height": safe_bbox["height"],
        "content": text,
        "textGrowth": "fixed-width-height",
        # system-ui previews consistently in Pencil across macOS/Windows. Figma importers should use metadata.fontCandidates.
        "fontFamily": "system-ui",
        "fontSize": font_size,
        "fontWeight": font_weight,
        "lineHeight": 1.0,
        "letterSpacing": 0,
        "textAlign": "left",
        "textAlignVertical": "middle",
        "fill": color,
        "metadata": {
            "type": "m29_editable_text",
            "primitiveId": primitive.id,
            "primitiveType": "text_region",
            "sourceText": text,
            "editableMode": "ocr_text",
            "script": script,
            "fontCandidates": candidates,
            "figmaPreferredFontFamily": candidates[0],
            "fontFamilyPreview": "system-ui",
            "measurementFontFamily": measure_family,
            "fontSize": font_size,
            "fontWeight": font_weight,
            "originalBBox": bbox,
            "safeBBox": safe_bbox,
            "safeBoundsPolicy": "pencil_text_safe_bounds.v1",
            "colorSource": color_source,
            "colorScore": round(float(color_score), 4),
            "z": layer["z"],
        },
    }


def make_text_crop_layer(layer: dict[str, Any], primitive: Primitive, role: str = "art_text_region") -> dict[str, Any]:
    copied = dict(layer)
    copied["role"] = role
    copied["nodeType"] = "rectangle"
    copied["sourcePrimitiveId"] = primitive.id
    copied["fillImage"] = f"./assets/{primitive.crop_ref}"
    return copied


def layer_area(layer: dict[str, Any]) -> float:
    return area_of(layer["bbox"])


def crop_owner_priority(layer: dict[str, Any]) -> int:
    role = layer.get("role")
    if role == "image_region":
        return 60
    if role == "surface_region":
        return 50
    if role == "unknown_region":
        return 45
    if role in {"art_text_region", "visual_text_region"}:
        return 40
    if role == "symbol_region":
        return 30
    if role == "rect":
        return 10
    return 20


def crop_owner_score(layer: dict[str, Any]) -> tuple[int, float, int, str]:
    return (
        crop_owner_priority(layer),
        layer_area(layer),
        int(layer.get("z", 0)),
        str(layer.get("id", "")),
    )


def is_canvas_like_crop(layer: dict[str, Any], canvas: dict[str, int]) -> bool:
    bbox = layer["bbox"]
    canvas_width = max(1.0, float(canvas["width"]))
    canvas_height = max(1.0, float(canvas["height"]))
    if float(bbox["width"]) >= canvas_width * 0.96 and float(bbox["height"]) >= canvas_height * 0.82:
        return True
    if layer.get("role") == "rect" and area_of(bbox) >= canvas_width * canvas_height * 0.35:
        return True
    return False


def component_parent_area_limit(parent: dict[str, Any], canvas_area: float) -> float:
    role = parent.get("role")
    if role == "image_region":
        return canvas_area * 0.55
    if role in {"surface_region", "unknown_region"}:
        return canvas_area * 0.32
    if role in {"art_text_region", "visual_text_region"}:
        return canvas_area * 0.24
    if role == "symbol_region":
        return canvas_area * 0.18
    return canvas_area * 0.12


def can_component_parent(parent: dict[str, Any], child: dict[str, Any], canvas: dict[str, int]) -> bool:
    if parent is child:
        return False
    if parent.get("role") == "rect":
        return False
    if is_canvas_like_crop(parent, canvas):
        return False

    parent_bbox = parent["bbox"]
    child_bbox = child["bbox"]
    parent_area = area_of(parent_bbox)
    child_area = area_of(child_bbox)
    if parent_area <= 0 or child_area <= 0:
        return False
    min_area_ratio = 1.03 if parent.get("role") == "image_region" else 1.12
    if parent_area < child_area * min_area_ratio:
        return False

    canvas_area = max(1.0, float(canvas["width"]) * float(canvas["height"]))
    if parent_area > component_parent_area_limit(parent, canvas_area):
        return False

    child_in_parent = ioa(child_bbox, parent_bbox)
    if child_in_parent < 0.9:
        return False

    # A high-texture image crop from M29 is usually the whole local visual
    # object: card, hero illustration, component, or icon group. In production
    # handoff mode, internal solid surfaces and symbol fragments under that
    # image crop are debug evidence, not separate visible assets. Do not require
    # symmetric margins here: many cards have a lower body surface that shares
    # the parent's left/right/bottom edges and only leaves headroom for an icon.
    if parent.get("role") == "image_region":
        return True

    # Require a real enclosing margin on at least two sides. This keeps near-equal
    # duplicate boxes in the same-region path, and avoids collapsing adjacent chips.
    margins = [
        float(child_bbox["x"]) - float(parent_bbox["x"]),
        float(child_bbox["y"]) - float(parent_bbox["y"]),
        float(parent_bbox["x"] + parent_bbox["width"]) - float(child_bbox["x"] + child_bbox["width"]),
        float(parent_bbox["y"] + parent_bbox["height"]) - float(child_bbox["y"] + child_bbox["height"]),
    ]
    if sum(1 for margin in margins if margin >= 3.0) < 2:
        return False

    return True


def find_component_crop_owner(
    child: dict[str, Any],
    layers: list[dict[str, Any]],
    canvas: dict[str, int],
) -> tuple[dict[str, Any], str] | None:
    same_region: list[dict[str, Any]] = []
    enclosing: list[dict[str, Any]] = []
    child_bbox = child["bbox"]
    child_area = area_of(child_bbox)

    for candidate in layers:
        if candidate is child:
            continue
        candidate_bbox = candidate["bbox"]
        overlap = iou(child_bbox, candidate_bbox)
        candidate_area = area_of(candidate_bbox)
        if overlap >= 0.92 and crop_owner_score(candidate) > crop_owner_score(child):
            same_region.append(candidate)
            continue
        if candidate_area > child_area and can_component_parent(candidate, child, canvas):
            enclosing.append(candidate)

    if same_region:
        return max(same_region, key=crop_owner_score), "same_region_duplicate"
    if enclosing:
        # The smallest enclosing owner is the local component boundary. A larger
        # ancestor may still suppress that owner later, but this keeps the decision
        # grounded in local visual structure instead of global page area.
        return min(enclosing, key=lambda item: (layer_area(item), -crop_owner_priority(item), str(item.get("id", "")))), (
            "internal_fragment_covered_by_component_crop"
        )
    return None


def resolve_suppression_root(
    layer_id: str,
    suppressed_by: dict[str, tuple[str, str]],
) -> tuple[str, str]:
    seen: set[str] = set()
    current = layer_id
    reason = suppressed_by[layer_id][1]
    while current in suppressed_by:
        parent, parent_reason = suppressed_by[current]
        if parent in seen:
            break
        seen.add(parent)
        current = parent
        reason = parent_reason
    return current, reason


def dedupe_component_crop_layers(
    layers: list[dict[str, Any]],
    canvas: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid_layers: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for layer in layers:
        if layer_area(layer) <= 0:
            suppressed.append({"id": layer["id"], "reason": "empty_bbox"})
        else:
            valid_layers.append(layer)

    suppressed_by: dict[str, tuple[str, str]] = {}
    layer_by_id = {str(layer["id"]): layer for layer in valid_layers}
    for layer in sorted(valid_layers, key=lambda item: (layer_area(item), str(item.get("id", "")))):
        owner = find_component_crop_owner(layer, valid_layers, canvas)
        if owner:
            parent, reason = owner
            suppressed_by[str(layer["id"])] = (str(parent["id"]), reason)

    for layer_id, (parent_id, reason) in sorted(suppressed_by.items()):
        duplicate_of, root_reason = resolve_suppression_root(layer_id, suppressed_by)
        layer = layer_by_id[layer_id]
        parent = layer_by_id.get(parent_id)
        root = layer_by_id.get(duplicate_of)
        suppressed.append(
            {
                "id": layer["id"],
                "primitiveId": layer.get("sourcePrimitiveId"),
                "role": layer.get("role"),
                "reason": reason,
                "duplicateOf": duplicate_of,
                "duplicateOfRole": root.get("role") if root else (parent.get("role") if parent else None),
                "rootReason": root_reason,
                "ioaToOwner": round(ioa(layer["bbox"], (root or parent or layer)["bbox"]), 4),
            }
        )

    kept = [layer for layer in valid_layers if str(layer["id"]) not in suppressed_by]
    return sorted(kept, key=lambda item: item.get("z", 0)), suppressed


def dedupe_editable_crop_layers(layers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for layer in sorted(layers, key=lambda item: item.get("z", 0), reverse=True):
        bbox = layer["bbox"]
        area = area_of(bbox)
        if area <= 0:
            suppressed.append({"id": layer["id"], "reason": "empty_bbox"})
            continue
        duplicate_of = None
        for existing in kept:
            existing_bbox = existing["bbox"]
            layer_in_existing = ioa(bbox, existing_bbox)
            existing_in_layer = ioa(existing_bbox, bbox)
            overlap = iou(bbox, existing_bbox)

            # Same or almost-same crops: keep the topmost one.
            if overlap >= 0.92:
                duplicate_of = (existing, "same_region_duplicate")
                break

            # Lower layer is almost fully covered by an already kept upper layer.
            if layer_in_existing >= 0.88:
                duplicate_of = (existing, "covered_by_upper_crop")
                break

            # A small lower fragment nested inside an upper visual crop is usually a
            # duplicate extraction artifact. Preserve explicit art text crops.
            if (
                layer.get("role") not in {"art_text_region", "visual_text_region"}
                and area <= area_of(existing_bbox) * 0.45
                and layer_in_existing >= 0.72
            ):
                duplicate_of = (existing, "nested_duplicate_crop")
                break

            # If the already-kept upper crop is a smaller foreground object inside
            # this larger container, keep both. That is the normal crop/text/icon model.
            if existing_in_layer >= 0.72:
                continue
        if duplicate_of:
            existing, reason = duplicate_of
            suppressed.append(
                {
                    "id": layer["id"],
                    "primitiveId": layer.get("sourcePrimitiveId"),
                    "role": layer.get("role"),
                    "reason": reason,
                    "duplicateOf": existing.get("id"),
                }
            )
        else:
            kept.append(layer)
    return sorted(kept, key=lambda item: item.get("z", 0)), suppressed


def dedupe_visible_crop_layers(
    layers: list[dict[str, Any]],
    canvas: dict[str, int],
    crop_policy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if crop_policy == "component":
        return dedupe_component_crop_layers(layers, canvas)
    return dedupe_editable_crop_layers(layers)


def make_image_node(layer: dict[str, Any], asset_url: str, asset_metadata: dict[str, Any]) -> dict[str, Any]:
    bbox = layer["bbox"]
    metadata = {
        "type": "m29_visible_crop",
        "primitiveId": layer.get("sourcePrimitiveId"),
        "primitiveType": layer["role"],
        "editableMode": "raster_crop",
        "z": layer["z"],
    }
    metadata.update(asset_metadata)
    return {
        "id": f"node_{layer['id']}",
        "type": "rectangle",
        "name": f"{layer['id']} {layer['role']}",
        "x": bbox["x"],
        "y": bbox["y"],
        "width": bbox["width"],
        "height": bbox["height"],
        "fill": {"type": "image", "enabled": True, "url": asset_url, "mode": "stretch"},
        "metadata": metadata,
    }


def make_source_fallback_layer(image: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "source_full",
        "sourcePrimitiveId": "source_full",
        "role": "source_full_raster",
        "bbox": {"x": 0, "y": 0, "width": int(image["width"]), "height": int(image["height"])},
        "z": 0,
    }


def make_shape_node(layer: dict[str, Any]) -> dict[str, Any]:
    bbox = layer["bbox"]
    style = layer.get("shapeStyle") or {}
    fill = style.get("fill") or "#FFFFFF"
    node: dict[str, Any] = {
        "id": f"node_{layer['id']}",
        "type": "rectangle",
        "name": f"{layer['id']} editable shape",
        "x": bbox["x"],
        "y": bbox["y"],
        "width": bbox["width"],
        "height": bbox["height"],
        "fill": fill,
        "metadata": {
            "type": "psdlike_editable_shape",
            "primitiveId": layer["sourcePrimitiveId"],
            "primitiveType": layer["role"],
            "sourceLayerId": layer.get("sourceLayerId"),
            "editableMode": "shape",
            "z": layer["z"],
        },
    }
    radius = style.get("cornerRadius") or style.get("radius")
    if radius is not None:
        node["cornerRadius"] = radius
    stroke = style.get("stroke")
    if isinstance(stroke, dict) and stroke.get("color"):
        node["stroke"] = {
            "align": stroke.get("align", "inside"),
            "thickness": stroke.get("width", stroke.get("thickness", 1)),
            "fill": stroke.get("color"),
        }
    return node


def make_debug_image_node(layer: dict[str, Any]) -> dict[str, Any]:
    bbox = layer["bbox"]
    return {
        "id": f"debug_node_{layer['id']}",
        "type": "rectangle",
        "name": f"{layer['id']} raw {layer['role']}",
        "x": bbox["x"],
        "y": bbox["y"],
        "width": bbox["width"],
        "height": bbox["height"],
        "fill": {"type": "image", "enabled": True, "url": layer["fillImage"].replace("./assets/crops/", "./assets/raw-crops/"), "mode": "stretch"},
        "metadata": {
            "type": "m29_debug_raw_crop",
            "primitiveId": layer["sourcePrimitiveId"],
            "primitiveType": layer["role"],
            "z": layer["z"],
        },
    }


def build_production_document(
    paths: ExportPaths,
    name: str,
    evidence: dict[str, Any],
    replay: dict[str, Any],
    page_fill: str,
    mode: ExportMode,
    enable_text_knockout: bool,
    enable_art_text_gate: bool,
    enable_crop_dedupe: bool,
    crop_policy: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    image = evidence["image"]
    canvas = {"width": int(image["width"]), "height": int(image["height"])}
    primitives = load_primitives(evidence)
    layers = sorted(replay["layers"], key=lambda item: item.get("z", 0))
    editable_text_layers: list[tuple[dict[str, Any], Primitive]] = []
    editable_text_primitives: list[Primitive] = []
    editable_shape_layers: list[dict[str, Any]] = []
    crop_layers: list[dict[str, Any]] = []
    text_decisions: list[dict[str, Any]] = []
    text_items = [
        (layer, primitive)
        for layer in layers
        if layer.get("role") == "text_region"
        and (primitive := primitives.get(layer["sourcePrimitiveId"])) is not None
        and primitive.text.strip()
    ]
    single_visual_text_decisions: dict[str, dict[str, Any]] = {}
    visual_text_decisions: dict[str, dict[str, Any]] = {}
    if enable_art_text_gate and mode.visible_ocr_text:
        for layer, primitive in text_items:
            decision = visual_text_rejection_decision(layer, primitive, layers, primitives, canvas)
            if decision:
                single_visual_text_decisions[primitive.id] = decision
        visual_text_decisions = build_visual_text_cluster_decisions(
            text_items,
            single_visual_text_decisions,
            canvas,
        )

    for layer in layers:
        if layer.get("editableMode") == "shape":
            editable_shape_layers.append(layer)
            continue
        primitive = primitives.get(layer["sourcePrimitiveId"])
        if layer.get("role") != "text_region":
            crop_layers.append(layer)
            continue
        if not primitive or not primitive.text.strip():
            crop_layers.append(layer)
            continue
        art_reason = art_text_rejection_reason(primitive) if enable_art_text_gate else None
        if art_reason:
            crop_layers.append(make_text_crop_layer(layer, primitive))
            text_decisions.append(
                {
                    "primitiveId": primitive.id,
                    "text": primitive.text,
                    "decision": "crop",
                    "reason": art_reason,
                }
            )
            continue
        visual_text_decision = visual_text_decisions.get(primitive.id)
        if visual_text_decision:
            crop_layers.append(make_text_crop_layer(layer, primitive, role="visual_text_region"))
            text_decisions.append(
                {
                    "primitiveId": primitive.id,
                    "text": primitive.text,
                    "decision": "crop",
                    **visual_text_decision,
                }
            )
            continue
        if mode.crop_text_regions:
            crop_layers.append(make_text_crop_layer(layer, primitive, role="text_region"))
        if mode.visible_ocr_text:
            editable_text_layers.append((layer, primitive))
            editable_text_primitives.append(primitive)
        text_decisions.append(
            {
                "primitiveId": primitive.id,
                "text": primitive.text,
                "decision": (
                    "crop_and_visible_ocr"
                    if mode.crop_text_regions and mode.visible_ocr_text
                    else ("editable_text" if mode.visible_ocr_text else "crop")
                ),
                "reason": "normal_ocr_text" if mode.visible_ocr_text else "visual_fidelity_text_crop",
            }
        )

    if enable_crop_dedupe:
        crop_layers, suppressed_crop_layers = dedupe_visible_crop_layers(crop_layers, canvas, crop_policy)
    else:
        suppressed_crop_layers = []

    children: list[dict[str, Any]] = []
    counts = Counter()
    clean_assets: list[dict[str, Any]] = []
    text_nodes = 0
    crop_nodes = 0
    shape_nodes = 0
    knockout_nodes = 0
    source_fallback_nodes = 0

    for layer in sorted(editable_shape_layers, key=lambda item: item.get("z", 0)):
        counts[layer["role"]] += 1
        children.append(make_shape_node(layer))
        shape_nodes += 1

    for layer in sorted(crop_layers, key=lambda item: item.get("z", 0)):
        role = layer["role"]
        counts[role] += 1
        asset_url, asset_metadata = copy_used_crop_to_visible_assets(
            paths,
            layer,
            editable_text_primitives,
            enable_text_knockout=enable_text_knockout,
        )
        children.append(make_image_node(layer, asset_url, asset_metadata))
        crop_nodes += 1
        if asset_metadata.get("textKnockout"):
            knockout_nodes += 1
        clean_assets.append(
            {
                "primitiveId": layer["sourcePrimitiveId"],
                "role": role,
                "url": asset_url,
                **asset_metadata,
            }
        )

    for layer, primitive in editable_text_layers:
        counts[layer["role"]] += 1
        children.append(make_text_node(layer, primitive, paths, canvas))
        text_nodes += 1

    if not children:
        layer = make_source_fallback_layer(image)
        asset_url, asset_metadata = copy_source_to_visible_asset(paths)
        counts[layer["role"]] += 1
        children.append(make_image_node(layer, asset_url, asset_metadata))
        crop_nodes += 1
        source_fallback_nodes += 1
        clean_assets.append(
            {
                "primitiveId": layer["sourcePrimitiveId"],
                "role": layer["role"],
                "url": asset_url,
                **asset_metadata,
            }
        )

    children.sort(key=lambda node: int((node.get("metadata") or {}).get("z", 0)))
    frame_fill = "#FFFFFF" if source_fallback_nodes else page_fill

    document = {
        "version": PEN_VERSION,
        "children": [
            {
                "id": "m29_pencil_page",
                "type": "frame",
                "name": name,
                "x": 0,
                "y": 0,
                "width": image["width"],
                "height": image["height"],
                "layout": "none",
                "fill": frame_fill,
                "clip": False,
                "metadata": {
                    "type": "m29_pencil_production_page",
                    "source": "m29_physical_evidence",
                    "exportMode": mode.name,
                    "rawSourceVisible": False,
                    "sourceFallback": bool(source_fallback_nodes),
                },
                "children": children,
            }
        ],
    }
    manifest = {
        "schema": "m29.pencil.production_manifest.v1",
        "pen": "design.pen",
        "mode": mode.name,
        "modeDescription": mode.description,
        "canvas": {"width": image["width"], "height": image["height"], "fill": page_fill},
        "cropPolicy": crop_policy if enable_crop_dedupe else "disabled",
        "visibleOcrText": mode.visible_ocr_text,
        "cropTextRegions": mode.crop_text_regions,
        "counts": dict(counts),
        "textNodes": text_nodes,
        "cropNodes": crop_nodes,
        "shapeNodes": shape_nodes,
        "textKnockoutCropNodes": knockout_nodes,
        "sourceFallbackNodes": source_fallback_nodes,
        "artTextCropNodes": sum(1 for item in text_decisions if str(item.get("reason", "")).startswith("large_")),
        "visualTextCropNodes": sum(
            1
            for item in text_decisions
            if item["decision"] in {"crop", "crop_and_visible_ocr"}
            and str(item.get("reason", ""))
            in {
                "text_inside_raster_owner",
                "promo_display_text_preserved_as_raster",
                "promo_text_cluster_preserved_as_raster",
            }
        ),
        "cropTextNodes": sum(
            1
            for item in text_decisions
            if item["decision"] in {"crop", "crop_and_visible_ocr"}
            and not str(item.get("reason", "")).startswith("large_")
        ),
        "suppressedDuplicateCropNodes": len(suppressed_crop_layers),
        "suppressedInternalCropNodes": sum(
            1 for item in suppressed_crop_layers if item.get("reason") == "internal_fragment_covered_by_component_crop"
        ),
        "textDecisions": text_decisions,
        "suppressedCropLayers": suppressed_crop_layers,
        "assets": clean_assets,
        "fontPolicy": {
            "penPreviewFontFamily": "system-ui",
            "cjkOrMixedCandidates": CJK_FONT_CANDIDATES,
            "latinCandidates": LATIN_FONT_CANDIDATES,
            "figmaImportRule": "Use metadata.fontCandidates with figma.listAvailableFontsAsync(), then figma.loadFontAsync().",
            "textGrowth": "fixed-width-height",
            "lineHeight": 1.0,
            "verticalAlign": "middle",
        },
        "productionGuarantees": {
            "referencesSourceImage": False,
            "referencesRawCrops": False,
            "referencesMasks": False,
            "referencesTextRegionCrops": mode.crop_text_regions,
            "rendersEditableShapes": shape_nodes > 0,
        },
    }
    return document, manifest


def build_debug_document(
    name: str,
    evidence: dict[str, Any],
    replay: dict[str, Any],
    page_fill: str,
) -> dict[str, Any]:
    image = evidence["image"]
    children: list[dict[str, Any]] = [
        {
            "id": "debug_reference_source_image",
            "type": "rectangle",
            "name": "Debug Reference Source Image",
            "x": 0,
            "y": 0,
            "width": image["width"],
            "height": image["height"],
            "opacity": 0.16,
            "fill": {"type": "image", "enabled": True, "url": "./assets/source.png", "mode": "stretch"},
            "metadata": {"type": "m29_debug_reference_image"},
        }
    ]
    for layer in sorted(replay["layers"], key=lambda item: item.get("z", 0)):
        children.append(make_debug_image_node(layer))
    return {
        "version": PEN_VERSION,
        "children": [
            {
                "id": "m29_pencil_debug_page",
                "type": "frame",
                "name": f"{name} Debug",
                "x": 0,
                "y": 0,
                "width": image["width"],
                "height": image["height"],
                "layout": "none",
                "fill": page_fill,
                "clip": False,
                "metadata": {"type": "m29_pencil_debug_page"},
                "children": children,
            }
        ],
    }


def prepare_dirs(paths: ExportPaths) -> None:
    if paths.out_dir.exists():
        shutil.rmtree(paths.out_dir)
    paths.production_dir.mkdir(parents=True, exist_ok=True)
    paths.debug_assets_dir.mkdir(parents=True, exist_ok=True)


def prepare_mode_dirs(paths: ExportPaths) -> None:
    paths.production_assets_dir.mkdir(parents=True, exist_ok=True)


def copy_debug_assets(
    paths: ExportPaths,
    evidence_path: Path,
    replay_path: Path,
    replay: dict[str, Any],
) -> None:
    source = paths.input_dir / "assets" / "source.png"
    if not source.exists():
        source = Path(str((evidence_path.parent / "m29_physical_evidence.v1.json"))).parent / "source.png"
    if source.exists():
        shutil.copy2(source, paths.debug_assets_dir / "source.png")
    raw_crops = paths.debug_assets_dir / "raw-crops"
    masks = paths.debug_assets_dir / "masks"
    crops_source = paths.input_dir / "assets" / "crops"
    if not crops_source.exists():
        crops_source = paths.input_dir / "crops"
    masks_source = paths.input_dir / "assets" / "masks"
    if not masks_source.exists():
        masks_source = paths.input_dir / "masks"
    if crops_source.exists():
        shutil.copytree(crops_source, raw_crops, dirs_exist_ok=True)
    if masks_source.exists():
        shutil.copytree(masks_source, masks, dirs_exist_ok=True)
    evidence_dir = paths.debug_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(evidence_path, evidence_dir / evidence_path.name)
    if replay_path.exists():
        shutil.copy2(replay_path, evidence_dir / replay_path.name)
    else:
        write_json(evidence_dir / replay_path.name, replay)


def verify_production_document(document: dict[str, Any]) -> list[str]:
    serialized = json.dumps(document, ensure_ascii=False)
    forbidden = ["source.png", "raw-crops", "masks/", "./assets/crops/", "./assets/masks/"]
    return [item for item in forbidden if item in serialized]


def export_package(args: argparse.Namespace) -> dict[str, Any]:
    input_dir = args.input_dir.resolve()
    out_dir = args.out.resolve()
    paths = ExportPaths(
        input_dir=input_dir,
        out_dir=out_dir,
        production_dir=out_dir / "production",
        debug_dir=out_dir / "debug",
        production_assets_dir=out_dir / "production" / "assets" / "visible",
        debug_assets_dir=out_dir / "debug" / "assets",
    )
    evidence_path = input_dir / "m29_physical_evidence.v1.json"
    replay_path = input_dir / "m29-pencil-replay.v1.json"
    if not evidence_path.exists():
        raise FileNotFoundError(f"Missing evidence: {evidence_path}")

    evidence = read_json(evidence_path)
    replay = read_json(replay_path) if replay_path.exists() else build_replay_from_evidence(evidence)
    page_fill = infer_page_fill(evidence, args.page_fill)

    prepare_dirs(paths)
    mode_results: dict[str, Any] = {}
    first_result: dict[str, Any] | None = None
    for mode in export_modes(args):
        mode_paths = paths_for_mode(paths, mode)
        prepare_mode_dirs(mode_paths)
        production_doc, manifest = build_production_document(
            mode_paths,
            f"{args.name} [{mode.name}]",
            evidence,
            replay,
            page_fill,
            mode=mode,
            enable_text_knockout=mode.enable_text_knockout,
            enable_art_text_gate=not args.disable_art_text_gate,
            enable_crop_dedupe=mode.enable_crop_dedupe,
            crop_policy=mode.crop_policy,
        )
        forbidden_refs = verify_production_document(production_doc)
        if forbidden_refs:
            raise RuntimeError(f"{mode.name} .pen references forbidden debug/raw assets: {forbidden_refs}")

        write_json(mode_paths.production_dir / "design.pen", production_doc)
        write_json(mode_paths.production_dir / "manifest.json", manifest)
        write_json(mode_paths.production_dir / "pencil-document.v1.json", production_doc)
        summary = {
            "textNodes": manifest["textNodes"],
            "cropNodes": manifest["cropNodes"],
            "textKnockoutCropNodes": manifest["textKnockoutCropNodes"],
            "artTextCropNodes": manifest["artTextCropNodes"],
            "cropTextNodes": manifest["cropTextNodes"],
            "suppressedDuplicateCropNodes": manifest["suppressedDuplicateCropNodes"],
            "suppressedInternalCropNodes": manifest["suppressedInternalCropNodes"],
            "sourceFallbackNodes": manifest["sourceFallbackNodes"],
            "assetCount": len(manifest["assets"]),
        }
        result = {
            "mode": mode.name,
            "dir": str(mode_paths.production_dir),
            "pen": str(mode_paths.production_dir / "design.pen"),
            "manifest": str(mode_paths.production_dir / "manifest.json"),
            "summary": summary,
        }
        mode_results[mode.name] = result
        if first_result is None:
            first_result = result

    copy_debug_assets(paths, evidence_path, replay_path, replay)
    if args.include_debug_pen:
        debug_doc = build_debug_document(args.name, evidence, replay, page_fill)
        write_json(paths.debug_dir / "design-debug.pen", debug_doc)
        write_json(paths.debug_dir / "pencil-document.debug.v1.json", debug_doc)
    write_json(paths.debug_dir / "reports" / "export-modes-summary.json", mode_results)
    if "clean-editable" in mode_results:
        clean_manifest = read_json(Path(mode_results["clean-editable"]["manifest"]))
        write_json(paths.debug_dir / "reports" / "production-manifest-copy.json", clean_manifest)

    primary = mode_results.get("clean-editable") or first_result
    assert primary is not None
    return {
        "outDir": str(out_dir),
        "mode": args.mode,
        "productionPen": primary["pen"],
        "manifest": primary["manifest"],
        "debugDir": str(paths.debug_dir),
        "summary": primary["summary"],
        "modes": mode_results,
    }


def main() -> None:
    result = export_package(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
