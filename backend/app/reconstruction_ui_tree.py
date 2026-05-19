from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, PngRegion, crop_png, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_primitive_graph import (
    bbox_area,
    bbox_clamp,
    bbox_in_bounds,
    bbox_intersects,
    bbox_iou,
    bbox_x2,
    bbox_y2,
)


M31Profile = Literal["development", "production"]
M31UnitKind = Literal[
    "container_backed_unit",
    "row_unit",
    "media_text_unit",
    "single_primitive_unit",
]

ALLOWED_REVIEW_REASONS = {
    "orphan_primitive",
    "ambiguous_container",
    "cross_unit_overlap",
    "unsafe_text_visual_overlap",
    "out_of_bounds",
    "duplicate_source",
    "insufficient_geometry",
}
FORBIDDEN_M31_TERMS = {
    "bottom_nav",
    "tab",
    "toolbar",
    "ecommerce",
    "education",
    "wallet",
    "coupon",
    "merchant",
    "product",
    "course",
    "recoverable_icon",
    "promotable_icon",
    "icon_recovery",
    "restore",
}
CONTAINER_SUBTYPES = {"card_background", "large_container", "container", "rect", "rounded_rect"}


@dataclass(frozen=True)
class M31Result:
    tree: dict[str, Any]
    report: dict[str, Any]
    output_dir: Path


@dataclass(frozen=True)
class OcrTextBox:
    id: str
    text: str
    bbox: list[int]
    confidence: float


@dataclass
class PrimitiveRef:
    id: str
    source_kind: str
    source_id: str
    source_order: int
    primitive_type: str
    primitive_subtype: str
    bbox: list[int]
    confidence: float
    layer_hint: str
    text: str | None
    source_refs: dict[str, Any]
    owner_unit_id: str | None = None
    review_bucket_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "kind": "primitive_ref",
            "sourceKind": self.source_kind,
            "sourceId": self.source_id,
            "sourceOrder": self.source_order,
            "primitiveType": self.primitive_type,
            "primitiveSubtype": self.primitive_subtype,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "layerHint": self.layer_hint,
            "sourceRefs": self.source_refs,
            "ownerUnitId": self.owner_unit_id,
            "reviewBucketId": self.review_bucket_id,
        }
        if self.text is not None:
            data["text"] = self.text
        return data


def extract_m31_reconstruction_ui_tree(
    *,
    source_image_path: str,
    ocr_document: dict[str, Any],
    ocr_json_path: str,
    m29_document: dict[str, Any],
    m29_nodes_json_path: str,
    output_dir: Path,
    profile: M31Profile = "development",
    png_data: bytes | None = None,
) -> M31Result:
    source_path = Path(source_image_path).expanduser().resolve()
    if png_data is None:
        png_data = source_path.read_bytes()
    image = read_png_metadata(png_data)
    if image is None:
        raise ValueError("M31 source image is not a readable PNG.")
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_boxes = parse_ocr_boxes(ocr_document)
    primitive_refs, warnings = build_primitive_refs(m29_document, ocr_boxes, image.width, image.height)
    context = TreeBuildContext(
        source_png=png_data,
        pixels=pixels,
        output_dir=output_dir,
        primitive_refs=primitive_refs,
        source_nodes=list_dicts(m29_document.get("nodes")),
        relations=list_dicts(m29_document.get("relations")),
        warnings=warnings,
    )
    build_tree_nodes(context)
    assign_remaining_to_review(context, "orphan_primitive")
    tree = build_tree_document(
        source_image=str(source_path),
        source_ocr_json=str(Path(ocr_json_path).expanduser().resolve()),
        source_m29_nodes_json=str(Path(m29_nodes_json_path).expanduser().resolve()),
        width=image.width,
        height=image.height,
        context=context,
    )
    report = build_report(tree, ocr_boxes, context, output_dir)
    validate_m31_result(tree, report)

    tree_path = output_dir / "m31_reconstruction_tree.json"
    report_path = output_dir / "m31_reconstruction_tree_report.json"
    tree_path.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if profile == "development":
        (output_dir / "m31_reconstruction_tree_overlay.png").write_bytes(build_overlay(pixels, tree, context.review_buckets))
    return M31Result(tree=tree, report=report, output_dir=output_dir)


@dataclass
class TreeBuildContext:
    source_png: bytes
    pixels: PngPixels
    output_dir: Path
    primitive_refs: list[PrimitiveRef]
    source_nodes: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    warnings: list[str]
    nodes: list[dict[str, Any]] | None = None
    assets: list[dict[str, Any]] | None = None
    root_children: list[str] | None = None
    review_buckets: list[dict[str, Any]] | None = None
    unit_index: int = 0
    group_index: int = 0
    item_index: int = 0
    bucket_index: int = 0

    def __post_init__(self) -> None:
        self.nodes = []
        self.assets = []
        self.root_children = []
        self.review_buckets = []


def build_tree_nodes(context: TreeBuildContext) -> None:
    assign_preflight_review_buckets(context)
    build_container_units(context)
    build_repeated_units(context)
    build_row_units(context)
    build_single_primitive_units(context)


def assign_preflight_review_buckets(context: TreeBuildContext) -> None:
    invalid = [ref for ref in unassigned_refs(context) if not bbox_in_bounds(ref.bbox, context.pixels.width, context.pixels.height)]
    if invalid:
        add_review_bucket(context, "out_of_bounds", invalid)
    duplicates = [ref for ref in unassigned_refs(context) if ref.source_refs.get("duplicateSource") is True]
    if duplicates:
        add_review_bucket(context, "duplicate_source", duplicates)


def build_container_units(context: TreeBuildContext) -> None:
    refs_by_source = refs_by_source_id(context.primitive_refs)
    nodes_by_id = {str(node.get("id")): node for node in context.source_nodes if node.get("id") is not None}
    children_by_parent: dict[str, list[str]] = {}
    for relation in context.relations:
        if relation.get("type") != "contains":
            continue
        parent_id = str(relation.get("parentId") or "")
        child_id = str(relation.get("childId") or "")
        if parent_id and child_id:
            children_by_parent.setdefault(parent_id, []).append(child_id)

    for parent_id, child_ids in sorted(children_by_parent.items(), key=lambda item: source_order(nodes_by_id.get(item[0], {}))):
        parent_node = nodes_by_id.get(parent_id, {})
        parent_ref = refs_by_source.get(parent_id)
        if parent_ref is None or parent_ref.owner_unit_id or parent_ref.review_bucket_id:
            continue
        if not is_container_candidate(parent_node):
            continue
        owned_refs = [parent_ref]
        for child_id in child_ids:
            child_ref = refs_by_source.get(child_id)
            if child_ref is not None and child_ref.owner_unit_id is None and child_ref.review_bucket_id is None:
                owned_refs.append(child_ref)
        if len(owned_refs) < 2:
            continue
        add_unit(
            context,
            unit_kind="container_backed_unit",
            visual_kind="card_like",
            bbox=parent_ref.bbox,
            bbox_derivation="container_from_m29_shape",
            primitive_refs=owned_refs,
            root_child=True,
        )


def build_repeated_units(context: TreeBuildContext) -> None:
    candidates = [
        ref
        for ref in unassigned_refs(context)
        if ref.primitive_type in {"shape", "image", "symbol"} and bbox_area(ref.bbox) >= 16 and bbox_in_bounds(ref.bbox, context.pixels.width, context.pixels.height)
    ]
    groups: list[list[PrimitiveRef]] = []
    used: set[str] = set()
    for ref in sorted(candidates, key=lambda item: (center_y(item.bbox), item.bbox[0], item.id)):
        if ref.id in used:
            continue
        peers = [
            item
            for item in candidates
            if item.id not in used
            and item.primitive_type == ref.primitive_type
            and similar_size(ref.bbox, item.bbox)
            and abs(center_y(ref.bbox) - center_y(item.bbox)) <= max(6, max(ref.bbox[3], item.bbox[3]) * 0.35)
        ]
        peers = sorted(peers, key=lambda item: item.bbox[0])
        if len(peers) >= 3 and regular_spacing(peers):
            groups.append(peers)
            used.update(item.id for item in peers)

    for peers in groups:
        context.group_index += 1
        group_id = f"repeat_group_{context.group_index:04d}"
        item_ids: list[str] = []
        for ref in peers:
            unit = add_unit(
                context,
                unit_kind="single_primitive_unit",
                visual_kind="unknown",
                bbox=ref.bbox,
                bbox_derivation="source_m29_bbox",
                primitive_refs=[ref],
                root_child=False,
            )
            context.item_index += 1
            item_id = f"repeat_item_{context.item_index:04d}"
            item_ids.append(item_id)
            context.nodes.append(
                {
                    "id": item_id,
                    "kind": "repeated_item",
                    "visualKind": "unknown",
                    "bbox": unit["bbox"],
                    "bboxDerivation": "repeat_cell_partition",
                    "children": [unit["id"]],
                    "sourceRefs": unit["sourceRefs"],
                }
            )
        context.nodes.append(
            {
                "id": group_id,
                "kind": "repeated_group",
                "visualKind": "matrix",
                "bbox": union_bbox([ref.bbox for ref in peers]),
                "bboxDerivation": "repeat_cell_partition",
                "children": item_ids,
                "sourceRefs": {"m29NodeIds": [ref.source_id for ref in peers], "ocrTextBoxIds": [], "blockedEvidenceIds": []},
            }
        )
        context.root_children.append(group_id)


def build_row_units(context: TreeBuildContext) -> None:
    refs = sorted(unassigned_refs(context), key=lambda item: (center_y(item.bbox), item.bbox[0], item.id))
    clusters: list[list[PrimitiveRef]] = []
    for ref in refs:
        placed = False
        for cluster in clusters:
            if row_compatible(cluster, ref):
                cluster.append(ref)
                placed = True
                break
        if not placed:
            clusters.append([ref])

    for cluster in clusters:
        if len(cluster) < 2:
            continue
        cluster = sorted(cluster, key=lambda item: item.bbox[0])
        if too_spread_out(cluster, context.pixels.width):
            continue
        visual_kind = classify_cluster_visual_kind(cluster)
        add_unit(
            context,
            unit_kind="media_text_unit" if visual_kind == "media_text_block" else "row_unit",
            visual_kind=visual_kind,
            bbox=union_bbox([ref.bbox for ref in cluster]),
            bbox_derivation="row_cluster_from_alignment",
            primitive_refs=cluster,
            root_child=True,
        )


def build_single_primitive_units(context: TreeBuildContext) -> None:
    for ref in list(unassigned_refs(context)):
        add_unit(
            context,
            unit_kind="single_primitive_unit",
            visual_kind=single_visual_kind(ref),
            bbox=ref.bbox,
            bbox_derivation="source_m29_bbox",
            primitive_refs=[ref],
            root_child=True,
        )


def assign_remaining_to_review(context: TreeBuildContext, reason: str) -> None:
    remaining = unassigned_refs(context)
    if remaining:
        add_review_bucket(context, reason, remaining)


def add_unit(
    context: TreeBuildContext,
    *,
    unit_kind: M31UnitKind,
    visual_kind: str,
    bbox: list[int],
    bbox_derivation: str,
    primitive_refs: list[PrimitiveRef],
    root_child: bool,
) -> dict[str, Any]:
    clamped = bbox_clamp(bbox, context.pixels.width, context.pixels.height)
    if clamped is None or not primitive_refs:
        add_review_bucket(context, "insufficient_geometry", primitive_refs)
        raise ValueError("M31 unit bbox is invalid.")
    context.unit_index += 1
    unit_id = f"unit_{context.unit_index:04d}"
    asset_id = f"m31_unit_fallback_{context.unit_index:04d}"
    asset_path = Path("m31_unit_fallback_assets") / f"{unit_id}.png"
    full_asset_path = context.output_dir / asset_path
    full_asset_path.parent.mkdir(parents=True, exist_ok=True)
    full_asset_path.write_bytes(crop_png(context.source_png, PngRegion(unit_id, clamped[0], clamped[1], clamped[2], clamped[3])))

    source_refs = unit_source_refs(primitive_refs)
    unit = {
        "id": unit_id,
        "kind": "reconstruction_unit",
        "unitKind": unit_kind,
        "visualKind": visual_kind,
        "bbox": clamped,
        "bboxDerivation": bbox_derivation,
        "children": [ref.id for ref in primitive_refs],
        "fallback": {
            "assetId": asset_id,
            "cropBBox": clamped,
            "visible": True,
        },
        "sourceRefs": source_refs,
        "reconstruction": {
            "mode": "fallback_plus_planned_editable_overlays",
            "status": "planned",
            "risk": unit_risk(primitive_refs),
        },
        "semantic": {
            "role": None,
            "confidence": 0,
        },
    }
    context.nodes.append(unit)
    context.assets.append(
        {
            "id": asset_id,
            "kind": "unit_fallback",
            "path": str(asset_path),
            "bbox": clamped,
            "source": "source_png_crop",
        }
    )
    for ref in primitive_refs:
        ref.owner_unit_id = unit_id
    if root_child:
        context.root_children.append(unit_id)
    return unit


def add_review_bucket(context: TreeBuildContext, reason: str, primitive_refs: list[PrimitiveRef]) -> None:
    if reason not in ALLOWED_REVIEW_REASONS:
        raise ValueError(f"M31 review reason is not allowed: {reason}")
    if not primitive_refs:
        return
    context.bucket_index += 1
    bucket_id = f"review_bucket_{context.bucket_index:04d}"
    for ref in primitive_refs:
        if ref.owner_unit_id is None:
            ref.review_bucket_id = bucket_id
    bucket = {
        "id": bucket_id,
        "kind": "review_bucket",
        "visualKind": "unknown",
        "reason": reason,
        "children": [ref.id for ref in primitive_refs],
        "sourceRefs": unit_source_refs(primitive_refs),
    }
    context.review_buckets.append(bucket)


def build_tree_document(
    *,
    source_image: str,
    source_ocr_json: str,
    source_m29_nodes_json: str,
    width: int,
    height: int,
    context: TreeBuildContext,
) -> dict[str, Any]:
    primitive_refs = [ref.to_dict() for ref in context.primitive_refs]
    return {
        "schemaName": "M31ReconstructionUiTree",
        "schemaVersion": "0.1",
        "sourceImage": source_image,
        "sourceOcrJson": source_ocr_json,
        "sourceM29NodesJson": source_m29_nodes_json,
        "imageSize": {"width": width, "height": height},
        "root": {"id": "page", "kind": "page", "bbox": [0, 0, width, height], "children": list(context.root_children)},
        "nodes": list(context.nodes),
        "primitiveRefs": primitive_refs,
        "reviewBuckets": list(context.review_buckets),
        "assets": list(context.assets),
        "meta": {
            "notes": "m31_reconstruction_ui_tree_from_primitive_evidence",
            "inputPolicy": "source_png_ocr_and_m29_nodes_only",
            "doesNotModifyM29": True,
        },
    }


def build_report(tree: dict[str, Any], ocr_boxes: list[OcrTextBox], context: TreeBuildContext, output_dir: Path) -> dict[str, Any]:
    primitive_refs = [ref.to_dict() for ref in context.primitive_refs]
    units = [node for node in tree["nodes"] if node.get("kind") == "reconstruction_unit"]
    repeated_groups = [node for node in tree["nodes"] if node.get("kind") == "repeated_group"]
    owned_count = sum(1 for ref in primitive_refs if ref.get("ownerUnitId"))
    orphan_count = sum(1 for ref in primitive_refs if not ref.get("ownerUnitId") and not ref.get("reviewBucketId"))
    fallback_count = sum(1 for unit in units if isinstance(unit.get("fallback"), dict) and unit["fallback"].get("assetId"))
    forbidden_hits = find_m31_forbidden_terms(json.dumps(forbidden_check_payload(tree, context.review_buckets), ensure_ascii=False).lower())
    unit_fallback_coverage = 1.0 if not units else round(fallback_count / len(units), 4)
    summary = {
        "m29NodeCount": len(context.source_nodes),
        "ocrTextBoxCount": len(ocr_boxes),
        "primitiveRefCount": len(primitive_refs),
        "regionCount": sum(1 for node in tree["nodes"] if node.get("kind") == "region"),
        "unitCount": len(units),
        "repeatedGroupCount": len(repeated_groups),
        "reviewBucketCount": len(context.review_buckets),
        "ownedPrimitiveCount": owned_count,
        "orphanPrimitiveCount": orphan_count,
        "primitiveOwnershipRate": round(owned_count / max(1, len(primitive_refs)), 4),
        "rootLeafPrimitiveCount": sum(1 for child_id in tree["root"]["children"] if child_id in {ref["id"] for ref in primitive_refs}),
        "unitFallbackCount": fallback_count,
        "unitFallbackCoverage": unit_fallback_coverage,
        "createdDetectionBBoxCount": 0,
        "permissionViolationCount": 0,
        "forbiddenHitCount": len(forbidden_hits),
    }
    return {
        "schemaName": "M31ReconstructionUiTreeReport",
        "schemaVersion": "0.1",
        "sourceImage": tree["sourceImage"],
        "sourceOcrJson": tree["sourceOcrJson"],
        "sourceM29NodesJson": tree["sourceM29NodesJson"],
        "outputTree": str((output_dir / "m31_reconstruction_tree.json").resolve()),
        "summary": summary,
        "unitSummaries": [
            {
                "id": unit["id"],
                "visualKind": unit["visualKind"],
                "bbox": unit["bbox"],
                "primitiveRefCount": len(unit["children"]),
                "fallbackAssetId": unit["fallback"]["assetId"],
            }
            for unit in units
        ],
        "reviewBuckets": list(context.review_buckets),
        "skippedItems": [],
        "warnings": list(context.warnings),
        "forbiddenTermCheck": {"hits": forbidden_hits, "checkedScope": "m31_structural_contract_terms"},
        "meta": {
            "notes": "m31_script_only_diagnostic",
            "primaryInputs": ["source_png", "ocr_json", "m29_nodes_json"],
            "excludedPrimaryInputs": ["m2902", "m2903", "m2904", "m2905", "m30_dsl"],
        },
    }


def validate_m31_result(tree: dict[str, Any], report: dict[str, Any]) -> None:
    summary = report["summary"]
    if tree.get("schemaName") != "M31ReconstructionUiTree":
        raise ValueError("M31 tree schemaName is invalid.")
    if report.get("schemaName") != "M31ReconstructionUiTreeReport":
        raise ValueError("M31 report schemaName is invalid.")
    if summary["createdDetectionBBoxCount"] != 0:
        raise ValueError("M31 must not create detection bboxes.")
    if summary["permissionViolationCount"] != 0:
        raise ValueError("M31 permission violation count must be zero.")
    if summary["rootLeafPrimitiveCount"] != 0:
        raise ValueError("M31 root must not contain primitive leaves.")
    if summary["unitCount"] and summary["unitFallbackCoverage"] != 1.0:
        raise ValueError("Every M31 reconstruction unit must have fallback coverage.")
    if summary["orphanPrimitiveCount"] != 0:
        raise ValueError("Every M31 primitive ref must be owned or assigned to a review bucket.")
    if summary["forbiddenHitCount"] != 0:
        raise ValueError("M31 forbidden contract terms detected.")


def parse_ocr_boxes(document: dict[str, Any]) -> list[OcrTextBox]:
    boxes: list[OcrTextBox] = []
    for index, block in enumerate(list_dicts(document.get("blocks"))):
        bbox = parse_bbox(block.get("bbox"))
        text = str(block.get("text") or "").strip()
        if bbox is None or not text:
            continue
        boxes.append(
            OcrTextBox(
                id=str(block.get("id") or f"ocr_text_{index + 1:03d}"),
                text=text,
                bbox=bbox,
                confidence=clamp_float(block.get("confidence", 1.0), 0, 1),
            )
        )
    return boxes


def build_primitive_refs(m29_document: dict[str, Any], ocr_boxes: list[OcrTextBox], image_width: int, image_height: int) -> tuple[list[PrimitiveRef], list[str]]:
    refs: list[PrimitiveRef] = []
    warnings: list[str] = []
    seen_source_ids: set[str] = set()
    matched_ocr_ids: set[str] = set()
    for index, node in enumerate(list_dicts(m29_document.get("nodes"))):
        raw_id = str(node.get("id") or f"m29_node_{index + 1:04d}")
        source_id = raw_id
        duplicate_source = source_id in seen_source_ids
        if duplicate_source:
            warnings.append(f"duplicate_source:{source_id}")
        seen_source_ids.add(source_id)
        bbox = parse_bbox(node.get("bbox")) or [0, 0, 0, 0]
        matched_ocr = match_ocr_box(node, bbox, ocr_boxes) if node.get("type") == "text" else None
        source_refs: dict[str, Any] = {"m29NodeId": source_id}
        if duplicate_source:
            source_refs["duplicateSource"] = True
        if matched_ocr is not None:
            source_refs["ocrTextBoxId"] = matched_ocr.id
            matched_ocr_ids.add(matched_ocr.id)
        if not bbox_in_bounds(bbox, image_width, image_height):
            warnings.append(f"out_of_bounds:{source_id}")
        refs.append(
            PrimitiveRef(
                id=f"prim_ref_{index + 1:04d}",
                source_kind="m29_node",
                source_id=source_id,
                source_order=int(node.get("sourceOrder", index) or index),
                primitive_type=str(node.get("type") or "unknown"),
                primitive_subtype=str(node.get("subtype") or "unknown"),
                bbox=bbox,
                confidence=clamp_float(node.get("confidence", 1.0), 0, 1),
                layer_hint=str(node.get("layerHint") or "unknown"),
                text=str(node.get("text")) if node.get("text") is not None else None,
                source_refs=source_refs,
            )
        )
    for box in ocr_boxes:
        if box.id in matched_ocr_ids:
            continue
        duplicate_source = box.id in seen_source_ids
        if duplicate_source:
            warnings.append(f"duplicate_source:{box.id}")
        seen_source_ids.add(box.id)
        source_refs = {"ocrTextBoxId": box.id}
        if duplicate_source:
            source_refs["duplicateSource"] = True
        if not bbox_in_bounds(box.bbox, image_width, image_height):
            warnings.append(f"out_of_bounds:{box.id}")
        refs.append(
            PrimitiveRef(
                id=f"prim_ref_{len(refs) + 1:04d}",
                source_kind="ocr_text_box",
                source_id=box.id,
                source_order=len(refs),
                primitive_type="text",
                primitive_subtype="line",
                bbox=box.bbox,
                confidence=box.confidence,
                layer_hint="content",
                text=box.text,
                source_refs=source_refs,
            )
        )
    return refs, warnings


def match_ocr_box(node: dict[str, Any], bbox: list[int], boxes: list[OcrTextBox]) -> OcrTextBox | None:
    if not boxes:
        return None
    text = str(node.get("text") or "").strip()
    ranked = sorted(
        boxes,
        key=lambda box: (
            text_match_score(text, box.text),
            bbox_iou(bbox, box.bbox),
            bbox_overlap_ratio(bbox, box.bbox),
        ),
        reverse=True,
    )
    best = ranked[0]
    if text_match_score(text, best.text) > 0 and bbox_intersects(bbox, best.bbox):
        return best
    if bbox_iou(bbox, best.bbox) >= 0.45 or bbox_overlap_ratio(bbox, best.bbox) >= 0.72:
        return best
    return None


def text_match_score(left: str, right: str) -> int:
    return 1 if left.strip() and left.strip() == right.strip() else 0


def bbox_overlap_ratio(left: list[int], right: list[int]) -> float:
    if not bbox_intersects(left, right):
        return 0.0
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(bbox_x2(left), bbox_x2(right))
    y2 = min(bbox_y2(left), bbox_y2(right))
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    return intersection / max(1, min(bbox_area(left), bbox_area(right)))


def refs_by_source_id(refs: list[PrimitiveRef]) -> dict[str, PrimitiveRef]:
    result: dict[str, PrimitiveRef] = {}
    for ref in refs:
        result.setdefault(ref.source_id, ref)
    return result


def unassigned_refs(context: TreeBuildContext) -> list[PrimitiveRef]:
    return [ref for ref in context.primitive_refs if ref.owner_unit_id is None and ref.review_bucket_id is None]


def is_container_candidate(node: dict[str, Any]) -> bool:
    return (
        node.get("type") == "shape"
        and (node.get("layerHint") == "container" or str(node.get("subtype") or "") in CONTAINER_SUBTYPES)
    )


def row_compatible(cluster: list[PrimitiveRef], ref: PrimitiveRef) -> bool:
    cluster_bbox = union_bbox([item.bbox for item in cluster])
    y_overlap = min(bbox_y2(cluster_bbox), bbox_y2(ref.bbox)) - max(cluster_bbox[1], ref.bbox[1])
    if y_overlap <= 0:
        return abs(center_y(cluster_bbox) - center_y(ref.bbox)) <= max(8, max(cluster_bbox[3], ref.bbox[3]) * 0.45)
    return (y_overlap / max(1, min(cluster_bbox[3], ref.bbox[3]))) >= 0.35


def too_spread_out(cluster: list[PrimitiveRef], image_width: int) -> bool:
    sorted_cluster = sorted(cluster, key=lambda item: item.bbox[0])
    max_gap = max((sorted_cluster[index + 1].bbox[0] - bbox_x2(sorted_cluster[index].bbox)) for index in range(len(sorted_cluster) - 1))
    return max_gap > max(96, image_width * 0.28)


def classify_cluster_visual_kind(cluster: list[PrimitiveRef]) -> str:
    types = {ref.primitive_type for ref in cluster}
    if "text" in types and ({"image", "symbol"} & types):
        return "media_text_block"
    if types == {"text"}:
        return "text_block"
    if "shape" in types and "text" in types:
        return "control_cluster"
    return "row"


def single_visual_kind(ref: PrimitiveRef) -> str:
    if ref.primitive_type == "text":
        return "text_block"
    if ref.primitive_type == "shape" and ref.layer_hint == "container":
        return "container"
    if ref.primitive_type == "image":
        return "media_panel"
    if ref.primitive_type == "symbol":
        return "control_cluster"
    return "unknown"


def similar_size(left: list[int], right: list[int]) -> bool:
    width_delta = abs(left[2] - right[2]) / max(1, max(left[2], right[2]))
    height_delta = abs(left[3] - right[3]) / max(1, max(left[3], right[3]))
    return width_delta <= 0.18 and height_delta <= 0.18


def regular_spacing(refs: list[PrimitiveRef]) -> bool:
    if len(refs) < 3:
        return False
    gaps = [refs[index + 1].bbox[0] - bbox_x2(refs[index].bbox) for index in range(len(refs) - 1)]
    if any(gap < 0 for gap in gaps):
        return False
    average = sum(gaps) / len(gaps)
    return all(abs(gap - average) <= max(6, average * 0.25) for gap in gaps)


def unit_source_refs(refs: list[PrimitiveRef]) -> dict[str, list[str]]:
    ocr_ids = [str(ref.source_refs["ocrTextBoxId"]) for ref in refs if ref.source_refs.get("ocrTextBoxId")]
    return {
        "m29NodeIds": [ref.source_id for ref in refs if ref.source_kind == "m29_node"],
        "ocrTextBoxIds": ocr_ids,
        "blockedEvidenceIds": [],
    }


def unit_risk(refs: list[PrimitiveRef]) -> str:
    if any(ref.review_bucket_id for ref in refs):
        return "high"
    if len(refs) == 1:
        return "low"
    return "medium"


def source_order(node: dict[str, Any]) -> int:
    try:
        return int(node.get("sourceOrder", 0) or 0)
    except (TypeError, ValueError):
        return 0


def center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2


def union_bbox(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def parse_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [round(float(item)) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def forbidden_check_payload(tree: dict[str, Any], review_buckets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "nodeContracts": [
            {
                "kind": node.get("kind"),
                "unitKind": node.get("unitKind"),
                "visualKind": node.get("visualKind"),
                "bboxDerivation": node.get("bboxDerivation"),
                "reconstruction": node.get("reconstruction"),
            }
            for node in tree.get("nodes", [])
            if isinstance(node, dict)
        ],
        "reviewReasons": [bucket.get("reason") for bucket in review_buckets],
        "meta": tree.get("meta", {}),
    }


def find_m31_forbidden_terms(text: str) -> list[str]:
    hits: list[str] = []
    for term in sorted(FORBIDDEN_M31_TERMS):
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text):
            hits.append(term)
    return hits


def build_overlay(pixels: PngPixels, tree: dict[str, Any], review_buckets: list[dict[str, Any]]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for node in tree.get("nodes", []):
        if isinstance(node, dict) and node.get("kind") == "reconstruction_unit":
            draw_rect(rows, pixels.width, pixels.height, node.get("bbox", []), (0, 122, 255), 2)
    primitive_by_id = {ref.get("id"): ref for ref in tree.get("primitiveRefs", []) if isinstance(ref, dict)}
    for bucket in review_buckets:
        for child_id in bucket.get("children", []):
            ref = primitive_by_id.get(child_id)
            if ref:
                draw_rect(rows, pixels.width, pixels.height, ref.get("bbox", []), (235, 64, 52), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def draw_rect(rows: list[bytearray], image_width: int, image_height: int, bbox: list[int], color: tuple[int, int, int], thickness: int) -> None:
    clamped = bbox_clamp(bbox, image_width, image_height)
    if clamped is None:
        return
    x, y, width, height = clamped
    color_bytes = bytes(color)
    for row_index in range(y, y + height):
        if row_index < y + thickness or row_index >= y + height - thickness:
            for column in range(x, x + width):
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes
        else:
            for column in list(range(x, min(x + thickness, x + width))) + list(range(max(x, x + width - thickness), x + width)):
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes
