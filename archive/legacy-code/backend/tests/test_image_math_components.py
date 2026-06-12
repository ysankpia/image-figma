from __future__ import annotations

import numpy as np

from app.image_math.components import component_metrics, label_components, largest_component_area


def test_label_components_separates_four_connected_regions() -> None:
    mask = np.zeros((5, 7), dtype=bool)
    mask[1:3, 1:3] = True
    mask[1:4, 5] = True

    labels = label_components(mask)

    assert labels.max() == 2
    assert labels[1, 1] != labels[1, 5]


def test_component_metrics_reports_bbox_area_centroid_and_fill_ratio() -> None:
    mask = np.zeros((5, 7), dtype=bool)
    mask[1:3, 1:3] = True
    mask[1:4, 5] = True

    metrics = component_metrics(mask)

    assert [item.bbox for item in metrics] == [[1, 1, 2, 2], [5, 1, 1, 3]]
    assert [item.area for item in metrics] == [4, 3]
    assert metrics[0].centroid == (1.5, 1.5)
    assert metrics[0].fill_ratio == 1.0


def test_component_metrics_filters_tiny_components() -> None:
    mask = np.zeros((4, 4), dtype=bool)
    mask[0, 0] = True
    mask[2:4, 2:4] = True

    metrics = component_metrics(mask, min_area=2)

    assert len(metrics) == 1
    assert metrics[0].bbox == [2, 2, 2, 2]
    assert largest_component_area(mask) == 4
