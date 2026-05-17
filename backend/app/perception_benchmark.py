from __future__ import annotations

import importlib
import json
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .component_annotation import index_dsl_elements
from .config import Settings
from .icon_business_candidate import IconBusinessCandidateDocument, is_line_like, is_text_like, unique_bboxes
from .icon_candidate import IconCandidateDocument, bbox_in_bounds, iou, normalize_bbox
from .icon_coverage import draw_rect, bboxes_by_role
from .icon_gap_candidate import IconGapCandidateDocument
from .png_tools import PngMetadata, PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png


PerceptionDocumentStatus = Literal["completed", "failed", "skipped"]
PerceptionProviderStatus = Literal["completed", "failed", "skipped", "unavailable"]

PROVIDERS = {"current_rules", "opencv", "sam2", "uied"}
PROVIDER_STATUSES = {"completed", "failed", "skipped", "unavailable"}
CANDIDATE_KINDS = {
    "icon_candidate",
    "text_like",
    "component_candidate",
    "image_candidate",
    "card_candidate",
    "button_candidate",
    "nav_candidate",
    "unknown_visual",
}

OVERLAY_COLORS = {
    "current_rules": (0, 200, 90),
    "opencv": (0, 122, 255),
    "sam2": (150, 80, 220),
    "uied": (255, 149, 0),
    "blocked": (255, 205, 0),
    "failed": (235, 64, 52),
    "unavailable": (128, 128, 128),
}


@dataclass
class PerceptionWarning:
    code: str
    message: str
    provider: str | None = None


@dataclass
class PerceptionQuality:
    risk: str
    reasons: list[str]


@dataclass
class PerceptionCandidate:
    id: str
    bbox: list[int]
    kind: str
    source: str
    confidence: float
    area: int
    maskArea: int | None
    quality: PerceptionQuality


@dataclass
class PerceptionBlocked:
    id: str
    bbox: list[int]
    kind: str
    source: str
    confidence: float
    reasons: list[str]


@dataclass
class PerceptionOverlay:
    assetId: str
    assetPath: str
    assetUrl: str


@dataclass
class PerceptionProviderResult:
    provider: str
    status: PerceptionProviderStatus
    available: bool
    elapsedMs: int
    candidateCount: int
    blockedCount: int
    duplicateCount: int
    textOverlapCount: int
    largeBackgroundCount: int
    smallStrokeCount: int
    textStrokeFalsePositiveCount: int
    borderFalsePositiveCount: int
    illustrationFalsePositiveCount: int
    bedMapFalsePositiveCount: int
    statusBarFalsePositiveCount: int
    duplicateExistingIconCount: int
    bottomNavLikelyHitCount: int
    buttonArrowLikelyHitCount: int
    cardTileLikelyHitCount: int
    roomStatusLikelyHitCount: int
    candidates: list[PerceptionCandidate]
    blocked: list[PerceptionBlocked]
    overlay: PerceptionOverlay | None
    warnings: list[PerceptionWarning]
    error: dict[str, str] | None = None


@dataclass
class PerceptionBenchmarkDocument:
    version: str
    taskId: str
    status: PerceptionDocumentStatus
    imageSize: dict[str, int]
    providers: list[PerceptionProviderResult]
    comparison: dict[str, Any]
    meta: dict[str, Any]
    warnings: list[PerceptionWarning] = field(default_factory=list)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerceptionStorageAdapter:
    assets_root: Path
    public_base_url: str

    def overlay_path(self, task_id: str, provider: str) -> Path:
        return self.assets_root / task_id / "debug" / f"perception_overlay_{overlay_slug(provider)}.png"

    def overlay_url(self, task_id: str, provider: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/files/assets/{task_id}/debug/perception_overlay_{overlay_slug(provider)}.png"

    def write_overlay(self, task_id: str, provider: str, data: bytes) -> Path:
        path = self.overlay_path(task_id, provider)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


@dataclass(frozen=True)
class PerceptionContext:
    task_id: str
    image: PngMetadata
    png_data: bytes
    dsl: dict[str, Any]
    settings: Settings
    storage: PerceptionStorageAdapter
    icon_candidate_document: IconCandidateDocument | None
    icon_gap_document: IconGapCandidateDocument | None
    icon_business_document: IconBusinessCandidateDocument | None
    pixels: PngPixels | None
    text_bboxes: list[list[int]]
    cover_bboxes: list[list[int]]
    existing_icon_bboxes: list[list[int]]
    exclusion_bboxes: list[list[int]]


def build_perception_benchmark_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    dsl: dict[str, Any],
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    icon_business_document: IconBusinessCandidateDocument | None,
    settings: Settings,
    storage: PerceptionStorageAdapter,
) -> PerceptionBenchmarkDocument:
    if not settings.perception_benchmark_enabled:
        return build_skipped_perception_document(
            task_id=task_id,
            image=image,
            code="perception_benchmark_disabled",
            message="Perception benchmark is disabled.",
        )

    try:
        pixels = decode_png_pixels(png_data)
    except UnsupportedPngCropError:
        pixels = None

    elements = index_dsl_elements(dsl)
    text_bboxes = unique_bboxes(bboxes_by_role(elements, {"visible_text_replacement"}) + bboxes_by_role(elements, {"candidate_text"}))
    cover_bboxes = unique_bboxes(bboxes_by_role(elements, {"text_replacement_cover"}))
    existing_icon_bboxes = collect_existing_icon_bboxes(
        icon_candidate_document=icon_candidate_document,
        icon_gap_document=icon_gap_document,
        icon_business_document=icon_business_document,
        elements=elements,
    )
    context = PerceptionContext(
        task_id=task_id,
        image=image,
        png_data=png_data,
        dsl=dsl,
        settings=settings,
        storage=storage,
        icon_candidate_document=icon_candidate_document,
        icon_gap_document=icon_gap_document,
        icon_business_document=icon_business_document,
        pixels=pixels,
        text_bboxes=text_bboxes,
        cover_bboxes=cover_bboxes,
        existing_icon_bboxes=existing_icon_bboxes,
        exclusion_bboxes=exclusion_zones(image),
    )

    providers: list[PerceptionProviderResult] = []
    for provider in configured_providers(settings):
        started = time.perf_counter()
        try:
            providers.append(run_provider(provider, context))
        except Exception as error:
            providers.append(
                failed_provider_result(
                    provider=provider,
                    elapsed_ms=elapsed_ms(started),
                    code="PERCEPTION_BENCHMARK_FAILED",
                    message=str(error),
                )
            )

    if not providers:
        return build_skipped_perception_document(
            task_id=task_id,
            image=image,
            code="no_perception_providers_configured",
            message="No perception benchmark providers were configured.",
        )

    document = PerceptionBenchmarkDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        providers=providers,
        comparison=build_comparison(providers),
        meta=build_meta(providers),
        warnings=[warning for provider in providers for warning in provider.warnings],
    )
    validation_errors = validate_perception_benchmark_document(document, image)
    if validation_errors:
        return build_failed_perception_document(
            task_id=task_id,
            image=image,
            code="PERCEPTION_BENCHMARK_VALIDATION_FAILED",
            message="Perception benchmark validation failed.",
            warnings=[PerceptionWarning(code="PERCEPTION_BENCHMARK_VALIDATION_ERROR", message=error) for error in validation_errors],
        )
    return document


def run_provider(provider: str, context: PerceptionContext) -> PerceptionProviderResult:
    if provider == "current_rules":
        return current_rules_provider(context)
    if provider == "opencv":
        return opencv_provider(context)
    if provider == "sam2":
        return sam2_provider(context)
    if provider == "uied":
        return uied_provider(context)
    return unavailable_provider_result(provider, 0, "provider_unavailable", "Perception provider is not supported.")


def current_rules_provider(context: PerceptionContext) -> PerceptionProviderResult:
    started = time.perf_counter()
    candidates: list[PerceptionCandidate] = []
    blocked: list[PerceptionBlocked] = []
    seen: list[list[int]] = []
    add_existing_candidates(
        candidates,
        seen,
        context.icon_candidate_document.icons if context.icon_candidate_document and context.icon_candidate_document.status == "completed" else [],
        source="m20_icon_candidate",
        reason="from_existing_m20_candidate",
        id_prefix="perception_rules",
    )
    add_existing_candidates(
        candidates,
        seen,
        context.icon_gap_document.gapIcons if context.icon_gap_document and context.icon_gap_document.status == "completed" else [],
        source="m22_gap_icon",
        reason="from_existing_m22_candidate",
        id_prefix="perception_rules",
    )
    add_existing_candidates(
        candidates,
        seen,
        context.icon_business_document.businessIcons if context.icon_business_document and context.icon_business_document.status == "completed" else [],
        source="m25_business_icon",
        reason="from_existing_m25_candidate",
        id_prefix="perception_rules",
    )
    for document in [context.icon_business_document]:
        if document is None or document.status != "completed":
            continue
        for item in document.blockedCandidates:
            blocked.append(
                PerceptionBlocked(
                    id=f"perception_rules_blocked_{len(blocked) + 1:03d}",
                    bbox=list(item.bbox),
                    kind="unknown_visual",
                    source="m25_blocked_business_icon",
                    confidence=item.confidence,
                    reasons=list(item.reasons),
                )
            )
    return build_provider_result(
        provider="current_rules",
        status="completed",
        available=True,
        elapsed_ms=elapsed_ms(started),
        candidates=candidates[: context.settings.perception_benchmark_max_candidates_per_provider],
        blocked=blocked,
        context=context,
        warnings=[],
    )


def opencv_provider(context: PerceptionContext) -> PerceptionProviderResult:
    started = time.perf_counter()
    if not context.settings.perception_opencv_enabled:
        return unavailable_provider_result("opencv", elapsed_ms(started), "provider_unavailable", "OpenCV provider is disabled.")
    try:
        cv2 = importlib.import_module(context.settings.perception_opencv_import_name)
        np = importlib.import_module("numpy")
    except Exception:
        return unavailable_provider_result("opencv", elapsed_ms(started), "dependency_missing", "OpenCV import failed.")
    if context.pixels is None:
        return unavailable_provider_result("opencv", elapsed_ms(started), "png_decode_unsupported", "PNG pixels could not be decoded.")

    del cv2, np
    candidates, blocked = simple_cv_candidates(context, provider="opencv", reason="opencv_connected_component")
    return build_provider_result(
        provider="opencv",
        status="completed",
        available=True,
        elapsed_ms=elapsed_ms(started),
        candidates=candidates,
        blocked=blocked,
        context=context,
        warnings=[],
    )


def sam2_provider(context: PerceptionContext) -> PerceptionProviderResult:
    started = time.perf_counter()
    if not context.settings.perception_sam2_enabled:
        return unavailable_provider_result("sam2", elapsed_ms(started), "provider_unavailable", "SAM2 provider is disabled.")
    checkpoint = context.settings.perception_sam2_checkpoint
    if not checkpoint or not Path(checkpoint).exists():
        return unavailable_provider_result("sam2", elapsed_ms(started), "model_missing", "SAM2 checkpoint is not configured or does not exist.")
    try:
        torch = importlib.import_module("torch")
        np = importlib.import_module("numpy")
        build_module = importlib.import_module("sam2.build_sam")
        mask_module = importlib.import_module("sam2.automatic_mask_generator")
    except Exception as error:
        return unavailable_provider_result("sam2", elapsed_ms(started), "dependency_missing", f"SAM2 dependency import failed: {error}")
    if context.pixels is None:
        return unavailable_provider_result("sam2", elapsed_ms(started), "png_decode_unsupported", "PNG pixels could not be decoded.")

    try:
        device = sam2_device(context.settings.perception_sam2_device, torch)
        config = context.settings.perception_sam2_model_cfg or infer_sam2_config(checkpoint)
        rgb = np.frombuffer(b"".join(context.pixels.rows), dtype=np.uint8).reshape((context.image.height, context.image.width, 3))
        scaled_rgb, scale = resize_rgb_for_sam2(rgb, context.settings.perception_sam2_max_image_edge, np)
        model = build_module.build_sam2(config, checkpoint, device=device, apply_postprocessing=False)
        generator = mask_module.SAM2AutomaticMaskGenerator(
            model,
            points_per_side=16,
            points_per_batch=32,
            pred_iou_thresh=0.72,
            stability_score_thresh=0.82,
            crop_n_layers=0,
            min_mask_region_area=16,
            output_mode="binary_mask",
        )
        with torch.inference_mode():
            masks = generator.generate(scaled_rgb)
    except Exception as error:
        return failed_provider_result("sam2", elapsed_ms(started), "PERCEPTION_PROVIDER_UNAVAILABLE", str(error))

    candidates: list[PerceptionCandidate] = []
    blocked: list[PerceptionBlocked] = []
    sorted_masks = sorted(masks, key=lambda item: float(item.get("predicted_iou") or 0), reverse=True)
    for mask in sorted_masks[: context.settings.perception_sam2_max_masks]:
        bbox = sam2_bbox_to_image_bbox(mask.get("bbox"), scale, context.image)
        if bbox is None:
            continue
        mask_area = int(round(float(mask.get("area") or 0) / max(scale * scale, 0.000001)))
        append_candidate_or_block(
            context=context,
            candidates=candidates,
            blocked=blocked,
            bbox=bbox,
            provider="sam2",
            source="sam2_automatic_mask",
            reason="sam2_automatic_mask",
            confidence=sam2_confidence(mask),
            mask_area=mask_area,
            kind=classify_bbox(bbox, context),
        )
        if len(candidates) >= context.settings.perception_benchmark_max_candidates_per_provider:
            break
    return build_provider_result(
        provider="sam2",
        status="completed",
        available=True,
        elapsed_ms=elapsed_ms(started),
        candidates=candidates,
        blocked=blocked,
        context=context,
        warnings=[],
    )


def sam2_device(value: str, torch: Any) -> str:
    if value and value != "auto":
        return value
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def infer_sam2_config(checkpoint: str) -> str:
    name = Path(checkpoint).name
    if "hiera_large" in name or "hiera_l" in name:
        suffix = "l"
    elif "base_plus" in name or "hiera_b+" in name:
        suffix = "b+"
    elif "hiera_small" in name or "hiera_s" in name:
        suffix = "s"
    else:
        suffix = "t"
    prefix = "configs/sam2.1" if "sam2.1" in name else "configs/sam2"
    version = "sam2.1" if "sam2.1" in name else "sam2"
    return f"{prefix}/{version}_hiera_{suffix}.yaml"


def resize_rgb_for_sam2(rgb: Any, max_edge: int, np: Any) -> tuple[Any, float]:
    height, width = rgb.shape[:2]
    if max_edge <= 0 or max(width, height) <= max_edge:
        return rgb, 1.0
    scale = max_edge / max(width, height)
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    xs = np.minimum((np.arange(new_width) / scale).astype(int), width - 1)
    ys = np.minimum((np.arange(new_height) / scale).astype(int), height - 1)
    return rgb[ys[:, None], xs[None, :]], scale


def sam2_bbox_to_image_bbox(raw_bbox: Any, scale: float, image: PngMetadata) -> list[int] | None:
    if raw_bbox is None or len(raw_bbox) != 4:
        return None
    if scale <= 0:
        scale = 1
    x, y, width, height = raw_bbox
    bbox = [
        round(float(x) / scale),
        round(float(y) / scale),
        max(1, round(float(width) / scale)),
        max(1, round(float(height) / scale)),
    ]
    return normalize_bbox(bbox, image)


def sam2_confidence(mask: dict[str, Any]) -> float:
    predicted = float(mask.get("predicted_iou") or 0.0)
    stability = float(mask.get("stability_score") or 0.0)
    if predicted <= 0 and stability <= 0:
        return 0.65
    return round(max(0, min(0.99, predicted * 0.65 + stability * 0.35)), 3)


def uied_provider(context: PerceptionContext) -> PerceptionProviderResult:
    started = time.perf_counter()
    command = context.settings.perception_uied_command
    if not context.settings.perception_uied_enabled or not command:
        return unavailable_provider_result("uied", elapsed_ms(started), "provider_unavailable", "UIED provider is disabled or command is not configured.")
    try:
        completed = subprocess.run(
            shlex.split(command),
            input=context.png_data,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception as error:
        return failed_provider_result("uied", elapsed_ms(started), "external_command_failed", str(error))
    if completed.returncode != 0:
        return failed_provider_result("uied", elapsed_ms(started), "external_command_failed", completed.stderr.decode("utf-8", errors="replace"))
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError as error:
        return failed_provider_result("uied", elapsed_ms(started), "external_command_failed", str(error))
    candidates: list[PerceptionCandidate] = []
    blocked: list[PerceptionBlocked] = []
    for raw in payload.get("candidates", []):
        bbox = normalize_bbox(raw.get("bbox"), context.image)
        if bbox is None:
            continue
        append_candidate_or_block(
            context=context,
            candidates=candidates,
            blocked=blocked,
            bbox=bbox,
            provider="uied",
            source=str(raw.get("source") or "uied_component"),
            reason="uied_component",
            confidence=float(raw.get("confidence") or 0.6),
            mask_area=raw.get("maskArea"),
            kind=str(raw.get("kind") or "unknown_visual"),
        )
    return build_provider_result(
        provider="uied",
        status="completed",
        available=True,
        elapsed_ms=elapsed_ms(started),
        candidates=candidates,
        blocked=blocked,
        context=context,
        warnings=[],
    )


def simple_cv_candidates(
    context: PerceptionContext,
    *,
    provider: str,
    reason: str,
) -> tuple[list[PerceptionCandidate], list[PerceptionBlocked]]:
    if context.pixels is None:
        return [], []
    image = context.image
    candidates: list[PerceptionCandidate] = []
    blocked: list[PerceptionBlocked] = []
    visited: set[tuple[int, int]] = set()
    step = 2
    for y in range(0, image.height, step):
        for x in range(0, image.width, step):
            if (x, y) in visited:
                continue
            rgb = pixel_at(context.pixels, x, y)
            if not is_visual_pixel(rgb):
                continue
            stack = [(x, y)]
            visited.add((x, y))
            points: list[tuple[int, int]] = []
            while stack and len(points) < 16000:
                cx, cy = stack.pop()
                points.append((cx, cy))
                for nx, ny in ((cx + step, cy), (cx - step, cy), (cx, cy + step), (cx, cy - step)):
                    if nx < 0 or ny < 0 or nx >= image.width or ny >= image.height or (nx, ny) in visited:
                        continue
                    if not is_visual_pixel(pixel_at(context.pixels, nx, ny)):
                        continue
                    visited.add((nx, ny))
                    stack.append((nx, ny))
            if len(points) < 8:
                continue
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            bbox = normalize_bbox([min(xs), min(ys), max(xs) - min(xs) + step, max(ys) - min(ys) + step], image)
            if bbox is None:
                continue
            append_candidate_or_block(
                context=context,
                candidates=candidates,
                blocked=blocked,
                bbox=bbox,
                provider=provider,
                source=reason,
                reason=reason,
                confidence=score_perception_bbox(bbox, context),
                mask_area=len(points) * step * step,
                kind=classify_bbox(bbox, context),
            )
            if len(candidates) >= context.settings.perception_benchmark_max_candidates_per_provider:
                return candidates, blocked
    return candidates, blocked


def append_candidate_or_block(
    *,
    context: PerceptionContext,
    candidates: list[PerceptionCandidate],
    blocked: list[PerceptionBlocked],
    bbox: list[int],
    provider: str,
    source: str,
    reason: str,
    confidence: float,
    mask_area: int | None,
    kind: str,
) -> None:
    reasons = classify_block_reasons(bbox, context)
    if any(iou(bbox, item.bbox) > 0.80 for item in candidates):
        reasons.append("duplicate_existing_icon")
    if reasons:
        blocked.append(
            PerceptionBlocked(
                id=f"perception_{provider}_blocked_{len(blocked) + 1:03d}",
                bbox=bbox,
                kind=kind if kind in CANDIDATE_KINDS else "unknown_visual",
                source=source,
                confidence=round(confidence, 3),
                reasons=reasons,
            )
        )
        return
    candidates.append(
        PerceptionCandidate(
            id=f"perception_{provider}_{len(candidates) + 1:03d}",
            bbox=bbox,
            kind=kind if kind in CANDIDATE_KINDS else "unknown_visual",
            source=source,
            confidence=round(confidence, 3),
            area=bbox[2] * bbox[3],
            maskArea=mask_area,
            quality=PerceptionQuality(risk="low" if confidence >= 0.8 else "medium", reasons=[reason, "bbox_valid"]),
        )
    )


def add_existing_candidates(
    candidates: list[PerceptionCandidate],
    seen: list[list[int]],
    items: list[Any],
    *,
    source: str,
    reason: str,
    id_prefix: str,
) -> None:
    for item in items:
        if getattr(item, "status", None) != "candidate":
            continue
        bbox = list(getattr(item, "bbox"))
        if any(iou(bbox, existing) > 0.80 for existing in seen):
            continue
        seen.append(bbox)
        candidates.append(
            PerceptionCandidate(
                id=f"{id_prefix}_{len(candidates) + 1:03d}",
                bbox=bbox,
                kind="icon_candidate",
                source=source,
                confidence=float(getattr(item, "confidence", 0.7)),
                area=bbox[2] * bbox[3],
                maskArea=None,
                quality=PerceptionQuality(risk="low", reasons=[reason, "bbox_valid"]),
            )
        )


def build_provider_result(
    *,
    provider: str,
    status: PerceptionProviderStatus,
    available: bool,
    elapsed_ms: int,
    candidates: list[PerceptionCandidate],
    blocked: list[PerceptionBlocked],
    context: PerceptionContext,
    warnings: list[PerceptionWarning],
    error: dict[str, str] | None = None,
) -> PerceptionProviderResult:
    overlay = build_overlay(context, provider, candidates, blocked) if context.settings.perception_benchmark_overlay_enabled else None
    if overlay is None and context.settings.perception_benchmark_overlay_enabled and status == "completed":
        warnings.append(PerceptionWarning(code="perception_overlay_write_failed", message="Perception overlay could not be written.", provider=provider))
    duplicate_count = count_reason(blocked, "duplicate_existing_icon")
    text_overlap_count = count_reason(blocked, "text_overlap") + count_reason(blocked, "candidate_text_overlap") + count_reason(blocked, "cover_overlap")
    large_background_count = count_reason(blocked, "background_like")
    small_stroke_count = count_reason(blocked, "mask_area_too_small") + count_reason(blocked, "line_like")
    return PerceptionProviderResult(
        provider=provider,
        status=status,
        available=available,
        elapsedMs=elapsed_ms,
        candidateCount=len(candidates),
        blockedCount=len(blocked),
        duplicateCount=duplicate_count,
        textOverlapCount=text_overlap_count,
        largeBackgroundCount=large_background_count,
        smallStrokeCount=small_stroke_count,
        textStrokeFalsePositiveCount=count_reason(blocked, "text_overlap") + count_reason(blocked, "candidate_text_overlap"),
        borderFalsePositiveCount=count_reason(blocked, "border_like"),
        illustrationFalsePositiveCount=count_reason(blocked, "inside_illustration_zone"),
        bedMapFalsePositiveCount=count_reason(blocked, "inside_bed_map_zone"),
        statusBarFalsePositiveCount=count_reason(blocked, "inside_status_bar"),
        duplicateExistingIconCount=duplicate_count,
        bottomNavLikelyHitCount=count_likely_hits(candidates, "bottom_nav"),
        buttonArrowLikelyHitCount=count_likely_hits(candidates, "button_arrow"),
        cardTileLikelyHitCount=count_likely_hits(candidates, "card_tile"),
        roomStatusLikelyHitCount=count_likely_hits(candidates, "room_status"),
        candidates=candidates,
        blocked=blocked,
        overlay=overlay,
        warnings=warnings,
        error=error,
    )


def build_overlay(
    context: PerceptionContext,
    provider: str,
    candidates: list[PerceptionCandidate],
    blocked: list[PerceptionBlocked],
) -> PerceptionOverlay | None:
    if context.pixels is None:
        return None
    rows = [bytearray(row) for row in context.pixels.rows]
    for item in blocked:
        color = OVERLAY_COLORS["blocked"]
        if "duplicate_existing_icon" in item.reasons:
            color = OVERLAY_COLORS["unavailable"]
        draw_rect(rows, context.image.width, context.image.height, item.bbox, color, thickness=2)
    for item in candidates:
        draw_rect(rows, context.image.width, context.image.height, item.bbox, OVERLAY_COLORS.get(provider, (0, 200, 90)), thickness=2)
    try:
        data = encode_rgb_png(context.image.width, context.image.height, [bytes(row) for row in rows])
        path = context.storage.write_overlay(context.task_id, provider, data)
        return PerceptionOverlay(
            assetId=f"asset_perception_overlay_{overlay_slug(provider)}",
            assetPath=str(path),
            assetUrl=context.storage.overlay_url(context.task_id, provider),
        )
    except (OSError, UnsupportedPngCropError):
        return None


def unavailable_provider_result(provider: str, elapsed_ms: int, code: str, message: str) -> PerceptionProviderResult:
    return PerceptionProviderResult(
        provider=provider,
        status="unavailable",
        available=False,
        elapsedMs=elapsed_ms,
        candidateCount=0,
        blockedCount=0,
        duplicateCount=0,
        textOverlapCount=0,
        largeBackgroundCount=0,
        smallStrokeCount=0,
        textStrokeFalsePositiveCount=0,
        borderFalsePositiveCount=0,
        illustrationFalsePositiveCount=0,
        bedMapFalsePositiveCount=0,
        statusBarFalsePositiveCount=0,
        duplicateExistingIconCount=0,
        bottomNavLikelyHitCount=0,
        buttonArrowLikelyHitCount=0,
        cardTileLikelyHitCount=0,
        roomStatusLikelyHitCount=0,
        candidates=[],
        blocked=[],
        overlay=None,
        warnings=[PerceptionWarning(code=code, message=message, provider=provider)],
        error={"code": code, "message": message},
    )


def failed_provider_result(provider: str, elapsed_ms: int, code: str, message: str) -> PerceptionProviderResult:
    result = unavailable_provider_result(provider, elapsed_ms, code, message)
    result.status = "failed"
    result.available = True
    return result


def build_skipped_perception_document(*, task_id: str, image: PngMetadata, code: str, message: str) -> PerceptionBenchmarkDocument:
    warning = PerceptionWarning(code=code, message=message)
    return PerceptionBenchmarkDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        providers=[],
        comparison=empty_comparison(),
        meta=empty_meta(),
        warnings=[warning],
        error={"code": code, "message": message},
    )


def build_failed_perception_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[PerceptionWarning] | None = None,
) -> PerceptionBenchmarkDocument:
    return PerceptionBenchmarkDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        providers=[],
        comparison=empty_comparison(),
        meta=empty_meta(),
        warnings=warnings or [PerceptionWarning(code=code, message=message)],
        error={"code": code, "message": message},
    )


def validate_perception_benchmark_document(document: PerceptionBenchmarkDocument, image: PngMetadata) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    if document.status not in {"completed", "failed", "skipped"}:
        errors.append("document status is invalid")
    provider_names = [provider.provider for provider in document.providers]
    if any(provider not in PROVIDERS for provider in provider_names):
        errors.append("provider enum is invalid")
    if len(set(provider_names)) != len(provider_names):
        errors.append("provider names must be unique")
    for provider in document.providers:
        if provider.status not in PROVIDER_STATUSES:
            errors.append(f"provider status is invalid: {provider.provider}")
        if provider.candidateCount != len(provider.candidates):
            errors.append(f"candidateCount mismatch: {provider.provider}")
        if provider.blockedCount != len(provider.blocked):
            errors.append(f"blockedCount mismatch: {provider.provider}")
        for item in provider.candidates:
            if item.kind not in CANDIDATE_KINDS:
                errors.append(f"candidate kind is invalid: {item.id}")
            if not bbox_in_bounds(item.bbox, image):
                errors.append(f"candidate bbox out of bounds: {item.id}")
        for item in provider.blocked:
            if item.kind not in CANDIDATE_KINDS:
                errors.append(f"blocked kind is invalid: {item.id}")
        if provider.overlay is not None:
            if provider.overlay.assetId != f"asset_perception_overlay_{overlay_slug(provider.provider)}":
                errors.append(f"overlay asset id is invalid: {provider.provider}")
            if not Path(provider.overlay.assetPath).exists():
                errors.append(f"overlay asset path must exist: {provider.provider}")
    if document.meta.get("providerCount") != len(document.providers):
        errors.append("meta providerCount must match providers")
    if document.meta.get("totalCandidateCount") != sum(provider.candidateCount for provider in document.providers):
        errors.append("meta totalCandidateCount must match providers")
    if document.meta.get("totalBlockedCount") != sum(provider.blockedCount for provider in document.providers):
        errors.append("meta totalBlockedCount must match providers")
    return errors


def perception_overlay_asset_records(document: PerceptionBenchmarkDocument, task_id: str, created_at: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for provider in document.providers:
        if provider.overlay is None:
            continue
        width, height = document.imageSize["width"], document.imageSize["height"]
        records.append(
            {
                "asset_id": provider.overlay.assetId,
                "task_id": task_id,
                "role": provider.overlay.assetId,
                "path": provider.overlay.assetPath,
                "url": provider.overlay.assetUrl,
                "mime_type": "image/png",
                "width": width,
                "height": height,
                "created_at": created_at,
            }
        )
    return records


def configured_providers(settings: Settings) -> list[str]:
    providers = [provider.strip().lower() for provider in settings.perception_benchmark_providers if provider.strip()]
    result: list[str] = []
    for provider in providers:
        if provider in PROVIDERS and provider not in result:
            result.append(provider)
    return result


def overlay_slug(provider: str) -> str:
    return "rules" if provider == "current_rules" else provider


def classify_block_reasons(bbox: list[int], context: PerceptionContext) -> list[str]:
    reasons: list[str] = []
    if not bbox_in_bounds(bbox, context.image):
        reasons.append("bbox_invalid")
    if bbox[2] * bbox[3] < 64:
        reasons.append("mask_area_too_small")
    if bbox[2] * bbox[3] > context.image.width * context.image.height * 0.20:
        reasons.append("background_like")
    if is_line_like(bbox):
        reasons.append("line_like")
    if is_text_like(bbox):
        reasons.append("text_overlap")
    if bbox[1] < round(context.image.height * 0.055):
        reasons.append("inside_status_bar")
    if any(iou(bbox, text_bbox) > 0.10 for text_bbox in context.text_bboxes):
        reasons.append("candidate_text_overlap")
    if any(iou(bbox, cover_bbox) > 0.10 for cover_bbox in context.cover_bboxes):
        reasons.append("cover_overlap")
    if any(iou(bbox, existing) > 0.50 for existing in context.existing_icon_bboxes):
        reasons.append("duplicate_existing_icon")
    overlapping_exclusion = next((zone for zone in context.exclusion_bboxes if iou(bbox, zone) > 0.20), None)
    if overlapping_exclusion is not None:
        if zone_kind(overlapping_exclusion, context.image) == "bed_map":
            reasons.append("inside_bed_map_zone")
        else:
            reasons.append("inside_illustration_zone")
    if is_border_like(bbox, context.image):
        reasons.append("border_like")
    return unique_strings(reasons)


def classify_bbox(bbox: list[int], context: PerceptionContext) -> str:
    y_center = bbox[1] + bbox[3] / 2
    if y_center > context.image.height * 0.84:
        return "nav_candidate"
    if bbox[2] >= context.image.width * 0.45 and 30 <= bbox[3] <= 120:
        return "button_candidate"
    if bbox[2] >= 80 and bbox[3] >= 50:
        return "card_candidate"
    if bbox[2] <= 120 and bbox[3] <= 120:
        return "icon_candidate"
    return "unknown_visual"


def score_perception_bbox(bbox: list[int], context: PerceptionContext) -> float:
    score = 0.62
    if 8 <= bbox[2] <= 120 and 8 <= bbox[3] <= 120:
        score += 0.14
    if bbox[1] > context.image.height * 0.10:
        score += 0.06
    if not is_line_like(bbox):
        score += 0.06
    if bbox[2] * bbox[3] < 64:
        score -= 0.20
    if bbox[2] * bbox[3] > context.image.width * context.image.height * 0.15:
        score -= 0.25
    return max(0, min(0.99, round(score, 3)))


def collect_existing_icon_bboxes(
    *,
    icon_candidate_document: IconCandidateDocument | None,
    icon_gap_document: IconGapCandidateDocument | None,
    icon_business_document: IconBusinessCandidateDocument | None,
    elements: dict[str, dict[str, Any]],
) -> list[list[int]]:
    bboxes: list[list[int]] = []
    if icon_candidate_document is not None and icon_candidate_document.status == "completed":
        bboxes.extend([icon.bbox for icon in icon_candidate_document.icons if icon.status == "candidate"])
    if icon_gap_document is not None and icon_gap_document.status == "completed":
        bboxes.extend([icon.bbox for icon in icon_gap_document.gapIcons if icon.status == "candidate"])
    if icon_business_document is not None and icon_business_document.status == "completed":
        bboxes.extend([icon.bbox for icon in icon_business_document.businessIcons if icon.status == "candidate"])
    bboxes.extend(bboxes_by_role(elements, {"visible_icon_fallback"}))
    return unique_bboxes(bboxes)


def exclusion_zones(image: PngMetadata) -> list[list[int]]:
    return [
        [0, 0, image.width, round(image.height * 0.055)],
        [0, round(image.height * 0.10), image.width, round(image.height * 0.18)],
        [round(image.width * 0.04), round(image.height * 0.30), round(image.width * 0.92), round(image.height * 0.34)],
    ]


def zone_kind(zone: list[int], image: PngMetadata) -> str:
    if zone[1] >= round(image.height * 0.28):
        return "bed_map"
    return "illustration"


def is_visual_pixel(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    if r < 80 and g < 80 and b < 80:
        return True
    if b > r + 35 and b > 120:
        return True
    if g > 145 and g > r + 20:
        return True
    if r > 170 and g > 90 and b < 130:
        return True
    return False


def pixel_at(pixels: PngPixels, x: int, y: int) -> tuple[int, int, int]:
    row = pixels.rows[y]
    offset = x * 3
    return row[offset], row[offset + 1], row[offset + 2]


def is_border_like(bbox: list[int], image: PngMetadata) -> bool:
    if bbox[2] >= image.width * 0.70 and bbox[3] <= 8:
        return True
    if bbox[3] >= image.height * 0.10 and bbox[2] <= 8:
        return True
    return False


def count_reason(blocked: list[PerceptionBlocked], reason: str) -> int:
    return sum(1 for item in blocked if reason in item.reasons)


def count_likely_hits(candidates: list[PerceptionCandidate], target: str) -> int:
    if target == "bottom_nav":
        return sum(1 for item in candidates if item.kind == "nav_candidate")
    if target == "button_arrow":
        return sum(1 for item in candidates if item.kind == "button_candidate" or "button" in item.source)
    if target == "card_tile":
        return sum(1 for item in candidates if item.kind == "card_candidate" or "business" in item.source)
    if target == "room_status":
        return sum(1 for item in candidates if "room" in item.source or item.kind == "icon_candidate")
    return 0


def build_comparison(providers: list[PerceptionProviderResult]) -> dict[str, Any]:
    scores = {provider.provider: provider_score(provider) for provider in providers}
    if not scores:
        return empty_comparison()
    recommended = max(scores.items(), key=lambda item: item[1])[0]
    if recommended == "opencv":
        recommended = "opencv_plus_rules"
    elif recommended == "sam2":
        recommended = "sam2_offline_enhancement"
    reasons: list[str] = []
    if any(provider.provider == "opencv" and provider.status == "completed" for provider in providers):
        reasons.append("opencv_runtime_under_threshold")
    if any(provider.provider == "sam2" and provider.status == "unavailable" for provider in providers):
        reasons.append("sam2_requires_optional_model_runtime")
    if any(provider.provider == "current_rules" and provider.status == "completed" for provider in providers):
        reasons.append("current_rules_baseline_available")
    return {
        "recommendedProvider": recommended,
        "reasons": reasons or ["benchmark_completed"],
        "providerScores": scores,
    }


def provider_score(provider: PerceptionProviderResult) -> float:
    if provider.status != "completed":
        return 0
    score = 0.35
    score += min(0.35, provider.candidateCount * 0.015)
    score -= min(0.25, provider.blockedCount * 0.005)
    if provider.elapsedMs <= 3000:
        score += 0.15
    elif provider.elapsedMs > 20000:
        score -= 0.20
    score += min(0.15, (provider.bottomNavLikelyHitCount + provider.buttonArrowLikelyHitCount + provider.cardTileLikelyHitCount) * 0.03)
    return round(max(0, min(0.99, score)), 3)


def build_meta(providers: list[PerceptionProviderResult]) -> dict[str, Any]:
    return {
        "notes": "visual_perception_provider_benchmark",
        "providerCount": len(providers),
        "totalCandidateCount": sum(provider.candidateCount for provider in providers),
        "totalBlockedCount": sum(provider.blockedCount for provider in providers),
        "elapsedMs": sum(provider.elapsedMs for provider in providers),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "visual_perception_provider_benchmark",
        "providerCount": 0,
        "totalCandidateCount": 0,
        "totalBlockedCount": 0,
        "elapsedMs": 0,
    }


def empty_comparison() -> dict[str, Any]:
    return {"recommendedProvider": None, "reasons": [], "providerScores": {}}


def elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
