from __future__ import annotations

from ..visual_primitive_graph import bbox_area, bbox_iou
from .types import M292SourceObject


def dedupe_objects(objects: list[M292SourceObject], threshold: float) -> list[M292SourceObject]:
    priority = {
        "text_replay": 5,
        "image_replay": 4,
        "icon_replay": 3,
        "shape_replay": 2,
        "preserve_in_parent_raster": 1,
        "skip": 0,
    }
    kept: list[M292SourceObject] = []
    for item in sorted(objects, key=lambda obj: (-priority[obj.replay_decision], obj.bbox[1], obj.bbox[0], -bbox_area(obj.bbox))):
        duplicate_index = next((index for index, kept_item in enumerate(kept) if bbox_iou(item.bbox, kept_item.bbox) >= threshold), None)
        if duplicate_index is None:
            kept.append(item)
            continue
        existing = kept[duplicate_index]
        if priority[item.replay_decision] > priority[existing.replay_decision]:
            kept[duplicate_index] = item
    return sorted(rename_objects(kept), key=lambda obj: (obj.bbox[1], obj.bbox[0], bbox_area(obj.bbox)))


def rename_objects(objects: list[M292SourceObject]) -> list[M292SourceObject]:
    return [
        M292SourceObject(
            id=f"m292_object_{index + 1:04d}",
            bbox=item.bbox,
            visual_kind=item.visual_kind,
            pixel_owner=item.pixel_owner,
            replay_decision=item.replay_decision,
            source_evidence=item.source_evidence,
            confidence=item.confidence,
            reasons=item.reasons,
            risks=item.risks,
        )
        for index, item in enumerate(objects)
    ]
