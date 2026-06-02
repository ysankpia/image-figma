#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path
import sys
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.core.pipeline import PipelineOptions, run_pipeline
from app.ocr_cache import ResolvedOCRArtifact, resolve_or_create_ocr_artifact
from tools._eval_common import (
    InputCase,
    build_cases,
    collect_image_paths,
    compute_visual_metrics,
    count_assets,
    count_reason,
    cases_from_manifest,
    validate_basic_dsl,
    write_contact_sheet,
    write_source_vs_draft_contact_sheet,
)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.manifest:
        manifest_path = Path(args.manifest).expanduser().resolve()
        cases = cases_from_manifest(manifest_path)
        input_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        input_dir = Path(args.input_dir).expanduser().resolve()
        paths = collect_image_paths(input_dir)
        cases = build_cases(paths, dedupe=not args.no_dedupe)
        input_manifest = {
            "version": "psdlike_python_service_input_manifest.v1",
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
        json.dumps(input_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.limit:
        cases = cases[: args.limit]

    print(f"PSD-like Python batch: cases={len(cases)} out={out_dir}", flush=True)
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        started = time.monotonic()
        print(f"[{index}/{len(cases)}] {case.case_id} {case.source_path}", flush=True)
        row = run_case(case, out_dir, args)
        row["runtimeSeconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        write_outputs(out_dir, rows)

    write_contact_sheet(out_dir / "draft_preview_contact_sheet.png", rows, "draft_preview.png")
    write_contact_sheet(out_dir / "overlay_contact_sheet.png", rows, "overlay.png")
    write_source_vs_draft_contact_sheet(out_dir / "source_vs_draft_contact_sheet.png", rows)
    print(f"done: {out_dir / 'summary.md'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-evaluate clean PSD-like Python service.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", default="", help="Input manifest created by PSD-like batch eval.")
    source.add_argument("--input-dir", default="", help="Directory containing screenshots/images.")
    parser.add_argument("--out", required=True, help="Output directory for batch artifacts.")
    parser.add_argument("--limit", type=int, default=0, help="Limit cases. 0 means all.")
    parser.add_argument("--no-dedupe", action="store_true", help="When using --input-dir, evaluate every image path.")
    parser.add_argument("--ocr-cache-dir", default="", help="Directory containing <sha>.ocr_blocks.v1.json artifacts.")
    parser.add_argument(
        "--model-evidence-root",
        default="",
        help="Directory containing <caseId>/model_evidence.v1.json artifacts.",
    )
    parser.add_argument("--require-ocr", action="store_true", help="Fail when OCR cache artifact is missing.")
    parser.add_argument("--max-rasters", type=int, default=60)
    parser.add_argument("--max-tiny-rasters", type=int, default=10)
    parser.add_argument("--tile-size", type=int, default=8)
    return parser.parse_args()


def run_case(case: InputCase, out_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    case_out = out_dir / case.case_id
    case_out.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "case": case.case_id,
        "sourcePath": str(case.source_path),
        "sha256": case.sha256,
        "duplicateCount": len(case.duplicate_paths),
        "duplicatePaths": [str(path) for path in case.duplicate_paths],
        "ocrPresent": False,
        "ocrTextCount": 0,
        "ocrProvider": "",
        "ocrCacheHit": False,
        "ocrElapsedSeconds": 0,
        "ocrArtifactPath": "",
        "ocrError": "",
        "modelEvidencePresent": False,
        "modelDetectionCount": 0,
        "modelControlDetectionCount": 0,
        "modelMediaDetectionCount": 0,
        "modelOcrOverlapRiskCount": 0,
        "semanticTagCount": 0,
        "modelEvidenceIgnoredReason": "",
        "dslValid": False,
        "dslErrorCount": 0,
        "failureTypes": [],
    }
    try:
        with Image.open(case.source_path) as image:
            row.update({"width": image.width, "height": image.height})
    except Exception as exc:
        return finish_failed_case(row, case_out, "IMAGE_LOAD_FAILURE", exc)

    ocr_resolution = resolve_case_ocr(case, case_out, args)
    ocr_path = ocr_resolution.path
    row.update(ocr_resolution.diagnostics)
    if ocr_path is None:
        row["ocrError"] = row.get("ocrError") or "missing"
        if args.require_ocr:
            return finish_failed_case(row, case_out, "OCR_MISSING", FileNotFoundError(case.sha256))
    else:
        row["ocrPresent"] = True
        try:
            ocr_data = json.loads(ocr_path.read_text(encoding="utf-8"))
            row["ocrTextCount"] = len(ocr_data.get("blocks", []))
        except Exception as exc:
            row["ocrError"] = f"{type(exc).__name__}: {exc}"

    try:
        result = run_pipeline(
            image_path=case.source_path,
            ocr_path=ocr_path,
            out_dir=case_out,
            allow_missing_ocr=not args.require_ocr,
            options=PipelineOptions(tile_size=args.tile_size),
            task_id=case.case_id,
            model_evidence_path=find_model_evidence_path(case, args),
            ocr_diagnostics=ocr_resolution.diagnostics,
        )
        layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
        diagnostics = layer_stack.get("diagnostics", {})
        dsl_valid, dsl_errors = validate_basic_dsl(result.dsl_path, case_out)
        row.update(
            {
                "textLayerCount": diagnostics.get("textLayerCount", 0),
                "visibleTextLayerCount": diagnostics.get("visibleTextLayerCount", diagnostics.get("textLayerCount", 0)),
                "mediaOwnedTextBlockCount": diagnostics.get("mediaOwnedTextBlockCount", 0),
                "mediaTextOwnerRasterCount": diagnostics.get("mediaTextOwnerRasterCount", 0),
                "textFitShrinkCount": diagnostics.get("textFitShrinkCount", 0),
                "darkControlSurfaceCount": diagnostics.get("darkControlSurfaceCount", 0),
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
                "assetCount": count_assets(result.dsl_path),
                "missingAssetCount": diagnostics.get("missingAssetCount", 0),
                "tinyRasterFragments": diagnostics.get("tinyRasterFragments", 0),
                "fullPageVisibleRaster": diagnostics.get("fullPageVisibleRaster", 0),
                "textOverlapRaster": diagnostics.get("textOverlapRaster", 0),
                "rawTextOverlapRaster": diagnostics.get("rawTextOverlapRaster", 0),
                "rasterTextKnockoutCount": diagnostics.get("rasterTextKnockoutCount", 0),
                "rasterCoveredTextBlockCount": diagnostics.get("rasterCoveredTextBlockCount", 0),
                "ocrProvider": diagnostics.get("ocrProvider", row.get("ocrProvider", "")),
                "ocrCacheHit": diagnostics.get("ocrCacheHit", row.get("ocrCacheHit", False)),
                "ocrElapsedSeconds": diagnostics.get("ocrElapsedSeconds", row.get("ocrElapsedSeconds", 0)),
                "ocrArtifactPath": diagnostics.get("ocrArtifactPath", row.get("ocrArtifactPath", "")),
                "ocrError": diagnostics.get("ocrError", row.get("ocrError", "")),
                "modelEvidencePresent": diagnostics.get("modelEvidencePresent", False),
                "modelDetectionCount": diagnostics.get("modelDetectionCount", 0),
                "modelControlDetectionCount": diagnostics.get("modelControlDetectionCount", 0),
                "modelMediaDetectionCount": diagnostics.get("modelMediaDetectionCount", 0),
                "modelOcrOverlapRiskCount": diagnostics.get("modelOcrOverlapRiskCount", 0),
                "semanticTagCount": diagnostics.get("semanticTagCount", 0),
                "modelEvidenceIgnoredReason": diagnostics.get("modelEvidenceIgnoredReason", ""),
                "rejectedCandidateCount": diagnostics.get("rejectedCandidateCount", 0),
                "dslValid": dsl_valid,
                "dslErrorCount": len(dsl_errors),
                "dslErrors": dsl_errors[:20],
                **compute_visual_metrics(case.source_path, case_out / "draft_preview.png"),
            }
        )
        row["failureTypes"] = classify_failures(row, args)
        return row
    except Exception as exc:
        return finish_failed_case(row, case_out, "PIPELINE_EXCEPTION", exc)


def find_ocr_path(case: InputCase, args: argparse.Namespace) -> Path | None:
    if not args.ocr_cache_dir:
        return None
    path = Path(args.ocr_cache_dir).expanduser().resolve() / f"{case.sha256}.ocr_blocks.v1.json"
    return path if path.exists() else None


def resolve_case_ocr(case: InputCase, case_out: Path, args: argparse.Namespace) -> ResolvedOCRArtifact:
    cached = find_ocr_path(case, args)
    if cached is not None:
        data = read_ocr_artifact(cached)
        blocks = data.get("blocks", []) if isinstance(data, dict) else []
        return ResolvedOCRArtifact(
            path=cached,
            diagnostics={
                "ocrProvider": data.get("provider") or data.get("meta", {}).get("provider") or "cache",
                "ocrPresent": True,
                "ocrTextCount": len(blocks) if isinstance(blocks, list) else 0,
                "ocrCacheHit": True,
                "ocrElapsedSeconds": 0.0,
                "ocrError": "",
                "ocrArtifactPath": str(cached),
            },
        )
    if args.ocr_cache_dir:
        return ResolvedOCRArtifact(
            path=None,
            diagnostics={
                "ocrProvider": "",
                "ocrPresent": False,
                "ocrTextCount": 0,
                "ocrCacheHit": False,
                "ocrElapsedSeconds": 0.0,
                "ocrError": "missing",
                "ocrArtifactPath": "",
            },
        )
    settings = get_settings()
    return resolve_or_create_ocr_artifact(
        image_path=case.source_path,
        task_ocr_path=case_out / "input.ocr_blocks.v1.json",
        settings=settings,
        require_ocr=args.require_ocr,
    )


def read_ocr_artifact(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def find_model_evidence_path(case: InputCase, args: argparse.Namespace) -> Path | None:
    if not args.model_evidence_root:
        return None
    path = Path(args.model_evidence_root).expanduser().resolve() / case.case_id / "model_evidence.v1.json"
    return path if path.exists() else None


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
    (case_out / "case_error.v1.json").write_text(
        json.dumps(
            {
                "version": "psdlike_python_batch_error.v1",
                "kind": failure_type,
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
    row["failureTypes"] = sorted(set([*row.get("failureTypes", []), failure_type]))
    row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def write_outputs(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    summary = {
        "version": "psdlike_python_batch_eval_summary.v1",
        "caseCount": len(rows),
        "failureCaseCount": sum(1 for row in rows if row.get("failureTypes")),
        "failureTypeCounts": count_failure_types(rows),
        "rows": rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        "# PSD-like Python Service Batch Eval",
        "",
        f"- cases: {len(rows)}",
        f"- failed cases: {sum(1 for row in rows if row.get('failureTypes'))}",
        f"- failure types: `{json.dumps(count_failure_types(rows), ensure_ascii=False)}`",
        "",
        "| case | size | ocr | ocrProvider | ocrCache | ocrSec | text | mediaText | fitShrink | darkCtrl | raster | shape | ctrl | ocrCtrl | ctrlSup | txtSup | surface | fg | assets | rawOverlap | knockout | model | semTags | risk | visualMae | diff30 | dsl | failures |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "|{case}|{width}x{height}|{ocrTextCount}|{ocrProvider}|{ocrCacheHit}|{ocrElapsedSeconds}|"
            "{textLayerCount}|{mediaOwnedTextBlockCount}|"
            "{textFitShrinkCount}|{darkControlSurfaceCount}|{rasterLayerCount}|{shapeLayerCount}|"
            "{controlSurfaceShapeLayerCount}|{ocrAnchoredControlSurfaceCount}|{controlOwnedRasterSuppressedCount}|"
            "{textOwnedRasterSuppressedCount}|{surfaceShapeLayerCount}|{foregroundObjectCount}|{assetCount}|"
            "{rawTextOverlapRaster}|{rasterTextKnockoutCount}|{modelDetectionCount}|{semanticTagCount}|"
            "{modelOcrOverlapRiskCount}|{visualMae}|{visualDiff30Ratio}|{dslValid}|{failures}|".format(
                case=row.get("case", ""),
                width=row.get("width", 0),
                height=row.get("height", 0),
                ocrTextCount=row.get("ocrTextCount", 0),
                ocrProvider=row.get("ocrProvider", ""),
                ocrCacheHit=row.get("ocrCacheHit", False),
                ocrElapsedSeconds=row.get("ocrElapsedSeconds", 0),
                textLayerCount=row.get("textLayerCount", 0),
                mediaOwnedTextBlockCount=row.get("mediaOwnedTextBlockCount", 0),
                textFitShrinkCount=row.get("textFitShrinkCount", 0),
                darkControlSurfaceCount=row.get("darkControlSurfaceCount", 0),
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
                modelDetectionCount=row.get("modelDetectionCount", 0),
                semanticTagCount=row.get("semanticTagCount", 0),
                modelOcrOverlapRiskCount=row.get("modelOcrOverlapRiskCount", 0),
                visualMae=row.get("visualMae", 0),
                visualDiff30Ratio=row.get("visualDiff30Ratio", 0),
                dslValid=row.get("dslValid", False),
                failures=", ".join(row.get("failureTypes", [])),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_failure_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# PSD-like Python Service Batch Failure Ledger",
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
        return "ocr/artifact"
    if "PIPELINE_EXCEPTION" in failures or "IMAGE_LOAD_FAILURE" in failures:
        return "pipeline/input"
    if "DSL_INVALID" in failures or "MISSING_ASSET" in failures:
        return "dsl/assets"
    if "FULL_PAGE_BACKING" in failures or "TEXT_DUPLICATED" in failures:
        return "ownership/planner"
    if "ASSET_EXPLOSION" in failures or "TINY_FRAGMENT_EXPLOSION" in failures:
        return "candidate extraction"
    return "unknown"


if __name__ == "__main__":
    main()
