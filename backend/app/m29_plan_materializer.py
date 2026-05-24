from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .dsl_factory import build_deterministic_dsl
from .m29_materialization_utils import layout_from_bbox, list_dicts, map_page_bbox_to_asset_pixels, next_unique_asset_id, next_unique_id, sample_outer_bbox_ring_rgb
from .png_tools import (
    PngMetadata,
    PngPixels,
    UnsupportedPngCropError,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
    rgb_to_hex,
)
from .text_masked_media_audit import text_boxes_from_ocr_document
from .visual_primitive_graph import bbox_clamp, bbox_in_bounds, crop_pixels, measure_region


@dataclass(frozen=True)
class M29PlanMaterializerOptions:
    enable_text_replay: bool = True
    enable_image_replay: bool = True
    enable_symbol_replay: bool = True
    enable_simple_shape_replay: bool = True
    erase_replayed_bboxes_from_fallback: bool = True
    max_total_visible_nodes: int = 260

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M29PlanMaterializerResult:
    dsl: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True)
class ReplayNode:
    id: str
    kind: str
    source_id: str
    bbox: list[int]
    role: str | None = None
    asset_id: str | None = None
    asset_url: str | None = None
    replay_decision: str | None = None


def build_m29_plan_materialized_dsl(
    *,
    source_png: bytes,
    source_image_path: str,
    m29_document: dict[str, Any],
    output_dir: Path,
    ocr_document: dict[str, Any] | None = None,
    m292_document: dict[str, Any] | None = None,
    m295_replay_plan: dict[str, Any] | None = None,
    extra_warnings: list[str] | None = None,
    options: M29PlanMaterializerOptions | None = None,
    task_id: str = "m29_materialized",
) -> M29PlanMaterializerResult:
    options = options or M29PlanMaterializerOptions()
    image = read_png_metadata(source_png)
    if image is None:
        raise UnsupportedPngCropError("M29 plan-driven replay source image is not a readable PNG.")
    pixels = decode_png_pixels(source_png)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(source_image_path).expanduser()
    fallback_dir = output_dir / "assets" / "m29_fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    fallback_path = fallback_dir / (source_path.name or "source.png")
    fallback_path.write_bytes(source_png)

    dsl = build_deterministic_dsl(
        task_id=task_id,
        original_url=str(source_path),
        fallback_url=relative_posix(output_dir, fallback_path),
        image=image,
        quality_flags=["m29_plan_driven_materialization"],
    )
    apply_source_background(dsl, pixels)
    namespace_base_dsl(dsl)
    dsl["meta"].update(
        {
            "notes": "m29_plan_driven_materialization",
            "m29PlanDrivenMaterialization": True,
            "sourceM29MainlineMaterialization": "mainline",
        }
    )

    existing_ids = collect_element_ids(dsl["root"])
    asset_ids = {str(asset.get("assetId")) for asset in list_dicts(dsl.get("assets")) if asset.get("assetId")}
    replayed: list[ReplayNode] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[str] = []

    ocr_boxes = []
    if extra_warnings:
        warnings.extend(extra_warnings)
    if ocr_document is not None:
        ocr_boxes, ocr_warnings = text_boxes_from_ocr_document(ocr_document)
        warnings.extend(ocr_warnings)
    elif options.enable_text_replay:
        warnings.append("ocr_missing_text_replay_disabled")

    m29_nodes = list_dicts(m29_document.get("nodes"))
    m292_objects = list_dicts((m292_document or {}).get("sourceObjects"))
    if m295_replay_plan is None:
        raise ValueError("M29.5 replay plan is required for plan-driven materialization.")
    m295_plan_items = list_dicts(m295_replay_plan.get("planItems"))
    replay_m295_plan_items(
        dsl=dsl,
        existing_ids=existing_ids,
        asset_ids=asset_ids,
        pixels=pixels,
        image=image,
        m29_nodes=m29_nodes,
        m29_dir=resolve_m29_dir(m29_document),
        output_dir=output_dir,
        ocr_boxes=ocr_boxes,
        m292_objects=m292_objects,
        plan_items=m295_plan_items,
        replayed=replayed,
        skipped=skipped,
        options=options,
    )

    copied_image_asset_text_erased_count = clean_text_from_copied_image_assets(
        dsl,
        output_dir,
        replayed,
        plan_items=m295_plan_items,
    )

    fallback_erased_count = 0
    if options.erase_replayed_bboxes_from_fallback:
        fallback_erased_count = erase_replayed_bboxes_from_fallback(dsl, output_dir, pixels, replayed, plan_items=m295_plan_items)

    summary = build_summary(
        m29_document=m29_document,
        ocr_count=len(ocr_boxes),
        replayed=replayed,
        skipped=skipped,
        fallback_erased_count=fallback_erased_count,
        copied_image_asset_text_erased_count=copied_image_asset_text_erased_count,
        options=options,
    )
    if isinstance((m292_document or {}).get("summary"), dict):
        summary["m292SourcePhysicalGraph"] = dict(m292_document["summary"])
    if isinstance((m295_replay_plan or {}).get("summary"), dict):
        summary["m295ReplayPlan"] = dict(m295_replay_plan["summary"])
    report = {
        "schemaName": "M29PlanMaterializationReport",
        "schemaVersion": "0.1",
        "sourceImage": source_image_path,
        "summary": summary,
        "options": options.to_dict(),
        "replayedNodes": [asdict(item) for item in replayed],
        "skippedItems": skipped,
        "warnings": warnings,
        "meta": {
            "dslChanged": True,
            "branchOnlyExperiment": False,
            "truthSource": "source_png_plus_ocr_plus_m29_5_replay_plan",
        },
    }
    (output_dir / "m29_materialized_dsl.json").write_text(json.dumps(dsl, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "m29_materialization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29PlanMaterializerResult(dsl=dsl, report=report)


def namespace_base_dsl(dsl: dict[str, Any]) -> None:
    asset_id_map = {
        "asset_original": "m29_asset_original",
        "asset_banner": "m29_asset_fallback",
    }
    for asset in list_dicts(dsl.get("assets")):
        asset_id = str(asset.get("assetId") or "")
        if asset_id in asset_id_map:
            asset["assetId"] = asset_id_map[asset_id]

    root = dsl.get("root")
    if not isinstance(root, dict):
        return
    root["id"] = "m29_root"
    root["name"] = "M29 Plan Materialized Design"
    rewrite_element_asset_refs(root, asset_id_map)


def apply_source_background(dsl: dict[str, Any], pixels: PngPixels) -> None:
    background = rgb_to_hex(sample_canvas_background(pixels))
    page = dsl.get("page") if isinstance(dsl.get("page"), dict) else {}
    page["background"] = {"type": "color", "value": background}
    dsl["page"] = page
    root = dsl.get("root") if isinstance(dsl.get("root"), dict) else {}
    style = root.get("style") if isinstance(root.get("style"), dict) else {}
    style["fill"] = background
    root["style"] = style
    dsl["root"] = root


def sample_canvas_background(pixels: PngPixels) -> list[int]:
    samples: list[tuple[int, int, int]] = []
    for x in range(0, pixels.width, max(1, pixels.width // 24)):
        samples.append(pixel_at(pixels, x, 0))
        samples.append(pixel_at(pixels, x, pixels.height - 1))
    for y in range(0, pixels.height, max(1, pixels.height // 24)):
        samples.append(pixel_at(pixels, 0, y))
        samples.append(pixel_at(pixels, pixels.width - 1, y))
    if not samples:
        raise ValueError("source image has no edge samples for M29 background materialization.")
    return median_rgb(samples)


def pixel_at(pixels: PngPixels, x: int, y: int) -> tuple[int, int, int]:
    row = pixels.rows[max(0, min(pixels.height - 1, y))]
    col = max(0, min(pixels.width - 1, x))
    offset = col * 3
    return row[offset], row[offset + 1], row[offset + 2]


def median_rgb(samples: list[tuple[int, int, int]]) -> list[int]:
    return [
        sorted(sample[channel] for sample in samples)[len(samples) // 2]
        for channel in range(3)
    ]


def rewrite_element_asset_refs(element: dict[str, Any], asset_id_map: dict[str, str]) -> None:
    element_id = str(element.get("id") or "")
    if element_id == "original_ref":
        element["id"] = "m29_original_ref"
    elif element_id == "fallback_full_image":
        element["id"] = "m29_fallback_full_image"

    source = element.get("source")
    if isinstance(source, dict):
        asset_id = str(source.get("assetId") or "")
        if asset_id in asset_id_map:
            source["assetId"] = asset_id_map[asset_id]

    for child in list_dicts(element.get("children")):
        rewrite_element_asset_refs(child, asset_id_map)


def replay_m295_plan_items(
    *,
    dsl: dict[str, Any],
    existing_ids: set[str],
    asset_ids: set[str],
    pixels: PngPixels,
    image: PngMetadata,
    m29_nodes: list[dict[str, Any]],
    m29_dir: Path | None,
    output_dir: Path,
    ocr_boxes: list[Any],
    m292_objects: list[dict[str, Any]],
    plan_items: list[dict[str, Any]],
    replayed: list[ReplayNode],
    skipped: list[dict[str, Any]],
    options: M29PlanMaterializerOptions,
) -> None:
    children = dsl["root"].setdefault("children", [])
    m29_by_id = {str(node.get("id") or ""): node for node in m29_nodes if node.get("id")}
    ocr_by_id = {str(box.id): box for box in ocr_boxes if getattr(box, "id", None)}
    m292_by_id = {str(item.get("id") or ""): item for item in m292_objects if item.get("id")}
    for plan in plan_items:
        plan_id = str(plan.get("id") or "unknown_m295_plan")
        source_object_id = str(plan.get("sourceObjectId") or "")
        item = m292_by_id.get(source_object_id)
        if item is None:
            skipped.append(skip_item(source_object_id or plan_id, "m29_5_plan_item", None, "missing_source_object"))
            continue
        action = str(plan.get("finalReplayAction") or "")
        if action in {"preserve_in_parent_raster", "suppress_duplicate", "fallback_only", "diagnostic_only"}:
            skipped.append(skip_item(source_object_id, "m29_5_plan_item", parse_bbox(plan.get("bbox")), action))
            continue
        bbox = parse_bbox(plan.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, image.width, image.height):
            skipped.append(skip_item(source_object_id, "m29_5_plan_item", bbox, "invalid_bbox"))
            continue
        if len(replayed) >= options.max_total_visible_nodes:
            skipped.append(skip_item(source_object_id, "m29_5_plan_item", bbox, "node_budget_exceeded"))
            continue
        meta = {**m292_meta(item), **m295_meta(plan)}
        if action == "text_replay" and options.enable_text_replay:
            source_box = first_ocr_box(item, ocr_by_id)
            text = str(getattr(source_box, "text", "") or "").strip()
            if not text:
                skipped.append(skip_item(source_object_id, "m29_5_text", bbox, "missing_text"))
                continue
            bg = sample_text_background(pixels, bbox)
            fg = sample_text_foreground(pixels, bbox, bg)
            node_id = next_unique_id(existing_ids, f"m29_text_{len([node for node in replayed if node.kind == 'text']) + 1:04d}")
            children.append(
                {
                    "id": node_id,
                    "type": "text",
                    "role": "m29_text",
                    "name": f"M29 Text / {source_object_id}",
                    "layout": layout_from_bbox(bbox),
                    "style": {
                        "visible": True,
                        "opacity": 1,
                        "color": rgb_to_hex(list(fg)),
                        "fontSize": estimate_font_size(bbox),
                        "fontFamily": "Inter",
                        "fontWeight": 400,
                        "textAlign": "left",
                    },
                    "content": {"text": text},
                    "meta": {
                        "m29PlanDrivenMaterialization": True,
                        "sourceKind": "m29_5_replay_plan_item",
                        "sourceOcrBlockId": getattr(source_box, "id", source_object_id),
                        "sourceBBox": bbox,
                        "replayDecision": "ocr_text_replay",
                        "replayReasons": ["m29_5_replay_plan_text_replay"],
                        **meta,
                    },
                }
            )
            replayed.append(ReplayNode(node_id, "text", source_object_id, bbox, role="m29_text", replay_decision="text_replay"))
        elif action == "image_replay" and options.enable_image_replay:
            node = first_m29_node(item, m29_by_id)
            append_image_replay_node(
                dsl,
                children,
                existing_ids,
                asset_ids,
                pixels,
                m29_dir,
                output_dir,
                node or {"id": source_object_id, "type": "image"},
                bbox,
                replayed,
                "m29_image",
                extra_meta=meta,
                replay_source_id=source_object_id,
            )
        elif action == "icon_replay" and options.enable_symbol_replay:
            append_image_replay_node(
                dsl,
                children,
                existing_ids,
                asset_ids,
                pixels,
                m29_dir,
                output_dir,
                {"id": source_object_id, "type": "symbol"},
                bbox,
                replayed,
                "m29_symbol",
                extra_meta={**meta, "sourceM29NodeIds": m292_source_ids(item, "m29NodeIds")},
                force_crop=True,
                replay_source_id=source_object_id,
            )
        elif action == "shape_replay" and options.enable_simple_shape_replay:
            source_node = first_m29_node(item, m29_by_id)
            append_shape_replay_node(
                children,
                existing_ids,
                {
                    "id": source_object_id,
                    "type": "shape",
                    "style": build_shape_replay_style(pixels, bbox, source_node, item),
                    "subtype": str(item.get("visualKind") or ""),
                },
                bbox,
                replayed,
                extra_meta={**meta, "sourceM29NodeIds": m292_source_ids(item, "m29NodeIds")},
            )
        else:
            skipped.append(skip_item(source_object_id, "m29_5_plan_item", bbox, "unsupported_replay_action"))


def append_image_replay_node(
    dsl: dict[str, Any],
    children: list[dict[str, Any]],
    existing_ids: set[str],
    asset_ids: set[str],
    pixels: PngPixels,
    m29_dir: Path | None,
    output_dir: Path,
    node: dict[str, Any],
    bbox: list[int],
    replayed: list[ReplayNode],
    role: str,
    *,
    extra_meta: dict[str, Any] | None = None,
    force_crop: bool = False,
    replay_source_id: str | None = None,
) -> None:
    source_id = str(node.get("id") or f"{role}_unknown")
    replay_kind = "symbol" if role == "m29_symbol" else "image"
    replay_decision = "icon_replay" if role == "m29_symbol" else "image_replay"
    asset_dir = output_dir / "assets" / role
    asset_dir.mkdir(parents=True, exist_ok=True)
    source_asset = resolve_source_asset(m29_dir, node)
    suffix = source_asset.suffix.lower() if source_asset is not None else ".png"
    copied_path = asset_dir / f"{source_id}{suffix or '.png'}"
    if source_asset is not None and source_asset.exists() and not force_crop:
        shutil.copy2(source_asset, copied_path)
    else:
        copied_path.write_bytes(crop_pixels(pixels, bbox))

    asset_id = next_unique_asset_id(asset_ids, f"{role}_{len([item for item in replayed if item.kind in {'image', 'symbol'}]) + 1:04d}")
    dsl["assets"].append(
        {
            "assetId": asset_id,
            "type": "image",
            "role": role,
            "url": relative_posix(output_dir, copied_path),
            "format": "png",
            "width": bbox[2],
            "height": bbox[3],
            "storage": "local",
            "meta": {
                "m29PlanDrivenMaterialization": True,
                "sourceKind": f"m29_{node.get('type')}",
                "sourceM29NodeId": source_id,
                "sourceAssetPath": node.get("assetPath"),
            },
        }
    )
    node_id = next_unique_id(existing_ids, f"{role}_{len(replayed) + 1:04d}")
    children.append(
        {
            "id": node_id,
            "type": "image",
            "role": role,
            "name": f"M29 {str(node.get('type') or 'Image').title()} / {source_id}",
            "layout": layout_from_bbox(bbox),
            "source": {"assetId": asset_id},
            "imageFill": {"mode": "fit"},
            "style": {"visible": True, "opacity": 1},
            "meta": {
                "m29PlanDrivenMaterialization": True,
                "sourceKind": f"m29_{node.get('type')}",
                "sourceM29NodeId": source_id,
                "sourceBBox": bbox,
                "sourceAssetPath": node.get("assetPath"),
                "replayDecision": replay_decision,
                "replayReasons": ["m29_visual_primitive_replay"],
                **(extra_meta or {}),
            },
        }
    )
    replayed.append(
        ReplayNode(
            node_id,
            replay_kind,
            replay_source_id or source_id,
            bbox,
            role=role,
            asset_id=asset_id,
            asset_url=relative_posix(output_dir, copied_path),
            replay_decision=replay_decision,
        )
    )


def append_shape_replay_node(
    children: list[dict[str, Any]],
    existing_ids: set[str],
    node: dict[str, Any],
    bbox: list[int],
    replayed: list[ReplayNode],
    *,
    extra_meta: dict[str, Any] | None = None,
) -> None:
    source_id = str(node.get("id") or "unknown_shape")
    style = node.get("style") if isinstance(node.get("style"), dict) else {}
    style_meta = style.get("meta") if isinstance(style.get("meta"), dict) else {}
    fill = str(style.get("fill") or "")
    if not fill:
        raise ValueError(f"M29 shape replay style is missing source-derived fill for {source_id}.")
    node_id = next_unique_id(existing_ids, f"m29_shape_{len([item for item in replayed if item.kind == 'shape']) + 1:04d}")
    shape_node = {
        "id": node_id,
        "type": "shape",
        "role": "m29_shape",
        "name": f"M29 Shape / {source_id}",
        "layout": layout_from_bbox(bbox),
        "style": {
            "visible": True,
            "opacity": 1,
            "fill": fill,
            **({"radius": style.get("radius")} if style.get("radius") is not None else {}),
        },
        "meta": {
            "m29PlanDrivenMaterialization": True,
            "sourceKind": "m29_shape",
            "sourceM29NodeId": source_id,
            "sourceBBox": bbox,
            "replayDecision": "simple_shape_replay",
            "replayReasons": ["simple_shape"],
            **style_meta,
            **(extra_meta or {}),
        },
    }
    children.append(shape_node)
    replayed.append(ReplayNode(node_id, "shape", source_id, bbox, role="m29_shape", replay_decision="simple_shape_replay"))


def clean_text_from_copied_image_assets(
    dsl: dict[str, Any],
    output_dir: Path,
    replayed: list[ReplayNode],
    *,
    plan_items: list[dict[str, Any]] | None = None,
) -> int:
    text_nodes = [item for item in replayed if item.role == "m29_text" and item.replay_decision in {"ocr_text_replay", "text_replay"}]
    image_nodes = [item for item in replayed if item.role == "m29_image" and item.asset_url]
    if not text_nodes or not image_nodes:
        return 0

    assets = {
        str(asset.get("assetId")): asset
        for asset in list_dicts(dsl.get("assets"))
        if asset.get("assetId") and asset.get("role") == "m29_image"
    }
    erased_count = 0
    for image_node in image_nodes:
        if image_node.asset_id and image_node.asset_id not in assets:
            continue
        image_path = (output_dir / str(image_node.asset_url)).resolve()
        if not image_path.exists():
            continue
        try:
            pixels = decode_png_pixels(image_path.read_bytes())
        except Exception:
            continue

        scale_x = pixels.width / max(1, image_node.bbox[2])
        scale_y = pixels.height / max(1, image_node.bbox[3])
        rows = [bytearray(row) for row in pixels.rows]
        modified = False
        for text_node in text_nodes:
            if not plan_allows_copied_image_cleanup(plan_items, text_node.source_id, image_node.source_id):
                continue
            local_bbox = map_page_bbox_to_asset_pixels(text_node.bbox, image_node.bbox, pixels.width, pixels.height, scale_x, scale_y)
            if local_bbox is None:
                continue
            try:
                fill = sample_outer_bbox_ring_rgb(pixels, local_bbox)
            except Exception:
                fill = sample_canvas_background(pixels)
            x, y, width, height = local_bbox
            for row_idx in range(y, y + height):
                row = rows[row_idx]
                for col_idx in range(x, x + width):
                    offset = col_idx * 3
                    row[offset] = fill[0]
                    row[offset + 1] = fill[1]
                    row[offset + 2] = fill[2]
            modified = True
            erased_count += 1
        if modified:
            image_path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return erased_count


def plan_allows_copied_image_cleanup(plan_items: list[dict[str, Any]], text_source_id: str, image_source_id: str) -> bool:
    for item in plan_items:
        if str(item.get("sourceObjectId") or "") != text_source_id:
            continue
        if item.get("finalReplayAction") != "text_replay":
            return False
        for target in item.get("cleanupTargets", []) if isinstance(item.get("cleanupTargets"), list) else []:
            if (
                isinstance(target, dict)
                and target.get("target") == "copied_image_asset"
                and str(target.get("targetSourceObjectId") or "") == image_source_id
            ):
                return True
    return False


def erase_replayed_bboxes_from_fallback(
    dsl: dict[str, Any],
    output_dir: Path,
    source_pixels: PngPixels,
    replayed: list[ReplayNode],
    *,
    plan_items: list[dict[str, Any]],
) -> int:
    fallback_assets = [asset for asset in list_dicts(dsl.get("assets")) if asset.get("role") == "fallback_region" and asset.get("type") == "image"]
    if not fallback_assets or not replayed:
        return 0
    erased = 0
    for asset in fallback_assets:
        path = output_dir / str(asset.get("url") or "")
        if not path.exists():
            continue
        try:
            pixels = decode_png_pixels(path.read_bytes())
        except Exception:
            continue
        rows = [bytearray(row) for row in pixels.rows]
        modified = False
        for item in replayed:
            if not plan_allows_fallback_cleanup(plan_items, item.source_id):
                continue
            bbox = bbox_clamp(item.bbox, pixels.width, pixels.height)
            if bbox is None:
                continue
            fill = sample_outer_bbox_ring_rgb(source_pixels, bbox)
            x, y, width, height = bbox
            for row_idx in range(y, y + height):
                row = rows[row_idx]
                for col_idx in range(x, x + width):
                    offset = col_idx * 3
                    row[offset] = fill[0]
                    row[offset + 1] = fill[1]
                    row[offset + 2] = fill[2]
            modified = True
            erased += 1
        if modified:
            path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return erased


def plan_allows_fallback_cleanup(plan_items: list[dict[str, Any]], source_id: str) -> bool:
    for item in plan_items:
        if str(item.get("sourceObjectId") or "") != source_id:
            continue
        if item.get("finalReplayAction") not in {"text_replay", "image_replay", "icon_replay", "shape_replay"}:
            return False
        for target in item.get("cleanupTargets", []) if isinstance(item.get("cleanupTargets"), list) else []:
            if isinstance(target, dict) and target.get("target") == "fallback":
                return True
    return False


def build_summary(
    *,
    m29_document: dict[str, Any],
    ocr_count: int,
    replayed: list[ReplayNode],
    skipped: list[dict[str, Any]],
    fallback_erased_count: int,
    copied_image_asset_text_erased_count: int,
    options: M29PlanMaterializerOptions,
) -> dict[str, Any]:
    replay_counts: dict[str, int] = {}
    for item in replayed:
        replay_counts[item.kind] = replay_counts.get(item.kind, 0) + 1
    skipped_counts: dict[str, int] = {}
    for item in skipped:
        reason = str(item.get("reason") or "unknown")
        skipped_counts[reason] = skipped_counts.get(reason, 0) + 1
    return {
        "m29NodeCount": len(list_dicts(m29_document.get("nodes"))),
        "ocrTextCount": ocr_count,
        "replayedTextCount": replay_counts.get("text", 0),
        "replayedImageCount": replay_counts.get("image", 0),
        "replayedSymbolCount": replay_counts.get("symbol", 0),
        "replayedShapeCount": replay_counts.get("shape", 0),
        "skippedBlockedCount": skipped_counts.get("blocked_primitive", 0),
        "skippedDuplicateCount": skipped_counts.get("duplicate_bbox", 0),
        "fallbackErasedBBoxCount": fallback_erased_count,
        "copiedImageAssetTextErasedCount": copied_image_asset_text_erased_count,
        "visibleNodeCount": len(replayed),
        "maxTotalVisibleNodesExceeded": len(replayed) >= options.max_total_visible_nodes and any(item.get("reason") == "node_budget_exceeded" for item in skipped),
        "skippedReasons": skipped_counts,
    }


def sample_text_background(pixels: PngPixels, bbox: list[int]) -> list[int]:
    try:
        return sample_outer_bbox_ring_rgb(pixels, bbox)
    except Exception:
        metrics = measure_region(pixels, bbox)
        return list(metrics.mean_rgb)


def sample_text_foreground(pixels: PngPixels, bbox: list[int], bg_rgb: list[int]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    best = (32, 32, 32)
    best_distance = -1
    for row_idx in range(max(0, y), min(pixels.height, y + height)):
        row = pixels.rows[row_idx]
        for col_idx in range(max(0, x), min(pixels.width, x + width)):
            offset = col_idx * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            distance = abs(rgb[0] - bg_rgb[0]) + abs(rgb[1] - bg_rgb[1]) + abs(rgb[2] - bg_rgb[2])
            if distance > best_distance:
                best_distance = distance
                best = rgb
    return best


def estimate_font_size(bbox: list[int]) -> int:
    return max(8, min(64, round(bbox[3] * 0.82)))


def m292_meta(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceM292ObjectId": str(item.get("id") or ""),
        "m292VisualKind": str(item.get("visualKind") or ""),
        "m292PixelOwner": str(item.get("pixelOwner") or ""),
        "m292ReplayDecision": str(item.get("replayDecision") or ""),
        "m292Reasons": [str(reason) for reason in item.get("reasons", []) if isinstance(reason, str)],
    }


def m295_meta(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceM295PlanItemId": str(item.get("id") or ""),
        "m295FinalReplayAction": str(item.get("finalReplayAction") or ""),
        "m295CleanupTargets": [target for target in item.get("cleanupTargets", []) if isinstance(target, dict)],
        "m295ClusterIds": [str(cluster_id) for cluster_id in item.get("clusterIds", []) if isinstance(cluster_id, str)],
        "m295Reasons": [str(reason) for reason in item.get("reasons", []) if isinstance(reason, str)],
        "m295Risks": [str(risk) for risk in item.get("risks", []) if isinstance(risk, str)],
    }


def m292_source_ids(item: dict[str, Any], key: str) -> list[str]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    values = evidence.get(key) if isinstance(evidence, dict) else []
    return [str(value) for value in values if isinstance(value, str) and value]


def first_m29_node(item: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for source_id in m292_source_ids(item, "m29NodeIds"):
        node = by_id.get(source_id)
        if node is not None:
            return node
    return None


def first_ocr_box(item: dict[str, Any], by_id: dict[str, Any]) -> Any | None:
    for source_id in m292_source_ids(item, "ocrBoxIds"):
        box = by_id.get(source_id)
        if box is not None:
            return box
    return None


def sampled_shape_fill(pixels: PngPixels, bbox: list[int]) -> str:
    metrics = measure_region(pixels, bbox)
    return rgb_to_hex(list(metrics.mean_rgb))


def build_shape_replay_style(pixels: PngPixels, bbox: list[int], source_node: dict[str, Any] | None, m292_object: dict[str, Any] | None = None) -> dict[str, Any]:
    style: dict[str, Any] = {"fill": sampled_shape_fill(pixels, bbox)}
    style_source = "sampled_fill_only"
    radius: int | None = None
    geometry = source_node.get("geometry") if isinstance(source_node, dict) and isinstance(source_node.get("geometry"), dict) else {}
    geometry_kind = str(geometry.get("kind") or "")
    geometry_confidence = str(geometry.get("confidence") or "")
    geometry_params = geometry.get("params") if isinstance(geometry.get("params"), dict) else {}
    geometry_radius = numeric_radius(geometry_params.get("radius"))

    if geometry_kind in {"rounded_rect", "pill", "circle", "ellipse"} and geometry_confidence != "low" and geometry_radius is not None:
        radius = clamp_radius(geometry_radius, bbox)
        style_source = "shape_geometry_fit"

    if radius is not None:
        style["radius"] = radius
    style["meta"] = {
        "m29ShapeStyleSource": style_source,
        **({"m29ShapeRadius": radius} if radius is not None else {}),
    }
    return style


def numeric_radius(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return round(value)


def clamp_radius(radius: int, bbox: list[int]) -> int:
    return max(0, min(radius, min(bbox[2], bbox[3]) // 2))


def resolve_m29_dir(m29_document: dict[str, Any]) -> Path | None:
    source = str(m29_document.get("sourceM29NodesJson") or "")
    if source:
        return Path(source).expanduser().resolve().parent
    source_image = str(m29_document.get("sourceImage") or "")
    if source_image:
        return None
    return None


def resolve_source_asset(m29_dir: Path | None, node: dict[str, Any]) -> Path | None:
    asset_path = str(node.get("assetPath") or "").strip()
    if not asset_path:
        return None
    candidate = Path(asset_path).expanduser()
    if candidate.is_absolute():
        return candidate
    if m29_dir is None:
        return None
    return (m29_dir / candidate).resolve()


def parse_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(round(float(item))) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def collect_element_ids(root: dict[str, Any]) -> set[str]:
    ids: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        if isinstance(node.get("id"), str):
            ids.add(node["id"])
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            if isinstance(child, dict):
                visit(child)

    visit(root)
    return ids


def relative_posix(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def skip_item(source_id: str, source_kind: str, bbox: list[int] | None, reason: str) -> dict[str, Any]:
    return {"sourceId": source_id, "sourceKind": source_kind, "bbox": bbox, "reason": reason}
