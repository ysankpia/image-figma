#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import load_config, load_dotenv_local
from app.ocr import run_ocr
from app.schema import TextBlock
from tools.psd_like_layer_decomposition_experiment import run as run_psd_like


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class InputCase:
    case_id: str
    source_path: Path
    sha256: str
    duplicate_paths: list[Path]


def main() -> None:
    args = parse_args()
    load_dotenv_local()

    input_dir = Path(args.input_dir).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = collect_image_paths(input_dir)
    cases = build_cases(paths, dedupe=not args.no_dedupe)
    manifest = {
        "version": "psd_like_batch_eval_input.v1",
        "inputDir": str(input_dir),
        "pathCount": len(paths),
        "caseCount": len(cases),
        "dedupe": not args.no_dedupe,
        "cases": [
            {
                "caseId": case.case_id,
                "sourcePath": str(case.source_path),
                "sha256": case.sha256,
                "duplicateCount": len(case.duplicate_paths),
                "duplicatePaths": [str(path) for path in case.duplicate_paths],
            }
            for case in cases
        ],
    }
    (out_dir / "input_manifest.v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.limit:
        cases = cases[: args.limit]

    print(
        f"PSD-like batch eval: paths={len(paths)} cases={len(cases)} "
        f"dedupe={not args.no_dedupe} out={out_dir}",
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    config = load_config()
    for index, case in enumerate(cases, start=1):
        started = time.monotonic()
        print(f"[{index}/{len(cases)}] {case.case_id} {case.source_path}", flush=True)
        row = run_case(case, out_dir, config, args)
        row["runtimeSeconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        write_outputs(out_dir, rows)

    write_contact_sheet(out_dir / "draft_preview_contact_sheet.png", rows, "draft_preview.png")
    write_contact_sheet(out_dir / "overlay_contact_sheet.png", rows, "overlay.png")
    write_source_vs_draft_contact_sheet(out_dir / "source_vs_draft_contact_sheet.png", rows)
    print(f"done: {out_dir / 'summary.md'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-evaluate PSD-like decomposition on a real image directory.")
    parser.add_argument("--input-dir", required=True, help="Directory containing screenshots/images.")
    parser.add_argument("--out", required=True, help="Output directory for batch artifacts.")
    parser.add_argument("--limit", type=int, default=0, help="Limit unique cases for a dry run.")
    parser.add_argument("--no-dedupe", action="store_true", help="Evaluate every path instead of one case per SHA-256.")
    parser.add_argument("--skip-ocr", action="store_true", help="Skip real OCR and run with no OCR artifact.")
    parser.add_argument("--require-ocr", action="store_true", help="Fail a case instead of degrading when OCR is unavailable.")
    parser.add_argument("--ocr-cache-dir", default="", help="Optional shared OCR cache directory. Defaults to <out>/ocr_cache.")
    parser.add_argument("--ocr-retries", type=int, default=3, help="Real OCR attempts per uncached image.")
    parser.add_argument("--ocr-retry-delay", type=float, default=2.0, help="Initial OCR retry delay in seconds.")
    parser.add_argument("--max-rasters", type=int, default=60, help="Failure threshold for raster asset explosion.")
    parser.add_argument("--max-tiny-rasters", type=int, default=10, help="Failure threshold for tiny raster explosion.")
    parser.add_argument("--tile-size", type=int, default=8)
    return parser.parse_args()


def collect_image_paths(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def build_cases(paths: list[Path], dedupe: bool) -> list[InputCase]:
    if not dedupe:
        return [
            InputCase(
                case_id=f"case_{index:04d}_{file_sha256(path)[:10]}",
                source_path=path,
                sha256=file_sha256(path),
                duplicate_paths=[path],
            )
            for index, path in enumerate(paths, start=1)
        ]

    by_hash: dict[str, list[Path]] = {}
    for path in paths:
        by_hash.setdefault(file_sha256(path), []).append(path)

    cases: list[InputCase] = []
    for index, sha in enumerate(sorted(by_hash), start=1):
        duplicates = sorted(by_hash[sha])
        cases.append(
            InputCase(
                case_id=f"case_{index:04d}_{sha[:10]}",
                source_path=duplicates[0],
                sha256=sha,
                duplicate_paths=duplicates,
            )
        )
    return cases


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_case(case: InputCase, out_dir: Path, config: Any, args: argparse.Namespace) -> dict[str, Any]:
    case_out = out_dir / case.case_id
    evidence_dir = case_out / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    base_row: dict[str, Any] = {
        "case": case.case_id,
        "sourcePath": str(case.source_path),
        "sha256": case.sha256,
        "duplicateCount": len(case.duplicate_paths),
        "duplicatePaths": [str(path) for path in case.duplicate_paths],
        "ocrPresent": False,
        "ocrTextCount": 0,
        "ocrError": "",
        "dslValid": False,
        "dslErrorCount": 0,
        "failureTypes": [],
    }

    try:
        with Image.open(case.source_path) as image:
            width, height = image.size
        base_row.update({"width": width, "height": height})
    except Exception as exc:
        return finish_failed_case(base_row, case_out, "IMAGE_LOAD_FAILURE", exc)

    ocr_path: Path | None = None
    if not args.skip_ocr:
        try:
            ocr_path = ensure_ocr_artifact(case, evidence_dir, out_dir, config, args)
            ocr_data = json.loads(ocr_path.read_text(encoding="utf-8"))
            blocks = ocr_data.get("blocks", [])
            base_row["ocrPresent"] = True
            base_row["ocrTextCount"] = len(blocks)
        except Exception as exc:
            write_error(evidence_dir / "ocr_error.v1.json", "ocr_error", exc)
            base_row["ocrError"] = f"{type(exc).__name__}: {exc}"
            if args.require_ocr:
                return finish_failed_case(base_row, case_out, "OCR_MISSING", exc)
    else:
        base_row["ocrError"] = "skipped"

    try:
        namespace = argparse.Namespace(
            image=str(case.source_path),
            ocr=str(ocr_path) if ocr_path else "",
            out=str(case_out),
            allow_missing_ocr=True,
            tile_size=args.tile_size,
            text_padding=3,
            ocr_min_confidence=config.ocr.min_confidence,
            raster_threshold=0.42,
            shape_threshold=0.62,
            raster_min_area=512,
            shape_min_area=1200,
            surface_min_area=2400,
            max_text_overlap=0.24,
        )
        layer_stack = run_psd_like(namespace)
        dsl_path = case_out / "draft_runtime.dsl.v1_0.json"
        dsl_valid, dsl_errors = validate_basic_dsl(dsl_path, case_out)
        diagnostics = layer_stack.get("diagnostics", {})
        visual_metrics = compute_visual_metrics(case.source_path, case_out / "draft_preview.png")
        row = {
            **base_row,
            "textLayerCount": diagnostics.get("textLayerCount", 0),
            "rasterLayerCount": diagnostics.get("rasterLayerCount", 0),
            "shapeLayerCount": diagnostics.get("shapeLayerCount", 0),
            "surfaceShapeLayerCount": diagnostics.get("surfaceShapeLayerCount", 0),
            "controlSurfaceShapeLayerCount": diagnostics.get("controlSurfaceShapeLayerCount", 0),
            "ocrAnchoredControlSurfaceCount": diagnostics.get("ocrAnchoredControlSurfaceCount", 0),
            "controlOwnedRasterSuppressedCount": diagnostics.get("controlOwnedRasterSuppressedCount", 0),
            "controlResidualSuppressedCount": diagnostics.get("controlResidualSuppressedCount", 0),
            "textOwnedRasterSuppressedCount": diagnostics.get("textOwnedRasterSuppressedCount", 0),
            "shapeAssetCount": diagnostics.get("shapeAssetCount", 0),
            "foregroundObjectCount": count_reason(layer_stack, "foreground_object_on_surface"),
            "assetCount": count_assets(dsl_path),
            "missingAssetCount": diagnostics.get("missingAssetCount", 0),
            "tinyRasterFragments": diagnostics.get("tinyRasterFragments", 0),
            "fullPageVisibleRaster": diagnostics.get("fullPageVisibleRaster", 0),
            "textOverlapRaster": diagnostics.get("textOverlapRaster", 0),
            "rawTextOverlapRaster": diagnostics.get("rawTextOverlapRaster", 0),
            "rasterTextKnockoutCount": diagnostics.get("rasterTextKnockoutCount", 0),
            "rasterCoveredTextBlockCount": diagnostics.get("rasterCoveredTextBlockCount", 0),
            "rejectedCandidateCount": diagnostics.get("rejectedCandidateCount", 0),
            "dslValid": dsl_valid,
            "dslErrorCount": len(dsl_errors),
            "dslErrors": dsl_errors[:20],
            **visual_metrics,
        }
        row["failureTypes"] = classify_failures(row, args)
        return row
    except Exception as exc:
        return finish_failed_case(base_row, case_out, "PIPELINE_EXCEPTION", exc)


def ensure_ocr_artifact(
    case: InputCase,
    evidence_dir: Path,
    out_dir: Path,
    config: Any,
    args: argparse.Namespace,
) -> Path:
    cache_dir = Path(args.ocr_cache_dir).expanduser().resolve() if args.ocr_cache_dir else out_dir / "ocr_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{case.sha256}.ocr_blocks.v1.json"
    local = evidence_dir / "ocr_blocks.v1.json"
    if cached.exists():
        local.write_text(cached.read_text(encoding="utf-8"), encoding="utf-8")
        return local

    if not config.ocr.token:
        raise RuntimeError("BAIDU_PADDLE_OCR_TOKEN is not configured")

    blocks = run_ocr_with_retries(str(case.source_path), config, args)
    artifact = ocr_blocks_artifact(blocks)
    text = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
    cached.write_text(text, encoding="utf-8")
    local.write_text(text, encoding="utf-8")
    return local


def run_ocr_with_retries(image_path: str, config: Any, args: argparse.Namespace) -> list[TextBlock]:
    attempts = max(1, int(args.ocr_retries))
    delay = max(0.0, float(args.ocr_retry_delay))
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return asyncio.run(run_ocr(image_path, config.ocr))
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            time.sleep(delay * attempt)
    assert last_exc is not None
    raise last_exc


def ocr_blocks_artifact(blocks: list[TextBlock]) -> dict[str, Any]:
    return {
        "version": "ocr_blocks.v1",
        "blocks": [
            {
                "id": block.id,
                "text": block.text,
                "bbox": block.bbox.to_dict(),
                "confidence": block.confidence,
                "source": block.source,
            }
            for block in blocks
        ],
    }


def validate_basic_dsl(path: Path, case_out: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not path.exists():
        return False, ["dsl_missing"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"dsl_parse_error:{type(exc).__name__}:{exc}"]

    if data.get("version") != "1.0":
        errors.append("version_not_1_0")
    if data.get("kind") != "draft_runtime":
        errors.append("kind_not_draft_runtime")

    asset_ids = {item.get("assetId") for item in data.get("assets", [])}
    asset_paths = {item.get("assetId"): item.get("path") or item.get("url") for item in data.get("assets", [])}
    for child in data.get("root", {}).get("children", []):
        if child.get("type") != "image":
            continue
        asset_id = child.get("image", {}).get("assetId")
        if not asset_id:
            errors.append(f"{child.get('id')}:image_asset_missing")
            continue
        if asset_id not in asset_ids:
            errors.append(f"{child.get('id')}:image_asset_unknown:{asset_id}")
            continue
        asset_ref = asset_paths.get(asset_id)
        if asset_ref and not (case_out / str(asset_ref)).exists():
            errors.append(f"{child.get('id')}:asset_file_missing:{asset_ref}")
    return len(errors) == 0, errors


def count_assets(dsl_path: Path) -> int:
    if not dsl_path.exists():
        return 0
    data = json.loads(dsl_path.read_text(encoding="utf-8"))
    return len(data.get("assets", []))


def compute_visual_metrics(source_path: Path, draft_path: Path) -> dict[str, float]:
    if not source_path.exists() or not draft_path.exists():
        return {
            "visualMae": 0.0,
            "visualDiff30Ratio": 0.0,
            "visualDiff60Ratio": 0.0,
        }
    with Image.open(source_path) as source, Image.open(draft_path) as draft:
        source_rgb = source.convert("RGB")
        draft_rgb = draft.convert("RGB")
        if draft_rgb.size != source_rgb.size:
            draft_rgb = draft_rgb.resize(source_rgb.size)
        source_arr = np.asarray(source_rgb).astype(np.int16)
        draft_arr = np.asarray(draft_rgb).astype(np.int16)
        diff = np.abs(source_arr - draft_arr).mean(axis=2)
    return {
        "visualMae": round(float(diff.mean()), 4),
        "visualDiff30Ratio": round(float((diff > 30).mean()), 4),
        "visualDiff60Ratio": round(float((diff > 60).mean()), 4),
    }


def count_reason(layer_stack: dict[str, Any], reason: str) -> int:
    return sum(1 for layer in layer_stack.get("layers", []) if layer.get("reason") == reason)


def classify_failures(row: dict[str, Any], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    if not row.get("ocrPresent"):
        failures.append("OCR_MISSING")
    if not row.get("dslValid"):
        failures.append("DSL_INVALID")
    if int(row.get("fullPageVisibleRaster", 0)) > 0:
        failures.append("FULL_PAGE_BACKING")
    if int(row.get("missingAssetCount", 0)) > 0:
        failures.append("MISSING_ASSET")
    if int(row.get("shapeAssetCount", 0)) > 0:
        failures.append("SHAPE_ASSET")
    if int(row.get("textOverlapRaster", 0)) > 0:
        failures.append("TEXT_DUPLICATED")
    if int(row.get("rasterLayerCount", 0)) > args.max_rasters:
        failures.append("ASSET_EXPLOSION")
    if int(row.get("tinyRasterFragments", 0)) > args.max_tiny_rasters:
        failures.append("TINY_FRAGMENT_EXPLOSION")
    return failures


def finish_failed_case(row: dict[str, Any], case_out: Path, failure_type: str, exc: Exception) -> dict[str, Any]:
    case_out.mkdir(parents=True, exist_ok=True)
    write_error(case_out / "case_error.v1.json", failure_type, exc)
    row["failureTypes"] = sorted(set([*row.get("failureTypes", []), failure_type]))
    row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def write_error(path: Path, kind: str, exc: Exception) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": "psd_like_batch_error.v1",
                "kind": kind,
                "errorType": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_outputs(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    summary = {
        "version": "psd_like_batch_eval_summary.v1",
        "caseCount": len(rows),
        "failureCaseCount": sum(1 for row in rows if row.get("failureTypes")),
        "failureTypeCounts": count_failure_types(rows),
        "rows": rows,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_summary_md(out_dir / "summary.md", rows)
    write_failure_ledger(out_dir / "failure_ledger.md", rows)


def count_failure_types(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for failure in row.get("failureTypes", []):
            counts[failure] = counts.get(failure, 0) + 1
    return dict(sorted(counts.items()))


def write_summary_md(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# PSD-like Batch Eval",
        "",
        f"- cases: {len(rows)}",
        f"- failed cases: {sum(1 for row in rows if row.get('failureTypes'))}",
        f"- failure types: `{json.dumps(count_failure_types(rows), ensure_ascii=False)}`",
        "",
        "| case | size | ocr | text | raster | shape | ctrl | ocrCtrl | ctrlSup | txtSup | surface | fg | assets | rawOverlap | knockout | coveredText | visualMae | diff30 | dsl | failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "|{case}|{width}x{height}|{ocrTextCount}|{textLayerCount}|{rasterLayerCount}|"
            "{shapeLayerCount}|{controlSurfaceShapeLayerCount}|{ocrAnchoredControlSurfaceCount}|{controlOwnedRasterSuppressedCount}|"
            "{textOwnedRasterSuppressedCount}|{surfaceShapeLayerCount}|{foregroundObjectCount}|{assetCount}|"
            "{rawTextOverlapRaster}|{rasterTextKnockoutCount}|{rasterCoveredTextBlockCount}|"
            "{visualMae}|{visualDiff30Ratio}|{dslValid}|{failures}|".format(
                case=row.get("case", ""),
                width=row.get("width", 0),
                height=row.get("height", 0),
                ocrTextCount=row.get("ocrTextCount", 0),
                textLayerCount=row.get("textLayerCount", 0),
                rasterLayerCount=row.get("rasterLayerCount", 0),
                shapeLayerCount=row.get("shapeLayerCount", 0),
                controlSurfaceShapeLayerCount=row.get("controlSurfaceShapeLayerCount", 0),
                ocrAnchoredControlSurfaceCount=row.get("ocrAnchoredControlSurfaceCount", 0),
                controlOwnedRasterSuppressedCount=row.get("controlOwnedRasterSuppressedCount", 0),
                textOwnedRasterSuppressedCount=row.get("textOwnedRasterSuppressedCount", 0),
                surfaceShapeLayerCount=row.get("surfaceShapeLayerCount", 0),
                foregroundObjectCount=row.get("foregroundObjectCount", 0),
                assetCount=row.get("assetCount", 0),
                rawTextOverlapRaster=row.get("rawTextOverlapRaster", 0),
                rasterTextKnockoutCount=row.get("rasterTextKnockoutCount", 0),
                rasterCoveredTextBlockCount=row.get("rasterCoveredTextBlockCount", 0),
                visualMae=row.get("visualMae", 0),
                visualDiff30Ratio=row.get("visualDiff30Ratio", 0),
                dslValid=row.get("dslValid", False),
                failures=", ".join(row.get("failureTypes", [])),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_failure_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# PSD-like Batch Failure Ledger",
        "",
        "| case | failures | suspected owner | source | error |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        failures = row.get("failureTypes", [])
        if not failures:
            continue
        lines.append(
            "|{case}|{failures}|{owner}|`{source}`|{error}|".format(
                case=row.get("case", ""),
                failures=", ".join(failures),
                owner=suspected_owner(failures),
                source=str(row.get("sourcePath", "")).replace("|", "\\|"),
                error=str(row.get("error") or row.get("ocrError") or "").replace("|", "\\|"),
            )
        )
    if len(lines) == 4:
        lines.append("| none | none | none | none | none |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def suspected_owner(failures: list[str]) -> str:
    if "OCR_MISSING" in failures:
        return "ocr/provider"
    if "PIPELINE_EXCEPTION" in failures or "IMAGE_LOAD_FAILURE" in failures:
        return "batch/input"
    if "DSL_INVALID" in failures or "MISSING_ASSET" in failures:
        return "dsl/assets"
    if "FULL_PAGE_BACKING" in failures or "TEXT_DUPLICATED" in failures:
        return "ownership/planner"
    if "ASSET_EXPLOSION" in failures or "TINY_FRAGMENT_EXPLOSION" in failures:
        return "candidate extraction"
    return "unknown"


def write_contact_sheet(path: Path, rows: list[dict[str, Any]], image_name: str) -> None:
    items: list[tuple[str, Image.Image, bool]] = []
    for row in rows:
        case_out = path.parent / str(row.get("case", ""))
        image_path = case_out / image_name
        if not image_path.exists():
            continue
        with Image.open(image_path) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((180, 320))
            items.append((str(row.get("case", "")), thumb.copy(), bool(row.get("failureTypes"))))

    if not items:
        return

    columns = min(6, max(1, math.ceil(math.sqrt(len(items)))))
    cell_w = 210
    cell_h = 360
    rows_count = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image, failed) in enumerate(items):
        x = (index % columns) * cell_w + 12
        y = (index // columns) * cell_h + 28
        color = (180, 30, 30) if failed else (20, 120, 45)
        draw.text((x, y - 20), label, fill=color)
        sheet.paste(image, (x, y))
    sheet.save(path)


def write_source_vs_draft_contact_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    items: list[tuple[str, Image.Image, Image.Image, bool]] = []
    for row in rows:
        source_path = Path(str(row.get("sourcePath", "")))
        draft_path = path.parent / str(row.get("case", "")) / "draft_preview.png"
        if not source_path.exists() or not draft_path.exists():
            continue
        with Image.open(source_path) as source, Image.open(draft_path) as draft:
            source_thumb = source.convert("RGB")
            draft_thumb = draft.convert("RGB")
            source_thumb.thumbnail((130, 260))
            draft_thumb.thumbnail((130, 260))
            items.append(
                (
                    str(row.get("case", "")),
                    source_thumb.copy(),
                    draft_thumb.copy(),
                    bool(row.get("failureTypes")),
                )
            )

    if not items:
        return

    columns = 4
    cell_w = 300
    cell_h = 330
    rows_count = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, source, draft, failed) in enumerate(items):
        x = (index % columns) * cell_w + 8
        y = (index // columns) * cell_h + 34
        color = (180, 30, 30) if failed else (20, 120, 45)
        draw.text((x, y - 30), label, fill=color)
        draw.text((x, y - 16), "src", fill=(0, 0, 0))
        draw.text((x + 142, y - 16), "draft", fill=(0, 0, 0))
        sheet.paste(source, (x, y))
        sheet.paste(draft, (x + 142, y))
    sheet.save(path)


if __name__ == "__main__":
    main()
