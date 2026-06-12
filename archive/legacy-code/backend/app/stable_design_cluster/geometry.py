from __future__ import annotations


def node_sort_key(node: dict[str, Any]) -> tuple[int, int, str]:
    bbox = node["bbox"]
    return bbox[1], bbox[0], node["id"]


def cluster_sort_key(cluster: dict[str, Any]) -> tuple[int, int, int, str]:
    bbox = cluster["bbox"]
    return bbox[1], bbox[0], -len(cluster["memberNodeIds"]), str(cluster["clusterPattern"])


def size_signature(bbox: list[int]) -> str:
    width_bucket = round(bbox[2] / 8) * 8
    height_bucket = round(bbox[3] / 8) * 8
    return f"{width_bucket}x{height_bucket}"


def bbox_union(bboxes: list[list[int]]) -> list[int]:
    min_x = min(bbox[0] for bbox in bboxes)
    min_y = min(bbox[1] for bbox in bboxes)
    max_x = max(x2(bbox) for bbox in bboxes)
    max_y = max(y2(bbox) for bbox in bboxes)
    return [min_x, min_y, max_x - min_x, max_y - min_y]


def bbox_iou(left: list[int], right: list[int]) -> float:
    intersection = max(0, min(x2(left), x2(right)) - max(left[0], right[0])) * max(
        0,
        min(y2(left), y2(right)) - max(left[1], right[1]),
    )
    union = left[2] * left[3] + right[2] * right[3] - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def member_overlap_ratio(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / min(len(left_set), len(right_set))


def x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]
