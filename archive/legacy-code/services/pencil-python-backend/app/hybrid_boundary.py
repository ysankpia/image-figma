from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image


class HybridBoundaryError(RuntimeError):
    pass


def build_hybrid_boundary_artifact(
    *,
    psdlike_dir: Path,
    m29_dir: Path,
    output_dir: Path,
) -> Path:
    psdlike_dir = psdlike_dir.expanduser().resolve()
    m29_dir = m29_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(psdlike_dir, output_dir)

    layer_stack_path = output_dir / "layer_stack.v1.json"
    m29_evidence_path = m29_dir / "m29_physical_evidence.v1.json"
    if not layer_stack_path.exists():
        raise HybridBoundaryError(f"Missing PSD-like layer stack: {layer_stack_path}")
    if not m29_evidence_path.exists():
        raise HybridBoundaryError(f"Missing M29 evidence: {m29_evidence_path}")

    layer_stack = read_json(layer_stack_path)
    m29_evidence = read_json(m29_evidence_path)
    source_path = output_dir / "source.png"
    if not source_path.exists():
        source_path = resolve_source_path(layer_stack)
    if source_path is None or not source_path.exists():
        raise HybridBoundaryError("Hybrid boundary needs a source image")

    added_layers = make_fallback_layers(
        layer_stack=layer_stack,
        m29_evidence=m29_evidence,
        output_dir=output_dir,
        source_path=source_path,
    )
    if added_layers:
        layer_stack["layers"] = sorted((layer_stack.get("layers") or []) + added_layers, key=lambda item: item.get("z", 0))
    diagnostics = layer_stack.setdefault("diagnostics", {})
    diagnostics["boundarySource"] = "hybrid"
    diagnostics["hybridFallbackLayerCount"] = len(added_layers)
    diagnostics["hybridFallbackPolicy"] = "psdlike_primary_m29_low_coverage_v1"
    diagnostics["hybridM29PrimitiveCount"] = len(m29_evidence.get("primitives") or [])
    layer_stack["version"] = "layer_stack.hybrid.v1"
    write_json(layer_stack_path, layer_stack)

    report = {
        "schema": "pencil.hybrid_boundary_report.v1",
        "policy": diagnostics["hybridFallbackPolicy"],
        "fallbackLayerCount": len(added_layers),
        "fallbackLayers": [
            {
                "id": item["id"],
                "bbox": item["bbox"],
                "sourcePrimitiveIds": item.get("sourcePrimitiveIds", []),
                "reason": item.get("reason"),
                "asset": item.get("asset"),
            }
            for item in added_layers
        ],
    }
    write_json(output_dir / "hybrid_boundary_report.v1.json", report)
    return output_dir


def make_fallback_layers(
    *,
    layer_stack: dict[str, Any],
    m29_evidence: dict[str, Any],
    output_dir: Path,
    source_path: Path,
) -> list[dict[str, Any]]:
    canvas = layer_stack.get("canvas") or m29_evidence.get("image") or {}
    canvas_width = int(canvas.get("width") or 0)
    canvas_height = int(canvas.get("height") or 0)
    if canvas_width <= 0 or canvas_height <= 0:
        return []

    psd_visual_layers = [
        item
        for item in layer_stack.get("layers") or []
        if is_psd_coverage_layer(item, canvas_width, canvas_height)
    ]
    psd_text_layers = [
        item
        for item in layer_stack.get("layers") or []
        if item.get("type") == "text"
    ]
    candidates = [
        primitive
        for primitive in m29_evidence.get("primitives") or []
        if is_m29_fallback_candidate(primitive, psd_visual_layers, psd_text_layers, canvas_width, canvas_height)
    ]
    clusters = cluster_candidates(candidates, canvas_width, canvas_height)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    fallback_layers: list[dict[str, Any]] = []
    with Image.open(source_path) as source_image:
        source = source_image.convert("RGBA")
        for index, cluster in enumerate(clusters, start=1):
            bbox = expand_bbox(union_bbox([item["bbox"] for item in cluster]), 2, canvas_width, canvas_height)
            if not valid_cluster_bbox(bbox, canvas_width, canvas_height):
                continue
            asset_name = f"hybrid_m29_{index:04d}.png"
            source.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"])).save(assets_dir / asset_name)
            fallback_layers.append(
                {
                    "id": f"hybrid_m29_{index:04d}",
                    "type": "raster",
                    "bbox": bbox,
                    "z": fallback_z(index, layer_stack),
                    "asset": f"assets/{asset_name}",
                    "scores": {
                        "coverageByPsd": round(max(coverage_by_layers(item["bbox"], psd_visual_layers) for item in cluster), 4),
                        "textOverlap": round(max(coverage_by_layers(item["bbox"], psd_text_layers) for item in cluster), 4),
                    },
                    "ownership": {},
                    "reason": "m29_low_coverage_fallback_object",
                    "source": "hybrid_boundary",
                    "sourcePrimitiveIds": [str(item.get("id")) for item in cluster],
                    "sourceRoles": [str(item.get("primitiveType")) for item in cluster],
                }
            )
    return fallback_layers


def is_psd_coverage_layer(layer: dict[str, Any], canvas_width: int, canvas_height: int) -> bool:
    layer_type = str(layer.get("type") or "")
    if layer_type == "raster":
        return True
    if layer_type != "shape":
        return False
    bbox = normalize_bbox(layer.get("bbox") or {})
    area = area_of(bbox)
    canvas_area = max(1, canvas_width * canvas_height)
    if area <= 0:
        return False
    if area >= canvas_area * 0.18:
        return False
    if bbox["width"] > canvas_width * 0.72 and bbox["height"] < canvas_height * 0.18:
        return False
    if bbox["height"] > canvas_height * 0.55 and bbox["width"] < canvas_width * 0.22:
        return False
    reason = str(layer.get("reason") or "")
    if "background" in reason or "container" in reason:
        return False
    return True


def is_m29_fallback_candidate(
    primitive: dict[str, Any],
    psd_visual_layers: list[dict[str, Any]],
    psd_text_layers: list[dict[str, Any]],
    canvas_width: int,
    canvas_height: int,
) -> bool:
    role = str(primitive.get("primitiveType") or "")
    if role not in {"symbol_region", "image_region", "unknown_region", "rect", "line"}:
        return False
    bbox = normalize_bbox(primitive.get("bbox") or {})
    area = area_of(bbox)
    canvas_area = max(1, canvas_width * canvas_height)
    if area < 80 or area > min(25_000, canvas_area * 0.035):
        return False
    if bbox["width"] > canvas_width * 0.5 or bbox["height"] > canvas_height * 0.12:
        return False
    psd_coverage = coverage_by_layers(bbox, psd_visual_layers)
    if psd_coverage >= 0.35:
        return False
    text_overlap = coverage_by_layers(bbox, psd_text_layers)
    if text_overlap >= 0.72:
        return False
    if text_overlap >= 0.45 and not looks_like_pill(bbox):
        return False
    return True


def fallback_z(index: int, layer_stack: dict[str, Any]) -> int:
    layers = layer_stack.get("layers") or []
    non_text_values = [int(item.get("z") or 0) for item in layers if item.get("type") != "text"]
    text_values = [int(item.get("z") or 0) for item in layers if item.get("type") == "text"]
    non_text_max = max(non_text_values) if non_text_values else 0
    z = non_text_max + index
    if text_values:
        text_min = min(text_values)
        if z >= text_min:
            z = max(0, text_min - 1)
    return z


def looks_like_pill(bbox: dict[str, int]) -> bool:
    width = max(1, bbox["width"])
    height = max(1, bbox["height"])
    ratio = width / height
    area = width * height
    return 1.5 <= ratio <= 4.8 and 900 <= area <= 8_000


def cluster_candidates(candidates: list[dict[str, Any]], canvas_width: int, canvas_height: int) -> list[list[dict[str, Any]]]:
    if not candidates:
        return []
    radius = max(2, min(8, round(min(canvas_width, canvas_height) / 250)))
    remaining = {str(item.get("id")): item for item in candidates}
    clusters: list[list[dict[str, Any]]] = []
    while remaining:
        _, first = remaining.popitem()
        cluster = [first]
        changed = True
        while changed:
            changed = False
            cluster_bbox = union_bbox([item["bbox"] for item in cluster])
            for key, item in list(remaining.items()):
                if bbox_distance(cluster_bbox, normalize_bbox(item.get("bbox") or {})) <= radius:
                    test_bbox = union_bbox([cluster_bbox, normalize_bbox(item.get("bbox") or {})])
                    if valid_cluster_bbox(test_bbox, canvas_width, canvas_height):
                        cluster.append(item)
                        remaining.pop(key)
                        changed = True
        clusters.append(sorted(cluster, key=lambda item: str(item.get("id"))))
    return sorted(clusters, key=lambda items: (union_bbox([item["bbox"] for item in items])["y"], union_bbox([item["bbox"] for item in items])["x"]))


def valid_cluster_bbox(bbox: dict[str, int], canvas_width: int, canvas_height: int) -> bool:
    area = area_of(bbox)
    canvas_area = max(1, canvas_width * canvas_height)
    if area < 80 or area > min(36_000, canvas_area * 0.045):
        return False
    if bbox["width"] > canvas_width * 0.55 and bbox["height"] < canvas_height * 0.12:
        return False
    if bbox["height"] > canvas_height * 0.35 and bbox["width"] < canvas_width * 0.16:
        return False
    return True


def coverage_by_layers(bbox: dict[str, int], layers: list[dict[str, Any]]) -> float:
    bbox_area = area_of(bbox)
    if bbox_area <= 0:
        return 0.0
    covered = 0
    for layer in layers:
        covered += intersection_area(bbox, normalize_bbox(layer.get("bbox") or {}))
    return min(1.0, covered / bbox_area)


def union_bbox(boxes: list[dict[str, Any]]) -> dict[str, int]:
    normalized = [normalize_bbox(box) for box in boxes]
    x1 = min(box["x"] for box in normalized)
    y1 = min(box["y"] for box in normalized)
    x2 = max(box["x"] + box["width"] for box in normalized)
    y2 = max(box["y"] + box["height"] for box in normalized)
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def expand_bbox(bbox: dict[str, int], px: int, canvas_width: int, canvas_height: int) -> dict[str, int]:
    x1 = max(0, bbox["x"] - px)
    y1 = max(0, bbox["y"] - px)
    x2 = min(canvas_width, bbox["x"] + bbox["width"] + px)
    y2 = min(canvas_height, bbox["y"] + bbox["height"] + px)
    return {"x": x1, "y": y1, "width": max(1, x2 - x1), "height": max(1, y2 - y1)}


def normalize_bbox(raw: dict[str, Any]) -> dict[str, int]:
    x = int(round(float(raw.get("x") or 0)))
    y = int(round(float(raw.get("y") or 0)))
    width = max(1, int(round(float(raw.get("width") or 0))))
    height = max(1, int(round(float(raw.get("height") or 0))))
    return {"x": x, "y": y, "width": width, "height": height}


def area_of(bbox: dict[str, int]) -> int:
    return max(0, int(bbox["width"])) * max(0, int(bbox["height"]))


def intersection_area(a: dict[str, int], b: dict[str, int]) -> int:
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["width"], b["x"] + b["width"])
    y2 = min(a["y"] + a["height"], b["y"] + b["height"])
    return max(0, x2 - x1) * max(0, y2 - y1)


def bbox_distance(a: dict[str, int], b: dict[str, int]) -> int:
    ax2 = a["x"] + a["width"]
    ay2 = a["y"] + a["height"]
    bx2 = b["x"] + b["width"]
    by2 = b["y"] + b["height"]
    dx = max(b["x"] - ax2, a["x"] - bx2, 0)
    dy = max(b["y"] - ay2, a["y"] - by2, 0)
    return max(dx, dy)


def resolve_source_path(layer_stack: dict[str, Any]) -> Path | None:
    value = layer_stack.get("sourceImage")
    if isinstance(value, str) and value:
        return Path(value).expanduser().resolve()
    return None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
