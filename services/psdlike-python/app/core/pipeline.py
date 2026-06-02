from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .assets import crop_raster_assets
from .candidates import (
    build_foreground_object_candidates,
    build_raster_candidates,
    build_shape_candidates,
    build_surface_candidates,
    nms_candidates,
    promote_complex_shape_regions,
)
from .colors import estimate_background_color
from .controls import (
    build_control_profile,
    control_shape_candidates,
    control_profile_diagnostics,
    detect_ocr_anchored_control_surfaces,
    promote_control_surfaces,
    suppress_container_parent_shapes,
    suppress_control_owned_shapes,
    suppress_control_owned_rasters,
    suppress_text_owned_raster_fragments,
)
from .dsl import build_draft_runtime_dsl
from .evidence import compute_tile_maps
from .layers import build_layer_stack
from .masks import build_text_knockout_mask, build_text_mask
from .media_text import assign_media_owned_text_blocks
from .model_control import detect_model_assisted_control_surfaces
from .model_evidence import apply_model_evidence, load_model_evidence_context
from .model_media import refine_model_assisted_media
from .ocr import load_ocr_blocks
from .ownership import build_raster_ownership
from .previews import (
    draw_overlay,
    draw_reconstructed_preview,
    heatmap_image,
    write_draft_preview_png,
    write_preview_html,
    write_preview_report,
)
from .reports import write_diagnostics, write_ownership_report, write_semantic_audit_artifacts
from .runtime import wire_runtime_namespace
from .surfaces import infer_background_plate_candidates, merge_surface_and_shape_candidates


@dataclass(frozen=True)
class PipelineOptions:
    tile_size: int = 8
    text_padding: int = 3
    ocr_min_confidence: float = 0.70
    raster_threshold: float = 0.42
    shape_threshold: float = 0.62
    raster_min_area: int = 512
    shape_min_area: int = 1200
    surface_min_area: int = 2400
    max_text_overlap: float = 0.24
    enable_model_control_refinement: bool = True
    enable_model_media_refinement: bool = True


@dataclass(frozen=True)
class PipelineResult:
    task_id: str
    out_dir: Path
    layer_stack_path: Path
    dsl_path: Path
    preview_html_path: Path
    diagnostics_path: Path
    semantic_evidence_path: Path | None
    asset_count: int
    diagnostics: dict[str, Any]


def control_hardening_diagnostics(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = [str(item.get("reason", "")) for item in decisions]
    roles = [str(item.get("role", "")) for item in decisions]
    accepted_controls = sum(
        1
        for item in decisions
        if str(item.get("role", "")) == "control_surface"
        and str(item.get("decision", "")) in {"accepted", "accepted_model_control_surface"}
    )
    return {
        "localSurfaceCandidateCount": sum(1 for item in decisions if str(item.get("kind", "")).endswith("control_surface")),
        "localSurfaceAcceptedControlCount": accepted_controls,
        "localSurfaceContainerCount": sum(1 for role in roles if role == "container_surface"),
        "localSurfaceChartInternalCount": sum(1 for role in roles if role == "chart_or_media_internal"),
        "localSurfaceAuditOnlyCount": sum(1 for role in roles if role == "audit_only"),
        "localSurfaceRejectedReasons": dict(sorted({reason: reasons.count(reason) for reason in reasons if reason}.items())),
        "controlParentSurfaceSliceRejectedCount": sum(1 for reason in reasons if reason == "parent_surface_slice_not_control"),
        "controlChartInternalRejectedCount": sum(
            1 for reason in reasons if reason in {"chart_tick_like_surface_not_control", "chart_or_media_internal"}
        ),
        "controlTextRoleRejectedCount": sum(
            1 for reason in reasons if reason in {"chart_tick_like_control_rejected", "chart_tick_like_surface_not_control"}
        ),
        "controlMultiTextRejectedCount": sum(1 for reason in reasons if reason == "single_control_contains_unrelated_text"),
        "controlBoundaryClosureRejectedCount": sum(
            1 for reason in reasons if reason in {"one_sided_graphic_edge", "weak_boundary_closure"}
        ),
        "controlBackgroundLikeRejectedCount": sum(1 for reason in reasons if reason == "invisible_background_like_control"),
        "controlDuplicateShapeSuppressedCount": sum(
            1 for item in decisions if item.get("kind") == "control_duplicate_shape_suppressed"
        ),
        "controlFalsePositiveHardeningVersion": 108,
        "controlFalsePositiveHardeningMode": "surface_first",
    }


def run_pipeline(
    image_path: Path,
    out_dir: Path,
    ocr_path: Path | None = None,
    allow_missing_ocr: bool = True,
    options: PipelineOptions = PipelineOptions(),
    task_id: str = "local",
    model_evidence_path: Path | None = None,
    ocr_diagnostics: dict[str, Any] | None = None,
) -> PipelineResult:
    wire_runtime_namespace()

    image_path = image_path.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_ocr: Path | None = None
    if ocr_path is not None:
        candidate = ocr_path.expanduser().resolve()
        if candidate.exists():
            resolved_ocr = candidate
        elif not allow_missing_ocr:
            raise FileNotFoundError(f"OCR artifact not found: {candidate}")
    elif not allow_missing_ocr:
        raise FileNotFoundError("OCR artifact is required when allow_missing_ocr is false")
    resolved_model_evidence: Path | None = None
    if model_evidence_path is not None:
        candidate = model_evidence_path.expanduser().resolve()
        if candidate.exists():
            resolved_model_evidence = candidate

    image = Image.open(image_path).convert("RGB")
    rgb = np.asarray(image)
    page_background = estimate_background_color(rgb)
    control_profile = build_control_profile(image.width, image.height)
    model_context = load_model_evidence_context(
        resolved_model_evidence,
        {"width": image.width, "height": image.height},
    )
    ocr_blocks = load_ocr_blocks(resolved_ocr, image.width, image.height, options.ocr_min_confidence)
    text_mask = build_text_mask(image.width, image.height, ocr_blocks, options.text_padding)
    text_knockout_mask = build_text_knockout_mask(rgb, ocr_blocks)
    maps = compute_tile_maps(rgb, text_mask, options.tile_size)

    raster_candidates, raster_rejected = build_raster_candidates(
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=ocr_blocks,
        width=image.width,
        height=image.height,
        tile_size=options.tile_size,
        threshold=options.raster_threshold,
        min_area=options.raster_min_area,
        max_text_overlap=options.max_text_overlap,
    )
    shape_candidates, shape_rejected = build_shape_candidates(
        maps=maps,
        text_mask=text_mask,
        raster_candidates=raster_candidates,
        width=image.width,
        height=image.height,
        tile_size=options.tile_size,
        threshold=options.shape_threshold,
        min_area=options.shape_min_area,
    )
    surface_candidates, surface_rejected = build_surface_candidates(
        maps=maps,
        text_mask=text_mask,
        width=image.width,
        height=image.height,
        tile_size=options.tile_size,
        min_area=options.surface_min_area,
    )
    background_plate_candidates = infer_background_plate_candidates(
        surface_candidates,
        width=image.width,
        height=image.height,
        page_background=page_background,
    )
    foreground_candidates, foreground_rejected = build_foreground_object_candidates(
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=ocr_blocks,
        surface_candidates=surface_candidates,
        width=image.width,
        height=image.height,
        tile_size=options.tile_size,
        min_area=options.raster_min_area,
        max_text_overlap=options.max_text_overlap,
    )
    raster_candidates = nms_candidates(raster_candidates + foreground_candidates, overlap_threshold=0.48)

    ocr_control_candidates, ocr_control_rejected = detect_ocr_anchored_control_surfaces(
        rgb=rgb,
        ocr_blocks=ocr_blocks,
        text_mask=text_knockout_mask,
        profile=control_profile,
        page_background=page_background,
    )
    model_ownership_decisions: list[dict[str, Any]] = []
    model_control_diagnostics: dict[str, Any] = {}
    model_media_diagnostics: dict[str, Any] = {}
    if options.enable_model_control_refinement and model_context is not None:
        model_control_result = detect_model_assisted_control_surfaces(
            detections=model_context.detections,
            rgb=rgb,
            ocr_blocks=ocr_blocks,
            text_mask=text_knockout_mask,
            profile=control_profile,
            page_background=page_background,
        )
        ocr_control_candidates = merge_surface_and_shape_candidates(
            model_control_result.candidates,
            ocr_control_candidates,
        )
        model_ownership_decisions.extend(model_control_result.decisions)
        model_control_diagnostics.update(model_control_result.diagnostics)
    shape_candidates = merge_surface_and_shape_candidates(
        background_plate_candidates + surface_candidates,
        shape_candidates,
    )
    shape_candidates = merge_surface_and_shape_candidates(ocr_control_candidates, shape_candidates)

    raster_candidates, shape_candidates, promotion_decisions = promote_complex_shape_regions(
        raster_candidates,
        shape_candidates,
    )
    raster_candidates, shape_candidates, control_decisions = promote_control_surfaces(
        raster_candidates,
        shape_candidates,
        ocr_blocks=ocr_blocks,
        text_mask=text_knockout_mask,
        rgb=rgb,
        profile=control_profile,
        page_background=page_background,
    )
    promotion_decisions.extend(control_decisions)

    shape_candidates, control_shape_suppressed = suppress_control_owned_shapes(shape_candidates)
    promotion_decisions.extend(control_shape_suppressed)

    shape_candidates, container_parent_suppressed = suppress_container_parent_shapes(shape_candidates)
    promotion_decisions.extend(container_parent_suppressed)

    control_suppression = suppress_control_owned_rasters(
        raster_candidates,
        control_shape_candidates(shape_candidates),
    )
    raster_candidates = control_suppression.rasters
    promotion_decisions.extend(control_suppression.suppressed)

    if options.enable_model_media_refinement and model_context is not None:
        model_media_result = refine_model_assisted_media(
            detections=model_context.detections,
            raster_candidates=raster_candidates,
            control_shapes=control_shape_candidates(shape_candidates),
            maps=maps,
            text_mask=text_knockout_mask,
            ocr_blocks=ocr_blocks,
            width=image.width,
            height=image.height,
            tile_size=options.tile_size,
        )
        raster_candidates = model_media_result.rasters
        model_ownership_decisions.extend(model_media_result.decisions)
        model_media_diagnostics.update(model_media_result.diagnostics)

    raster_candidates, text_owned_suppressed = suppress_text_owned_raster_fragments(
        raster_candidates,
        ocr_blocks,
        text_knockout_mask,
    )
    promotion_decisions.extend(text_owned_suppressed)

    media_owned_text_ids, media_owned_text_decisions = assign_media_owned_text_blocks(
        raster_candidates=raster_candidates,
        ocr_blocks=ocr_blocks,
        text_mask=text_knockout_mask,
        image_width=image.width,
        image_height=image.height,
    )
    if model_media_diagnostics:
        accepted_model_media_ids = {
            str(item.get("candidateId", ""))
            for item in model_ownership_decisions
            if str(item.get("kind", "")) == "model_media_ownership_decision"
            and str(item.get("decision", "")).startswith("accepted_")
        }
        model_media_diagnostics["modelMediaOwnedTextSuppressedCount"] = sum(
            1 for item in media_owned_text_decisions if str(item.get("ownerRasterId", "")) in accepted_model_media_ids
        )
    visible_ocr_blocks = [block for block in ocr_blocks if block.id not in media_owned_text_ids]
    visible_text_knockout_mask = build_text_knockout_mask(rgb, visible_ocr_blocks)

    ownership = build_raster_ownership(raster_candidates, visible_ocr_blocks, visible_text_knockout_mask)
    asset_refs = crop_raster_assets(
        image,
        raster_candidates,
        out_dir,
        text_mask=visible_text_knockout_mask,
        ocr_blocks=visible_ocr_blocks,
        rgb=rgb,
    )
    thresholds = {
        "tileSize": options.tile_size,
        "rasterThreshold": options.raster_threshold,
        "shapeThreshold": options.shape_threshold,
        "rasterMinArea": options.raster_min_area,
        "shapeMinArea": options.shape_min_area,
        "surfaceMinArea": options.surface_min_area,
        "maxTextOverlap": options.max_text_overlap,
        "ocrMinConfidence": options.ocr_min_confidence,
    }
    layer_stack = build_layer_stack(
        image_path=image_path,
        ocr_path=resolved_ocr,
        image=image,
        rgb=rgb,
        ocr_blocks=ocr_blocks,
        raster_candidates=raster_candidates,
        shape_candidates=shape_candidates,
        asset_refs=asset_refs,
        ownership=ownership,
        rejected=raster_rejected
        + shape_rejected
        + surface_rejected
        + foreground_rejected
        + ocr_control_rejected
        + promotion_decisions,
        thresholds=thresholds,
        media_owned_text_ids=media_owned_text_ids,
        media_owned_text_decisions=media_owned_text_decisions,
    )
    if ocr_diagnostics:
        layer_stack.setdefault("diagnostics", {}).update(ocr_diagnostics)
    layer_stack.setdefault("diagnostics", {}).update(control_profile_diagnostics(control_profile))
    layer_stack.setdefault("diagnostics", {}).update(
        control_hardening_diagnostics(ocr_control_rejected + promotion_decisions + model_ownership_decisions)
    )
    if model_control_diagnostics:
        layer_stack.setdefault("diagnostics", {}).update(model_control_diagnostics)
    if model_media_diagnostics:
        layer_stack.setdefault("diagnostics", {}).update(model_media_diagnostics)
    semantic_evidence_path = apply_model_evidence(
        layer_stack,
        resolved_model_evidence,
        ocr_blocks,
        out_dir / "semantic_evidence.v1.json",
        ownership_decisions=model_ownership_decisions,
    )

    layer_stack_path = out_dir / "layer_stack.v1.json"
    layer_stack_path.write_text(json.dumps(layer_stack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dsl_path = out_dir / "draft_runtime.dsl.v1_0.json"
    draft_runtime = build_draft_runtime_dsl(layer_stack, rgb)
    dsl_path.write_text(json.dumps(draft_runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_preview_html(out_dir / "preview.html", draft_runtime)
    write_preview_report(out_dir / "preview_report.md", draft_runtime, layer_stack)
    write_draft_preview_png(out_dir / "draft_preview.png", draft_runtime, out_dir)
    heatmap_image(maps["raster"], image.width, image.height, options.tile_size, (255, 80, 80)).save(
        out_dir / "raster_heatmap.png"
    )
    heatmap_image(maps["shape"], image.width, image.height, options.tile_size, (80, 220, 120)).save(
        out_dir / "shape_heatmap.png"
    )
    draw_overlay(image, ocr_blocks, raster_candidates, shape_candidates, out_dir / "overlay.png")
    draw_reconstructed_preview(
        image,
        rgb,
        visible_ocr_blocks,
        raster_candidates,
        shape_candidates,
        visible_text_knockout_mask,
        out_dir / "reconstructed_preview.png",
    )
    diagnostics_path = out_dir / "diagnostics.md"
    write_diagnostics(diagnostics_path, layer_stack)
    write_ownership_report(out_dir / "ownership_report.v1.json", layer_stack)
    write_semantic_audit_artifacts(out_dir, layer_stack, semantic_evidence_path)

    diagnostics = dict(layer_stack.get("diagnostics") or {})
    assets_dir = out_dir / "assets"
    asset_count = len(list(assets_dir.glob("*.png"))) if assets_dir.exists() else 0
    return PipelineResult(
        task_id=task_id,
        out_dir=out_dir,
        layer_stack_path=layer_stack_path,
        dsl_path=dsl_path,
        preview_html_path=out_dir / "preview.html",
        diagnostics_path=diagnostics_path,
        semantic_evidence_path=semantic_evidence_path,
        asset_count=asset_count,
        diagnostics=diagnostics,
    )
