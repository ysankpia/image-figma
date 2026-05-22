from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .dsl_factory import build_deterministic_dsl
from .evidence_grounded_dsl_materialization import (
    bbox_overlap_ratio,
    layout_from_bbox,
    list_dicts,
    next_unique_asset_id,
    next_unique_id,
    sample_outer_bbox_ring_rgb,
)
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
from .visual_primitive_graph import bbox_area, bbox_clamp, bbox_in_bounds, bbox_iou, crop_pixels, measure_region


@dataclass(frozen=True)
class M29DirectReplayOptions:
    enable_text_replay: bool = True
    enable_image_replay: bool = True
    enable_symbol_replay: bool = True
    enable_simple_shape_replay: bool = True
    erase_replayed_bboxes_from_fallback: bool = True
    min_symbol_area: int = 16
    max_total_visible_nodes: int = 260
    ocr_overlap_threshold: float = 0.45
    duplicate_iou_threshold: float = 0.88
    min_text_confidence: float = 0.60

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M29DirectReplayResult:
    dsl: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True)
class ReplayNode:
    id: str
    kind: str
    source_id: str
    bbox: list[int]


def build_m29_direct_replay_dsl(
    *,
    source_png: bytes,
    source_image_path: str,
    m29_document: dict[str, Any],
    output_dir: Path,
    ocr_document: dict[str, Any] | None = None,
    m292_document: dict[str, Any] | None = None,
    options: M29DirectReplayOptions | None = None,
    task_id: str = "m29_direct_replay",
) -> M29DirectReplayResult:
    options = options or M29DirectReplayOptions()
    image = read_png_metadata(source_png)
    if image is None:
        raise UnsupportedPngCropError("M29 direct replay source image is not a readable PNG.")
    pixels = decode_png_pixels(source_png)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(source_image_path).expanduser()
    fallback_dir = output_dir / "assets" / "m29_direct_fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    fallback_path = fallback_dir / (source_path.name or "source.png")
    fallback_path.write_bytes(source_png)

    dsl = build_deterministic_dsl(
        task_id=task_id,
        original_url=str(source_path),
        fallback_url=relative_posix(output_dir, fallback_path),
        image=image,
        quality_flags=["m29_direct_replay_experiment"],
    )
    namespace_base_dsl(dsl)
    dsl["meta"].update(
        {
            "notes": "m29_direct_replay_experiment",
            "m29DirectReplay": True,
            "sourceM29DirectReplay": "branch_experiment",
        }
    )

    existing_ids = collect_element_ids(dsl["root"])
    asset_ids = {str(asset.get("assetId")) for asset in list_dicts(dsl.get("assets")) if asset.get("assetId")}
    replayed: list[ReplayNode] = []
    skipped: list[dict[str, Any]] = []
    warnings: list[str] = []

    ocr_boxes = []
    if ocr_document is not None:
        ocr_boxes, ocr_warnings = text_boxes_from_ocr_document(ocr_document)
        warnings.extend(ocr_warnings)
    elif options.enable_text_replay:
        warnings.append("ocr_missing_text_replay_disabled")

    m29_nodes = list_dicts(m29_document.get("nodes"))
    m292_objects = list_dicts((m292_document or {}).get("sourceObjects"))
    if m292_objects:
        replay_m292_objects(
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
            replayed=replayed,
            skipped=skipped,
            options=options,
        )
    else:
        replay_text_nodes(
            dsl=dsl,
            existing_ids=existing_ids,
            pixels=pixels,
            image=image,
            ocr_boxes=ocr_boxes,
            m29_nodes=m29_nodes,
            options=options,
            replayed=replayed,
            skipped=skipped,
        )
        replay_m29_nodes(
            dsl=dsl,
            existing_ids=existing_ids,
            asset_ids=asset_ids,
            pixels=pixels,
            image=image,
            m29_nodes=m29_nodes,
            m29_blocked=list_dicts(m29_document.get("blocked")),
            m29_dir=resolve_m29_dir(m29_document),
            output_dir=output_dir,
            ocr_bboxes=[item.bbox for item in ocr_boxes],
            replayed=replayed,
            skipped=skipped,
            options=options,
        )

    fallback_erased_count = 0
    if options.erase_replayed_bboxes_from_fallback:
        fallback_erased_count = erase_replayed_bboxes_from_fallback(dsl, output_dir, pixels, replayed)

    summary = build_summary(
        m29_document=m29_document,
        ocr_count=len(ocr_boxes),
        replayed=replayed,
        skipped=skipped,
        fallback_erased_count=fallback_erased_count,
        options=options,
    )
    if isinstance((m292_document or {}).get("summary"), dict):
        summary["m292SourcePhysicalGraph"] = dict(m292_document["summary"])
    report = {
        "schemaName": "M29DirectReplayReport",
        "schemaVersion": "0.1",
        "sourceImage": source_image_path,
        "summary": summary,
        "options": options.to_dict(),
        "replayedNodes": [asdict(item) for item in replayed],
        "skippedItems": skipped,
        "warnings": warnings,
        "meta": {
            "dslChanged": True,
            "branchOnlyExperiment": True,
            "truthSource": "source_png_plus_ocr_plus_m29_2_source_objects" if m292_objects else "source_png_plus_ocr_plus_m29_nodes",
        },
    }
    (output_dir / "m29_direct_replay_dsl.json").write_text(json.dumps(dsl, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "m29_direct_replay_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29DirectReplayResult(dsl=dsl, report=report)


def namespace_base_dsl(dsl: dict[str, Any]) -> None:
    """Keep the experimental variant distinct from the mainline DSL inside one task."""
    asset_id_map = {
        "asset_original": "m29_direct_asset_original",
        "asset_banner": "m29_direct_asset_fallback",
    }
    for asset in list_dicts(dsl.get("assets")):
        asset_id = str(asset.get("assetId") or "")
        if asset_id in asset_id_map:
            asset["assetId"] = asset_id_map[asset_id]

    root = dsl.get("root")
    if not isinstance(root, dict):
        return
    root["id"] = "m29_direct_root"
    root["name"] = "M29 Direct Replay"
    rewrite_element_asset_refs(root, asset_id_map)


def rewrite_element_asset_refs(element: dict[str, Any], asset_id_map: dict[str, str]) -> None:
    element_id = str(element.get("id") or "")
    if element_id == "original_ref":
        element["id"] = "m29_direct_original_ref"
    elif element_id == "fallback_full_image":
        element["id"] = "m29_direct_fallback_full_image"

    source = element.get("source")
    if isinstance(source, dict):
        asset_id = str(source.get("assetId") or "")
        if asset_id in asset_id_map:
            source["assetId"] = asset_id_map[asset_id]

    for child in list_dicts(element.get("children")):
        rewrite_element_asset_refs(child, asset_id_map)


def replay_text_nodes(
    *,
    dsl: dict[str, Any],
    existing_ids: set[str],
    pixels: PngPixels,
    image: PngMetadata,
    ocr_boxes: list[Any],
    m29_nodes: list[dict[str, Any]],
    options: M29DirectReplayOptions,
    replayed: list[ReplayNode],
    skipped: list[dict[str, Any]],
) -> None:
    if not options.enable_text_replay:
        return
    children = dsl["root"].setdefault("children", [])
    for index, box in enumerate(ocr_boxes):
        bbox = bbox_clamp(box.bbox, image.width, image.height)
        source_id = str(box.id or f"ocr_text_{index + 1:03d}")
        text = str(box.text or "").strip()
        if bbox is None:
            skipped.append(skip_item(source_id, "ocr_text", None, "invalid_bbox"))
            continue
        if not text:
            skipped.append(skip_item(source_id, "ocr_text", bbox, "missing_text"))
            continue
        if float(box.confidence) < options.min_text_confidence:
            skipped.append(skip_item(source_id, "ocr_text", bbox, "low_confidence"))
            continue
        if len(replayed) >= options.max_total_visible_nodes:
            skipped.append(skip_item(source_id, "ocr_text", bbox, "node_budget_exceeded"))
            continue

        bg = sample_text_background(pixels, bbox)
        fg = sample_text_foreground(pixels, bbox, bg)
        overlapped_m29_ids = overlapped_m29_node_ids(bbox, m29_nodes, options.ocr_overlap_threshold)
        node_id = next_unique_id(existing_ids, f"m29_direct_text_{len([item for item in replayed if item.kind == 'text']) + 1:04d}")
        node = {
            "id": node_id,
            "type": "text",
            "role": "m29_direct_text",
            "name": f"M29 Direct Text / {source_id}",
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
                "m29DirectReplay": True,
                "sourceKind": "ocr_text_box",
                "sourceOcrBlockId": source_id,
                "sourceM29OverlappedNodeIds": overlapped_m29_ids,
                "sourceBBox": bbox,
                "ocrConfidence": round(float(box.confidence), 4),
                "replayDecision": "ocr_text_replay",
                "replayReasons": ["ocr_text_priority"],
            },
        }
        children.append(node)
        replayed.append(ReplayNode(node_id, "text", source_id, bbox))


def replay_m29_nodes(
    *,
    dsl: dict[str, Any],
    existing_ids: set[str],
    asset_ids: set[str],
    pixels: PngPixels,
    image: PngMetadata,
    m29_nodes: list[dict[str, Any]],
    m29_blocked: list[dict[str, Any]],
    m29_dir: Path | None,
    output_dir: Path,
    ocr_bboxes: list[list[int]],
    replayed: list[ReplayNode],
    skipped: list[dict[str, Any]],
    options: M29DirectReplayOptions,
) -> None:
    children = dsl["root"].setdefault("children", [])
    for node in m29_nodes:
        node_type = str(node.get("type") or "")
        source_id = str(node.get("id") or "unknown_m29_node")
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, image.width, image.height):
            skipped.append(skip_item(source_id, f"m29_{node_type}", bbox, "invalid_bbox"))
            continue
        if node_type == "text":
            skipped.append(skip_item(source_id, "m29_text", bbox, "ocr_text_preferred"))
            continue
        if any(bbox_overlap_ratio(bbox, ocr_bbox) >= options.ocr_overlap_threshold for ocr_bbox in ocr_bboxes):
            skipped.append(skip_item(source_id, f"m29_{node_type}", bbox, "overlapped_by_ocr_text"))
            continue
        if is_duplicate_replay_bbox(bbox, replayed, options.duplicate_iou_threshold):
            skipped.append(skip_item(source_id, f"m29_{node_type}", bbox, "duplicate_bbox"))
            continue
        if len(replayed) >= options.max_total_visible_nodes:
            skipped.append(skip_item(source_id, f"m29_{node_type}", bbox, "node_budget_exceeded"))
            continue

        if node_type == "image" and options.enable_image_replay:
            append_image_replay_node(dsl, children, existing_ids, asset_ids, pixels, m29_dir, output_dir, node, bbox, replayed, "m29_direct_image")
        elif node_type == "symbol" and options.enable_symbol_replay:
            if bbox_area(bbox) < options.min_symbol_area:
                skipped.append(skip_item(source_id, "m29_symbol", bbox, "too_small"))
                continue
            append_image_replay_node(dsl, children, existing_ids, asset_ids, pixels, m29_dir, output_dir, node, bbox, replayed, "m29_direct_symbol")
        elif node_type == "shape" and options.enable_simple_shape_replay:
            if not is_simple_shape(node):
                skipped.append(skip_item(source_id, "m29_shape", bbox, "unsupported_shape_complexity"))
                continue
            append_shape_replay_node(children, existing_ids, node, bbox, replayed)
        elif node_type in {"unknown", "blocked"}:
            skipped.append(skip_item(source_id, f"m29_{node_type}", bbox, "blocked_primitive"))
        else:
            skipped.append(skip_item(source_id, f"m29_{node_type}", bbox, "unsupported_visual_kind"))

    for blocked in m29_blocked:
        bbox = parse_bbox(blocked.get("bbox"))
        skipped.append(skip_item(str(blocked.get("id") or "unknown_blocked"), "m29_blocked", bbox, "blocked_primitive"))


def replay_m292_objects(
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
    replayed: list[ReplayNode],
    skipped: list[dict[str, Any]],
    options: M29DirectReplayOptions,
) -> None:
    children = dsl["root"].setdefault("children", [])
    m29_by_id = {str(node.get("id") or ""): node for node in m29_nodes if node.get("id")}
    ocr_by_id = {str(box.id): box for box in ocr_boxes if getattr(box, "id", None)}
    for item in m292_objects:
        object_id = str(item.get("id") or "unknown_m292_object")
        decision = str(item.get("replayDecision") or "")
        visual_kind = str(item.get("visualKind") or "")
        pixel_owner = str(item.get("pixelOwner") or "")
        bbox = parse_bbox(item.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, image.width, image.height):
            skipped.append(skip_item(object_id, "m29_2_source_object", bbox, "invalid_bbox"))
            continue
        if decision in {"preserve_in_parent_raster", "skip"}:
            skipped.append(skip_item(object_id, "m29_2_source_object", bbox, decision))
            continue
        if len(replayed) >= options.max_total_visible_nodes:
            skipped.append(skip_item(object_id, "m29_2_source_object", bbox, "node_budget_exceeded"))
            continue
        meta = m292_meta(item)
        if decision == "text_replay" and options.enable_text_replay:
            source_box = first_ocr_box(item, ocr_by_id)
            text = str(getattr(source_box, "text", "") or "").strip()
            if not text:
                skipped.append(skip_item(object_id, "m29_2_text", bbox, "missing_text"))
                continue
            bg = sample_text_background(pixels, bbox)
            fg = sample_text_foreground(pixels, bbox, bg)
            node_id = next_unique_id(existing_ids, f"m29_direct_text_{len([node for node in replayed if node.kind == 'text']) + 1:04d}")
            children.append(
                {
                    "id": node_id,
                    "type": "text",
                    "role": "m29_direct_text",
                    "name": f"M29 Direct Text / {object_id}",
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
                        "m29DirectReplay": True,
                        "sourceKind": "m29_2_source_object",
                        "sourceOcrBlockId": getattr(source_box, "id", object_id),
                        "sourceBBox": bbox,
                        "replayDecision": "ocr_text_replay",
                        "replayReasons": ["m29_2_source_ownership_text_replay"],
                        **meta,
                    },
                }
            )
            replayed.append(ReplayNode(node_id, "text", object_id, bbox))
        elif decision == "image_replay" and options.enable_image_replay:
            node = first_m29_node(item, m29_by_id)
            append_image_replay_node(
                dsl,
                children,
                existing_ids,
                asset_ids,
                pixels,
                m29_dir,
                output_dir,
                node or {"id": object_id, "type": "image"},
                bbox,
                replayed,
                "m29_direct_image",
                extra_meta=meta,
            )
        elif decision == "icon_replay" and options.enable_symbol_replay:
            if bbox_area(bbox) < options.min_symbol_area:
                skipped.append(skip_item(object_id, "m29_2_icon", bbox, "too_small"))
                continue
            append_image_replay_node(
                dsl,
                children,
                existing_ids,
                asset_ids,
                pixels,
                m29_dir,
                output_dir,
                {"id": object_id, "type": "symbol"},
                bbox,
                replayed,
                "m29_direct_symbol",
                extra_meta={**meta, "sourceM29NodeIds": m292_source_ids(item, "m29NodeIds")},
                force_crop=True,
            )
        elif decision == "shape_replay" and options.enable_simple_shape_replay:
            append_shape_replay_node(
                children,
                existing_ids,
                {
                    "id": object_id,
                    "type": "shape",
                    "style": {"fill": sampled_shape_fill(pixels, bbox)},
                    "subtype": visual_kind,
                },
                bbox,
                replayed,
                extra_meta=meta,
            )
        else:
            skipped.append(skip_item(object_id, f"m29_2_{visual_kind}_{pixel_owner}", bbox, "unsupported_replay_decision"))


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
) -> None:
    source_id = str(node.get("id") or f"{role}_unknown")
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
                "m29DirectReplay": True,
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
            "name": f"M29 Direct {str(node.get('type') or 'Image').title()} / {source_id}",
            "layout": layout_from_bbox(bbox),
            "source": {"assetId": asset_id},
            "imageFill": {"mode": "fit"},
            "style": {"visible": True, "opacity": 1},
            "meta": {
                "m29DirectReplay": True,
                "sourceKind": f"m29_{node.get('type')}",
                "sourceM29NodeId": source_id,
                "sourceBBox": bbox,
                "sourceAssetPath": node.get("assetPath"),
                "replayDecision": f"{node.get('type')}_replay",
                "replayReasons": ["m29_visual_primitive_replay"],
                **(extra_meta or {}),
            },
        }
    )
    replayed.append(ReplayNode(node_id, str(node.get("type") or "image"), source_id, bbox))


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
    node_id = next_unique_id(existing_ids, f"m29_direct_shape_{len([item for item in replayed if item.kind == 'shape']) + 1:04d}")
    shape_node = {
        "id": node_id,
        "type": "shape",
        "role": "m29_direct_shape",
        "name": f"M29 Direct Shape / {source_id}",
        "layout": layout_from_bbox(bbox),
        "style": {
            "visible": True,
            "opacity": 1,
            "fill": str(style.get("fill") or "#F7F8FA"),
            **({"radius": style.get("radius")} if style.get("radius") is not None else {}),
        },
        "meta": {
            "m29DirectReplay": True,
            "sourceKind": "m29_shape",
            "sourceM29NodeId": source_id,
            "sourceBBox": bbox,
            "replayDecision": "simple_shape_replay",
            "replayReasons": ["simple_shape"],
            **(extra_meta or {}),
        },
    }
    children.append(shape_node)
    replayed.append(ReplayNode(node_id, "shape", source_id, bbox))


def erase_replayed_bboxes_from_fallback(
    dsl: dict[str, Any],
    output_dir: Path,
    source_pixels: PngPixels,
    replayed: list[ReplayNode],
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


def build_summary(
    *,
    m29_document: dict[str, Any],
    ocr_count: int,
    replayed: list[ReplayNode],
    skipped: list[dict[str, Any]],
    fallback_erased_count: int,
    options: M29DirectReplayOptions,
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
        "visibleNodeCount": len(replayed),
        "maxTotalVisibleNodesExceeded": len(replayed) >= options.max_total_visible_nodes and any(item.get("reason") == "node_budget_exceeded" for item in skipped),
        "skippedReasons": skipped_counts,
    }


def is_simple_shape(node: dict[str, Any]) -> bool:
    subtype = str(node.get("subtype") or "")
    metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
    reasons = {str(reason) for reason in node.get("reasons", [])}
    color_count = int(metrics.get("colorCount") or 0)
    texture_score = float(metrics.get("textureScore") or 0)
    return subtype in {"separator", "small_rect", "card_background", "container_background", "small_ellipse", "badge_background"} or (
        "solid_fill" in reasons and color_count <= 12 and texture_score <= 0.14
    )


def is_duplicate_replay_bbox(bbox: list[int], replayed: list[ReplayNode], threshold: float) -> bool:
    return any(bbox_iou(bbox, item.bbox) >= threshold for item in replayed)


def overlapped_m29_node_ids(bbox: list[int], m29_nodes: list[dict[str, Any]], threshold: float) -> list[str]:
    ids: list[str] = []
    for node in m29_nodes:
        node_type = str(node.get("type") or "")
        if node_type == "text":
            continue
        node_bbox = parse_bbox(node.get("bbox"))
        if node_bbox is None:
            continue
        if bbox_overlap_ratio(node_bbox, bbox) >= threshold:
            node_id = str(node.get("id") or "")
            if node_id:
                ids.append(node_id)
    return ids


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
