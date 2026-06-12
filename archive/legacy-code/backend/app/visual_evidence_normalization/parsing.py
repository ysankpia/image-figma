from __future__ import annotations

from ..visual_primitive_graph import M29PrimitiveMetrics
from .types import VisualEvidenceKind, VisualEvidenceOptions, VisualEvidenceSource


def parse_source(value: object) -> VisualEvidenceSource | None:
    if value in {"m29_image", "m29_unknown", "m29_symbol", "m29_shape", "m29_blocked", "m291_group", "after_text_mask_candidate"}:
        return value  # type: ignore[return-value]
    return None

def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(item) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox

def parse_metrics(value: object) -> M29PrimitiveMetrics:
    if not isinstance(value, dict):
        raise ValueError("M29.0.3 mediaEvidence item requires metrics")
    mean = value.get("meanRgb", value.get("mean_rgb", [0, 0, 0]))
    if not isinstance(mean, list) or len(mean) != 3:
        raise ValueError("M29.0.3 metrics require meanRgb")
    return M29PrimitiveMetrics(
        color_count=int(value.get("colorCount", value.get("color_count", 0))),
        texture_score=float(value.get("textureScore", value.get("texture_score", 0.0))),
        edge_score=float(value.get("edgeScore", value.get("edge_score", 0.0))),
        fill_ratio=float(value.get("fillRatio", value.get("fill_ratio", 0.0))),
        aspect_ratio=float(value.get("aspectRatio", value.get("aspect_ratio", 0.0))),
        brightness=float(value.get("brightness", 0.0)),
        mean_rgb=(int(mean[0]), int(mean[1]), int(mean[2])),
    )

def next_item_id(visual_kind: VisualEvidenceKind, counters: dict[str, int]) -> str:
    counters[visual_kind] = counters.get(visual_kind, 0) + 1
    return f"{visual_kind}_{counters[visual_kind]:03d}"

def media_candidate_confidence(metrics: M29PrimitiveMetrics, area: int, options: VisualEvidenceOptions) -> float:
    color_score = min(1.0, metrics.color_count / max(1, options.media_candidate_min_color_count * 2))
    texture_score = min(1.0, metrics.texture_score / max(0.001, options.media_candidate_min_texture_score * 2))
    area_score = min(1.0, area / max(1, options.media_candidate_min_area * 4))
    return 0.58 + 0.14 * color_score + 0.18 * texture_score + 0.10 * area_score
