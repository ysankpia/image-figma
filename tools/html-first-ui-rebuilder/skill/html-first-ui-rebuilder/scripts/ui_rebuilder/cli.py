from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .assets import extract_assets
from .diffing import write_report
from .html_builder import build_html
from .planner import create_asset_plan, initialize_run
from .qwen import run_qwen, run_qwen_full
from .sheets import make_sheets
from .paths import RunPaths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ui-rebuilder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--input", required=True, type=Path)
    run_parser.add_argument("--out", required=True, type=Path)
    run_parser.add_argument("--token-env", default="MOARK_API_TOKEN")
    run_parser.add_argument("--fast", action="store_true")
    run_parser.add_argument("--mock-qwen", action="store_true")
    run_parser.add_argument("--no-qwen", action="store_true")
    run_parser.add_argument("--full-page-qwen", action="store_true")
    run_parser.add_argument("--skip-sheet-qwen", action="store_true")
    run_parser.add_argument("--one-roi-per-sheet", action="store_true")
    run_parser.add_argument("--force", action="store_true")

    plan_parser = subparsers.add_parser("plan-assets")
    plan_parser.add_argument("--input", required=True, type=Path)
    plan_parser.add_argument("--out", required=True, type=Path)
    plan_parser.add_argument("--force", action="store_true")

    sheet_parser = subparsers.add_parser("make-sheets")
    sheet_parser.add_argument("--run", required=True, type=Path)
    sheet_parser.add_argument("--max-sheet-side", default=1400, type=int)
    sheet_parser.add_argument("--padding", default=16, type=int)
    sheet_parser.add_argument("--gutter", default=32, type=int)
    sheet_parser.add_argument("--one-roi-per-sheet", action="store_true")
    sheet_parser.add_argument("--force", action="store_true")

    qwen_parser = subparsers.add_parser("qwen")
    qwen_parser.add_argument("--run", required=True, type=Path)
    qwen_parser.add_argument("--token-env", default="MOARK_API_TOKEN")
    qwen_parser.add_argument("--layers", default=4, type=int)
    qwen_parser.add_argument("--steps", default=50, type=int)
    qwen_parser.add_argument("--fast", action="store_true")
    qwen_parser.add_argument("--mock", action="store_true")
    qwen_parser.add_argument("--force", action="store_true")

    qwen_full_parser = subparsers.add_parser("qwen-full")
    qwen_full_parser.add_argument("--run", required=True, type=Path)
    qwen_full_parser.add_argument("--token-env", default="MOARK_API_TOKEN")
    qwen_full_parser.add_argument("--layers", default=4, type=int)
    qwen_full_parser.add_argument("--steps", default=50, type=int)
    qwen_full_parser.add_argument("--fast", action="store_true")
    qwen_full_parser.add_argument("--mock", action="store_true")
    qwen_full_parser.add_argument("--force", action="store_true")

    extract_parser = subparsers.add_parser("extract-assets")
    extract_parser.add_argument("--run", required=True, type=Path)
    extract_parser.add_argument("--no-full-page-components", action="store_true")
    extract_parser.add_argument("--force", action="store_true")

    html_parser = subparsers.add_parser("build-html")
    html_parser.add_argument("--run", required=True, type=Path)
    html_parser.add_argument("--force", action="store_true")

    diff_parser = subparsers.add_parser("diff")
    diff_parser.add_argument("--run", required=True, type=Path)
    diff_parser.add_argument("--rendered", type=Path)

    args = parser.parse_args(argv)
    result = _dispatch(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "run":
        return _run_all(args)
    if args.command == "plan-assets":
        paths = initialize_run(args.input, args.out, force=args.force)
        plan = create_asset_plan(paths, force=args.force)
        return {"ok": True, "run": str(paths.root), "assetPlan": plan}
    if args.command == "make-sheets":
        paths = RunPaths(args.run.resolve())
        manifest = make_sheets(
            paths,
            args.max_sheet_side,
            args.padding,
            args.gutter,
            one_roi_per_sheet=args.one_roi_per_sheet,
            force=args.force,
        )
        return {"ok": True, "run": str(paths.root), "sheetManifest": manifest}
    if args.command == "qwen":
        paths = RunPaths(args.run.resolve())
        steps = 15 if args.fast else args.steps
        manifest = run_qwen(paths, token_env=args.token_env, layers=args.layers, steps=steps, mock=args.mock, force=args.force)
        return {"ok": True, "run": str(paths.root), "qwenManifest": manifest}
    if args.command == "qwen-full":
        paths = RunPaths(args.run.resolve())
        steps = 15 if args.fast else args.steps
        manifest = run_qwen_full(
            paths,
            token_env=args.token_env,
            layers=args.layers,
            steps=steps,
            mock=args.mock,
            force=args.force,
        )
        return {"ok": True, "run": str(paths.root), "qwenFullManifest": manifest}
    if args.command == "extract-assets":
        paths = RunPaths(args.run.resolve())
        manifest = extract_assets(paths, include_full_page_components=not args.no_full_page_components, force=args.force)
        return {"ok": True, "run": str(paths.root), "assetManifest": manifest}
    if args.command == "build-html":
        paths = RunPaths(args.run.resolve())
        result = build_html(paths, force=args.force)
        return {"ok": True, "run": str(paths.root), "html": result}
    if args.command == "diff":
        paths = RunPaths(args.run.resolve())
        result = write_report(paths, args.rendered)
        return {"ok": True, "run": str(paths.root), "report": result}
    raise ValueError(f"unknown command {args.command}")


def _run_all(args: argparse.Namespace) -> dict[str, Any]:
    paths = initialize_run(args.input, args.out, force=args.force)
    plan = create_asset_plan(paths, force=args.force)
    sheets = make_sheets(paths, one_roi_per_sheet=args.one_roi_per_sheet, force=args.force)
    qwen_manifest: dict[str, Any] | None = None
    qwen_full_manifest: dict[str, Any] | None = None
    if not args.no_qwen:
        steps = 15 if args.fast else 50
        use_mock = args.mock_qwen
        if args.full_page_qwen:
            qwen_full_manifest = run_qwen_full(paths, token_env=args.token_env, steps=steps, mock=use_mock, force=args.force)
        if not args.skip_sheet_qwen:
            qwen_manifest = run_qwen(paths, token_env=args.token_env, steps=steps, mock=use_mock, force=args.force)
    assets = extract_assets(paths, force=args.force)
    html_result = build_html(paths, force=args.force)
    report = write_report(paths)
    return {
        "ok": True,
        "run": str(paths.root),
        "usedQwen": bool(qwen_manifest or qwen_full_manifest),
        "qwenTokenPresent": bool(os.environ.get(args.token_env)),
        "assetPlanPath": str(paths.asset_plan_json),
        "sheetManifestPath": str(paths.sheet_manifest_json),
        "qwenFullManifestPath": str(paths.qwen_full_manifest_json) if qwen_full_manifest else None,
        "assetManifestPath": str(paths.asset_manifest_json),
        "previewPath": str(paths.preview_html),
        "reportPath": str(paths.report_md),
        "summary": {
            "roiCount": len(plan.get("rois", [])),
            "sheetCount": len(sheets.get("sheets", [])),
            "assetCount": assets.get("summary", {}).get("assetCount"),
            "qwenFullComponentCount": assets.get("summary", {}).get("qwenFullComponentCount"),
            "html": html_result,
            "report": report,
        },
    }
