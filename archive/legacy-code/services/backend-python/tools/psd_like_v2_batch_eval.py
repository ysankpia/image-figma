#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
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
    collect_image_paths,
    compute_visual_metrics,
    count_assets,
    count_reason,
    ensure_ocr_artifact,
    validate_basic_dsl,
    write_error,
)
from tools.psd_like_layer_decomposition_experiment import run as run_v1
from tools.psd_like_v2_vector_surface_experiment import run as run_v2


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
    write_input_manifest(out_dir, input_dir, paths, cases, not args.no_dedupe)

    print(
        f"PSD-like v2 A/B eval: paths={len(paths)} cases={len(cases)} "
        f"dedupe={not args.no_dedupe} out={out_dir}",
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    config = load_config()
    for index, case in enumerate(cases, start=1):
        started = time.monotonic()
        print(f"[{index}/{len(cases)}] {case.case_id} {case.source_path}", flush=True)
        row = run_ab_case(case, out_dir, config, args)
        row["runtimeSeconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        write_ab_outputs(out_dir, rows)

    write_source_v1_v2_contact_sheet(out_dir / "source_v1_v2_contact_sheet.png", rows)
    print(f"done: {out_dir / 'ab_summary.md'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A/B evaluate PSD-like v1 against v2 vector-surface pipeline.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-dedupe", action="store_true")
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--require-ocr", action="store_true")
    parser.add_argument("--ocr-cache-dir", default="")
    parser.add_argument("--ocr-retries", type=int, default=3)
    parser.add_argument("--ocr-retry-delay", type=float, default=2.0)
    parser.add_argument("--max-rasters", type=int, default=60)
    parser.add_argument("--max-tiny-rasters", type=int, default=10)
    parser.add_argument("--tile-size", type=int, default=8)
    parser.add_argument("--visual-mae-tolerance", type=float, default=0.05)
    return parser.parse_args()


def write_input_manifest(out_dir: Path, input_dir: Path, paths: list[Path], cases: list[InputCase], dedupe: bool) -> None:
    manifest = {
        "version": "psd_like_v2_ab_input.v1",
        "inputDir": str(input_dir),
        "pathCount": len(paths),
        "caseCount": len(cases),
        "dedupe": dedupe,
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


def run_ab_case(case: InputCase, out_dir: Path, config: Any, args: argparse.Namespace) -> dict[str, Any]:
    v1_out = out_dir / "v1" / case.case_id
    v2_out = out_dir / "v2" / case.case_id
    evidence_dir = out_dir / "evidence" / case.case_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    base: dict[str, Any] = {
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
        base.update({"width": width, "height": height})
    except Exception as exc:
        row = {**base, "v1": failed_pipeline_row("IMAGE_LOAD_FAILURE", exc), "v2": failed_pipeline_row("IMAGE_LOAD_FAILURE", exc)}
        row["comparison"] = compare_rows(row["v1"], row["v2"], args)
        return row

    ocr_path: Path | None = None
    if not args.skip_ocr:
        try:
            ocr_path = ensure_ocr_artifact(case, evidence_dir, out_dir, config, args)
            ocr_data = json.loads(ocr_path.read_text(encoding="utf-8"))
            base["ocrPresent"] = True
            base["ocrTextCount"] = len(ocr_data.get("blocks", []))
        except Exception as exc:
            write_error(evidence_dir / "ocr_error.v1.json", "ocr_error", exc)
            base["ocrError"] = f"{type(exc).__name__}: {exc}"
            if args.require_ocr:
                row = {**base, "v1": failed_pipeline_row("OCR_MISSING", exc), "v2": failed_pipeline_row("OCR_MISSING", exc)}
                row["comparison"] = compare_rows(row["v1"], row["v2"], args)
                return row
    else:
        base["ocrError"] = "skipped"

    v1_row = run_one_pipeline(
        pipeline="v1",
        case=case,
        case_out=v1_out,
        ocr_path=ocr_path,
        config=config,
        args=args,
    )
    v2_row = run_one_pipeline(
        pipeline="v2",
        case=case,
        case_out=v2_out,
        ocr_path=ocr_path,
        config=config,
        args=args,
    )
    return {
        **base,
        "v1": v1_row,
        "v2": v2_row,
        "comparison": compare_rows(v1_row, v2_row, args),
    }


def run_one_pipeline(
    pipeline: str,
    case: InputCase,
    case_out: Path,
    ocr_path: Path | None,
    config: Any,
    args: argparse.Namespace,
) -> dict[str, Any]:
    case_out.mkdir(parents=True, exist_ok=True)
    try:
        if pipeline == "v1":
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
            layer_stack = run_v1(namespace)
            dsl_path = case_out / "draft_runtime.dsl.v1_0.json"
            preview_path = case_out / "draft_preview.png"
        else:
            namespace = argparse.Namespace(
                image=str(case.source_path),
                ocr=str(ocr_path) if ocr_path else "",
                out=str(case_out),
                allow_missing_ocr=True,
                tile_size=args.tile_size,
                text_padding=3,
                ocr_min_confidence=config.ocr.min_confidence,
                vector_min_area=480,
                raster_threshold=0.42,
                raster_min_area=512,
                max_text_overlap=0.04,
            )
            layer_stack = run_v2(namespace)
            dsl_path = case_out / "draft_runtime.v2.dsl.v1_0.json"
            preview_path = case_out / "draft_preview.v2.png"

        dsl_valid, dsl_errors = validate_basic_dsl(dsl_path, case_out)
        diagnostics = layer_stack.get("diagnostics", {})
        visual_metrics = compute_visual_metrics(case.source_path, preview_path)
        row = {
            "dslValid": dsl_valid,
            "dslErrorCount": len(dsl_errors),
            "dslErrors": dsl_errors[:20],
            "textLayerCount": diagnostics.get("textLayerCount", 0),
            "rasterLayerCount": diagnostics.get("rasterLayerCount", 0),
            "shapeLayerCount": diagnostics.get("shapeLayerCount", 0),
            "surfaceShapeLayerCount": diagnostics.get("surfaceShapeLayerCount", 0),
            "controlSurfaceShapeLayerCount": diagnostics.get("controlSurfaceShapeLayerCount", 0),
            "containerSurfaceShapeLayerCount": diagnostics.get("containerSurfaceShapeLayerCount", 0),
            "foregroundObjectCount": count_reason(layer_stack, "foreground_object_on_surface"),
            "assetCount": count_assets(dsl_path),
            "missingAssetCount": diagnostics.get("missingAssetCount", 0),
            "tinyRasterFragments": diagnostics.get("tinyRasterFragments", 0),
            "fullPageVisibleRaster": diagnostics.get("fullPageVisibleRaster", 0),
            "textOverlapRaster": diagnostics.get("textOverlapRaster", 0),
            "rawTextOverlapRaster": diagnostics.get("rawTextOverlapRaster", 0),
            "rasterTextKnockoutCount": diagnostics.get("rasterTextKnockoutCount", 0),
            "rejectedCandidateCount": diagnostics.get("rejectedCandidateCount", 0),
            **visual_metrics,
        }
        row["failureTypes"] = classify_pipeline_failures(row, args)
        return row
    except Exception as exc:
        write_error(case_out / "case_error.v1.json", f"{pipeline}_pipeline_exception", exc)
        return failed_pipeline_row("PIPELINE_EXCEPTION", exc)


def failed_pipeline_row(failure_type: str, exc: Exception) -> dict[str, Any]:
    return {
        "dslValid": False,
        "dslErrorCount": 1,
        "dslErrors": [failure_type],
        "textLayerCount": 0,
        "rasterLayerCount": 0,
        "shapeLayerCount": 0,
        "surfaceShapeLayerCount": 0,
        "controlSurfaceShapeLayerCount": 0,
        "containerSurfaceShapeLayerCount": 0,
        "foregroundObjectCount": 0,
        "assetCount": 0,
        "missingAssetCount": 0,
        "tinyRasterFragments": 0,
        "fullPageVisibleRaster": 0,
        "textOverlapRaster": 0,
        "rawTextOverlapRaster": 0,
        "rasterTextKnockoutCount": 0,
        "rejectedCandidateCount": 0,
        "visualMae": 0.0,
        "visualDiff30Ratio": 0.0,
        "visualDiff60Ratio": 0.0,
        "failureTypes": [failure_type],
        "error": f"{type(exc).__name__}: {exc}",
    }


def classify_pipeline_failures(row: dict[str, Any], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    if not row.get("dslValid"):
        failures.append("DSL_INVALID")
    if int(row.get("fullPageVisibleRaster", 0)) > 0:
        failures.append("FULL_PAGE_BACKING")
    if int(row.get("missingAssetCount", 0)) > 0:
        failures.append("MISSING_ASSET")
    if int(row.get("textOverlapRaster", 0)) > 0:
        failures.append("TEXT_DUPLICATED")
    if int(row.get("rasterLayerCount", 0)) > args.max_rasters:
        failures.append("ASSET_EXPLOSION")
    if int(row.get("tinyRasterFragments", 0)) > args.max_tiny_rasters:
        failures.append("TINY_FRAGMENT_EXPLOSION")
    return failures


def compare_rows(v1: dict[str, Any], v2: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    deltas = {
        "assetCount": int(v2.get("assetCount", 0)) - int(v1.get("assetCount", 0)),
        "rasterLayerCount": int(v2.get("rasterLayerCount", 0)) - int(v1.get("rasterLayerCount", 0)),
        "shapeLayerCount": int(v2.get("shapeLayerCount", 0)) - int(v1.get("shapeLayerCount", 0)),
        "rawTextOverlapRaster": int(v2.get("rawTextOverlapRaster", 0)) - int(v1.get("rawTextOverlapRaster", 0)),
        "rasterTextKnockoutCount": int(v2.get("rasterTextKnockoutCount", 0)) - int(v1.get("rasterTextKnockoutCount", 0)),
        "tinyRasterFragments": int(v2.get("tinyRasterFragments", 0)) - int(v1.get("tinyRasterFragments", 0)),
        "visualMae": round(float(v2.get("visualMae", 0.0)) - float(v1.get("visualMae", 0.0)), 4),
        "visualDiff30Ratio": round(float(v2.get("visualDiff30Ratio", 0.0)) - float(v1.get("visualDiff30Ratio", 0.0)), 4),
    }
    hard_regression = (
        not v2.get("dslValid", False)
        or int(v2.get("missingAssetCount", 0)) > 0
        or int(v2.get("fullPageVisibleRaster", 0)) > 0
        or int(v2.get("rawTextOverlapRaster", 0)) > int(v1.get("rawTextOverlapRaster", 0))
        or int(v2.get("rasterTextKnockoutCount", 0)) > int(v1.get("rasterTextKnockoutCount", 0))
        or int(v2.get("assetCount", 0)) > int(v1.get("assetCount", 0))
    )
    visual_regression = float(deltas["visualMae"]) > float(args.visual_mae_tolerance)
    improved = (
        not hard_regression
        and not visual_regression
        and (
            deltas["rawTextOverlapRaster"] < 0
            or deltas["rasterTextKnockoutCount"] < 0
            or deltas["assetCount"] < 0
            or deltas["tinyRasterFragments"] < 0
        )
    )
    return {
        "deltas": deltas,
        "improved": improved,
        "regressed": bool(hard_regression or visual_regression),
        "hardRegression": bool(hard_regression),
        "visualRegression": bool(visual_regression),
    }


def write_ab_outputs(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    summary = build_ab_summary(rows)
    (out_dir / "ab_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_ab_summary_md(out_dir / "ab_summary.md", rows, summary)
    write_regression_ledger(out_dir / "regression_ledger.md", rows)


def build_ab_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    v1_rows = [row["v1"] for row in rows]
    v2_rows = [row["v2"] for row in rows]
    comparisons = [row["comparison"] for row in rows]
    return {
        "version": "psd_like_v2_ab_summary.v1",
        "caseCount": len(rows),
        "v1": aggregate_pipeline(v1_rows),
        "v2": aggregate_pipeline(v2_rows),
        "comparison": {
            "improvedCases": sum(1 for item in comparisons if item.get("improved")),
            "regressedCases": sum(1 for item in comparisons if item.get("regressed")),
            "hardRegressedCases": sum(1 for item in comparisons if item.get("hardRegression")),
            "visualRegressedCases": sum(1 for item in comparisons if item.get("visualRegression")),
            "avgDelta": aggregate_deltas(comparisons),
        },
        "rows": rows,
    }


def aggregate_pipeline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "textLayerCount",
        "rasterLayerCount",
        "shapeLayerCount",
        "surfaceShapeLayerCount",
        "controlSurfaceShapeLayerCount",
        "assetCount",
        "missingAssetCount",
        "tinyRasterFragments",
        "fullPageVisibleRaster",
        "rawTextOverlapRaster",
        "rasterTextKnockoutCount",
        "visualMae",
        "visualDiff30Ratio",
    ]
    return {
        "dslValidCases": sum(1 for row in rows if row.get("dslValid")),
        "failureTypeCounts": failure_counts(rows),
        **{f"avg{key[0].upper()}{key[1:]}": average(rows, key) for key in keys},
    }


def aggregate_deltas(comparisons: list[dict[str, Any]]) -> dict[str, float]:
    keys = [
        "assetCount",
        "rasterLayerCount",
        "shapeLayerCount",
        "rawTextOverlapRaster",
        "rasterTextKnockoutCount",
        "tinyRasterFragments",
        "visualMae",
        "visualDiff30Ratio",
    ]
    return {key: round(sum(float(item.get("deltas", {}).get(key, 0.0)) for item in comparisons) / max(1, len(comparisons)), 4) for key in keys}


def average(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(row.get(key, 0.0)) for row in rows) / max(1, len(rows)), 4)


def failure_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for failure in row.get("failureTypes", []):
            counts[str(failure)] = counts.get(str(failure), 0) + 1
    return dict(sorted(counts.items()))


def write_ab_summary_md(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# PSD-like v2 A/B Summary",
        "",
        f"- cases: {summary['caseCount']}",
        f"- v1 DSL valid: {summary['v1']['dslValidCases']}/{summary['caseCount']}",
        f"- v2 DSL valid: {summary['v2']['dslValidCases']}/{summary['caseCount']}",
        f"- improved cases: {summary['comparison']['improvedCases']}",
        f"- regressed cases: {summary['comparison']['regressedCases']}",
        f"- hard regressed cases: {summary['comparison']['hardRegressedCases']}",
        f"- visual regressed cases: {summary['comparison']['visualRegressedCases']}",
        f"- avg delta: `{json.dumps(summary['comparison']['avgDelta'], ensure_ascii=False)}`",
        "",
        "| case | size | v1 assets | v2 assets | v1 raw | v2 raw | v1 knockout | v2 knockout | v1 mae | v2 mae | improved | regressed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        v1 = row["v1"]
        v2 = row["v2"]
        cmp = row["comparison"]
        lines.append(
            "|{case}|{width}x{height}|{v1_assets}|{v2_assets}|{v1_raw}|{v2_raw}|{v1_knockout}|{v2_knockout}|{v1_mae}|{v2_mae}|{improved}|{regressed}|".format(
                case=row.get("case", ""),
                width=row.get("width", 0),
                height=row.get("height", 0),
                v1_assets=v1.get("assetCount", 0),
                v2_assets=v2.get("assetCount", 0),
                v1_raw=v1.get("rawTextOverlapRaster", 0),
                v2_raw=v2.get("rawTextOverlapRaster", 0),
                v1_knockout=v1.get("rasterTextKnockoutCount", 0),
                v2_knockout=v2.get("rasterTextKnockoutCount", 0),
                v1_mae=v1.get("visualMae", 0),
                v2_mae=v2.get("visualMae", 0),
                improved=cmp.get("improved", False),
                regressed=cmp.get("regressed", False),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_regression_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# PSD-like v2 Regression Ledger",
        "",
        "| case | regression | deltas | suspected owner | source |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        comparison = row["comparison"]
        if not comparison.get("regressed"):
            continue
        deltas = comparison.get("deltas", {})
        lines.append(
            "|{case}|{kind}|`{deltas}`|{owner}|`{source}`|".format(
                case=row.get("case", ""),
                kind=regression_kind(comparison),
                deltas=json.dumps(deltas, ensure_ascii=False),
                owner=suspected_regression_owner(row),
                source=str(row.get("sourcePath", "")).replace("|", "\\|"),
            )
        )
    if len(lines) == 4:
        lines.append("| none | none | none | none | none |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def regression_kind(comparison: dict[str, Any]) -> str:
    if comparison.get("hardRegression") and comparison.get("visualRegression"):
        return "hard+visual"
    if comparison.get("hardRegression"):
        return "hard"
    if comparison.get("visualRegression"):
        return "visual"
    return "unknown"


def suspected_regression_owner(row: dict[str, Any]) -> str:
    v2 = row.get("v2", {})
    comparison = row.get("comparison", {})
    deltas = comparison.get("deltas", {})
    if not v2.get("dslValid", False) or v2.get("missingAssetCount", 0):
        return "dsl/assets"
    if v2.get("fullPageVisibleRaster", 0) or deltas.get("rawTextOverlapRaster", 0) > 0:
        return "v2 ownership"
    if deltas.get("assetCount", 0) > 0 or deltas.get("tinyRasterFragments", 0) > 0:
        return "v2 raster fallback"
    if deltas.get("visualMae", 0.0) > 0:
        return "v2 shape/raster approximation"
    return "unknown"


def write_source_v1_v2_contact_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    items: list[tuple[str, Image.Image, Image.Image, Image.Image, bool]] = []
    for row in rows:
        source_path = Path(str(row.get("sourcePath", "")))
        v1_path = path.parent / "v1" / str(row.get("case", "")) / "draft_preview.png"
        v2_path = path.parent / "v2" / str(row.get("case", "")) / "draft_preview.v2.png"
        if not source_path.exists() or not v1_path.exists() or not v2_path.exists():
            continue
        with Image.open(source_path) as source, Image.open(v1_path) as v1, Image.open(v2_path) as v2:
            source_thumb = source.convert("RGB")
            v1_thumb = v1.convert("RGB")
            v2_thumb = v2.convert("RGB")
            for image in (source_thumb, v1_thumb, v2_thumb):
                image.thumbnail((120, 240))
            items.append(
                (
                    str(row.get("case", "")),
                    source_thumb.copy(),
                    v1_thumb.copy(),
                    v2_thumb.copy(),
                    bool(row.get("comparison", {}).get("regressed")),
                )
            )

    if not items:
        return

    columns = 3
    cell_w = 410
    cell_h = 310
    rows_count = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, source, v1, v2, regressed) in enumerate(items):
        x = (index % columns) * cell_w + 8
        y = (index // columns) * cell_h + 42
        color = (180, 30, 30) if regressed else (20, 120, 45)
        draw.text((x, y - 34), label, fill=color)
        draw.text((x, y - 18), "src", fill=(0, 0, 0))
        draw.text((x + 132, y - 18), "v1", fill=(0, 0, 0))
        draw.text((x + 264, y - 18), "v2", fill=(0, 0, 0))
        sheet.paste(source, (x, y))
        sheet.paste(v1, (x + 132, y))
        sheet.paste(v2, (x + 264, y))
    sheet.save(path)


if __name__ == "__main__":
    main()
