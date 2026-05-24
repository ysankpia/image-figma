from __future__ import annotations


def bbox_union(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox[0] + bbox[2] for bbox in bboxes)
    y2 = max(bbox[1] + bbox[3] for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def group_sort_key(group: dict) -> tuple[int, int, int, str]:
    bbox = group["bbox"]
    return bbox[1], bbox[0], -len(group["memberSourceObjectIds"]), group["id"]
