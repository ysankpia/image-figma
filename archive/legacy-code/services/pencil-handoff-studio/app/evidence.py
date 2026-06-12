from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .config import Settings
from .jsonio import read_json, write_json
from .utils import bbox_area, bbox_iou, clamp_bbox, normalize_bbox, normalize_xyxy


@dataclass(frozen=True)
class EvidenceResult:
    evidence: dict[str, Any]
    warnings: list[str]


IMAGE_CLASS_NAMES = {"image", "backgroundimage", "background_image", "picture", "photo", "avatar"}
ICON_CLASS_NAMES = {"icon", "checkedtextview", "switch", "pageindicator"}
TEXT_CLASS_NAMES = {"text", "textbutton", "edittext"}


def collect_page_evidence(
    *,
    page_id: str,
    source_path: Path,
    work_dir: Path,
    settings: Settings,
    include_ocr: bool,
    include_basic_elements: bool,
) -> EvidenceResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    yolo = run_yolo(page_id=page_id, source_path=source_path, work_dir=work_dir, settings=settings, warnings=warnings)
    psdlike = run_psdlike(page_id=page_id, source_path=source_path, work_dir=work_dir, settings=settings, warnings=warnings)
    m29 = run_m29(page_id=page_id, source_path=source_path, work_dir=work_dir, settings=settings, warnings=warnings)
    ocr = run_ocr(page_id=page_id, work_dir=work_dir, settings=settings, warnings=warnings) if include_ocr else []
    items = [*yolo, *psdlike, *m29, *ocr]
    if not include_basic_elements:
        items = [item for item in items if item.get("kind") in {"image", "icon", "text"}]
    evidence = {
        "schema": "pencil_handoff.evidence.v1",
        "pageId": page_id,
        "sourceImage": str(source_path),
        "items": items,
        "warnings": warnings,
    }
    write_json(work_dir / "evidence.v1.json", evidence)
    draw_evidence_overlay(source_path, items, work_dir / "evidence_overlay.png")
    return EvidenceResult(evidence=evidence, warnings=warnings)


def run_yolo(*, page_id: str, source_path: Path, work_dir: Path, settings: Settings, warnings: list[str]) -> list[dict[str, Any]]:
    if settings.yolo_model is None:
        warnings.append("YOLO model not configured; skipped YOLO evidence")
        write_json(work_dir / "evidence_yolo.v1.json", {"schema": "pencil_handoff.evidence_yolo.v1", "items": []})
        return []
    if not settings.yolo_model.exists():
        warnings.append(f"YOLO model not found: {settings.yolo_model}; skipped YOLO evidence")
        write_json(work_dir / "evidence_yolo.v1.json", {"schema": "pencil_handoff.evidence_yolo.v1", "items": []})
        return []
    try:
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except Exception as error:
        warnings.append(f"ultralytics unavailable; skipped YOLO evidence: {error}")
        write_json(work_dir / "evidence_yolo.v1.json", {"schema": "pencil_handoff.evidence_yolo.v1", "items": []})
        return []

    try:
        model = YOLO(str(settings.yolo_model))
        kwargs: dict[str, Any] = {
            "source": str(source_path),
            "conf": settings.yolo_conf,
            "iou": settings.yolo_iou,
            "imgsz": settings.yolo_imgsz,
            "verbose": False,
        }
        if settings.yolo_device and settings.yolo_device != "auto":
            kwargs["device"] = settings.yolo_device
        results = model.predict(**kwargs)
    except Exception as error:
        warnings.append(f"YOLO inference failed; skipped YOLO evidence: {error}")
        write_json(work_dir / "evidence_yolo.v1.json", {"schema": "pencil_handoff.evidence_yolo.v1", "items": []})
        return []

    with Image.open(source_path) as image:
        width, height = image.size
    items: list[dict[str, Any]] = []
    for result in results:
        names = getattr(result, "names", {}) or {}
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for index, box in enumerate(boxes, start=1):
            xyxy = [float(value) for value in box.xyxy[0].tolist()]
            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])
            class_name = str(names.get(cls_id, cls_id))
            bbox = clamp_bbox(normalize_xyxy(xyxy), width, height)
            if bbox_area(bbox) <= 0:
                continue
            items.append(
                {
                    "id": f"{page_id}__yolo_{index:04d}",
                    "source": "yolo",
                    "rawKind": class_name,
                    "kind": map_yolo_kind(class_name),
                    "bbox": bbox,
                    "confidence": round(confidence, 4),
                    "reason": "yolo_detection",
                }
            )
    write_json(work_dir / "evidence_yolo.v1.json", {"schema": "pencil_handoff.evidence_yolo.v1", "items": items})
    return items


def map_yolo_kind(class_name: str) -> str:
    normalized = class_name.strip().lower().replace("-", "_")
    compact = normalized.replace("_", "")
    if normalized in IMAGE_CLASS_NAMES or compact in IMAGE_CLASS_NAMES:
        return "image"
    if normalized in ICON_CLASS_NAMES or compact in ICON_CLASS_NAMES:
        return "icon"
    if normalized in TEXT_CLASS_NAMES or compact in TEXT_CLASS_NAMES:
        return "text"
    return "ignore"


def run_psdlike(*, page_id: str, source_path: Path, work_dir: Path, settings: Settings, warnings: list[str]) -> list[dict[str, Any]]:
    script = settings.psdlike_root / "tools" / "run_one.py"
    if not script.exists():
        warnings.append(f"PSD-like runner missing: {script}; skipped PSD-like evidence")
        return []
    out_dir = work_dir / "psdlike"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [*python_command(settings.psdlike_root), str(script), "--image", str(source_path), "--out", str(out_dir), "--allow-missing-ocr"]
    env = os.environ.copy()
    env.setdefault("OCR_PROVIDER", "none")
    result = subprocess.run(cmd, cwd=str(settings.psdlike_root), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (out_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        warnings.append(f"PSD-like evidence failed: {result.stderr.strip() or result.stdout.strip() or result.returncode}")
        return []
    source = out_dir / "layer_stack.v1.json"
    if not source.exists():
        source = out_dir / "m29-pencil-replay.v1.json"
    if not source.exists():
        warnings.append("PSD-like evidence did not produce layer_stack.v1.json")
        return []
    raw = read_json(source)
    with Image.open(source_path) as image:
        width, height = image.size
    layers = raw.get("layers") or raw.get("items") or raw.get("nodes") or []
    items: list[dict[str, Any]] = []
    for index, layer in enumerate(layers, start=1):
        bbox = clamp_bbox(normalize_bbox(layer.get("bbox") or layer.get("bounds") or layer), width, height)
        if bbox_area(bbox) < 64:
            continue
        raw_kind = str(layer.get("kind") or layer.get("type") or layer.get("role") or "unknown")
        items.append(
            {
                "id": f"{page_id}__psdlike_{index:04d}",
                "source": "psdlike",
                "rawKind": raw_kind,
                "kind": map_physical_kind(raw_kind),
                "bbox": bbox,
                "confidence": 0.7,
                "reason": "psdlike_visual_block",
            }
        )
    write_json(work_dir / "evidence_psdlike.v1.json", {"schema": "pencil_handoff.evidence_psdlike.v1", "items": items})
    return items


def run_m29(*, page_id: str, source_path: Path, work_dir: Path, settings: Settings, warnings: list[str]) -> list[dict[str, Any]]:
    if settings.m29extract_path is None or not settings.m29extract_path.exists():
        warnings.append("m29extract missing; skipped M29 evidence")
        return []
    out_dir = work_dir / "m29"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(settings.m29extract_path), "--input", str(source_path), "--out", str(out_dir)]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (out_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        warnings.append(f"M29 evidence failed: {result.stderr.strip() or result.stdout.strip() or result.returncode}")
        return []
    candidates = list(out_dir.rglob("m29_physical_evidence.v1.json"))
    if not candidates:
        warnings.append("M29 evidence did not produce m29_physical_evidence.v1.json")
        return []
    raw = read_json(candidates[0])
    with Image.open(source_path) as image:
        width, height = image.size
    items: list[dict[str, Any]] = []
    for index, primitive in enumerate(raw.get("primitives") or raw.get("nodes") or [], start=1):
        bbox = clamp_bbox(normalize_bbox(primitive.get("bbox") or primitive.get("bounds") or primitive), width, height)
        if bbox_area(bbox) < 64:
            continue
        raw_kind = str(primitive.get("primitiveType") or primitive.get("role") or primitive.get("kind") or "unknown")
        items.append(
            {
                "id": f"{page_id}__m29_{index:04d}",
                "source": "m29",
                "rawKind": raw_kind,
                "kind": map_physical_kind(raw_kind),
                "bbox": bbox,
                "confidence": 0.62,
                "reason": "m29_physical_evidence",
            }
        )
    write_json(work_dir / "evidence_m29.v1.json", {"schema": "pencil_handoff.evidence_m29.v1", "items": items})
    return items


def run_ocr(*, page_id: str, work_dir: Path, settings: Settings, warnings: list[str]) -> list[dict[str, Any]]:
    if settings.ocr_provider == "none":
        write_json(work_dir / "evidence_ocr.v1.json", {"schema": "pencil_handoff.evidence_ocr.v1", "items": []})
        return []
    warnings.append(f"OCR provider {settings.ocr_provider} is not implemented in pencil-handoff-studio v1; skipped OCR evidence")
    write_json(work_dir / "evidence_ocr.v1.json", {"schema": "pencil_handoff.evidence_ocr.v1", "items": []})
    return []


def python_command(root: Path) -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "python"]
    for candidate in (root / ".venv" / "bin" / "python", root / ".venv" / "Scripts" / "python.exe"):
        if candidate.exists():
            return [str(candidate.resolve())]
    return [str(Path(sys.executable).resolve())]


def map_physical_kind(raw: str) -> str:
    normalized = raw.lower()
    if "icon" in normalized or "symbol" in normalized:
        return "icon"
    if "image" in normalized or "raster" in normalized or "media" in normalized or "bitmap" in normalized:
        return "image"
    if "text" in normalized or "ocr" in normalized:
        return "text"
    if "line" in normalized or "border" in normalized or "divider" in normalized:
        return "line"
    if "shape" in normalized or "surface" in normalized or "control" in normalized or "rect" in normalized:
        return "shape"
    return "ignore"


def merge_evidence_candidates(*, page_id: str, width: int, height: int, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    ranked = sorted(
        evidence_items,
        key=lambda item: (
            item.get("kind") not in {"image", "icon"},
            item.get("kind") not in {"shape", "line", "text"},
            -float(item.get("confidence") or 0.0),
            -bbox_area(item.get("bbox") or {"x": 0, "y": 0, "width": 0, "height": 0}),
        ),
    )
    for item in ranked:
        kind = str(item.get("kind") or "ignore")
        if kind not in {"image", "icon", "text", "shape", "line"}:
            continue
        bbox = clamp_bbox(item["bbox"], width, height)
        area = bbox_area(bbox)
        if area < 64:
            continue
        if kind in {"shape", "line"} and area > width * height * 0.45:
            continue
        if kind in {"image", "icon"} and bbox["width"] > width * 0.96 and bbox["height"] > height * 0.88:
            continue
        if any(bbox_iou(bbox, candidate["bbox"]) > 0.86 for candidate in candidates):
            continue
        sources = sorted({str(item.get("source")), *supporting_sources(bbox, evidence_items, skip_id=str(item.get("id")))})
        candidates.append(
            {
                "id": f"{page_id}__candidate_{len(candidates) + 1:04d}",
                "pageId": page_id,
                "kind": kind,
                "bbox": bbox,
                "confidence": round(float(item.get("confidence") or 0.5), 4),
                "sources": sources,
                "reason": candidate_reason(kind, sources),
                "sourceIds": [str(item.get("id"))],
                "selectedDefault": False,
            }
        )
    return candidates


def candidate_reason(kind: str, sources: list[str]) -> str:
    if kind in {"image", "icon"} and "yolo" in sources:
        return "semantic_asset_candidate"
    if kind in {"shape", "line"}:
        return "basic_element_candidate"
    if kind == "text":
        return "ocr_text_candidate"
    return "visual_candidate"


def supporting_sources(bbox: dict[str, int], items: list[dict[str, Any]], *, skip_id: str) -> list[str]:
    sources: set[str] = set()
    for item in items:
        if str(item.get("id")) == skip_id:
            continue
        other = item.get("bbox")
        if isinstance(other, dict) and bbox_iou(bbox, other) > 0.25:
            sources.add(str(item.get("source")))
    return sorted(sources)


def draw_evidence_overlay(source_path: Path, items: list[dict[str, Any]], output_path: Path) -> None:
    with Image.open(source_path) as image:
        canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    colors = {"image": "#22c55e", "icon": "#38bdf8", "text": "#ef4444", "shape": "#a78bfa", "line": "#f59e0b"}
    for item in items:
        bbox = item["bbox"]
        color = colors.get(str(item.get("kind")), "#94a3b8")
        x, y = bbox["x"], bbox["y"]
        w, h = bbox["width"], bbox["height"]
        draw.rectangle((x, y, x + w, y + h), outline=color, width=3)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
