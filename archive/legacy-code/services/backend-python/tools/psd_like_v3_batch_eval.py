#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import load_config, load_dotenv_local
from tools.psd_like_batch_eval import (
    InputCase,
    build_cases,
    classify_failures,
    collect_image_paths,
    compute_visual_metrics,
    count_assets,
    count_reason,
    ensure_ocr_artifact,
    finish_failed_case,
    validate_basic_dsl,
    write_error,
)
from tools.psd_like_layer_decomposition_experiment import run as run_v1
from tools.psd_like_v3_deki_yolo_experiment import run as run_v3


def main() -> None:
    args = parse_args()
    load_dotenv_local()

    input_dir = Path(args.input_dir).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = collect_image_paths(input_dir)
    cases = build_cases(paths, dedupe=not args.no_dedupe)
    if args.limit:
        cases = cases[: args.limit]
    deki_python = resolve_deki_python(str(args.deki_python))
    manifest = {
        "version": "psd_like_v3_ab_input.v1",
        "inputDir": str(input_dir),
        "pathCount": len(paths),
        "caseCount": len(cases),
        "dedupe": not args.no_dedupe,
        "dekiModel": str(Path(args.deki_model).expanduser()),
        "dekiPython": deki_python,
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
    (out_dir / "input_manifest.v1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"PSD-like V3 A/B eval: paths={len(paths)} cases={len(cases)} "
        f"dedupe={not args.no_dedupe} out={out_dir}",
        flush=True,
    )

    config = load_config()
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        started = time.monotonic()
        print(f"[{index}/{len(cases)}] {case.case_id} {case.source_path}", flush=True)
        row = run_ab_case(case, out_dir, config, args)
        row["runtimeSeconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        write_outputs(out_dir, rows)

    write_contact_sheet(out_dir / "source_v1_v3_contact_sheet.png", rows)
    print(f"done: {out_dir / 'ab_summary.md'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V1 vs V3 Deki YOLO PSD-like A/B batch evaluation.")
    parser.add_argument("--input-dir", required=True, help="Directory containing screenshots/images.")
    parser.add_argument("--out", required=True, help="Output directory for A/B artifacts.")
    parser.add_argument("--deki-model", default="/Volumes/WorkDrive/Models/deki-yolo.pt", help="Path to deki-yolo.pt.")
    parser.add_argument(
        "--deki-python",
        default="",
        help="Python interpreter that has ultralytics installed. Defaults to DEKI_PYTHON or ~/.asdf/shims/python3.",
    )
    parser.add_argument("--deki-confidence", type=float, default=0.25, help="YOLO export confidence.")
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


def run_ab_case(case: InputCase, out_dir: Path, config: Any, args: argparse.Namespace) -> dict[str, Any]:
    case_root = out_dir / case.case_id
    evidence_dir = case_root / "evidence"
    v1_out = case_root / "v1"
    v3_out = case_root / "v3"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    v1_out.mkdir(parents=True, exist_ok=True)
    v3_out.mkdir(parents=True, exist_ok=True)

    base_row: dict[str, Any] = {
        "case": case.case_id,
        "sourcePath": str(case.source_path),
        "sha256": case.sha256,
        "duplicateCount": len(case.duplicate_paths),
        "duplicatePaths": [str(path) for path in case.duplicate_paths],
        "ocrPresent": False,
        "ocrTextCount": 0,
        "ocrError": "",
    }

    try:
        with Image.open(case.source_path) as image:
            width, height = image.size
        base_row.update({"width": width, "height": height})
    except Exception as exc:
        failed = finish_failed_case(base_row, case_root, "IMAGE_LOAD_FAILURE", exc)
        return {"case": case.case_id, "sourcePath": str(case.source_path), "v1": failed, "v3": failed, "delta": {}}

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
                failed = finish_failed_case(base_row, case_root, "OCR_MISSING", exc)
                return {"case": case.case_id, "sourcePath": str(case.source_path), "v1": failed, "v3": failed, "delta": {}}
    else:
        base_row["ocrError"] = "skipped"

    deki_json = evidence_dir / "deki_yolo_candidates.v1.json"
    deki_error = ""
    try:
        export_deki_yolo(case.source_path, deki_json, args)
    except Exception as exc:
        deki_error = f"{type(exc).__name__}: {exc}"
        write_error(evidence_dir / "deki_yolo_error.v1.json", "deki_yolo_error", exc)

    v1_row = run_pipeline_case(
        base_row=base_row,
        case=case,
        output_dir=v1_out,
        ocr_path=ocr_path,
        config=config,
        args=args,
        version="v1",
        deki_path=None,
    )
    v3_row = run_pipeline_case(
        base_row=base_row,
        case=case,
        output_dir=v3_out,
        ocr_path=ocr_path,
        config=config,
        args=args,
        version="v3",
        deki_path=deki_json if deki_json.exists() else None,
    )
    v3_row["dekiError"] = deki_error
    if deki_error:
        v3_row["failureTypes"] = sorted(set([*v3_row.get("failureTypes", []), "DEKI_EXPORT_FAILURE"]))

    return {
        "case": case.case_id,
        "sourcePath": str(case.source_path),
        "sha256": case.sha256,
        "width": width,
        "height": height,
        "ocrTextCount": base_row["ocrTextCount"],
        "v1": v1_row,
        "v3": v3_row,
        "delta": compute_delta(v1_row, v3_row),
    }


def export_deki_yolo(image_path: Path, output_path: Path, args: argparse.Namespace) -> None:
    model_path = Path(args.deki_model).expanduser().resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"Deki YOLO model not found: {model_path}")
    script = Path(__file__).resolve().parent / "deki_yolo_export.py"
    deki_python = resolve_deki_python(str(args.deki_python))
    command = [
        deki_python,
        str(script),
        "--model",
        str(model_path),
        "--image",
        str(image_path),
        "--out",
        str(output_path),
        "--confidence",
        str(args.deki_confidence),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    (output_path.parent / "deki_yolo_export.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (output_path.parent / "deki_yolo_export.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"deki_yolo_export failed with code {result.returncode}: {result.stderr[-1000:]}")


def resolve_deki_python(value: str) -> str:
    if value.strip():
        return str(Path(value).expanduser())
    candidate = Path.home() / ".asdf" / "shims" / "python3"
    if candidate.exists():
        return str(candidate)
    return "python3"


def run_pipeline_case(
    base_row: dict[str, Any],
    case: InputCase,
    output_dir: Path,
    ocr_path: Path | None,
    config: Any,
    args: argparse.Namespace,
    version: str,
    deki_path: Path | None,
) -> dict[str, Any]:
    row = dict(base_row)
    try:
        namespace = argparse.Namespace(
            image=str(case.source_path),
            ocr=str(ocr_path) if ocr_path else "",
            deki_json=str(deki_path) if deki_path else "",
            out=str(output_dir),
            allow_missing_ocr=True,
            allow_missing_deki=True,
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
        if version == "v3":
            layer_stack = run_v3(namespace)
            dsl_path = output_dir / "draft_runtime.v3.dsl.v1_0.json"
            preview_path = output_dir / "draft_preview.v3.png"
        else:
            layer_stack = run_v1(namespace)
            dsl_path = output_dir / "draft_runtime.dsl.v1_0.json"
            preview_path = output_dir / "draft_preview.png"
        dsl_valid, dsl_errors = validate_basic_dsl(dsl_path, output_dir)
        diagnostics = layer_stack.get("diagnostics", {})
        visual_metrics = compute_visual_metrics(case.source_path, preview_path)
        result = {
            **row,
            "textLayerCount": diagnostics.get("textLayerCount", 0),
            "rasterLayerCount": diagnostics.get("rasterLayerCount", 0),
            "shapeLayerCount": diagnostics.get("shapeLayerCount", 0),
            "surfaceShapeLayerCount": diagnostics.get("surfaceShapeLayerCount", 0),
            "foregroundObjectCount": count_reason(layer_stack, "foreground_object_on_surface"),
            "assetCount": count_assets(dsl_path),
            "missingAssetCount": diagnostics.get("missingAssetCount", 0),
            "tinyRasterFragments": diagnostics.get("tinyRasterFragments", 0),
            "fullPageVisibleRaster": diagnostics.get("fullPageVisibleRaster", 0),
            "textOverlapRaster": diagnostics.get("textOverlapRaster", 0),
            "rawTextOverlapRaster": diagnostics.get("rawTextOverlapRaster", 0),
            "rasterTextKnockoutCount": diagnostics.get("rasterTextKnockoutCount", 0),
            "rasterCoveredTextBlockCount": diagnostics.get("rasterCoveredTextBlockCount", 0),
            "controlSurfaceShapeLayerCount": diagnostics.get("controlSurfaceShapeLayerCount", 0),
            "dekiCandidateCount": diagnostics.get("dekiCandidateCount", 0),
            "dekiViewCandidateCount": diagnostics.get("dekiViewCandidateCount", 0),
            "dekiImageViewCandidateCount": diagnostics.get("dekiImageViewCandidateCount", 0),
            "dekiTextDiagnosticCount": diagnostics.get("dekiTextDiagnosticCount", 0),
            "dekiLineDiagnosticCount": diagnostics.get("dekiLineDiagnosticCount", 0),
            "dekiViewShapePassCount": diagnostics.get("dekiViewShapePassCount", 0),
            "dekiViewShapeAcceptedCount": diagnostics.get("dekiViewShapeAcceptedCount", 0),
            "dekiImageViewRasterPassCount": diagnostics.get("dekiImageViewRasterPassCount", 0),
            "dekiImageViewRasterAcceptedCount": diagnostics.get("dekiImageViewRasterAcceptedCount", 0),
            "dslValid": dsl_valid,
            "dslErrorCount": len(dsl_errors),
            "dslErrors": dsl_errors[:20],
            **visual_metrics,
        }
        result["failureTypes"] = classify_failures(result, args)
        if result.get("textLayerCount") != row.get("ocrTextCount"):
            result["failureTypes"] = sorted(set([*result["failureTypes"], "TEXT_COUNT_MISMATCH"]))
        return result
    except Exception as exc:
        write_error(output_dir / f"{version}_case_error.v1.json", f"{version}_PIPELINE_EXCEPTION", exc)
        failed = dict(row)
        failed["failureTypes"] = [f"{version.upper()}_PIPELINE_EXCEPTION"]
        failed["error"] = f"{type(exc).__name__}: {exc}"
        failed["traceback"] = traceback.format_exc()
        return failed


def compute_delta(v1: dict[str, Any], v3: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "rasterLayerCount",
        "shapeLayerCount",
        "assetCount",
        "rawTextOverlapRaster",
        "rasterTextKnockoutCount",
        "tinyRasterFragments",
        "visualMae",
        "visualDiff30Ratio",
    ]
    delta = {key: round(float(v3.get(key, 0)) - float(v1.get(key, 0)), 4) for key in keys}
    delta["improved"] = is_improved(v1, v3)
    delta["regressed"] = is_regressed(v1, v3)
    return delta


def is_improved(v1: dict[str, Any], v3: dict[str, Any]) -> bool:
    if not v3.get("dslValid"):
        return False
    knockout_gain = int(v3.get("rasterTextKnockoutCount", 0)) < int(v1.get("rasterTextKnockoutCount", 0))
    overlap_gain = int(v3.get("rawTextOverlapRaster", 0)) <= int(v1.get("rawTextOverlapRaster", 0))
    no_visual_cliff = float(v3.get("visualMae", 0.0)) <= float(v1.get("visualMae", 0.0)) + 0.05
    return knockout_gain and overlap_gain and no_visual_cliff


def is_regressed(v1: dict[str, Any], v3: dict[str, Any]) -> bool:
    if v1.get("dslValid") and not v3.get("dslValid"):
        return True
    if int(v3.get("missingAssetCount", 0)) > int(v1.get("missingAssetCount", 0)):
        return True
    if int(v3.get("fullPageVisibleRaster", 0)) > int(v1.get("fullPageVisibleRaster", 0)):
        return True
    if int(v3.get("rawTextOverlapRaster", 0)) > int(v1.get("rawTextOverlapRaster", 0)):
        return True
    if float(v3.get("visualMae", 0.0)) > float(v1.get("visualMae", 0.0)) + 0.05:
        return True
    return False


def write_outputs(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    summary = {
        "version": "psd_like_v3_ab_summary.v1",
        "caseCount": len(rows),
        "v1": aggregate(rows, "v1"),
        "v3": aggregate(rows, "v3"),
        "improvedCaseCount": sum(1 for row in rows if row.get("delta", {}).get("improved")),
        "regressedCaseCount": sum(1 for row in rows if row.get("delta", {}).get("regressed")),
        "rows": rows,
    }
    (out_dir / "ab_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_summary_md(out_dir / "ab_summary.md", rows, summary)
    write_regression_ledger(out_dir / "regression_ledger.md", rows)


def aggregate(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    subrows = [row.get(key, {}) for row in rows]
    count = max(1, len(subrows))
    numeric_keys = [
        "dslValid",
        "missingAssetCount",
        "fullPageVisibleRaster",
        "textLayerCount",
        "rasterLayerCount",
        "shapeLayerCount",
        "assetCount",
        "rawTextOverlapRaster",
        "rasterTextKnockoutCount",
        "tinyRasterFragments",
        "visualMae",
        "visualDiff30Ratio",
        "dekiCandidateCount",
        "dekiViewCandidateCount",
        "dekiImageViewCandidateCount",
        "dekiTextDiagnosticCount",
        "dekiLineDiagnosticCount",
        "dekiViewShapePassCount",
        "dekiViewShapeAcceptedCount",
        "dekiImageViewRasterPassCount",
        "dekiImageViewRasterAcceptedCount",
    ]
    result: dict[str, Any] = {}
    for item in numeric_keys:
        values = [float(row.get(item, 0)) for row in subrows]
        result[f"{item}Avg"] = round(sum(values) / count, 4)
        result[f"{item}Sum"] = round(sum(values), 4)
    result["failureTypeCounts"] = count_failure_types(subrows)
    return result


def count_failure_types(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for failure in row.get("failureTypes", []):
            counts[failure] = counts.get(failure, 0) + 1
    return dict(sorted(counts.items()))


def write_summary_md(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# PSD-like V3 Deki YOLO A/B Eval",
        "",
        f"- cases: {len(rows)}",
        f"- improved cases: {summary['improvedCaseCount']}",
        f"- regressed cases: {summary['regressedCaseCount']}",
        f"- v1 failures: `{json.dumps(summary['v1']['failureTypeCounts'], ensure_ascii=False)}`",
        f"- v3 failures: `{json.dumps(summary['v3']['failureTypeCounts'], ensure_ascii=False)}`",
        "",
        "| case | size | ocr | v1 raster | v3 raster | v1 shape | v3 shape | v1 assets | v3 assets | v1 overlap | v3 overlap | v1 knockout | v3 knockout | v1 mae | v3 mae | deki view | deki img | delta | v3 failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        v1 = row.get("v1", {})
        v3 = row.get("v3", {})
        delta = row.get("delta", {})
        lines.append(
            "|{case}|{width}x{height}|{ocr}|{v1r}|{v3r}|{v1s}|{v3s}|{v1a}|{v3a}|"
            "{v1o}|{v3o}|{v1k}|{v3k}|{v1m}|{v3m}|{dv}|{di}|{delta}|{failures}|".format(
                case=row.get("case", ""),
                width=row.get("width", 0),
                height=row.get("height", 0),
                ocr=row.get("ocrTextCount", 0),
                v1r=v1.get("rasterLayerCount", 0),
                v3r=v3.get("rasterLayerCount", 0),
                v1s=v1.get("shapeLayerCount", 0),
                v3s=v3.get("shapeLayerCount", 0),
                v1a=v1.get("assetCount", 0),
                v3a=v3.get("assetCount", 0),
                v1o=v1.get("rawTextOverlapRaster", 0),
                v3o=v3.get("rawTextOverlapRaster", 0),
                v1k=v1.get("rasterTextKnockoutCount", 0),
                v3k=v3.get("rasterTextKnockoutCount", 0),
                v1m=v1.get("visualMae", 0),
                v3m=v3.get("visualMae", 0),
                dv=v3.get("dekiViewShapeAcceptedCount", 0),
                di=v3.get("dekiImageViewRasterAcceptedCount", 0),
                delta=("improved" if delta.get("improved") else "regressed" if delta.get("regressed") else "neutral"),
                failures=", ".join(v3.get("failureTypes", [])),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_regression_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# PSD-like V3 Regression Ledger",
        "",
        "| case | symptom | suspected owner | source |",
        "|---|---|---|---|",
    ]
    for row in rows:
        if not row.get("delta", {}).get("regressed"):
            continue
        v1 = row.get("v1", {})
        v3 = row.get("v3", {})
        symptoms = []
        if v1.get("dslValid") and not v3.get("dslValid"):
            symptoms.append("dsl regressed")
        if int(v3.get("rawTextOverlapRaster", 0)) > int(v1.get("rawTextOverlapRaster", 0)):
            symptoms.append("raw text overlap increased")
        if float(v3.get("visualMae", 0.0)) > float(v1.get("visualMae", 0.0)) + 0.05:
            symptoms.append("visualMae increased")
        if int(v3.get("missingAssetCount", 0)) > int(v1.get("missingAssetCount", 0)):
            symptoms.append("missing assets increased")
        lines.append(
            "|{case}|{symptom}|{owner}|`{source}`|".format(
                case=row.get("case", ""),
                symptom=", ".join(symptoms) or "unknown regression",
                owner="v3 candidate ownership/planner",
                source=str(row.get("sourcePath", "")).replace("|", "\\|"),
            )
        )
    if len(lines) == 4:
        lines.append("| none | none | none | none |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contact_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    items: list[tuple[str, Image.Image, Image.Image, Image.Image, bool]] = []
    for row in rows:
        source_path = Path(str(row.get("sourcePath", "")))
        root = path.parent / str(row.get("case", ""))
        v1_path = root / "v1" / "draft_preview.png"
        v3_path = root / "v3" / "draft_preview.v3.png"
        if not source_path.exists() or not v1_path.exists() or not v3_path.exists():
            continue
        with Image.open(source_path) as source, Image.open(v1_path) as v1, Image.open(v3_path) as v3:
            source_thumb = source.convert("RGB")
            v1_thumb = v1.convert("RGB")
            v3_thumb = v3.convert("RGB")
            source_thumb.thumbnail((120, 240))
            v1_thumb.thumbnail((120, 240))
            v3_thumb.thumbnail((120, 240))
            items.append(
                (
                    str(row.get("case", "")),
                    source_thumb.copy(),
                    v1_thumb.copy(),
                    v3_thumb.copy(),
                    bool(row.get("delta", {}).get("regressed")),
                )
            )
    if not items:
        return

    columns = 3
    cell_w = 400
    cell_h = 310
    rows_count = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, source, v1, v3, regressed) in enumerate(items):
        x = (index % columns) * cell_w + 8
        y = (index // columns) * cell_h + 38
        color = (180, 30, 30) if regressed else (20, 120, 45)
        draw.text((x, y - 34), label, fill=color)
        draw.text((x, y - 18), "src", fill=(0, 0, 0))
        draw.text((x + 130, y - 18), "v1", fill=(0, 0, 0))
        draw.text((x + 260, y - 18), "v3", fill=(0, 0, 0))
        sheet.paste(source, (x, y))
        sheet.paste(v1, (x + 130, y))
        sheet.paste(v3, (x + 260, y))
    sheet.save(path)


if __name__ == "__main__":
    main()
