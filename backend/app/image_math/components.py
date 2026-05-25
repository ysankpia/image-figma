from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from skimage.measure import label, regionprops

from .masks import ensure_bool_mask


@dataclass(frozen=True)
class ComponentMetric:
    component_id: int
    bbox: list[int]
    area: int
    centroid: tuple[float, float]
    fill_ratio: float

    def to_dict(self) -> dict[str, object]:
        return {
            "componentId": self.component_id,
            "bbox": self.bbox,
            "area": self.area,
            "centroid": [round(self.centroid[0], 4), round(self.centroid[1], 4)],
            "fillRatio": round(self.fill_ratio, 6),
        }


def label_components(mask: np.ndarray[Any, Any], *, connectivity: int = 1) -> np.ndarray[Any, np.dtype[np.int32]]:
    bool_mask = ensure_bool_mask(mask)
    if connectivity not in {1, 2}:
        raise ValueError("connectivity must be 1 or 2")
    return label(bool_mask, connectivity=connectivity).astype(np.int32, copy=False)


def component_metrics(mask: np.ndarray[Any, Any], *, min_area: int = 1, connectivity: int = 1) -> list[ComponentMetric]:
    if min_area < 1:
        raise ValueError("min_area must be positive")
    labels = label_components(mask, connectivity=connectivity)
    metrics: list[ComponentMetric] = []
    for region in regionprops(labels):
        area = int(region.area)
        if area < min_area:
            continue
        min_row, min_col, max_row, max_col = region.bbox
        width = int(max_col - min_col)
        height = int(max_row - min_row)
        bbox = [int(min_col), int(min_row), width, height]
        fill_ratio = area / max(1, width * height)
        metrics.append(
            ComponentMetric(
                component_id=int(region.label),
                bbox=bbox,
                area=area,
                centroid=(float(region.centroid[1]), float(region.centroid[0])),
                fill_ratio=fill_ratio,
            )
        )
    return metrics


def largest_component_area(mask: np.ndarray[Any, Any], *, connectivity: int = 1) -> int:
    metrics = component_metrics(mask, connectivity=connectivity)
    if not metrics:
        return 0
    return max(item.area for item in metrics)
