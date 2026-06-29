from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from .io import now_iso, read_json, rel, sha256_file, write_json
from .paths import RunPaths
from .planner import source_image_path

API_URL = "https://api.moark.com/v1/images/layers"
DEFAULT_MODEL = "Qwen-Image-Layered"


def run_qwen(
    paths: RunPaths,
    token_env: str = "MOARK_API_TOKEN",
    layers: int = 4,
    steps: int = 50,
    true_cfg_scale: float = 4.0,
    seed: int = 0,
    negative_prompt: str = "debug boxes, red outlines, green outlines, labels, watermarks, low quality artifacts",
    force: bool = False,
    mock: bool = False,
) -> dict[str, Any]:
    if layers < 1 or layers > 4:
        raise ValueError("Qwen-Image-Layered currently accepts layers between 1 and 4")
    sheet_manifest = read_json(paths.sheet_manifest_json)
    results: list[dict[str, Any]] = []

    for sheet in sheet_manifest["sheets"]:
        sheet_path = paths.root / sheet["path"]
        sheet_out = paths.qwen_dir / sheet["id"]
        sheet_out.mkdir(parents=True, exist_ok=True)
        config = {
            "apiUrl": API_URL,
            "model": DEFAULT_MODEL,
            "layers": layers,
            "numInferenceSteps": steps,
            "trueCfgScale": true_cfg_scale,
            "negativePrompt": negative_prompt,
            "seed": seed,
            "sheetSha256": sha256_file(sheet_path),
        }
        request_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()
        layer_paths = sorted(sheet_out.glob("layer_*.png"))
        if layer_paths and not force:
            results.append(
                {
                    "sheetId": sheet["id"],
                    "ok": True,
                    "cached": True,
                    "requestHash": request_hash,
                    "layers": [rel(path, paths.root) for path in layer_paths],
                }
            )
            continue

        if mock:
            result = _mock_layers(paths, sheet, sheet_path, sheet_out, layers, request_hash)
            results.append(result)
            continue

        token = os.environ.get(token_env)
        if not token:
            results.append(
                {
                    "sheetId": sheet["id"],
                    "ok": False,
                    "cached": False,
                    "requestHash": request_hash,
                    "error": f"missing environment variable {token_env}",
                }
            )
            continue

        request_path = sheet_out / "request.json"
        write_json(request_path, config)
        started = time.monotonic()
        try:
            response = _post_qwen(sheet_path, token, config)
            elapsed = time.monotonic() - started
            response_path = sheet_out / "response.json"
            write_json(response_path, response)
            saved_layers = _download_layers(paths, sheet_out, response)
            results.append(
                {
                    "sheetId": sheet["id"],
                    "ok": True,
                    "cached": False,
                    "mock": False,
                    "requestHash": request_hash,
                    "elapsedSec": round(elapsed, 2),
                    "responsePath": rel(response_path, paths.root),
                    "layers": [rel(path, paths.root) for path in saved_layers],
                    "rawImageCount": len(response.get("images", [])),
                }
            )
        except Exception as error:
            results.append(
                {
                    "sheetId": sheet["id"],
                    "ok": False,
                    "cached": False,
                    "mock": False,
                    "requestHash": request_hash,
                    "error": str(error),
                }
            )

    manifest = {
        "schema": "html_first_qwen_manifest.v1",
        "createdAt": now_iso(),
        "results": results,
    }
    write_json(paths.qwen_manifest_json, manifest)
    return manifest


def run_qwen_full(
    paths: RunPaths,
    token_env: str = "MOARK_API_TOKEN",
    layers: int = 4,
    steps: int = 50,
    true_cfg_scale: float = 4.0,
    seed: int = 0,
    negative_prompt: str = "debug boxes, red outlines, green outlines, labels, watermarks, low quality artifacts",
    force: bool = False,
    mock: bool = False,
) -> dict[str, Any]:
    if layers < 1 or layers > 4:
        raise ValueError("Qwen-Image-Layered currently accepts layers between 1 and 4")

    paths.ensure()
    image_path = source_image_path(paths)
    out_dir = paths.qwen_full_dir / "full_page"
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "apiUrl": API_URL,
        "model": DEFAULT_MODEL,
        "layers": layers,
        "numInferenceSteps": steps,
        "trueCfgScale": true_cfg_scale,
        "negativePrompt": negative_prompt,
        "seed": seed,
        "imageSha256": sha256_file(image_path),
        "source": "full_page",
    }
    request_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()
    layer_paths = sorted(out_dir.glob("layer_*.png"))
    if layer_paths and not force:
        result = {
            "imageId": "full_page",
            "ok": True,
            "cached": True,
            "requestHash": request_hash,
            "layers": [rel(path, paths.root) for path in layer_paths],
        }
    elif mock:
        result = _mock_image_layers(paths, image_path, out_dir, layers, request_hash, {"imageId": "full_page"})
    else:
        token = os.environ.get(token_env)
        if not token:
            result = {
                "imageId": "full_page",
                "ok": False,
                "cached": False,
                "requestHash": request_hash,
                "error": f"missing environment variable {token_env}",
            }
        else:
            request_path = out_dir / "request.json"
            write_json(request_path, config)
            started = time.monotonic()
            try:
                response = _post_qwen(image_path, token, config)
                elapsed = time.monotonic() - started
                response_path = out_dir / "response.json"
                write_json(response_path, response)
                saved_layers = _download_layers(paths, out_dir, response)
                result = {
                    "imageId": "full_page",
                    "ok": True,
                    "cached": False,
                    "mock": False,
                    "requestHash": request_hash,
                    "elapsedSec": round(elapsed, 2),
                    "responsePath": rel(response_path, paths.root),
                    "layers": [rel(path, paths.root) for path in saved_layers],
                    "rawImageCount": len(response.get("images", [])),
                }
            except Exception as error:
                result = {
                    "imageId": "full_page",
                    "ok": False,
                    "cached": False,
                    "mock": False,
                    "requestHash": request_hash,
                    "error": str(error),
                }

    manifest = {
        "schema": "html_first_qwen_full_manifest.v1",
        "createdAt": now_iso(),
        "result": result,
    }
    write_json(paths.qwen_full_manifest_json, manifest)
    return manifest


def _mock_layers(
    paths: RunPaths,
    sheet: dict[str, Any],
    sheet_path: Path,
    sheet_out: Path,
    layers: int,
    request_hash: str,
) -> dict[str, Any]:
    source = Image.open(sheet_path).convert("RGBA")
    saved: list[Path] = []
    for index in range(layers):
        out_path = sheet_out / f"layer_{index:02d}.png"
        if index == 0:
            source.save(out_path)
        else:
            Image.new("RGBA", source.size, (255, 255, 255, 0)).save(out_path)
        saved.append(out_path)
    write_json(sheet_out / "response.json", {"mock": True, "images": []})
    return {
        "sheetId": sheet["id"],
        "ok": True,
        "cached": False,
        "mock": True,
        "requestHash": request_hash,
        "layers": [rel(path, paths.root) for path in saved],
    }


def _mock_image_layers(
    paths: RunPaths,
    image_path: Path,
    out_dir: Path,
    layers: int,
    request_hash: str,
    result_fields: dict[str, Any],
) -> dict[str, Any]:
    source = Image.open(image_path).convert("RGBA")
    saved: list[Path] = []
    for index in range(layers):
        out_path = out_dir / f"layer_{index:02d}.png"
        if index == 0:
            source.save(out_path)
        else:
            Image.new("RGBA", source.size, (255, 255, 255, 0)).save(out_path)
        saved.append(out_path)
    write_json(out_dir / "response.json", {"mock": True, "images": []})
    return {
        **result_fields,
        "ok": True,
        "cached": False,
        "mock": True,
        "requestHash": request_hash,
        "layers": [rel(path, paths.root) for path in saved],
    }


def _post_qwen(sheet_path: Path, token: str, config: dict[str, Any]) -> dict[str, Any]:
    fields: list[tuple[str, str | tuple[str, bytes, str]]] = [
        ("model", str(config["model"])),
        ("layers", str(config["layers"])),
        ("num_inference_steps", str(config["numInferenceSteps"])),
        ("true_cfg_scale", str(config["trueCfgScale"])),
        ("negative_prompt", str(config["negativePrompt"])),
        ("seed", str(config["seed"])),
    ]
    mime_type = mimetypes.guess_type(sheet_path.name)[0] or "application/octet-stream"
    fields.append(("image", (sheet_path.name, sheet_path.read_bytes(), mime_type)))
    body, content_type = _multipart_encode(fields)
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MoArk HTTP {error.code}: {detail}") from error
    return json.loads(raw.decode("utf-8"))


def _multipart_encode(fields: list[tuple[str, str | tuple[str, bytes, str]]]) -> tuple[bytes, str]:
    boundary = f"----ui-rebuilder-{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        if isinstance(value, tuple):
            filename, content, content_type = value
            chunks.append(
                (
                    f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            chunks.append(content)
            chunks.append(b"\r\n")
        else:
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _download_layers(paths: RunPaths, sheet_out: Path, response: dict[str, Any]) -> list[Path]:
    saved: list[Path] = []
    for index, image in enumerate(response.get("images", [])):
        url = image.get("url")
        if not url:
            continue
        out_path = sheet_out / f"layer_{index:02d}.png"
        with urllib.request.urlopen(url, timeout=120) as remote:
            out_path.write_bytes(remote.read())
        saved.append(out_path)
    return saved
