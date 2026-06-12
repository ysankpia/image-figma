from __future__ import annotations

from .omniparser import Detection
from .schema import BBox, CandidateBatch, ObjectCandidate, TextBlock
from .spatial import clamp_bbox, intersection_area, iou, union_bbox


def build_candidates(
    detections: list[Detection],
    texts: list[TextBlock],
    page_width: int,
    page_height: int,
    min_area: int = 64,
    dedupe_iou: float = 0.75,
) -> list[ObjectCandidate]:
    normalized: list[tuple[BBox, float]] = []
    for detection in detections:
        box = clamp_bbox(
            BBox(detection.x, detection.y, detection.width, detection.height),
            page_width,
            page_height,
        )
        if box is None or box.width < 4 or box.height < 4 or box.area < min_area:
            continue
        normalized.append((box, detection.confidence))

    normalized.sort(key=lambda item: (-item[1], -item[0].area, item[0].y, item[0].x))
    kept: list[tuple[BBox, float]] = []
    for box, confidence in normalized:
        if any(iou(box, existing) > dedupe_iou for existing, _ in kept):
            continue
        kept.append((box, confidence))

    kept.sort(key=lambda item: (item[0].y, item[0].x, item[0].height, item[0].width))
    out: list[ObjectCandidate] = []
    for index, (box, confidence) in enumerate(kept, start=1):
        overlap_area = sum(intersection_area(box, text.bbox) for text in texts)
        text_count = sum(1 for text in texts if intersection_area(box, text.bbox) > 0)
        ratio = overlap_area / box.area if box.area > 0 else 0.0
        out.append(
            ObjectCandidate(
                id=f"cand_{index:04d}",
                bbox=box,
                confidence=confidence,
                area=box.area,
                overlaps_text=ratio > 0,
                text_overlap_ratio=round(ratio, 4),
                text_block_count=text_count,
            )
        )
    return out


def build_candidate_batches(
    candidates: list[ObjectCandidate],
    page_width: int,
    page_height: int,
    hard_cap: int = 25,
    window_height: int = 640,
    overlap: int = 80,
) -> list[CandidateBatch]:
    if not candidates:
        return []
    bands = split_by_vertical_gaps(candidates)
    batches: list[list[ObjectCandidate]] = []
    for band in bands:
        if len(band) <= hard_cap and union_bbox([item.bbox for item in band]).height <= window_height:
            batches.append(band)
            continue
        batches.extend(split_band_by_windows(band, page_height, hard_cap, window_height, overlap))

    out: list[CandidateBatch] = []
    for index, batch in enumerate(batches, start=1):
        box = union_bbox([item.bbox for item in batch])
        padded = clamp_bbox(
            BBox(box.x - 24, box.y - 24, box.width + 48, box.height + 48),
            page_width,
            page_height,
        ) or box
        out.append(
            CandidateBatch(
                id=f"batch_{index:04d}",
                bbox=padded,
                candidate_ids=[item.id for item in sorted(batch, key=lambda c: (c.bbox.y, c.bbox.x, c.id))],
            )
        )
    return out


def split_by_vertical_gaps(candidates: list[ObjectCandidate]) -> list[list[ObjectCandidate]]:
    items = sorted(candidates, key=lambda item: (item.bbox.y, item.bbox.x))
    bands: list[list[ObjectCandidate]] = []
    current: list[ObjectCandidate] = []
    current_bottom = 0
    for item in items:
        if not current:
            current = [item]
            current_bottom = item.bbox.y2
            continue
        gap = item.bbox.y - current_bottom
        if gap >= max(96, min(180, item.bbox.height * 2)):
            bands.append(current)
            current = [item]
            current_bottom = item.bbox.y2
            continue
        current.append(item)
        current_bottom = max(current_bottom, item.bbox.y2)
    if current:
        bands.append(current)
    return bands


def split_band_by_windows(
    band: list[ObjectCandidate],
    page_height: int,
    hard_cap: int,
    window_height: int,
    overlap: int,
) -> list[list[ObjectCandidate]]:
    if not band:
        return []
    items = sorted(band, key=lambda item: (item.bbox.y, item.bbox.x))
    out: list[list[ObjectCandidate]] = []
    current: list[ObjectCandidate] = []
    window_start = items[0].bbox.y
    window_end = min(page_height, window_start + window_height)
    for item in items:
        outside_window = item.bbox.y >= window_end and current
        over_cap = len(current) >= hard_cap
        if outside_window or over_cap:
            out.append(current)
            window_start = max(0, item.bbox.y - overlap)
            window_end = min(page_height, window_start + window_height)
            current = []
        current.append(item)
    if current:
        out.append(current)
    return out
