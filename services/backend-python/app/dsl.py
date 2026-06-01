from __future__ import annotations

from typing import Any

from PIL import Image

from .schema import DraftElement
from .style import sample_background


def build_dsl(
    elements: list[DraftElement],
    asset_map: dict[str, str],
    image: Image.Image,
    task_id: str,
) -> dict[str, Any]:
    page_w, page_h = image.size
    children: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []

    for element in sorted(elements, key=lambda item: (item.z, item.bbox.y, item.bbox.x, item.id)):
        node: dict[str, Any] = {
            "id": element.id,
            "type": element.type,
            "name": element_name(element),
            "bbox": element.bbox.to_dict(),
            "z": element.z,
            "meta": {
                "sourceIds": element.source_ids,
                "role": element.role,
                "confidence": element.confidence,
                "decisionReason": element.decision_reason,
            },
        }

        if element.type == "text":
            if not element.text.strip():
                continue
            node["text"] = {"characters": element.text}
            node["style"] = element.style
        elif element.type == "image":
            asset_filename = asset_map.get(element.id)
            if not asset_filename:
                continue
            asset_id = f"asset_{element.id}"
            node["image"] = {"assetId": asset_id, "mode": "fill"}
            assets.append(
                {
                    "assetId": asset_id,
                    "type": "image",
                    "url": f"assets/{asset_filename}",
                    "path": f"assets/{asset_filename}",
                    "format": "png",
                    "width": element.bbox.width,
                    "height": element.bbox.height,
                    "meta": {"sourceNodeId": element.id},
                }
            )
        elif element.type == "shape":
            node["style"] = element.style

        children.append(node)

    return {
        "version": "1.0",
        "kind": "draft_runtime",
        "taskId": task_id,
        "page": {
            "width": page_w,
            "height": page_h,
            "background": sample_background(image),
        },
        "root": {
            "id": "root",
            "type": "frame",
            "name": "Root",
            "bbox": {"x": 0, "y": 0, "width": page_w, "height": page_h},
            "children": children,
        },
        "assets": assets,
        "meta": {"pipeline": "omniparser_ocr_vlm_candidate_classifier.v1"},
    }


def element_name(element: DraftElement) -> str:
    if element.type == "text":
        label = element.text.strip()
        return label[:32] if label else element.id
    return f"{element.type}_{element.role}_{element.id}"
