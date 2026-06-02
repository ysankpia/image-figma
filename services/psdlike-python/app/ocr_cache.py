from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import Settings
from .ocr_provider import OCRProviderError, OCRRunResult, run_ocr_provider


@dataclass(frozen=True)
class ResolvedOCRArtifact:
    path: Path | None
    diagnostics: dict[str, Any]


OCRRunner = Callable[[Path, Settings], OCRRunResult]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_uploaded_ocr_artifact(uploaded_path: Path, task_ocr_path: Path) -> ResolvedOCRArtifact:
    task_ocr_path.parent.mkdir(parents=True, exist_ok=True)
    if uploaded_path.resolve() != task_ocr_path.resolve():
        shutil.copyfile(uploaded_path, task_ocr_path)
    data = _read_ocr_artifact(task_ocr_path)
    blocks = data.get("blocks", []) if isinstance(data, dict) else []
    return ResolvedOCRArtifact(
        path=task_ocr_path,
        diagnostics={
            "ocrProvider": "uploaded",
            "ocrPresent": True,
            "ocrTextCount": len(blocks) if isinstance(blocks, list) else 0,
            "ocrCacheHit": False,
            "ocrElapsedSeconds": 0.0,
            "ocrError": "",
            "ocrArtifactPath": str(task_ocr_path),
        },
    )


def resolve_or_create_ocr_artifact(
    *,
    image_path: Path,
    task_ocr_path: Path,
    settings: Settings,
    require_ocr: bool,
    runner: OCRRunner = run_ocr_provider,
) -> ResolvedOCRArtifact:
    started = time.perf_counter()
    cache_key = file_sha256(image_path)
    cache_path = settings.ocr_cache_dir / f"{cache_key}.ocr_blocks.v1.json"
    task_ocr_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        shutil.copyfile(cache_path, task_ocr_path)
        data = _read_ocr_artifact(task_ocr_path)
        blocks = data.get("blocks", []) if isinstance(data, dict) else []
        return ResolvedOCRArtifact(
            path=task_ocr_path,
            diagnostics={
                "ocrProvider": data.get("provider") or data.get("meta", {}).get("provider") or settings.ocr_provider,
                "ocrPresent": True,
                "ocrTextCount": len(blocks) if isinstance(blocks, list) else 0,
                "ocrCacheHit": True,
                "ocrElapsedSeconds": round(time.perf_counter() - started, 3),
                "ocrError": "",
                "ocrArtifactPath": str(task_ocr_path),
            },
        )

    try:
        result = runner(image_path, settings)
    except OCRProviderError as exc:
        if require_ocr:
            raise
        return ResolvedOCRArtifact(
            path=None,
            diagnostics={
                "ocrProvider": settings.ocr_provider,
                "ocrPresent": False,
                "ocrTextCount": 0,
                "ocrCacheHit": False,
                "ocrElapsedSeconds": round(time.perf_counter() - started, 3),
                "ocrError": f"{exc.code}: {exc.message}",
                "ocrArtifactPath": "",
            },
        )

    text = json.dumps(result.artifact, ensure_ascii=False, indent=2) + "\n"
    settings.ocr_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    task_ocr_path.write_text(text, encoding="utf-8")

    diagnostics = dict(result.diagnostics)
    diagnostics.update(
        {
            "ocrCacheHit": False,
            "ocrArtifactPath": str(task_ocr_path),
            "ocrElapsedSeconds": diagnostics.get("ocrElapsedSeconds", round(time.perf_counter() - started, 3)),
        }
    )
    return ResolvedOCRArtifact(path=task_ocr_path, diagnostics=diagnostics)


def _read_ocr_artifact(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
