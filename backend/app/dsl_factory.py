from __future__ import annotations

from typing import Any, Literal

from .storage import PngMetadata


def build_deterministic_dsl(
    *,
    task_id: str,
    original_url: str,
    fallback_url: str,
    image: PngMetadata,
) -> dict[str, Any]:
    platform_hint = infer_platform_hint(image.width, image.height)

    return {
        "version": "0.1",
        "taskId": task_id,
        "page": {
            "name": "uploaded_png",
            "width": image.width,
            "height": image.height,
            "originalWidth": image.width,
            "originalHeight": image.height,
            "scaleFactor": 1,
            "viewportHeight": image.height,
            "isScrollable": False,
            "background": {
                "type": "color",
                "value": "#F7F8FA",
            },
        },
        "assets": [
            {
                "assetId": "asset_original",
                "type": "image",
                "role": "original",
                "url": original_url,
                "format": "png",
                "width": image.width,
                "height": image.height,
                "storage": "local",
            },
            {
                "assetId": "asset_banner",
                "type": "image",
                "role": "fallback_region",
                "url": fallback_url,
                "format": "png",
                "width": image.width,
                "height": image.height,
                "storage": "local",
            },
        ],
        "root": {
            "id": "root",
            "type": "frame",
            "role": "screen",
            "name": "uploaded_png",
            "layout": {
                "x": 0,
                "y": 0,
                "width": image.width,
                "height": image.height,
            },
            "style": {
                "fill": "#F7F8FA",
            },
            "children": [
                {
                    "id": "original_ref",
                    "type": "image",
                    "role": "original_reference",
                    "name": "Original PNG Reference",
                    "layout": {
                        "x": 0,
                        "y": 0,
                        "width": image.width,
                        "height": image.height,
                    },
                    "source": {
                        "assetId": "asset_original",
                    },
                    "style": {
                        "visible": False,
                        "opacity": 0.5,
                    },
                    "imageFill": {
                        "mode": "fill",
                    },
                },
                {
                    "id": "fallback_full_image",
                    "type": "image",
                    "role": "fallback_region",
                    "name": "Fallback Full Image",
                    "layout": {
                        "x": 0,
                        "y": 0,
                        "width": image.width,
                        "height": image.height,
                    },
                    "source": {
                        "assetId": "asset_banner",
                    },
                    "imageFill": {
                        "mode": "fill",
                    },
                    "meta": {
                        "fallback": True,
                        "reason": "m6_deterministic_full_image",
                        "confidence": 1,
                    },
                },
            ],
        },
        "meta": {
            "source": "png",
            "platformHint": platform_hint,
            "fallbackCount": 1,
            "elementCount": 2,
            "notes": "deterministic_fallback_dsl",
        },
    }


def infer_platform_hint(width: int, height: int) -> Literal["mobile", "desktop_web", "unknown"]:
    if width <= 480 and height >= width:
        return "mobile"
    if width >= 900:
        return "desktop_web"
    return "unknown"
