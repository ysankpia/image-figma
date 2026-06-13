from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from fastapi import APIRouter, File, Form, HTTPException, Path as ApiPath, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .config import get_settings
from .core.pipeline import run_pipeline
from .core.schema import BBox, clamp_box
from .core.style import TextStyleContext, estimate_text_style
from .ocr_cache import copy_uploaded_ocr_artifact, resolve_or_create_ocr_artifact
from .ocr_provider import OCRProviderError
from .storage import compile_dir, create_task_dirs, new_task_id, save_upload, task_dir, write_error, write_error_payload

router = APIRouter()


@router.post("/api/draft-preview")
async def create_draft_preview(
    image: UploadFile = File(...),
    ocr: UploadFile | None = File(default=None),
    model_evidence: UploadFile | None = File(default=None, alias="modelEvidence"),
    allow_missing_ocr: bool | None = Query(default=None, alias="allowMissingOcr"),
) -> JSONResponse:
    settings = get_settings()
    effective_allow_missing_ocr = settings.psdlike_allow_missing_ocr if allow_missing_ocr is None else allow_missing_ocr
    task_id = new_task_id()
    root = create_task_dirs(task_id)
    image_path = root / "input.png"
    ocr_path: Path | None = None
    ocr_diagnostics: dict = {}
    model_evidence_path: Path | None = None
    try:
        save_upload(image_path, await image.read())
        if ocr is not None:
            ocr_path = root / "input.ocr_blocks.v1.json"
            save_upload(ocr_path, await ocr.read())
            resolved = copy_uploaded_ocr_artifact(ocr_path, ocr_path)
            ocr_diagnostics = resolved.diagnostics
        if model_evidence is not None:
            model_evidence_path = root / "input.model_evidence.v1.json"
            save_upload(model_evidence_path, await model_evidence.read())
        if ocr_path is None:
            resolved = resolve_or_create_ocr_artifact(
                image_path=image_path,
                task_ocr_path=root / "input.ocr_blocks.v1.json",
                settings=settings,
                require_ocr=not effective_allow_missing_ocr,
            )
            ocr_path = resolved.path
            ocr_diagnostics = resolved.diagnostics
        result = run_pipeline(
            image_path=image_path,
            ocr_path=ocr_path,
            out_dir=compile_dir(task_id),
            allow_missing_ocr=effective_allow_missing_ocr,
            task_id=task_id,
            model_evidence_path=model_evidence_path,
            ocr_diagnostics=ocr_diagnostics,
        )
    except OCRProviderError as exc:
        payload = {
            "taskId": task_id,
            "status": "failed",
            "stage": exc.stage,
            "code": exc.code,
            "error": exc.message,
        }
        write_error_payload(task_id, payload)
        raise HTTPException(status_code=500, detail=payload) from exc
    except Exception as exc:  # noqa: BLE001 - API writes error artifact for user visibility.
        write_error(task_id, exc)
        raise HTTPException(status_code=500, detail={"taskId": task_id, "error": str(exc)}) from exc
    payload = {
        "taskId": task_id,
        "status": "completed",
        "dslUrl": f"/api/draft-preview/{task_id}/dsl",
        "previewUrl": f"/api/draft-preview/{task_id}/preview",
        "diagnostics": result.diagnostics,
    }
    return JSONResponse({**payload, "success": True, "data": payload})


@router.get("/api/draft-preview/{taskId}")
def get_task(task_id: str = ApiPath(alias="taskId")) -> JSONResponse:
    root = task_dir(task_id)
    if not root.exists():
        raise HTTPException(status_code=404, detail="task not found")
    error_path = root / "error.json"
    if error_path.exists():
        return JSONResponse({"taskId": task_id, "status": "failed", "errorPath": str(error_path)})
    diagnostics_path = compile_dir(task_id) / "layer_stack.v1.json"
    if not diagnostics_path.exists():
        return JSONResponse({"taskId": task_id, "status": "running"})
    return JSONResponse(
        {
            "taskId": task_id,
            "status": "completed",
            "dslUrl": f"/api/draft-preview/{task_id}/dsl",
            "previewUrl": f"/api/draft-preview/{task_id}/preview",
        }
    )


@router.get("/api/draft-preview/{taskId}/dsl")
def get_dsl(task_id: str = ApiPath(alias="taskId")) -> FileResponse:
    return existing_file(compile_dir(task_id) / "draft_runtime.dsl.v1_0.json", media_type="application/json")


@router.get("/api/draft-preview/{taskId}/assets/{name}")
def get_asset(task_id: str = ApiPath(alias="taskId"), name: str = ApiPath()) -> FileResponse:
    if "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail="invalid asset name")
    return existing_file(compile_dir(task_id) / "assets" / name, media_type="image/png")


@router.get("/api/draft-preview/{taskId}/preview")
def get_preview(task_id: str = ApiPath(alias="taskId")) -> HTMLResponse:
    path = compile_dir(task_id) / "preview.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="preview not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.post("/api/text-style-batch")
async def text_style_batch(
    image: UploadFile = File(...),
    items: str = Form(...),
) -> JSONResponse:
    """Measurement-only text style for one page image and many OCR blocks.

    Returns fontSize/fontWeight/fontFamily/color/measured per item. Never
    decides raster-vs-editable; the caller owns that contract.
    """
    try:
        items_data = json.loads(items)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid items JSON: {exc}") from exc
    if not isinstance(items_data, list):
        raise HTTPException(status_code=400, detail="items must be a JSON array")

    try:
        pil = Image.open(io.BytesIO(await image.read())).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - boundary converts image errors to 400.
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
        box = _bbox_from_dict(item.get("bbox") or {})
        clamped = clamp_box(box, image_width, image_height) if box is not None else None
        if clamped is None or clamped.width <= 0 or clamped.height <= 0:
            results.append({"text": text, "error": "invalid_bbox"})
            continue
        context = _text_style_context_from_owner(item.get("ownerSurface"))
        try:
            style_result = estimate_text_style(rgb, clamped, text, context)
        except Exception as exc:  # noqa: BLE001 - per-item failure must not abort the batch.
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
            "measured": {"width": diagnostics["measuredWidth"], "height": diagnostics["measuredHeight"]},
            "source": "psdlike",
        })
    return JSONResponse({
        "results": results,
        "imageWidth": image_width,
        "imageHeight": image_height,
        "elapsedSeconds": round(time.perf_counter() - started, 3),
    })


def _text_style_context_from_owner(owner_surface: Any) -> TextStyleContext | None:
    if not isinstance(owner_surface, dict):
        return None
    owner_bbox = _bbox_from_dict(owner_surface.get("bbox") or {})
    fill_rgb = _hex_to_rgb(str(owner_surface.get("fill") or ""))
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


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    hex_value = value.strip().lstrip("#")
    if len(hex_value) != 6:
        return None
    try:
        return int(hex_value[0:2], 16), int(hex_value[2:4], 16), int(hex_value[4:6], 16)
    except ValueError:
        return None


def _bbox_from_dict(value: Any) -> BBox | None:
    if not isinstance(value, dict):
        return None
    try:
        return BBox(int(value["x"]), int(value["y"]), int(value["width"]), int(value["height"]))
    except (KeyError, TypeError, ValueError):
        return None


def existing_file(path: Path, media_type: str) -> FileResponse:
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, media_type=media_type)
