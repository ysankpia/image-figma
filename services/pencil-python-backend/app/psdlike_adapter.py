from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


class PSDLikeAdapterError(RuntimeError):
    pass


def adapt_psdlike_to_pencil_evidence(psdlike_dir: Path, output_dir: Path) -> Path:
    psdlike_dir = psdlike_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    layer_stack_path = psdlike_dir / "layer_stack.v1.json"
    if not layer_stack_path.exists():
        raise PSDLikeAdapterError(f"Missing PSD-like layer stack: {layer_stack_path}")
    layer_stack = json.loads(layer_stack_path.read_text(encoding="utf-8"))
    canvas = layer_stack.get("canvas") or {}
    width = int(canvas.get("width") or 0)
    height = int(canvas.get("height") or 0)
    if width <= 0 or height <= 0:
        raise PSDLikeAdapterError("PSD-like layer stack has invalid canvas size")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "crops").mkdir(exist_ok=True)
    (output_dir / "masks").mkdir(exist_ok=True)
    source_path = ensure_source_png(psdlike_dir, output_dir)

    primitives: list[dict[str, Any]] = []
    replay_layers: list[dict[str, Any]] = []
    for index, layer in enumerate(sorted(layer_stack.get("layers") or [], key=lambda item: item.get("z", 0)), start=1):
        layer_type = str(layer.get("type") or "")
        if layer_type == "raster":
            primitive, replay = adapt_raster_layer(layer, psdlike_dir, output_dir, index, width, height)
        elif layer_type == "shape":
            primitive, replay = adapt_shape_layer(layer, output_dir, index, width, height)
        elif layer_type == "text":
            primitive, replay = adapt_text_layer(layer, source_path, output_dir, index, width, height)
        else:
            continue
        primitives.append(primitive)
        replay_layers.append(replay)

    evidence = {
        "schema": "m29.physical_evidence.v1",
        "generator": {
            "name": "pencil-python-backend.psdlike_adapter",
            "source": "psdlike.layer_stack.v1",
        },
        "image": {
            "width": width,
            "height": height,
            "sourceRef": "source.png",
        },
        "diagnostics": {
            "pageBackground": layer_stack.get("pageBackground") or (layer_stack.get("diagnostics") or {}).get("pageBackground") or "#FFFFFF",
            "boundarySource": "psdlike",
            "psdlikeLayerCount": len(layer_stack.get("layers") or []),
            "psdlikeRasterLayerCount": sum(1 for item in layer_stack.get("layers") or [] if item.get("type") == "raster"),
            "psdlikeShapeLayerCount": sum(1 for item in layer_stack.get("layers") or [] if item.get("type") == "shape"),
            "psdlikeTextLayerCount": sum(1 for item in layer_stack.get("layers") or [] if item.get("type") == "text"),
        },
        "primitives": primitives,
    }
    replay = {
        "schema": "m29.pencil.replay.v1",
        "version": "1.0",
        "source": "generated_from_psdlike_layer_stack",
        "policy": {
            "mode": "psdlike_boundary_replay",
            "generatedBy": "psdlike_adapter.adapt_psdlike_to_pencil_evidence",
        },
        "layers": replay_layers,
        "summary": {
            "layerCount": len(replay_layers),
            "boundarySource": "psdlike",
        },
    }
    write_json(output_dir / "m29_physical_evidence.v1.json", evidence)
    write_json(output_dir / "m29-pencil-replay.v1.json", replay)
    copy_psdlike_debug(psdlike_dir, output_dir / "psdlike_debug")
    return output_dir


def ensure_source_png(psdlike_dir: Path, output_dir: Path) -> Path:
    source = psdlike_dir / "source.png"
    if not source.exists():
        source_image = psdlike_dir / "input.png"
        source = source_image if source_image.exists() else source
    target = output_dir / "source.png"
    if source.exists():
        shutil.copy2(source, target)
        return target

    source_from_stack = find_source_from_layer_stack(psdlike_dir / "layer_stack.v1.json")
    if source_from_stack and source_from_stack.exists():
        shutil.copy2(source_from_stack, target)
        return target
    raise PSDLikeAdapterError("PSD-like output does not contain source.png and sourceImage is unavailable")


def find_source_from_layer_stack(layer_stack_path: Path) -> Path | None:
    try:
        data = json.loads(layer_stack_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = data.get("sourceImage")
    if isinstance(value, str) and value:
        return Path(value).expanduser().resolve()
    return None


def adapt_raster_layer(
    layer: dict[str, Any],
    psdlike_dir: Path,
    output_dir: Path,
    index: int,
    canvas_width: int,
    canvas_height: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    primitive_id = f"psd_raster_{index:04d}"
    bbox = normalize_bbox(layer["bbox"])
    source_asset = psdlike_dir / str(layer.get("asset") or "")
    if not source_asset.exists():
        raise PSDLikeAdapterError(f"Missing PSD-like raster asset for {layer.get('id')}: {source_asset}")
    crop_ref = f"crops/{primitive_id}.png"
    mask_ref = f"masks/{primitive_id}.png"
    shutil.copy2(source_asset, output_dir / crop_ref)
    write_rect_mask(output_dir / mask_ref, canvas_width, canvas_height, bbox)
    primitive = {
        "id": primitive_id,
        "primitiveType": "image_region",
        "bbox": bbox,
        "maskRef": mask_ref,
        "cropRef": crop_ref,
        "source": {
            "kind": "psdlike_raster",
            "sourceLayerId": layer.get("id"),
            "reason": layer.get("reason"),
        },
        "measurements": layer.get("scores") or {},
        "compileHints": {},
    }
    replay = base_replay_layer(layer, primitive_id, "image_region", bbox, crop_ref, mask_ref)
    return primitive, replay


def adapt_shape_layer(
    layer: dict[str, Any],
    output_dir: Path,
    index: int,
    canvas_width: int,
    canvas_height: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    primitive_id = f"psd_shape_{index:04d}"
    bbox = normalize_bbox(layer["bbox"])
    crop_ref = f"crops/{primitive_id}.png"
    mask_ref = f"masks/{primitive_id}.png"
    style = layer.get("style") or {}
    fill = str(style.get("fill") or "#FFFFFF")
    image = Image.new("RGBA", (bbox["width"], bbox["height"]), css_to_rgba(fill))
    image.save(output_dir / crop_ref)
    write_text_mask(output_dir / mask_ref, output_dir / crop_ref, canvas_width, canvas_height, bbox)
    primitive = {
        "id": primitive_id,
        "primitiveType": "surface_region",
        "bbox": bbox,
        "maskRef": mask_ref,
        "cropRef": crop_ref,
        "source": {
            "kind": "psdlike_shape",
            "sourceLayerId": layer.get("id"),
            "reason": layer.get("reason"),
            "style": style,
        },
        "measurements": layer.get("scores") or {},
        "compileHints": {},
    }
    replay = {
        **base_replay_layer(layer, primitive_id, "surface_region", bbox, crop_ref, mask_ref),
        "editableMode": "shape",
        "shapeStyle": style,
    }
    return primitive, replay


def adapt_text_layer(
    layer: dict[str, Any],
    source_png: Path,
    output_dir: Path,
    index: int,
    canvas_width: int,
    canvas_height: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    primitive_id = f"psd_text_{index:04d}"
    bbox = normalize_bbox(layer["bbox"])
    crop_ref = f"crops/{primitive_id}.png"
    mask_ref = f"masks/{primitive_id}.png"
    with Image.open(source_png) as source:
        source.convert("RGBA").crop(
            (
                bbox["x"],
                bbox["y"],
                bbox["x"] + bbox["width"],
                bbox["y"] + bbox["height"],
            )
        ).save(output_dir / crop_ref)
    write_rect_mask(output_dir / mask_ref, canvas_width, canvas_height, bbox)
    text = str(layer.get("text") or "")
    primitive = {
        "id": primitive_id,
        "primitiveType": "text_region",
        "bbox": bbox,
        "maskRef": mask_ref,
        "cropRef": crop_ref,
        "source": {
            "kind": "ocr",
            "ocrBlockId": layer.get("id"),
            "text": text,
            "psdlikeStyle": layer.get("style") or {},
            "confidence": layer.get("confidence"),
        },
        "measurements": layer.get("textFit") or {},
        "compileHints": {},
    }
    replay = base_replay_layer(layer, primitive_id, "text_region", bbox, crop_ref, mask_ref)
    return primitive, replay


def base_replay_layer(
    layer: dict[str, Any],
    primitive_id: str,
    role: str,
    bbox: dict[str, int],
    crop_ref: str,
    mask_ref: str,
) -> dict[str, Any]:
    return {
        "id": primitive_id,
        "sourcePrimitiveId": primitive_id,
        "sourceLayerId": layer.get("id"),
        "role": role,
        "nodeType": "rectangle",
        "bbox": bbox,
        "fillImage": f"./assets/{crop_ref}",
        "maskImage": f"./assets/{mask_ref}",
        "editableMode": "raster_crop",
        "z": int(layer.get("z") or 0),
    }


def normalize_bbox(raw: dict[str, Any]) -> dict[str, int]:
    x = int(round(float(raw.get("x") or 0)))
    y = int(round(float(raw.get("y") or 0)))
    width = max(1, int(round(float(raw.get("width") or 0))))
    height = max(1, int(round(float(raw.get("height") or 0))))
    return {"x": x, "y": y, "width": width, "height": height}


def write_rect_mask(path: Path, canvas_width: int, canvas_height: int, bbox: dict[str, int]) -> None:
    image = Image.new("L", (max(1, canvas_width), max(1, canvas_height)), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (
            bbox["x"],
            bbox["y"],
            bbox["x"] + bbox["width"] - 1,
            bbox["y"] + bbox["height"] - 1,
        ),
        fill=255,
    )
    image.save(path)


def write_text_mask(path: Path, crop_path: Path, canvas_width: int, canvas_height: int, bbox: dict[str, int]) -> None:
    crop = Image.open(crop_path).convert("RGB")
    arr = np.asarray(crop, dtype=np.int16)
    if arr.size == 0:
        write_rect_mask(path, canvas_width, canvas_height, bbox)
        return
    background = estimate_edge_background(arr)
    delta = np.linalg.norm(arr - background.reshape(1, 1, 3), axis=2)
    mask = delta >= 32.0
    if mask.sum() < max(2, int(mask.size * 0.01)):
        luminance = (arr[:, :, 0] * 0.2126 + arr[:, :, 1] * 0.7152 + arr[:, :, 2] * 0.0722)
        bg_luminance = float(background[0] * 0.2126 + background[1] * 0.7152 + background[2] * 0.0722)
        mask = np.abs(luminance - bg_luminance) >= 24.0
    if not mask.any():
        write_rect_mask(path, canvas_width, canvas_height, bbox)
        return
    local = Image.fromarray((mask.astype(np.uint8) * 255), "L")
    page = Image.new("L", (max(1, canvas_width), max(1, canvas_height)), 0)
    page.paste(local, (bbox["x"], bbox["y"]))
    page.save(path)


def estimate_edge_background(arr: np.ndarray) -> np.ndarray:
    height, width = arr.shape[:2]
    border = max(1, min(4, height // 4, width // 4))
    samples = np.concatenate(
        [
            arr[:border, :, :].reshape(-1, 3),
            arr[height - border :, :, :].reshape(-1, 3),
            arr[:, :border, :].reshape(-1, 3),
            arr[:, width - border :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    if samples.size == 0:
        return np.array([255, 255, 255], dtype=np.int16)
    return np.median(samples, axis=0).astype(np.int16)


def css_to_rgba(value: str) -> tuple[int, int, int, int]:
    value = value.strip()
    if value.startswith("#"):
        if len(value) == 4:
            return tuple(int(ch * 2, 16) for ch in value[1:]) + (255,)
        if len(value) == 7:
            return (
                int(value[1:3], 16),
                int(value[3:5], 16),
                int(value[5:7], 16),
                255,
            )
    return (255, 255, 255, 255)


def copy_psdlike_debug(psdlike_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "layer_stack.v1.json",
        "draft_runtime.dsl.v1_0.json",
        "preview.html",
        "preview_report.md",
        "draft_preview.png",
        "reconstructed_preview.png",
        "overlay.png",
        "raster_heatmap.png",
        "shape_heatmap.png",
        "ownership_report.v1.json",
        "diagnostics.md",
        "input.ocr_blocks.v1.json",
        "psdlike.stdout.txt",
        "psdlike.stderr.txt",
    ):
        source = psdlike_dir / name
        if source.exists():
            shutil.copy2(source, target_dir / name)
    assets = psdlike_dir / "assets"
    if assets.exists():
        shutil.copytree(assets, target_dir / "assets", dirs_exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
