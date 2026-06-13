from __future__ import annotations

import io
import json
import time
from typing import Any

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from .schema import BBox, bbox_from_dict, clamp_box
from .style import TextStyleContext, estimate_text_style

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/api/text-style-batch")
async def text_style_batch(
    image: UploadFile = File(...),
    items: str = Form(...),
) -> JSONResponse:
    try:
        items_data = json.loads(items)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid items JSON: {exc}") from exc
    if not isinstance(items_data, list):
        raise HTTPException(status_code=400, detail="items must be a JSON array")

    try:
        pil = Image.open(io.BytesIO(await image.read())).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - convert image boundary errors to API errors.
        raise HTTPException(status_code=400, detail=f"invalid image: {exc}") from exc

    rgb = np.asarray(pil)
    image_height, image_width = rgb.shape[:2]
    started = time.perf_counter()
    results: list[dict[str, Any]] = []

    for item in items_data:
        if not isinstance(item, dict):
            results.append({"error": "invalid_item"})
            continue
        text = str(item.get("text") or "")
        box = bbox_from_dict(item.get("bbox") or {})
        clamped = clamp_box(box, image_width, image_height) if box is not None else None
        if clamped is None:
            results.append({"text": text, "error": "invalid_bbox"})
            continue
        context = text_style_context_from_owner(item.get("ownerSurface"))
        try:
            style_result = estimate_text_style(rgb, clamped, text, context)
        except Exception as exc:  # noqa: BLE001 - one bad item must not abort the whole page batch.
            results.append({"text": text, "error": f"estimate_failed: {exc}"})
            continue
        style = style_result["style"]
        diagnostics = style_result["diagnostics"]
        results.append({
            "text": text,
            "fontSize": style["fontSize"],
            "fontWeight": style["fontWeight"],
            "fontFamily": style["fontFamily"],
            "color": style["color"],
            "lineHeight": style["lineHeight"],
            "textAlign": style["textAlign"],
            "measured": {
                "width": diagnostics["measuredWidth"],
                "height": diagnostics["measuredHeight"],
            },
            "source": "psdlike",
        })

    return JSONResponse({
        "results": results,
        "imageWidth": image_width,
        "imageHeight": image_height,
        "elapsedSeconds": round(time.perf_counter() - started, 3),
    })


def text_style_context_from_owner(owner_surface: Any) -> TextStyleContext | None:
    if not isinstance(owner_surface, dict):
        return None
    owner_bbox = bbox_from_dict(owner_surface.get("bbox") or {})
    fill_rgb = hex_to_rgb(str(owner_surface.get("fill") or ""))
    if owner_bbox is None or fill_rgb is None:
        return None
    reason = str(owner_surface.get("reason") or "")
    role = "control_surface" if "control_surface" in reason else "container_surface"
    return TextStyleContext(
        owner_bbox=owner_bbox,
        owner_fill=fill_rgb,
        owner_reason=reason,
        owner_role=role,
        owner_id=str(owner_surface.get("id") or ""),
    )


def hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    hex_value = value.strip().lstrip("#")
    if len(hex_value) != 6:
        return None
    try:
        return int(hex_value[0:2], 16), int(hex_value[2:4], 16), int(hex_value[4:6], 16)
    except ValueError:
        return None
