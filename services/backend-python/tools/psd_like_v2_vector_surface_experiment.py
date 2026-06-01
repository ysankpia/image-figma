#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tools.psd_like_layer_decomposition_experiment import (
    BBox,
    OCRBlock,
    binary_close,
    binary_dilate,
    build_draft_runtime_dsl,
    build_layer_stack,
    build_text_mask,
    clamp,
    clamp_box,
    color_distance,
    color_hex,
    component_bbox,
    connected_components,
    count_text_blocks,
    dominant_cluster_stats,
    estimate_background_color,
    intersection_area,
    load_ocr_blocks,
    relative_luminance,
    sample_text_color,
    write_draft_preview_png,
    write_preview_html,
    write_preview_report,
)


@dataclass(frozen=True)
class VectorSurfaceCandidate:
    id: str
    bbox: BBox
    fill: tuple[int, int, int]
    corner_radius: int
    confidence: float
    contained_text_ids: list[str]
    reason: str
    scores: dict[str, float]


@dataclass(frozen=True)
class RasterFallbackCandidate:
    id: str
    bbox: BBox
    score: float
    reason: str
    scores: dict[str, float]


def contained_text_blocks(box: BBox, blocks: list[OCRBlock], min_coverage: float = 0.82) -> list[OCRBlock]:
    contained: list[OCRBlock] = []
    for block in blocks:
        if block.bbox.area <= 0:
            continue
        if intersection_area(box, block.bbox) / block.bbox.area >= min_coverage:
            contained.append(block)
    return contained


def text_union(blocks: list[OCRBlock]) -> BBox | None:
    if not blocks:
        return None
    x1 = min(block.bbox.x for block in blocks)
    y1 = min(block.bbox.y for block in blocks)
    x2 = max(block.bbox.x2 for block in blocks)
    y2 = max(block.bbox.y2 for block in blocks)
    return BBox(x1, y1, x2 - x1, y2 - y1)


def stable_fill_stats(rgb: np.ndarray, box: BBox, text_mask: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    crop = rgb[box.y : box.y2, box.x : box.x2]
    if crop.size == 0:
        return np.array([255, 255, 255], dtype=np.uint8), 0.0, 0.0, 1.0
    local_text = text_mask[box.y : box.y2, box.x : box.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)
    pixels = crop[~local_text]
    if pixels.shape[0] < max(16, crop.shape[0] * crop.shape[1] // 8):
        pixels = crop.reshape(-1, 3)
    fill, bucket_coverage = dominant_cluster_stats(pixels.astype(np.uint8), bucket_size=20)
    distances = np.linalg.norm(pixels.astype(np.float32) - fill.reshape(1, 3).astype(np.float32), axis=1)
    close_coverage = float((distances <= 64.0).mean()) if distances.size else 0.0
    texture = float(np.sqrt(np.mean(np.var(pixels.astype(np.float32), axis=0)))) if pixels.size else 255.0
    return fill, bucket_coverage, close_coverage, texture


def text_contrast(rgb: np.ndarray, blocks: list[OCRBlock], fill: np.ndarray) -> float:
    best = 0.0
    height, width, _ = rgb.shape
    for block in blocks:
        box = clamp_box(block.bbox, width, height)
        if box is None:
            continue
        region = rgb[box.y : box.y2, box.x : box.x2]
        if region.size == 0:
            continue
        pixels = region.reshape(-1, 3).astype(np.float32)
        distances = np.linalg.norm(pixels - fill.reshape(1, 3).astype(np.float32), axis=1)
        if distances.size:
            best = max(best, float(np.percentile(distances, 92)))
    return best


def infer_corner_radius(rgb: np.ndarray, box: BBox, fill: np.ndarray) -> int:
    max_radius = max(0, min(box.width, box.height) // 2 - 1)
    if max_radius <= 0:
        return 0
    crop = rgb[box.y : box.y2, box.x : box.x2].astype(np.float32)
    if crop.size == 0:
        return 0
    close = np.linalg.norm(crop - fill.reshape(1, 1, 3).astype(np.float32), axis=2) <= 64.0
    runs: list[int] = []
    for corner in ("tl", "tr", "bl", "br"):
        run = corner_background_run(close, corner, max_radius)
        if run > 0:
            runs.append(run)
    if not runs:
        return 0
    return max(0, min(max_radius, int(round(float(np.median(runs)) * 3.4))))


def corner_background_run(close_mask: np.ndarray, corner: str, max_radius: int) -> int:
    height, width = close_mask.shape
    limit = max(0, min(max_radius, height // 2, width // 2))
    run = 0
    for offset in range(limit):
        if corner == "tl":
            inside = bool(close_mask[offset, offset])
        elif corner == "tr":
            inside = bool(close_mask[offset, width - 1 - offset])
        elif corner == "bl":
            inside = bool(close_mask[height - 1 - offset, offset])
        else:
            inside = bool(close_mask[height - 1 - offset, width - 1 - offset])
        if inside:
            break
        run = offset + 1
    return run


def is_full_page_backing(box: BBox, width: int, height: int) -> bool:
    page_area = width * height
    if page_area <= 0:
        return False
    return box.area / page_area >= 0.62 or (box.width >= width * 0.94 and box.height >= height * 0.70)


def is_vector_surface_physical_match(
    box: BBox,
    blocks: list[OCRBlock],
    fill: np.ndarray,
    bucket_coverage: float,
    close_coverage: float,
    texture: float,
    contrast: float,
    width: int,
    height: int,
) -> bool:
    if not blocks or len(blocks) > 6:
        return False
    if box.area < 480 or is_full_page_backing(box, width, height):
        return False
    if box.width < 24 or box.height < 14:
        return False
    area_ratio = box.area / max(1, width * height)
    if area_ratio > 0.35:
        return False
    if bucket_coverage < 0.24 and close_coverage < 0.52:
        return False
    if texture > 88.0 and close_coverage < 0.70:
        return False
    if contrast < 38.0:
        return False
    text_box = text_union(blocks)
    if text_box is None:
        return False
    if text_box.area / max(1, box.area) > 0.62:
        return False
    left_pad = text_box.x - box.x
    right_pad = box.x2 - text_box.x2
    top_pad = text_box.y - box.y
    bottom_pad = box.y2 - text_box.y2
    if min(left_pad, right_pad, top_pad, bottom_pad) < -1:
        return False
    if left_pad + right_pad < max(6, int(box.width * 0.08)):
        return False
    if top_pad + bottom_pad < max(4, int(box.height * 0.08)):
        return False
    if relative_luminance(fill) < 20 and close_coverage < 0.72:
        return False
    return True


def expanded_box(box: BBox, width: int, height: int, x_pad: int, y_pad: int) -> BBox | None:
    return clamp_box(
        BBox(box.x - x_pad, box.y - y_pad, box.width + x_pad * 2, box.height + y_pad * 2),
        width,
        height,
    )


def estimate_surface_fill_near_text(rgb: np.ndarray, text_mask: np.ndarray, block: OCRBlock) -> tuple[np.ndarray, float]:
    height, width, _ = rgb.shape
    outer_pad_x = max(8, min(80, int(round(block.bbox.width * 0.55))))
    outer_pad_y = max(6, min(48, int(round(block.bbox.height * 1.35))))
    outer = expanded_box(block.bbox, width, height, outer_pad_x, outer_pad_y)
    inner = expanded_box(block.bbox, width, height, 1, 1)
    if outer is None:
        return np.array([255, 255, 255], dtype=np.uint8), 0.0

    crop = rgb[outer.y : outer.y2, outer.x : outer.x2]
    local_text = text_mask[outer.y : outer.y2, outer.x : outer.x2].copy()
    if inner is not None:
        local_text[
            max(0, inner.y - outer.y) : max(0, inner.y2 - outer.y),
            max(0, inner.x - outer.x) : max(0, inner.x2 - outer.x),
        ] = True

    pixels = crop[~local_text]
    if pixels.shape[0] < 16:
        pixels = crop.reshape(-1, 3)
    return dominant_cluster_stats(pixels.astype(np.uint8), bucket_size=20)


def candidate_window_for_block(box: BBox, width: int, height: int) -> BBox | None:
    x_pad = max(32, min(220, int(round(box.width * 2.2))))
    y_pad = max(22, min(150, int(round(box.height * 4.2))))
    return expanded_box(box, width, height, x_pad, y_pad)


def component_touching_seed(
    mask: np.ndarray,
    seed_box: BBox,
    origin_x: int,
    origin_y: int,
) -> list[tuple[int, int]] | None:
    local_seed = BBox(seed_box.x - origin_x, seed_box.y - origin_y, seed_box.width, seed_box.height)
    seed_mask = np.zeros_like(mask, dtype=bool)
    x1 = max(0, local_seed.x)
    y1 = max(0, local_seed.y)
    x2 = min(mask.shape[1], local_seed.x2)
    y2 = min(mask.shape[0], local_seed.y2)
    if x2 <= x1 or y2 <= y1:
        return None
    seed_mask[y1:y2, x1:x2] = True

    best: list[tuple[int, int]] | None = None
    best_overlap = 0
    for component in connected_components(mask):
        overlap = sum(1 for row, col in component if seed_mask[row, col])
        if overlap > best_overlap:
            best = component
            best_overlap = overlap
    return best if best_overlap > 0 else None


def extract_surface_from_text_seed(
    rgb: np.ndarray,
    text_mask: np.ndarray,
    block: OCRBlock,
    page_background: tuple[int, int, int],
) -> tuple[BBox, np.ndarray, dict[str, float]] | None:
    height, width, _ = rgb.shape
    window = candidate_window_for_block(block.bbox, width, height)
    if window is None:
        return None

    fill, seed_coverage = estimate_surface_fill_near_text(rgb, text_mask, block)
    page_distance = color_distance(fill, page_background)
    crop = rgb[window.y : window.y2, window.x : window.x2]
    local_text = text_mask[window.y : window.y2, window.x : window.x2]
    if crop.size == 0:
        return None

    distances = np.linalg.norm(crop.astype(np.float32) - fill.reshape(1, 1, 3).astype(np.float32), axis=2)
    close_threshold = 58.0 if page_distance >= 20.0 else 42.0
    close = distances <= close_threshold
    if local_text.shape == close.shape:
        close |= local_text
    close = binary_close(close, iterations=2)

    component = component_touching_seed(close, block.bbox, window.x, window.y)
    if component is None:
        return None
    local_box = component_bbox(component, 1, window.width, window.height)
    global_box = clamp_box(BBox(window.x + local_box.x, window.y + local_box.y, local_box.width, local_box.height), width, height)
    if global_box is None:
        return None

    return (
        global_box,
        fill,
        {
            "seedFillCoverage": round(float(seed_coverage), 4),
            "seedPageDistance": round(float(page_distance), 4),
            "seedCloseThreshold": round(float(close_threshold), 4),
        },
    )


def extract_vector_surfaces(
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
    min_area: int = 480,
) -> list[VectorSurfaceCandidate]:
    height, width, _ = rgb.shape
    page_background = estimate_background_color(rgb)
    candidates: list[VectorSurfaceCandidate] = []

    for index, block in enumerate(ocr_blocks, start=1):
        extracted = extract_surface_from_text_seed(rgb, text_mask, block, page_background)
        if extracted is None:
            continue
        box, seed_fill, seed_scores = extracted
        if box.area < min_area:
            continue
        blocks = contained_text_blocks(box, ocr_blocks)
        fill, bucket_coverage, close_coverage, texture = stable_fill_stats(rgb, box, text_mask)
        contrast = text_contrast(rgb, blocks, fill)
        if not is_vector_surface_physical_match(box, blocks, fill, bucket_coverage, close_coverage, texture, contrast, width, height):
            continue
        radius = infer_corner_radius(rgb, box, fill)
        confidence = clamp(0.35 + close_coverage * 0.30 + bucket_coverage * 0.20 + min(1.0, contrast / 160.0) * 0.15)
        seed_distance = color_distance(seed_fill, fill)
        candidates.append(
            VectorSurfaceCandidate(
                id=f"surface_{index:04d}",
                bbox=box,
                fill=(int(fill[0]), int(fill[1]), int(fill[2])),
                corner_radius=radius,
                confidence=round(confidence, 4),
                contained_text_ids=[block.id for block in blocks],
                reason="vector_surface_contains_ocr",
                scores={
                    **seed_scores,
                    "seedToFinalFillDistance": round(float(seed_distance), 4),
                    "bucketCoverage": round(float(bucket_coverage), 4),
                    "closeCoverage": round(float(close_coverage), 4),
                    "texture": round(float(texture), 4),
                    "textContrast": round(float(contrast), 4),
                },
            )
        )

    return dedupe_vector_surfaces(candidates)


def dedupe_vector_surfaces(candidates: list[VectorSurfaceCandidate]) -> list[VectorSurfaceCandidate]:
    accepted: list[VectorSurfaceCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.confidence, item.bbox.area), reverse=True):
        duplicate = False
        for kept in accepted:
            if intersection_area(candidate.bbox, kept.bbox) / max(1, min(candidate.bbox.area, kept.bbox.area)) >= 0.82:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def surface_to_dict(surface: VectorSurfaceCandidate) -> dict[str, Any]:
    return {
        "id": surface.id,
        "bbox": surface.bbox.to_dict(),
        "fill": color_hex(np.array(surface.fill, dtype=np.uint8)),
        "cornerRadius": surface.corner_radius,
        "confidence": surface.confidence,
        "containedTextIds": surface.contained_text_ids,
        "reason": surface.reason,
        "scores": surface.scores,
    }


def write_surface_overlay(
    image: Image.Image,
    surfaces: list[VectorSurfaceCandidate],
    ocr_blocks: list[OCRBlock],
    output_path: Path,
) -> None:
    overlay = image.convert("RGBA")
    draw = ImageDraw.Draw(overlay, "RGBA")
    for index, surface in enumerate(surfaces, start=1):
        box = surface.bbox
        draw.rounded_rectangle(
            (box.x, box.y, box.x2, box.y2),
            radius=max(0, surface.corner_radius),
            outline=(40, 180, 90, 255),
            width=3,
        )
        draw.text((box.x + 2, box.y + 2), f"V{index}", fill=(40, 180, 90, 255))
    for block in ocr_blocks:
        box = block.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(60, 120, 255, 220), width=2)
    overlay.convert("RGB").save(output_path)


def write_surface_diagnostics(path: Path, surfaces: list[VectorSurfaceCandidate], image: Image.Image, ocr_blocks: list[OCRBlock]) -> None:
    lines = [
        "# PSD-like v2 Vector Surface Diagnostics",
        "",
        f"- canvas: {image.width}x{image.height}",
        f"- OCR blocks: {len(ocr_blocks)}",
        f"- vector surfaces: {len(surfaces)}",
        "",
        "| id | bbox | fill | radius | confidence | text ids | reason |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for surface in surfaces:
        box = surface.bbox
        lines.append(
            f"|{surface.id}|{box.x},{box.y},{box.width},{box.height}|{color_hex(np.array(surface.fill, dtype=np.uint8))}|"
            f"{surface.corner_radius}|{surface.confidence}|{','.join(surface.contained_text_ids)}|{surface.reason}|"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    image_path = Path(args.image).expanduser().resolve()
    output_dir = Path(args.out).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_path: Path | None = None
    if args.ocr:
        candidate = Path(args.ocr).expanduser().resolve()
        if candidate.exists():
            ocr_path = candidate
        elif not args.allow_missing_ocr:
            raise FileNotFoundError(f"OCR artifact not found: {candidate}")

    image = Image.open(image_path).convert("RGB")
    rgb = np.asarray(image)
    ocr_blocks = load_ocr_blocks(ocr_path, image.width, image.height, args.ocr_min_confidence)
    text_mask = build_text_mask(image.width, image.height, ocr_blocks, args.text_padding)
    surfaces = extract_vector_surfaces(rgb, ocr_blocks, text_mask, min_area=args.vector_min_area)

    artifact = {
        "version": "vector_surfaces.v1",
        "sourceImage": str(image_path),
        "ocr": str(ocr_path) if ocr_path else "",
        "canvas": {"width": image.width, "height": image.height},
        "surfaces": [surface_to_dict(surface) for surface in surfaces],
    }
    (output_dir / "vector_surfaces.v1.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_surface_overlay(image, surfaces, ocr_blocks, output_dir / "surface_overlay.png")
    write_surface_diagnostics(output_dir / "surface_diagnostics.md", surfaces, image, ocr_blocks)
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PSD-like v2 vector surface extraction experiment.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--ocr", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--allow-missing-ocr", action="store_true")
    parser.add_argument("--text-padding", type=int, default=3)
    parser.add_argument("--ocr-min-confidence", type=float, default=0.70)
    parser.add_argument("--vector-min-area", type=int, default=480)
    return parser.parse_args()


def main() -> None:
    artifact = run(parse_args())
    print(
        "PSD-like v2 vector surface: "
        f"surfaces={len(artifact.get('surfaces', []))} "
        f"out={Path(artifact.get('sourceImage', '')).name}"
    )


if __name__ == "__main__":
    main()
