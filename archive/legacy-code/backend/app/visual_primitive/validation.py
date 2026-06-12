from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import read_png_metadata
from .bbox import bbox_in_bounds
from .types import M29_BLOCKED_EVIDENCE_VERSION, M29BlockedPrimitive, M29PrimitiveNode, M29VisualPrimitiveGraphDocument, M29VisualPrimitiveOptions


def validate_m29_document(document: M29VisualPrimitiveGraphDocument, output_dir: Path) -> None:
    if document.version != "0.1":
        raise ValueError("M29 document version must be 0.1")
    width = int(document.image_size.get("width", 0))
    height = int(document.image_size.get("height", 0))
    seen: set[str] = set()
    orders: set[int] = set()
    for node in document.nodes:
        if node.id in seen:
            raise ValueError(f"duplicate M29 node id: {node.id}")
        seen.add(node.id)
        if node.source_order in orders:
            raise ValueError(f"duplicate M29 source_order: {node.source_order}")
        orders.add(node.source_order)
        if not bbox_in_bounds(node.bbox, width, height):
            raise ValueError(f"M29 node bbox out of bounds: {node.id}")
        if node.asset_path is not None:
            assert_readable_relative_png(output_dir, node.asset_path)
        if node.mask_path is not None:
            assert_readable_relative_png(output_dir, node.mask_path)
    for relation in document.relations:
        if relation.parent_id not in seen or relation.child_id not in seen:
            raise ValueError("M29 relation references a missing node")
    for item in document.blocked:
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29 blocked bbox out of bounds: {item.id}")
        if item.metrics is None:
            raise ValueError(f"M29 blocked metrics missing: {item.id}")
        if not item.reasons:
            raise ValueError(f"M29 blocked reasons missing: {item.id}")
        if item.context is None:
            raise ValueError(f"M29 blocked context missing: {item.id}")
        validate_blocked_context(item)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)

def validate_blocked_context(item: M29BlockedPrimitive) -> None:
    context = item.context or {}
    required = {
        "area": int,
        "maxEdge": int,
        "textOverlapRatio": (int, float),
        "imageOverlapRatio": (int, float),
        "protectiveShapeOverlapRatio": (int, float),
        "insideImage": bool,
        "nearImage": bool,
        "nearProtectiveShape": bool,
    }
    for key, expected_type in required.items():
        if key not in context or not isinstance(context[key], expected_type):
            raise ValueError(f"M29 blocked context missing or invalid {key}: {item.id}")
    nearest_shape = context.get("nearestShapeId")
    if nearest_shape is not None and not isinstance(nearest_shape, str):
        raise ValueError(f"M29 blocked context nearestShapeId invalid: {item.id}")

def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29 PNG output missing or unreadable: {path}")

def build_meta(nodes: list[M29PrimitiveNode], blocked: list[M29BlockedPrimitive], options: M29VisualPrimitiveOptions) -> dict[str, Any]:
    counts = {"text": 0, "shape": 0, "image": 0, "symbol": 0, "unknown": 0, "blocked": len(blocked)}
    for node in nodes:
        counts[node.type] += 1
    reason_summary: dict[str, int] = {}
    for item in blocked:
        for reason in item.reasons:
            reason_summary[reason] = reason_summary.get(reason, 0) + 1
    return {
        "notes": "m29_visual_primitive_graph_harness",
        "blockedEvidenceVersion": M29_BLOCKED_EVIDENCE_VERSION,
        "counts": counts,
        "blockedReasonSummary": dict(sorted(reason_summary.items())),
        "options": options.to_dict(),
    }
