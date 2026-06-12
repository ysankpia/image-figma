from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, Literal

from .png_tools import PngMetadata


@dataclass(frozen=True)
class DslRegionAsset:
    asset_id: str
    name: str
    url: str
    x: int
    y: int
    width: int
    height: int


def build_deterministic_dsl(
    *,
    task_id: str,
    original_url: str,
    fallback_url: str,
    image: PngMetadata,
    regions: Sequence[DslRegionAsset] | None = None,
    quality_flags: Sequence[str] | None = None,
) -> dict[str, Any]:
    platform_hint = infer_platform_hint(image.width, image.height)
    region_assets = list(regions or [])
    use_region_assets = len(region_assets) > 0
    fallback_count = len(region_assets) if use_region_assets else 1
    children = [
        original_reference_element(image),
        *(
            region_fallback_element(region)
            for region in region_assets
        ),
    ] if use_region_assets else [
        original_reference_element(image),
        full_image_fallback_element(image),
    ]
    assets = [
        {
            "assetId": "asset_original",
            "type": "image",
            "role": "original",
            "url": original_url,
            "format": "png",
            "width": image.width,
            "height": image.height,
            "storage": "local",
        }
    ]
    if use_region_assets:
        assets.extend(region_asset(region) for region in region_assets)
    else:
        assets.append(
            {
                "assetId": "asset_banner",
                "type": "image",
                "role": "fallback_region",
                "url": fallback_url,
                "format": "png",
                "width": image.width,
                "height": image.height,
                "storage": "local",
            }
        )

    meta: dict[str, Any] = {
        "source": "png",
        "platformHint": platform_hint,
        "fallbackCount": fallback_count,
        "elementCount": len(children),
        "notes": "deterministic_region_dsl" if use_region_assets else "deterministic_fallback_dsl",
    }
    if quality_flags:
        meta["qualityFlags"] = list(quality_flags)

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
        "assets": assets,
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
            "children": children,
        },
        "meta": meta,
    }


def infer_platform_hint(width: int, height: int) -> Literal["mobile", "desktop_web", "unknown"]:
    if height >= width * 1.2 and width <= 1200:
        return "mobile"
    if width >= 1200:
        return "desktop_web"
    return "unknown"


def region_asset(region: DslRegionAsset) -> dict[str, Any]:
    return {
        "assetId": region.asset_id,
        "type": "image",
        "role": "fallback_region",
        "url": region.url,
        "format": "png",
        "width": region.width,
        "height": region.height,
        "storage": "local",
    }


def original_reference_element(image: PngMetadata) -> dict[str, Any]:
    return {
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
    }


def region_fallback_element(region: DslRegionAsset) -> dict[str, Any]:
    return {
        "id": f"fallback_region_{region.name}",
        "type": "image",
        "role": "fallback_region",
        "name": f"Fallback Region / {region.name}",
        "layout": {
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
        },
        "source": {
            "assetId": region.asset_id,
        },
        "imageFill": {
            "mode": "fill",
        },
        "meta": {
            "fallback": True,
            "reason": "m7_deterministic_region",
            "confidence": 1,
            "sourceBBox": [region.x, region.y, region.width, region.height],
        },
    }


def full_image_fallback_element(image: PngMetadata) -> dict[str, Any]:
    return {
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
    }
