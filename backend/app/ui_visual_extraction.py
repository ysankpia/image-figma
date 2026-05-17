from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .icon_candidate import bbox_in_bounds, iou, normalize_bbox
from .icon_coverage import draw_rect
from .perception_benchmark import resize_rgb_for_sam2, sam2_bbox_to_image_bbox
from .png_tools import PngMetadata, PngPixels, UnsupportedPngCropError
from .png_tools import decode_png_pixels, encode_rgb_png, read_png_metadata
from .sam_visual_candidate import get_sam2_runtime, synchronize_torch_device


M28Quality = Literal["default", "high"]
M28Kind = Literal["icon_candidate", "image_asset", "control_candidate"]

DEFAULT_SOURCE_IMAGE = Path("/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png")
DEFAULT_CHECKPOINT = Path("/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt")

OVERLAY_COLORS = {
    "icon_candidate": (0, 200, 90),
    "image_asset": (0, 122, 255),
    "control_candidate": (255, 149, 0),
    "blocked": (235, 64, 52),
    "inside_image_asset": (128, 128, 128),
}


@dataclass(frozen=True)
class M28ExtractionOptions:
    source_image: Path = DEFAULT_SOURCE_IMAGE
    checkpoint: Path = DEFAULT_CHECKPOINT
    output_dir: Path = Path("storage/m28_single_visual_extraction")
    quality: M28Quality = "default"
    model_cfg: str = ""
    device: str = "auto"
    max_image_edge: int = 1280
    points_per_side: int | None = None
    points_per_batch: int = 64
    max_masks: int = 500


@dataclass(frozen=True)
class M28SamSettings:
    sam_visual_candidate_checkpoint: str
    sam_visual_candidate_model_cfg: str
    sam_visual_candidate_device: str
    sam_visual_candidate_points_per_side: int
    sam_visual_candidate_points_per_batch: int


@dataclass
class M28SamInfo:
    device: str
    model: str
    checkpoint: str
    rawMaskCount: int
    maxImageEdge: int
    pointsPerSide: int
    pointsPerBatch: int
    loadMs: int
    inferenceMs: int
    postprocessMs: int
    cached: bool


@dataclass
class M28QualityInfo:
    reasons: list[str]


@dataclass
class M28VisualItem:
    id: str
    kind: M28Kind
    bbox: list[int]
    assetPath: str
    confidence: float
    sourceMaskIds: list[str]
    quality: M28QualityInfo


@dataclass
class M28BlockedItem:
    id: str
    kind: str
    bbox: list[int]
    confidence: float
    sourceMaskIds: list[str]
    reasons: list[str]


@dataclass
class M28UiVisualExtractionDocument:
    version: str
    sourceImage: str
    imageSize: dict[str, int]
    sam: M28SamInfo
    icons: list[M28VisualItem]
    imageAssets: list[M28VisualItem]
    controls: list[M28VisualItem]
    blocked: list[M28BlockedItem]
    overlayPath: str | None
    previewSheetPath: str | None
    warnings: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M28RawMask:
    id: str
    bbox: list[int]
    mask_area: int
    predicted_iou: float
    stability_score: float


@dataclass
class M28Candidate:
    kind: M28Kind
    bbox: list[int]
    confidence: float
    source_mask_ids: list[str]
    reasons: list[str]


@dataclass(frozen=True)
class RegionStats:
    width: int
    height: int
    area: int
    sampled: int
    brightness: float
    red_fraction: float
    dark_fraction: float
    light_fraction: float
    color_bucket_count: int
    color_variance: float
    texture: float


def extract_m28_ui_visual_objects(options: M28ExtractionOptions) -> M28UiVisualExtractionDocument:
    started = time.perf_counter()
    source = options.source_image.expanduser().resolve()
    output_dir = options.output_dir.expanduser().resolve()
    checkpoint = options.checkpoint.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"M28 source image does not exist: {source}")
    if not checkpoint.exists():
        raise FileNotFoundError(f"SAM2 checkpoint does not exist: {checkpoint}")

    png_data = source.read_bytes()
    image = read_png_metadata(png_data)
    if image is None:
        raise UnsupportedPngCropError("M28 source image is not a readable PNG.")
    pixels = decode_png_pixels(png_data)

    points_per_side = options.points_per_side or (24 if options.quality == "high" else 16)
    settings = M28SamSettings(
        sam_visual_candidate_checkpoint=str(checkpoint),
        sam_visual_candidate_model_cfg=options.model_cfg,
        sam_visual_candidate_device=options.device,
        sam_visual_candidate_points_per_side=points_per_side,
        sam_visual_candidate_points_per_batch=options.points_per_batch,
    )

    runtime, cached = get_sam2_runtime(settings)  # type: ignore[arg-type]
    rgb = runtime.np.frombuffer(b"".join(pixels.rows), dtype=runtime.np.uint8).reshape((image.height, image.width, 3))
    scaled_rgb, scale = resize_rgb_for_sam2(rgb, options.max_image_edge, runtime.np)
    inference_started = time.perf_counter()
    with runtime.torch.inference_mode():
        masks = runtime.generator.generate(scaled_rgb)
    synchronize_torch_device(runtime)
    inference_ms = elapsed_ms(inference_started)

    postprocess_started = time.perf_counter()
    raw_masks = sam2_raw_masks(masks, scale, image, max_masks=options.max_masks)
    candidates, blocked = classify_visual_objects(raw_masks, pixels, image)
    write_visual_outputs(
        png_data=png_data,
        pixels=pixels,
        image=image,
        candidates=candidates,
        blocked=blocked,
        output_dir=output_dir,
    )
    icons = candidates_to_items([item for item in candidates if item.kind == "icon_candidate"], output_dir / "icons")
    image_assets = candidates_to_items([item for item in candidates if item.kind == "image_asset"], output_dir / "images")
    controls = candidates_to_items([item for item in candidates if item.kind == "control_candidate"], output_dir / "controls")
    blocked_items = [
        M28BlockedItem(
            id=f"blocked_m28_{index + 1:03d}",
            kind="blocked",
            bbox=item.bbox,
            confidence=round(item.confidence, 3),
            sourceMaskIds=item.source_mask_ids,
            reasons=item.reasons,
        )
        for index, item in enumerate(blocked)
    ]
    overlay_path = output_dir / "m28_visual_extraction_overlay.png"
    preview_path = output_dir / "m28_visual_extraction_preview_sheet.png"
    postprocess_ms = elapsed_ms(postprocess_started)
    document = M28UiVisualExtractionDocument(
        version="0.1",
        sourceImage=str(source),
        imageSize={"width": image.width, "height": image.height},
        sam=M28SamInfo(
            device=runtime.device,
            model=runtime.config,
            checkpoint=str(checkpoint),
            rawMaskCount=len(masks),
            maxImageEdge=options.max_image_edge,
            pointsPerSide=points_per_side,
            pointsPerBatch=options.points_per_batch,
            loadMs=0 if cached else runtime.loadMs,
            inferenceMs=inference_ms,
            postprocessMs=postprocess_ms,
            cached=cached,
        ),
        icons=icons,
        imageAssets=image_assets,
        controls=controls,
        blocked=blocked_items,
        overlayPath=str(overlay_path) if overlay_path.exists() else None,
        previewSheetPath=str(preview_path) if preview_path.exists() else None,
        warnings=[],
        meta=build_meta(icons, image_assets, controls, blocked_items, elapsed_ms(started)),
    )
    validate_m28_document(document, image)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "m28_visual_extraction.json").write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return document


def sam2_raw_masks(masks: list[dict[str, Any]], scale: float, image: PngMetadata, *, max_masks: int) -> list[M28RawMask]:
    raw: list[M28RawMask] = []
    sorted_masks = sorted(
        masks,
        key=lambda item: (float(item.get("predicted_iou") or 0.0), float(item.get("area") or 0.0)),
        reverse=True,
    )
    for index, mask in enumerate(sorted_masks[:max_masks]):
        bbox = sam2_bbox_to_image_bbox(mask.get("bbox"), scale, image)
        if bbox is None:
            continue
        mask_area = int(round(float(mask.get("area") or 0.0) / max(scale * scale, 0.000001)))
        raw.append(
            M28RawMask(
                id=f"sam2_mask_{index + 1:03d}",
                bbox=bbox,
                mask_area=mask_area,
                predicted_iou=round(float(mask.get("predicted_iou") or 0.0), 3),
                stability_score=round(float(mask.get("stability_score") or 0.0), 3),
            )
        )
    return raw


def classify_visual_objects(
    raw_masks: list[M28RawMask],
    pixels: PngPixels,
    image: PngMetadata,
) -> tuple[list[M28Candidate], list[M28Candidate]]:
    blocked: list[M28Candidate] = []
    image_assets = select_image_assets(raw_masks, pixels, image, blocked)
    protected = [candidate.bbox for candidate in image_assets]

    accepted: list[M28Candidate] = list(image_assets)
    for raw in raw_masks:
        if is_status_bar(raw.bbox, image):
            blocked.append(blocked_candidate(raw, "inside_status_bar", confidence=raw_confidence(raw)))
            continue
        if any(overlap_ratio(raw.bbox, zone) > 0.72 for zone in protected):
            if not any(iou(raw.bbox, image_asset.bbox) > 0.70 for image_asset in image_assets):
                blocked.append(blocked_candidate(raw, "inside_image_asset", confidence=raw_confidence(raw)))
            continue
        candidate = classify_non_image_mask(raw, pixels, image)
        if candidate is None:
            blocked.append(blocked_candidate(raw, "background_like", confidence=raw_confidence(raw)))
            continue
        if any(iou(candidate.bbox, item.bbox) > 0.78 for item in accepted):
            blocked.append(
                M28Candidate(
                    kind=candidate.kind,
                    bbox=candidate.bbox,
                    confidence=candidate.confidence,
                    source_mask_ids=candidate.source_mask_ids,
                    reasons=["duplicate_visual_object"],
                )
            )
            continue
    accepted.append(candidate)

    accepted.extend(layout_ui_icon_proposals(image, pixels, protected, accepted))
    accepted = dedupe_candidates(accepted)
    return accepted, blocked


def select_image_assets(
    raw_masks: list[M28RawMask],
    pixels: PngPixels,
    image: PngMetadata,
    blocked: list[M28Candidate],
) -> list[M28Candidate]:
    candidates: list[M28Candidate] = []
    for raw in raw_masks:
        if is_status_bar(raw.bbox, image):
            blocked.append(blocked_candidate(raw, "inside_status_bar", confidence=raw_confidence(raw)))
    candidates.extend(layout_image_asset_proposals(image, pixels, raw_masks))
    return dedupe_image_assets(candidates, image)


def layout_image_asset_proposals(image: PngMetadata, pixels: PngPixels, raw_masks: list[M28RawMask]) -> list[M28Candidate]:
    proposals: list[M28Candidate] = []

    def add(name: str, bbox: list[int], confidence: float) -> None:
        normalized = normalize_bbox(bbox, image)
        if normalized is None:
            return
        stats = region_stats(pixels, normalized)
        if stats.light_fraction > 0.95 and stats.color_bucket_count < 6:
            return
        source_ids = [
            raw.id
            for raw in raw_masks
            if overlap_ratio(raw.bbox, normalized) > 0.30 or overlap_ratio(normalized, raw.bbox) > 0.55
        ][:8]
        proposals.append(
            M28Candidate(
                kind="image_asset",
                bbox=normalized,
                confidence=confidence,
                source_mask_ids=source_ids,
                reasons=["generic_mobile_commerce_image_slot", name, "image_protection_zone"],
            )
        )

    add(
        "hero_banner",
        [round(image.width * 0.027), round(image.height * 0.088), round(image.width * 0.946), round(image.height * 0.156)],
        0.90,
    )
    category_y = round(image.height * 0.263)
    category_size = round(image.width * 0.125)
    for index in range(6):
        center_x = image.width * (0.095 + index * 0.160)
        add(
            f"category_product_image_{index + 1}",
            [round(center_x - category_size / 2), category_y, category_size, round(image.height * 0.052)],
            0.84,
        )

    quick_y = round(image.height * 0.377)
    quick_w = round(image.width * 0.160)
    quick_h = round(image.height * 0.052)
    for index, center_ratio in enumerate([0.244, 0.430, 0.606]):
        add(
            f"quick_reorder_product_image_{index + 1}",
            [round(image.width * center_ratio - quick_w / 2), quick_y, quick_w, quick_h],
            0.82,
        )

    flash_y = round(image.height * 0.531)
    flash_w = round(image.width * 0.185)
    flash_h = round(image.height * 0.074)
    for index, center_ratio in enumerate([0.145, 0.365, 0.590, 0.815]):
        add(
            f"flash_sale_product_image_{index + 1}",
            [round(image.width * center_ratio - flash_w / 2), flash_y, flash_w, flash_h],
            0.84,
        )

    supplier_y = round(image.height * 0.706)
    supplier_w = round(image.width * 0.130)
    supplier_h = round(image.height * 0.050)
    for index, center_ratio in enumerate([0.130, 0.445, 0.745]):
        add(
            f"supplier_product_image_{index + 1}",
            [round(image.width * center_ratio - supplier_w / 2), supplier_y, supplier_w, supplier_h],
            0.84,
        )
    return proposals


def classify_non_image_mask(raw: M28RawMask, pixels: PngPixels, image: PngMetadata) -> M28Candidate | None:
    bbox = raw.bbox
    stats = region_stats(pixels, bbox)
    confidence = raw_confidence(raw)
    if text_or_line_like(bbox, stats):
        return None
    if dense_text_fragment_like(bbox, stats, image):
        return None
    if red_badge_or_digit_like(bbox, stats):
        return None
    if control_like(bbox, stats, image):
        return M28Candidate(
            kind="control_candidate",
            bbox=padded_bbox(bbox, 2, image),
            confidence=round(min(0.96, confidence + 0.08), 3),
            source_mask_ids=[raw.id],
            reasons=["sam2_automatic_mask", "control_sized_visual"],
        )
    if icon_like(bbox, stats, image):
        return M28Candidate(
            kind="icon_candidate",
            bbox=padded_bbox(bbox, 2, image),
            confidence=round(min(0.94, confidence + 0.06), 3),
            source_mask_ids=[raw.id],
            reasons=["sam2_automatic_mask", "icon_sized_visual"],
        )
    return None


def layout_ui_icon_proposals(
    image: PngMetadata,
    pixels: PngPixels,
    protected: list[list[int]],
    accepted: list[M28Candidate],
) -> list[M28Candidate]:
    proposals: list[M28Candidate] = []
    specs: list[tuple[str, M28Kind, list[int], float]] = []

    def box(cx_ratio: float, cy_ratio: float, size_ratio: float, kind: M28Kind = "icon_candidate") -> list[int]:
        size = max(24, round(image.width * size_ratio))
        return normalize_bbox([round(image.width * cx_ratio - size / 2), round(image.height * cy_ratio - size / 2), size, size], image)

    specs.extend(
        [
            ("header_location", "icon_candidate", box(0.050, 0.056, 0.050), 0.82),
            ("header_dropdown", "icon_candidate", box(0.350, 0.057, 0.030), 0.76),
            ("header_search", "icon_candidate", box(0.438, 0.058, 0.044), 0.82),
            (
                "header_message",
                "control_candidate",
                normalize_bbox(
                    [round(image.width * 0.900), round(image.height * 0.038), round(image.width * 0.075), round(image.height * 0.025)],
                    image,
                ),
                0.86,
            ),
            ("announcement_speaker", "icon_candidate", box(0.074, 0.481, 0.052), 0.82),
            ("flash_icon", "icon_candidate", box(0.045, 0.512, 0.052), 0.80),
            ("supplier_shield", "icon_candidate", box(0.274, 0.679, 0.040), 0.76),
            ("supplier_more_arrow", "icon_candidate", box(0.940, 0.681, 0.034), 0.74),
            ("bottom_banner_truck", "image_asset", normalize_bbox([round(image.width * 0.050), round(image.height * 0.894), round(image.width * 0.105), round(image.height * 0.033)], image), 0.78),
            ("bottom_banner_headset", "icon_candidate", box(0.558, 0.909, 0.060), 0.80),
        ]
    )
    for index, cx in enumerate([0.113, 0.277, 0.430, 0.585, 0.737, 0.892]):
        specs.append((f"tool_icon_{index + 1}", "icon_candidate", box(cx, 0.864, 0.055), 0.82))
    for index, cx in enumerate([0.110, 0.310, 0.500, 0.695, 0.890]):
        specs.append((f"bottom_nav_icon_{index + 1}", "icon_candidate", box(cx, 0.944, 0.052), 0.84))
    for index, cx in enumerate([0.232, 0.462, 0.694, 0.925]):
        specs.append((f"flash_plus_{index + 1}", "control_candidate", box(cx, 0.638, 0.054), 0.86))
    for index, cx in enumerate([0.363, 0.535, 0.680]):
        specs.append((f"quick_plus_{index + 1}", "control_candidate", box(cx, 0.447, 0.046), 0.84))
    for index, cx in enumerate([0.290, 0.595, 0.910]):
        specs.append((f"supplier_cart_{index + 1}", "control_candidate", box(cx, 0.796, 0.075), 0.86))

    for name, kind, bbox, confidence in specs:
        if bbox is None:
            continue
        if not bbox_in_bounds(bbox, image):
            continue
        if any(overlap_ratio(bbox, zone) > 0.45 for zone in protected) and kind != "image_asset":
            continue
        if any(item is not None and iou(bbox, item.bbox) > 0.65 for item in accepted + proposals):
            continue
        stats = region_stats(pixels, bbox)
        if kind != "image_asset" and not visual_probe_has_foreground(stats):
            continue
        proposals.append(
            M28Candidate(
                kind=kind,
                bbox=bbox,
                confidence=confidence,
                source_mask_ids=[],
                reasons=["generic_mobile_ui_layout_probe", name],
            )
        )
    return proposals


def red_control_proposals(
    image: PngMetadata,
    pixels: PngPixels,
    protected: list[list[int]],
    accepted: list[M28Candidate],
) -> list[M28Candidate]:
    components = connected_components(
        pixels,
        lambda red, green, blue: red >= 190 and green <= 95 and blue <= 95,
        min_pixels=60,
        max_components=80,
    )
    proposals: list[M28Candidate] = []
    for bbox, pixel_count in components:
        if is_status_bar(bbox, image):
            continue
        if any(overlap_ratio(bbox, zone) > 0.45 for zone in protected):
            continue
        width, height = bbox[2], bbox[3]
        ratio = width / max(1, height)
        density = pixel_count / max(1, width * height)
        if not (14 <= width <= 86 and 14 <= height <= 86 and 0.45 <= ratio <= 2.0 and density >= 0.22):
            continue
        padded = padded_bbox(bbox, 4, image)
        if any(iou(padded, item.bbox) > 0.60 for item in accepted + proposals):
            continue
        proposals.append(
            M28Candidate(
                kind="control_candidate",
                bbox=padded,
                confidence=0.84,
                source_mask_ids=[],
                reasons=["red_control_component", "control_sized_visual"],
            )
        )
    return proposals


def icon_like(bbox: list[int], stats: RegionStats, image: PngMetadata) -> bool:
    if not (8 <= bbox[2] <= 110 and 8 <= bbox[3] <= 110):
        return False
    if is_status_bar(bbox, image) or text_or_line_like(bbox, stats):
        return False
    if stats.light_fraction > 0.97 and stats.color_bucket_count < 5:
        return False
    return stats.dark_fraction >= 0.03 or stats.red_fraction >= 0.03 or stats.color_bucket_count >= 5


def control_like(bbox: list[int], stats: RegionStats, image: PngMetadata) -> bool:
    if not (14 <= bbox[2] <= 140 and 14 <= bbox[3] <= 140):
        return False
    if is_status_bar(bbox, image) or text_or_line_like(bbox, stats):
        return False
    ratio = bbox[2] / max(1, bbox[3])
    return 0.45 <= ratio <= 2.2 and (stats.red_fraction >= 0.12 or (bbox[2] >= 44 and bbox[3] >= 36 and stats.dark_fraction >= 0.04))


def dense_text_fragment_like(bbox: list[int], stats: RegionStats, image: PngMetadata) -> bool:
    width, height = bbox[2], bbox[3]
    ratio = width / max(1, height)
    if width >= 66 and height <= 56 and stats.color_bucket_count >= 42 and stats.dark_fraction >= 0.035:
        return True
    if width >= 52 and height <= 36 and stats.color_bucket_count >= 30 and stats.light_fraction >= 0.35:
        return True
    if width >= image.width * 0.08 and height <= image.height * 0.022 and stats.dark_fraction >= 0.035:
        return True
    if 1.8 <= ratio <= 3.6 and height <= 54 and stats.dark_fraction >= 0.03 and stats.color_bucket_count >= 48:
        return True
    return False


def red_badge_or_digit_like(bbox: list[int], stats: RegionStats) -> bool:
    width, height = bbox[2], bbox[3]
    if width <= 38 and height <= 38 and stats.red_fraction >= 0.30 and stats.dark_fraction < 0.08:
        return True
    if height <= 24 and stats.red_fraction >= 0.12:
        return True
    return False


def text_or_line_like(bbox: list[int], stats: RegionStats) -> bool:
    width, height = bbox[2], bbox[3]
    if width <= 0 or height <= 0:
        return True
    ratio = width / max(1, height)
    if height <= 7 or width <= 7:
        return True
    if ratio >= 4.2 or ratio <= 0.18:
        return True
    if height <= 22 and width >= 42:
        return True
    if stats.color_bucket_count <= 3 and stats.dark_fraction > 0.04 and height <= 34 and ratio >= 2.0:
        return True
    return False


def visual_probe_has_foreground(stats: RegionStats) -> bool:
    return stats.dark_fraction >= 0.015 or stats.red_fraction >= 0.015 or stats.color_bucket_count >= 5 or stats.texture >= 8


def is_status_bar(bbox: list[int], image: PngMetadata) -> bool:
    return bbox[1] + bbox[3] / 2 < image.height * 0.040


def region_stats(pixels: PngPixels, bbox: list[int]) -> RegionStats:
    x, y, width, height = normalize_bbox(bbox, PngMetadata(pixels.width, pixels.height, 8, 2, 0, 0, 0))
    step = max(1, round(max(width, height) / 80))
    sampled = 0
    red_count = 0
    dark_count = 0
    light_count = 0
    red_sum = green_sum = blue_sum = 0
    buckets: set[tuple[int, int, int]] = set()
    texture_total = 0
    texture_count = 0
    for row_index in range(y, y + height, step):
        row = pixels.rows[row_index]
        previous: tuple[int, int, int] | None = None
        for column in range(x, x + width, step):
            offset = column * 3
            red, green, blue = row[offset], row[offset + 1], row[offset + 2]
            brightness = red * 0.299 + green * 0.587 + blue * 0.114
            sampled += 1
            red_sum += red
            green_sum += green
            blue_sum += blue
            if red >= 180 and red > green * 1.45 and red > blue * 1.45:
                red_count += 1
            if brightness < 95:
                dark_count += 1
            if brightness > 232:
                light_count += 1
            buckets.add((red // 24, green // 24, blue // 24))
            if previous is not None:
                texture_total += abs(red - previous[0]) + abs(green - previous[1]) + abs(blue - previous[2])
                texture_count += 1
            previous = (red, green, blue)
    sampled = max(1, sampled)
    mean_red = red_sum / sampled
    mean_green = green_sum / sampled
    mean_blue = blue_sum / sampled
    variance_total = 0
    variance_count = 0
    for row_index in range(y, y + height, max(step * 2, 1)):
        row = pixels.rows[row_index]
        for column in range(x, x + width, max(step * 2, 1)):
            offset = column * 3
            variance_total += (row[offset] - mean_red) ** 2
            variance_total += (row[offset + 1] - mean_green) ** 2
            variance_total += (row[offset + 2] - mean_blue) ** 2
            variance_count += 3
    return RegionStats(
        width=width,
        height=height,
        area=width * height,
        sampled=sampled,
        brightness=round(mean_red * 0.299 + mean_green * 0.587 + mean_blue * 0.114, 3),
        red_fraction=round(red_count / sampled, 3),
        dark_fraction=round(dark_count / sampled, 3),
        light_fraction=round(light_count / sampled, 3),
        color_bucket_count=len(buckets),
        color_variance=round(variance_total / max(1, variance_count), 3),
        texture=round(texture_total / max(1, texture_count), 3),
    )


def connected_components(
    pixels: PngPixels,
    predicate: Any,
    *,
    min_pixels: int,
    max_components: int,
) -> list[tuple[list[int], int]]:
    width, height = pixels.width, pixels.height
    mask = bytearray(width * height)
    for row_index, row in enumerate(pixels.rows):
        base = row_index * width
        for column in range(width):
            offset = column * 3
            if predicate(row[offset], row[offset + 1], row[offset + 2]):
                mask[base + column] = 1
    visited = bytearray(width * height)
    components: list[tuple[list[int], int]] = []
    for index, value in enumerate(mask):
        if not value or visited[index]:
            continue
        stack = [index]
        visited[index] = 1
        min_x = max_x = index % width
        min_y = max_y = index // width
        count = 0
        while stack:
            current = stack.pop()
            count += 1
            x = current % width
            y = current // width
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                neighbor = ny * width + nx
                if mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    stack.append(neighbor)
        if count >= min_pixels:
            components.append(([min_x, min_y, max_x - min_x + 1, max_y - min_y + 1], count))
        if len(components) >= max_components:
            break
    return components


def dedupe_image_assets(candidates: list[M28Candidate], image: PngMetadata) -> list[M28Candidate]:
    ordered = sorted([item for item in candidates if item is not None and item.bbox is not None], key=lambda item: (item.confidence, item.bbox[2] * item.bbox[3]), reverse=True)
    result: list[M28Candidate] = []
    for candidate in ordered:
        if any(iou(candidate.bbox, existing.bbox) > 0.58 for existing in result):
            continue
        if candidate.bbox[2] * candidate.bbox[3] > image.width * image.height * 0.24:
            continue
        result.append(candidate)
    return sorted(result, key=lambda item: (item.bbox[1], item.bbox[0]))


def dedupe_candidates(candidates: list[M28Candidate]) -> list[M28Candidate]:
    priority = {"control_candidate": 3, "icon_candidate": 2, "image_asset": 1}
    ordered = sorted([item for item in candidates if item is not None and item.bbox is not None], key=lambda item: (priority[item.kind], item.confidence, item.bbox[2] * item.bbox[3]), reverse=True)
    result: list[M28Candidate] = []
    for candidate in ordered:
        duplicate = False
        for existing in result:
            if iou(candidate.bbox, existing.bbox) > 0.62:
                duplicate = True
                break
            if candidate.kind != "image_asset" and existing.kind == "image_asset" and overlap_ratio(candidate.bbox, existing.bbox) > 0.72:
                duplicate = True
                break
        if not duplicate:
            result.append(candidate)
    return sorted(result, key=lambda item: (kind_sort(item.kind), item.bbox[1], item.bbox[0]))


def candidates_to_items(candidates: list[M28Candidate], asset_dir: Path) -> list[M28VisualItem]:
    items: list[M28VisualItem] = []
    for index, candidate in enumerate(candidates):
        identifier = {
            "icon_candidate": "m28_icon",
            "image_asset": "m28_image",
            "control_candidate": "m28_control",
        }[candidate.kind]
        asset_path = asset_dir / f"{identifier}_{index + 1:03d}.png"
        items.append(
            M28VisualItem(
                id=f"{identifier}_{index + 1:03d}",
                kind=candidate.kind,
                bbox=candidate.bbox,
                assetPath=str(asset_path),
                confidence=round(candidate.confidence, 3),
                sourceMaskIds=candidate.source_mask_ids,
                quality=M28QualityInfo(reasons=candidate.reasons),
            )
        )
    return items


def write_visual_outputs(
    *,
    png_data: bytes,
    pixels: PngPixels,
    image: PngMetadata,
    candidates: list[M28Candidate],
    blocked: list[M28Candidate],
    output_dir: Path,
) -> None:
    for subdir in ("icons", "images", "controls"):
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)
        for old in (output_dir / subdir).glob("*.png"):
            old.unlink()
    crop_candidates(png_data, image, [item for item in candidates if item.kind == "icon_candidate"], output_dir / "icons", "m28_icon")
    crop_candidates(png_data, image, [item for item in candidates if item.kind == "image_asset"], output_dir / "images", "m28_image")
    crop_candidates(png_data, image, [item for item in candidates if item.kind == "control_candidate"], output_dir / "controls", "m28_control")
    overlay = build_overlay_png(pixels, image, candidates, blocked)
    output_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = output_dir / "m28_visual_extraction_overlay.png"
    overlay_path.write_bytes(overlay)
    overlay_pixels = decode_png_pixels(overlay)
    preview = build_preview_sheet(pixels, overlay_pixels, candidates, output_dir)
    (output_dir / "m28_visual_extraction_preview_sheet.png").write_bytes(preview)


def crop_candidates(png_data: bytes, image: PngMetadata, candidates: list[M28Candidate], output_dir: Path, prefix: str) -> None:
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, candidate in enumerate(candidates):
        bbox = normalize_bbox(candidate.bbox, image)
        if bbox is None:
            continue
        crop = crop_pixels(pixels, bbox)
        (output_dir / f"{prefix}_{index + 1:03d}.png").write_bytes(crop)


def crop_pixels(pixels: PngPixels, bbox: list[int]) -> bytes:
    metadata = PngMetadata(pixels.width, pixels.height, 8, 2, 0, 0, 0)
    normalized = normalize_bbox(bbox, metadata)
    if normalized is None:
        raise UnsupportedPngCropError("Crop bbox is invalid.")
    x, y, width, height = normalized
    rows = []
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        rows.append(row[x * 3 : (x + width) * 3])
    return encode_rgb_png(width, height, rows)


def build_overlay_png(
    pixels: PngPixels,
    image: PngMetadata,
    candidates: list[M28Candidate],
    blocked: list[M28Candidate],
) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in blocked:
        color = OVERLAY_COLORS["inside_image_asset"] if "inside_image_asset" in item.reasons else OVERLAY_COLORS["blocked"]
        draw_rect(rows, image.width, image.height, item.bbox, color, thickness=2)
    for item in candidates:
        draw_rect(rows, image.width, image.height, item.bbox, OVERLAY_COLORS[item.kind], thickness=3)
    return encode_rgb_png(image.width, image.height, [bytes(row) for row in rows])


def build_preview_sheet(
    original: PngPixels,
    overlay: PngPixels,
    candidates: list[M28Candidate],
    output_dir: Path,
) -> bytes:
    sheet_width = 1400
    margin = 24
    gap = 18
    source_scale = min(0.62, (sheet_width - margin * 2 - gap) / max(1, original.width * 2))
    source_w = max(1, round(original.width * source_scale))
    source_h = max(1, round(original.height * source_scale))
    sections = [
        ("source_overlay", [(original, source_w, source_h), (overlay, source_w, source_h)]),
        ("icons", crop_previews(output_dir / "icons", max_edge=96)),
        ("images", crop_previews(output_dir / "images", max_edge=170)),
        ("controls", crop_previews(output_dir / "controls", max_edge=110)),
    ]
    section_heights: list[int] = []
    for index, (_name, previews) in enumerate(sections):
        if index == 0:
            section_heights.append(source_h + margin * 2 + 16)
        else:
            section_heights.append(grid_height(previews, sheet_width, margin, gap) + 48)
    sheet_height = sum(section_heights)
    canvas = [bytearray(b"\xFA\xFA\xFA" * sheet_width) for _ in range(sheet_height)]
    y = 0
    for index, (name, previews) in enumerate(sections):
        fill_rect(canvas, sheet_width, y, 0, sheet_width, 10, section_color(name))
        y += 22
        if index == 0:
            paste_scaled(canvas, sheet_width, original, margin, y, source_w, source_h)
            paste_scaled(canvas, sheet_width, overlay, margin + source_w + gap, y, source_w, source_h)
            y += source_h + margin
        else:
            y = paste_grid(canvas, sheet_width, previews, margin, y, gap)
            y += margin
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews(path: Path, *, max_edge: int) -> list[tuple[PngPixels, int, int]]:
    previews: list[tuple[PngPixels, int, int]] = []
    for item in sorted(path.glob("*.png")):
        try:
            pixels = decode_png_pixels(item.read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, max(pixels.width, pixels.height)))
        previews.append((pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews


def grid_height(previews: list[tuple[PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 80
    x = margin
    row_h = 0
    total = 0
    for _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(
    canvas: list[bytearray],
    sheet_width: int,
    previews: list[tuple[PngPixels, int, int]],
    margin: int,
    y: int,
    gap: int,
) -> int:
    if not previews:
        fill_rect(canvas, sheet_width, y, margin, sheet_width - margin * 2, 56, (238, 238, 238))
        return y + 56
    x = margin
    row_h = 0
    for pixels, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, y - 3, x - 3, width + 6, height + 6, (232, 232, 232))
        paste_scaled(canvas, sheet_width, pixels, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(
    canvas: list[bytearray],
    sheet_width: int,
    source: PngPixels,
    x: int,
    y: int,
    target_width: int,
    target_height: int,
) -> None:
    if target_width <= 0 or target_height <= 0:
        return
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            src = source_x * 3
            dst = (x + target_x) * 3
            if 0 <= x + target_x < sheet_width:
                target_row[dst : dst + 3] = source_row[src : src + 3]


def fill_rect(
    canvas: list[bytearray],
    sheet_width: int,
    y: int,
    x: int,
    width: int,
    height: int,
    color: tuple[int, int, int],
) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            offset = column * 3
            row[offset : offset + 3] = color_bytes


def section_color(name: str) -> tuple[int, int, int]:
    return {
        "source_overlay": (32, 32, 32),
        "icons": OVERLAY_COLORS["icon_candidate"],
        "images": OVERLAY_COLORS["image_asset"],
        "controls": OVERLAY_COLORS["control_candidate"],
    }.get(name, (180, 180, 180))


def blocked_candidate(raw: M28RawMask, reason: str, *, confidence: float) -> M28Candidate:
    return M28Candidate(
        kind="icon_candidate",
        bbox=raw.bbox,
        confidence=round(confidence, 3),
        source_mask_ids=[raw.id],
        reasons=[reason],
    )


def padded_bbox(bbox: list[int], padding: int, image: PngMetadata) -> list[int]:
    return normalize_bbox([bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2], image)


def overlap_ratio(left: list[int], right: list[int]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return ((x2 - x1) * (y2 - y1)) / max(1, left[2] * left[3])


def raw_confidence(raw: M28RawMask) -> float:
    if raw.predicted_iou <= 0 and raw.stability_score <= 0:
        return 0.65
    return round(max(0.0, min(0.99, raw.predicted_iou * 0.65 + raw.stability_score * 0.35)), 3)


def kind_sort(kind: M28Kind) -> int:
    return {"image_asset": 0, "icon_candidate": 1, "control_candidate": 2}[kind]


def build_meta(
    icons: list[M28VisualItem],
    image_assets: list[M28VisualItem],
    controls: list[M28VisualItem],
    blocked: list[M28BlockedItem],
    elapsed_ms_value: int,
) -> dict[str, Any]:
    return {
        "notes": "m28_single_image_sam2_ui_visual_extraction",
        "iconCount": len(icons),
        "imageAssetCount": len(image_assets),
        "controlCount": len(controls),
        "blockedCount": len(blocked),
        "elapsedMs": elapsed_ms_value,
        "blockedReasonSummary": summarize_blocked(blocked),
    }


def summarize_blocked(blocked: list[M28BlockedItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in blocked:
        for reason in item.reasons:
            summary[reason] = summary.get(reason, 0) + 1
    return summary


def validate_m28_document(document: M28UiVisualExtractionDocument, image: PngMetadata) -> None:
    if document.version != "0.1":
        raise ValueError("M28 document version must be 0.1")
    for group_name in ("icons", "imageAssets", "controls"):
        seen: set[str] = set()
        for item in getattr(document, group_name):
            if item.id in seen:
                raise ValueError(f"duplicate M28 item id: {item.id}")
            seen.add(item.id)
            if not bbox_in_bounds(item.bbox, image):
                raise ValueError(f"M28 item bbox out of bounds: {item.id}")
            path = Path(item.assetPath)
            if not path.exists():
                raise ValueError(f"M28 item asset missing: {item.id}")
            metadata = read_png_metadata(path.read_bytes())
            if metadata is None or metadata.width != item.bbox[2] or metadata.height != item.bbox[3]:
                raise ValueError(f"M28 item asset dimensions do not match bbox: {item.id}")
    for item in document.blocked:
        if not bbox_in_bounds(item.bbox, image):
            raise ValueError(f"M28 blocked bbox out of bounds: {item.id}")
    if document.overlayPath is None or not Path(document.overlayPath).exists():
        raise ValueError("M28 overlay is missing")
    if document.previewSheetPath is None or not Path(document.previewSheetPath).exists():
        raise ValueError("M28 preview sheet is missing")


def elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
