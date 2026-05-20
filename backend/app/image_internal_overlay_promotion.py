from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata, rgb_to_hex
from .visual_evidence_normalization import parse_bbox
from .visual_primitive_graph import bbox_iou


M305Decision = Literal["promoted", "skipped"]


@dataclass(frozen=True)
class M305Options:
    max_promotions: int = 1
    ring_padding: int = 4
    glyph_dilation: int = 1
    min_glyph_pixels: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M305PromotionItem:
    id: str
    source_m294_item_id: str
    source_m293_overlay_id: str | None
    source_image_node_id: str | None
    source_m29_node_id: str | None
    source_image_bbox: list[int] | None
    overlay_bbox: list[int] | None
    recognized_text_bbox: list[int] | None
    recognized_text: str | None
    decision: M305Decision
    reasons: list[str]
    parent_image_node_id: str | None = None
    parent_source_asset_id: str | None = None
    cleaned_parent_asset_id: str | None = None
    cleaned_parent_asset_path: str | None = None
    created_text_node_id: str | None = None
    created_parent_image_node_id: str | None = None
    metrics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceM294ItemId": self.source_m294_item_id,
            "sourceM293OverlayId": self.source_m293_overlay_id,
            "sourceImageNodeId": self.source_image_node_id,
            "sourceM29NodeId": self.source_m29_node_id,
            "sourceImageBBox": self.source_image_bbox,
            "overlayBBox": self.overlay_bbox,
            "recognizedTextBBox": self.recognized_text_bbox,
            "recognizedText": self.recognized_text,
            "decision": self.decision,
            "parentImageNodeId": self.parent_image_node_id,
            "parentSourceAssetId": self.parent_source_asset_id,
            "cleanedParentAssetId": self.cleaned_parent_asset_id,
            "cleanedParentAssetPath": self.cleaned_parent_asset_path,
            "createdTextNodeId": self.created_text_node_id,
            "createdParentImageNodeId": self.created_parent_image_node_id,
            "reasons": self.reasons,
            "metrics": self.metrics or {},
        }


@dataclass(frozen=True)
class M305Document:
    schema_name: str
    schema_version: str
    source_m294_recognition_json: str | None
    source_m2905_refined_visual_objects_json: str | None
    source_m2902_media_audit_json: str | None
    options: M305Options
    summary: dict[str, Any]
    items: list[M305PromotionItem]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceM294RecognitionJson": self.source_m294_recognition_json,
            "sourceM2905RefinedVisualObjectsJson": self.source_m2905_refined_visual_objects_json,
            "sourceM2902MediaAuditJson": self.source_m2902_media_audit_json,
            "options": self.options.to_dict(),
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class ParentAsset:
    source_kind: Literal["existing_m30_image_node", "m2905_visual_asset", "m2902_accepted_image"]
    source_asset_path: Path
    source_asset_url: str | None
    source_asset_id: str | None
    source_visual_asset_id: str | None
    existing_node: dict[str, Any] | None
    bbox: list[int]
    width: int
    height: int


@dataclass(frozen=True)
class CleanupResult:
    pixels: PngPixels
    local_bbox: list[int]
    glyph_pixels: int
    background_rgb: tuple[int, int, int]
    foreground_rgb: tuple[int, int, int]
    scale_x: float
    scale_y: float


def promote_image_internal_overlay_text(
    *,
    dsl: dict[str, Any],
    output_dir: Path,
    m30_dir: Path,
    m294_document: dict[str, Any],
    m294_json_path: str | None,
    m2905_document: dict[str, Any],
    m2905_json_path: str | None,
    m2902_document: dict[str, Any],
    m2902_json_path: str | None,
    options: M305Options | None = None,
) -> M305Document:
    options = options or M305Options()
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_dsl_shape(dsl)

    source_items = [item for item in m294_document.get("items", []) if isinstance(item, dict)]
    promotion_ready = [item for item in source_items if item.get("decision") == "promotion_ready"]
    items: list[M305PromotionItem] = []
    promoted = 0

    for index, item in enumerate(promotion_ready, start=1):
        if promoted >= max(0, options.max_promotions):
            items.append(make_skipped_item(index, item, ["skipped_max_promotions"]))
            continue
        result = promote_one_item(
            item_index=index,
            item=item,
            dsl=dsl,
            output_dir=output_dir,
            m30_dir=m30_dir,
            m2905_document=m2905_document,
            m2905_dir=Path(m2905_json_path).expanduser().resolve().parent if m2905_json_path else output_dir,
            m2902_document=m2902_document,
            m2902_dir=Path(m2902_json_path).expanduser().resolve().parent if m2902_json_path else output_dir,
            options=options,
        )
        if result.decision == "promoted":
            promoted += 1
        items.append(result)

    document = M305Document(
        schema_name="M305ImageInternalOverlayPromotionDocument",
        schema_version="0.1",
        source_m294_recognition_json=m294_json_path,
        source_m2905_refined_visual_objects_json=m2905_json_path,
        source_m2902_media_audit_json=m2902_json_path,
        options=options,
        summary=build_summary(promotion_ready, items, options),
        items=items,
        warnings=[],
    )
    write_outputs(document, output_dir)
    return document


def promote_one_item(
    *,
    item_index: int,
    item: dict[str, Any],
    dsl: dict[str, Any],
    output_dir: Path,
    m30_dir: Path,
    m2905_document: dict[str, Any],
    m2905_dir: Path,
    m2902_document: dict[str, Any],
    m2902_dir: Path,
    options: M305Options,
) -> M305PromotionItem:
    gate_reasons = promotion_gate_rejections(item)
    if gate_reasons:
        return make_skipped_item(item_index, item, gate_reasons)

    source_image_bbox = parse_bbox(item.get("sourceImageBBox"))
    recognized_bbox = parse_bbox(item.get("recognizedTextBBox"))
    assert source_image_bbox is not None
    assert recognized_bbox is not None

    parent, parent_reasons = resolve_parent_asset(
        item=item,
        dsl=dsl,
        m30_dir=m30_dir,
        m2905_document=m2905_document,
        m2905_dir=m2905_dir,
        m2902_document=m2902_document,
        m2902_dir=m2902_dir,
    )
    if parent is None:
        return make_skipped_item(item_index, item, parent_reasons)

    try:
        cleanup = clean_parent_asset(parent.source_asset_path, source_image_bbox, recognized_bbox, options)
    except Exception as error:  # noqa: BLE001 - this is a guarded promotion stage.
        return make_skipped_item(item_index, item, ["parent_asset_cleanup_failed", error.__class__.__name__, str(error)])

    asset_id = next_unique_asset_id(dsl, f"m30_image_internal_overlay_cleaned_{item_index:04d}")
    cleaned_dir = m30_dir / "assets" / "m30_image_internal_overlay_cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = cleaned_dir / f"{asset_id}.png"
    cleaned_path.write_bytes(encode_rgb_png(cleanup.pixels.width, cleanup.pixels.height, cleanup.pixels.rows))
    asset_rel = relative_posix(m30_dir, cleaned_path)

    dsl["assets"].append(
        {
            "assetId": asset_id,
            "type": "image",
            "role": "m30_image_internal_overlay_cleaned_parent",
            "url": asset_rel,
            "format": "png",
            "width": parent.width,
            "height": parent.height,
            "storage": "local",
            "meta": {
                "m30Materialized": True,
                "sourceKind": "m305_cleaned_parent_image",
                "sourceM294ItemId": item.get("id"),
                "sourceImageNodeId": item.get("sourceImageNodeId"),
                "sourceM29NodeId": item.get("sourceM29NodeId"),
                "sourceImageBBox": source_image_bbox,
                "recognizedTextBBox": recognized_bbox,
                "parentSourceKind": parent.source_kind,
                "parentSourceAssetId": parent.source_asset_id,
                "parentSourceVisualAssetId": parent.source_visual_asset_id,
            },
        }
    )

    existing_ids = collect_element_ids(dsl.get("root", {}))
    parent_node_id: str | None = None
    created_parent_node_id: str | None = None
    if parent.existing_node is not None:
        parent_node_id = str(parent.existing_node.get("id") or "")
        parent.existing_node["source"] = {"assetId": asset_id}
        parent.existing_node.setdefault("meta", {})
        if isinstance(parent.existing_node["meta"], dict):
            parent.existing_node["meta"].update(
                {
                    "m305CleanedParentAssetId": asset_id,
                    "m305SourceM294ItemId": item.get("id"),
                    "m305ParentAssetCleanup": True,
                }
            )
    else:
        parent_node_id = next_unique_id(existing_ids, f"m30_image_internal_overlay_parent_{item_index:04d}")
        created_parent_node_id = parent_node_id
        parent_node = {
            "id": parent_node_id,
            "type": "image",
            "role": "m30_image_internal_overlay_parent",
            "name": f"M30.5 Cleaned Parent / {item.get('sourceImageNodeId')}",
            "layout": layout_from_bbox(source_image_bbox),
            "source": {"assetId": asset_id},
            "imageFill": {"mode": "fit"},
            "style": {"visible": True, "opacity": 1},
            "meta": {
                "m30Materialized": True,
                "sourceKind": "m305_cleaned_parent_image",
                "sourceM294ItemId": item.get("id"),
                "sourceM293OverlayId": item.get("sourceM293OverlayId"),
                "sourceImageNodeId": item.get("sourceImageNodeId"),
                "sourceM29NodeId": item.get("sourceM29NodeId"),
                "sourceImageBBox": source_image_bbox,
                "sourceVisualAssetId": parent.source_visual_asset_id,
                "cleanedParentAssetId": asset_id,
                "materializationConfidence": "medium",
            },
        }
        insert_parent_image_node(dsl, parent_node)

    text_node_id = next_unique_id(existing_ids, f"m30_image_internal_overlay_text_{item_index:04d}")
    text_node = {
        "id": text_node_id,
        "type": "text",
        "role": "m30_image_internal_overlay_text",
        "name": f"M30.5 Overlay Text / {item.get('sourceM293OverlayId')}",
        "layout": layout_from_bbox(recognized_bbox),
        "style": {
            "visible": True,
            "opacity": 1,
            "color": rgb_to_hex(list(cleanup.foreground_rgb)),
            "fontSize": max(8, min(36, round(recognized_bbox[3] * 0.82))),
            "fontFamily": "Inter",
            "fontWeight": 400,
            "textAlign": "left",
        },
        "content": {"text": str(item.get("recognizedText") or "")},
        "meta": {
            "m30Materialized": True,
            "sourceKind": "m294_image_internal_overlay_text",
            "sourceM294ItemId": item.get("id"),
            "sourceM293OverlayId": item.get("sourceM293OverlayId"),
            "sourceM292CandidateId": item.get("sourceM292CandidateId"),
            "sourceImageNodeId": item.get("sourceImageNodeId"),
            "sourceM29NodeId": item.get("sourceM29NodeId"),
            "sourceImageBBox": source_image_bbox,
            "overlayBBox": parse_bbox(item.get("overlayBBox")),
            "recognizedTextBBox": recognized_bbox,
            "cleanedParentAssetId": asset_id,
            "parentImageNodeId": parent_node_id,
            "textForegroundColorSource": "m305_glyph_median",
            "textForegroundBackgroundColor": rgb_to_hex(list(cleanup.background_rgb)),
            "materializationConfidence": "medium",
        },
    }
    insert_overlay_text_node(dsl, text_node)
    update_dsl_meta(dsl)

    return M305PromotionItem(
        id=f"m305_promotion_{item_index:03d}",
        source_m294_item_id=str(item.get("id") or ""),
        source_m293_overlay_id=str(item.get("sourceM293OverlayId")) if item.get("sourceM293OverlayId") else None,
        source_image_node_id=str(item.get("sourceImageNodeId")) if item.get("sourceImageNodeId") else None,
        source_m29_node_id=str(item.get("sourceM29NodeId")) if item.get("sourceM29NodeId") else None,
        source_image_bbox=source_image_bbox,
        overlay_bbox=parse_bbox(item.get("overlayBBox")),
        recognized_text_bbox=recognized_bbox,
        recognized_text=str(item.get("recognizedText") or ""),
        decision="promoted",
        parent_image_node_id=parent_node_id,
        parent_source_asset_id=parent.source_asset_id,
        cleaned_parent_asset_id=asset_id,
        cleaned_parent_asset_path=asset_rel,
        created_text_node_id=text_node_id,
        created_parent_image_node_id=created_parent_node_id,
        reasons=[
            "promotion_ready",
            "recognized_bbox_from_local_ocr",
            "parent_asset_cleaned_copy",
            "editable_overlay_text_node_created",
        ],
        metrics={
            "glyphPixelCount": cleanup.glyph_pixels,
            "scaleX": round(cleanup.scale_x, 4),
            "scaleY": round(cleanup.scale_y, 4),
            "localRecognizedTextBBox": cleanup.local_bbox,
            "backgroundColor": rgb_to_hex(list(cleanup.background_rgb)),
            "foregroundColor": rgb_to_hex(list(cleanup.foreground_rgb)),
            "parentSourceKind": parent.source_kind,
        },
    )


def promotion_gate_rejections(item: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if item.get("decision") != "promotion_ready":
        reasons.append("not_promotion_ready")
    if not str(item.get("recognizedText") or "").strip():
        reasons.append("missing_recognized_text")
    if parse_bbox(item.get("recognizedTextBBox")) is None:
        reasons.append("missing_tight_recognized_text_bbox")
    if "recognized_bbox_from_local_ocr" not in list_strings(item.get("reasons")):
        reasons.append("recognized_bbox_not_from_local_ocr")
    if parse_bbox(item.get("sourceImageBBox")) is None:
        reasons.append("missing_source_image_bbox")
    return reasons


def resolve_parent_asset(
    *,
    item: dict[str, Any],
    dsl: dict[str, Any],
    m30_dir: Path,
    m2905_document: dict[str, Any],
    m2905_dir: Path,
    m2902_document: dict[str, Any],
    m2902_dir: Path,
) -> tuple[ParentAsset | None, list[str]]:
    source_bbox = parse_bbox(item.get("sourceImageBBox"))
    if source_bbox is None:
        return None, ["missing_source_image_bbox"]

    existing = find_existing_parent_image_node(dsl, source_bbox, str(item.get("sourceImageNodeId") or ""), str(item.get("sourceM29NodeId") or ""))
    if len(existing) > 1:
        return None, ["ambiguous_existing_parent_image_node"]
    if len(existing) == 1:
        node = existing[0]
        asset_id = str(node.get("source", {}).get("assetId") or "")
        asset = find_asset_by_id(dsl, asset_id)
        source = resolve_m30_asset_path(m30_dir, str(asset.get("url") or "")) if asset else None
        metadata = read_png_metadata(source.read_bytes()) if source and source.exists() else None
        if source and metadata:
            return (
                ParentAsset(
                    source_kind="existing_m30_image_node",
                    source_asset_path=source,
                    source_asset_url=str(asset.get("url") or ""),
                    source_asset_id=asset_id,
                    source_visual_asset_id=str(node.get("meta", {}).get("sourceVisualAssetId") or "") or None,
                    existing_node=node,
                    bbox=source_bbox,
                    width=metadata.width,
                    height=metadata.height,
                ),
                [],
            )
        return None, ["existing_parent_asset_missing"]

    m2905_matches = find_m2905_visual_asset_matches(m2905_document, source_bbox)
    if len(m2905_matches) > 1:
        return None, ["ambiguous_m2905_parent_visual_asset"]
    if len(m2905_matches) == 1:
        visual = m2905_matches[0]
        asset_path = str(visual.get("assetPath") or "")
        source = (m2905_dir / asset_path).resolve()
        metadata = read_png_metadata(source.read_bytes()) if source.exists() else None
        if metadata:
            return (
                ParentAsset(
                    source_kind="m2905_visual_asset",
                    source_asset_path=source,
                    source_asset_url=asset_path,
                    source_asset_id=None,
                    source_visual_asset_id=str(visual.get("id") or "") or None,
                    existing_node=None,
                    bbox=source_bbox,
                    width=metadata.width,
                    height=metadata.height,
                ),
                [],
            )
        return None, ["m2905_parent_asset_missing"]

    m2902_matches = find_m2902_media_matches(m2902_document, source_bbox, str(item.get("sourceImageNodeId") or ""))
    if len(m2902_matches) > 1:
        return None, ["ambiguous_m2902_parent_image_asset"]
    if len(m2902_matches) == 1:
        media = m2902_matches[0]
        asset_path = str(media.get("assetPath") or "")
        source = (m2902_dir / asset_path).resolve()
        metadata = read_png_metadata(source.read_bytes()) if source.exists() else None
        if metadata:
            return (
                ParentAsset(
                    source_kind="m2902_accepted_image",
                    source_asset_path=source,
                    source_asset_url=asset_path,
                    source_asset_id=None,
                    source_visual_asset_id=None,
                    existing_node=None,
                    bbox=source_bbox,
                    width=metadata.width,
                    height=metadata.height,
                ),
                [],
            )
        return None, ["m2902_parent_asset_missing"]

    return None, ["parent_image_asset_not_found"]


def clean_parent_asset(source_path: Path, source_image_bbox: list[int], recognized_bbox: list[int], options: M305Options) -> CleanupResult:
    pixels = decode_png_pixels(source_path.read_bytes())
    scale_x = pixels.width / max(1, source_image_bbox[2])
    scale_y = pixels.height / max(1, source_image_bbox[3])
    local = map_page_bbox_to_asset_bbox(recognized_bbox, source_image_bbox, pixels.width, pixels.height)
    if local[2] <= 0 or local[3] <= 0:
        raise UnsupportedPngCropError("recognized bbox does not intersect parent asset")

    ring_points = collect_ring_points(local, pixels.width, pixels.height, options.ring_padding)
    if not ring_points:
        raise UnsupportedPngCropError("background sample ring is empty")
    ring_rgbs = [pixel_rgb(pixels, x, y) for x, y in ring_points]
    ring_lumas = [luma(rgb) for rgb in ring_rgbs]
    max_luma = max(ring_lumas)
    dark_candidates = [rgb for rgb, value in zip(ring_rgbs, ring_lumas, strict=False) if value <= max_luma - 35 or value <= 150]
    if not dark_candidates:
        dark_candidates = sorted(ring_rgbs, key=luma)[: max(1, len(ring_rgbs) // 3)]
    background = median_rgb(dark_candidates)
    background_luma = luma(background)

    glyph_points: set[tuple[int, int]] = set()
    foreground_rgbs: list[tuple[int, int, int]] = []
    x, y, width, height = local
    for row_idx in range(y, y + height):
        for col_idx in range(x, x + width):
            rgb = pixel_rgb(pixels, col_idx, row_idx)
            value = luma(rgb)
            if value >= 145 and value - background_luma >= 45:
                glyph_points.add((col_idx, row_idx))
                foreground_rgbs.append(rgb)
    if len(glyph_points) < options.min_glyph_pixels:
        raise UnsupportedPngCropError("not enough glyph pixels to clean parent asset")

    dilated = dilate_points(glyph_points, pixels.width, pixels.height, options.glyph_dilation)
    rows = [bytearray(row) for row in pixels.rows]
    bg_bytes = bytes(background)
    changed = 0
    for col_idx, row_idx in dilated:
        offset = col_idx * 3
        row = rows[row_idx]
        if row[offset : offset + 3] != bg_bytes:
            row[offset : offset + 3] = bg_bytes
            changed += 1
    if changed <= 0:
        raise UnsupportedPngCropError("parent asset cleanup made no pixel changes")

    return CleanupResult(
        pixels=PngPixels(width=pixels.width, height=pixels.height, rows=[bytes(row) for row in rows]),
        local_bbox=local,
        glyph_pixels=len(glyph_points),
        background_rgb=background,
        foreground_rgb=median_rgb(foreground_rgbs),
        scale_x=scale_x,
        scale_y=scale_y,
    )


def find_existing_parent_image_node(dsl: dict[str, Any], source_bbox: list[int], source_image_node_id: str, source_m29_node_id: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for child in dsl.get("root", {}).get("children", []):
        if not isinstance(child, dict) or child.get("type") != "image":
            continue
        meta = child.get("meta") if isinstance(child.get("meta"), dict) else {}
        layout = layout_to_bbox(child.get("layout"))
        if meta.get("sourceImageNodeId") == source_image_node_id or meta.get("sourceM29NodeId") == source_m29_node_id:
            matches.append(child)
        elif parse_bbox(meta.get("sourceBBox")) == source_bbox:
            matches.append(child)
        elif layout is not None and bbox_iou(layout, source_bbox) >= 0.98:
            matches.append(child)
    return unique_nodes(matches)


def find_m2905_visual_asset_matches(m2905_document: dict[str, Any], source_bbox: list[int]) -> list[dict[str, Any]]:
    matches = []
    for item in list_dicts(m2905_document.get("visualAssets")):
        bbox = parse_bbox(item.get("bbox"))
        if bbox == source_bbox or (bbox is not None and bbox_iou(bbox, source_bbox) >= 0.98):
            if str(item.get("assetPath") or ""):
                matches.append(item)
    return matches


def find_m2902_media_matches(m2902_document: dict[str, Any], source_bbox: list[int], source_image_node_id: str) -> list[dict[str, Any]]:
    matches = []
    for item in list_dicts(m2902_document.get("mediaEvidence")):
        if item.get("decision") != "accepted_image" or item.get("source") != "m29_image":
            continue
        if item.get("suggestedNextAction") != "keep_accepted_image":
            continue
        bbox = parse_bbox(item.get("bbox"))
        if str(item.get("id") or "") == source_image_node_id or bbox == source_bbox or (bbox is not None and bbox_iou(bbox, source_bbox) >= 0.98):
            if str(item.get("assetPath") or ""):
                matches.append(item)
    return matches


def make_skipped_item(item_index: int, item: dict[str, Any], reasons: list[str]) -> M305PromotionItem:
    return M305PromotionItem(
        id=f"m305_promotion_{item_index:03d}",
        source_m294_item_id=str(item.get("id") or ""),
        source_m293_overlay_id=str(item.get("sourceM293OverlayId")) if item.get("sourceM293OverlayId") else None,
        source_image_node_id=str(item.get("sourceImageNodeId")) if item.get("sourceImageNodeId") else None,
        source_m29_node_id=str(item.get("sourceM29NodeId")) if item.get("sourceM29NodeId") else None,
        source_image_bbox=parse_bbox(item.get("sourceImageBBox")),
        overlay_bbox=parse_bbox(item.get("overlayBBox")),
        recognized_text_bbox=parse_bbox(item.get("recognizedTextBBox")),
        recognized_text=str(item.get("recognizedText") or "") or None,
        decision="skipped",
        reasons=dedupe(reasons),
    )


def build_summary(source_items: list[dict[str, Any]], items: list[M305PromotionItem], options: M305Options) -> dict[str, Any]:
    promoted = [item for item in items if item.decision == "promoted"]
    return {
        "sourcePromotionReadyCount": len(source_items),
        "promotionAttemptCount": len([item for item in items if "skipped_max_promotions" not in item.reasons]),
        "promotedTextCount": len(promoted),
        "cleanedParentAssetCount": len([item for item in promoted if item.cleaned_parent_asset_id]),
        "createdTextNodeCount": len([item for item in promoted if item.created_text_node_id]),
        "skippedCount": len([item for item in items if item.decision == "skipped"]),
        "dslChanged": bool(promoted),
        "maxPromotions": options.max_promotions,
    }


def write_outputs(document: M305Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "image_internal_overlay_promotion_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "image_internal_overlay_promotion_report.md").write_text(build_markdown(document), encoding="utf-8")


def build_markdown(document: M305Document) -> str:
    lines = [
        "# M30.5 Image Internal Overlay Promotion",
        "",
        f"- Promotion ready source items: {document.summary['sourcePromotionReadyCount']}",
        f"- Promoted text: {document.summary['promotedTextCount']}",
        f"- Cleaned parent assets: {document.summary['cleanedParentAssetCount']}",
        f"- DSL changed: `{document.summary['dslChanged']}`",
        "",
        "## Items",
        "",
    ]
    for item in document.items:
        lines.append(
            f"- `{item.id}` `{item.decision}` source=`{item.source_m294_item_id}` "
            f"text=`{item.recognized_text}` bbox={item.recognized_text_bbox} reasons={item.reasons}"
        )
    return "\n".join(lines).rstrip() + "\n"


def ensure_dsl_shape(dsl: dict[str, Any]) -> None:
    if not isinstance(dsl.get("assets"), list):
        dsl["assets"] = []
    root = dsl.setdefault("root", {})
    if not isinstance(root.get("children"), list):
        root["children"] = []


def insert_parent_image_node(dsl: dict[str, Any], node: dict[str, Any]) -> None:
    children = dsl["root"].setdefault("children", [])
    index = 0
    for i, child in enumerate(children):
        if isinstance(child, dict) and child.get("role") in {"original_reference", "fallback_region"}:
            index = i + 1
    children.insert(index, node)


def insert_overlay_text_node(dsl: dict[str, Any], node: dict[str, Any]) -> None:
    dsl["root"].setdefault("children", []).append(node)


def update_dsl_meta(dsl: dict[str, Any]) -> None:
    meta = dict(dsl.get("meta") or {})
    flags = list(meta.get("qualityFlags") or [])
    if "m30_5_image_internal_overlay_promotion" not in flags:
        flags.append("m30_5_image_internal_overlay_promotion")
    meta["qualityFlags"] = flags
    meta["elementCount"] = count_elements(dsl.get("root", {}))
    dsl["meta"] = meta


def map_page_bbox_to_asset_bbox(page_bbox: list[int], source_bbox: list[int], asset_width: int, asset_height: int) -> list[int]:
    scale_x = asset_width / max(1, source_bbox[2])
    scale_y = asset_height / max(1, source_bbox[3])
    x1 = round((page_bbox[0] - source_bbox[0]) * scale_x)
    y1 = round((page_bbox[1] - source_bbox[1]) * scale_y)
    x2 = round((page_bbox[0] + page_bbox[2] - source_bbox[0]) * scale_x)
    y2 = round((page_bbox[1] + page_bbox[3] - source_bbox[1]) * scale_y)
    x1 = clamp(x1, 0, asset_width)
    y1 = clamp(y1, 0, asset_height)
    x2 = clamp(x2, 0, asset_width)
    y2 = clamp(y2, 0, asset_height)
    return [x1, y1, max(0, x2 - x1), max(0, y2 - y1)]


def collect_ring_points(bbox: list[int], width: int, height: int, padding: int) -> list[tuple[int, int]]:
    x, y, w, h = bbox
    outer_x1 = clamp(x - padding, 0, width)
    outer_y1 = clamp(y - padding, 0, height)
    outer_x2 = clamp(x + w + padding, 0, width)
    outer_y2 = clamp(y + h + padding, 0, height)
    points = []
    for row_idx in range(outer_y1, outer_y2):
        for col_idx in range(outer_x1, outer_x2):
            inside_inner = x <= col_idx < x + w and y <= row_idx < y + h
            if not inside_inner:
                points.append((col_idx, row_idx))
    return points


def dilate_points(points: set[tuple[int, int]], width: int, height: int, radius: int) -> set[tuple[int, int]]:
    if radius <= 0:
        return set(points)
    output: set[tuple[int, int]] = set()
    for x, y in points:
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                px = x + dx
                py = y + dy
                if 0 <= px < width and 0 <= py < height:
                    output.add((px, py))
    return output


def pixel_rgb(pixels: PngPixels, x: int, y: int) -> tuple[int, int, int]:
    row = pixels.rows[y]
    offset = x * 3
    return row[offset], row[offset + 1], row[offset + 2]


def median_rgb(values: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    if not values:
        return (0, 0, 0)
    return (
        round(median([rgb[0] for rgb in values])),
        round(median([rgb[1] for rgb in values])),
        round(median([rgb[2] for rgb in values])),
    )


def luma(rgb: tuple[int, int, int]) -> float:
    return rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114


def find_asset_by_id(dsl: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    for asset in dsl.get("assets", []):
        if isinstance(asset, dict) and asset.get("assetId") == asset_id:
            return asset
    return None


def resolve_m30_asset_path(m30_dir: Path, url: str) -> Path | None:
    if not url or url.startswith(("http://", "https://")):
        return None
    candidate = Path(url)
    if candidate.is_absolute():
        return candidate
    return (m30_dir / candidate).resolve()


def layout_to_bbox(layout: object) -> list[int] | None:
    if not isinstance(layout, dict):
        return None
    try:
        return [round(float(layout["x"])), round(float(layout["y"])), round(float(layout["width"])), round(float(layout["height"]))]
    except (KeyError, TypeError, ValueError):
        return None


def layout_from_bbox(bbox: list[int]) -> dict[str, int]:
    return {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]}


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


def next_unique_id(existing_ids: set[str], base: str) -> str:
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    existing_ids.add(candidate)
    return candidate


def next_unique_asset_id(dsl: dict[str, Any], base: str) -> str:
    ids = {str(asset.get("assetId")) for asset in dsl.get("assets", []) if isinstance(asset, dict) and asset.get("assetId")}
    return next_unique_id(ids, base)


def count_elements(root: dict[str, Any]) -> int:
    total = 1
    for child in root.get("children", []) if isinstance(root.get("children"), list) else []:
        if isinstance(child, dict):
            total += count_elements(child)
    return total


def unique_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[int] = set()
    for node in nodes:
        marker = id(node)
        if marker not in seen:
            seen.add(marker)
            output.append(node)
    return output


def list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def list_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def relative_posix(base: Path, path: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()
