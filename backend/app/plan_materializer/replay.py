from __future__ import annotations

from pathlib import Path
from typing import Any

from ..m29_materialization_utils import layout_from_bbox, next_unique_id
from ..png_tools import PngMetadata, PngPixels, rgb_to_hex
from ..visual_primitive_graph import bbox_in_bounds
from .assets import append_image_replay_node
from .background import build_shape_replay_style, estimate_font_size, sample_text_background, sample_text_foreground
from .types import PlanMaterializerOptions, ReplayNode


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
    options: PlanMaterializerOptions,
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
            transparent_asset = transparent_asset_path_for(item, output_dir)
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
                extra_meta={
                    **meta,
                    "sourceM29NodeIds": m292_source_ids(item, "m29NodeIds"),
                    **({"m29TransparentAssetPath": str(transparent_asset)} if transparent_asset is not None else {}),
                },
                force_crop=True,
                replay_source_id=source_object_id,
                source_asset_override=transparent_asset,
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


def transparent_asset_path_for(item: dict[str, Any], output_dir: Path) -> Path | None:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if evidence.get("promotionSource") not in {"m29_6_internal_icon_candidate", "m29_6_foreground_claim"}:
        return None
    value = str(evidence.get("transparentAssetPath") or "").strip()
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = output_dir.parent / "m29_transparent_assets" / value
    return candidate if candidate.exists() else None


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


def skip_item(source_id: str, source_kind: str, bbox: list[int] | None, reason: str) -> dict[str, Any]:
    return {"sourceId": source_id, "sourceKind": source_kind, "bbox": bbox, "reason": reason}
