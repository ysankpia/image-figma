#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.core.pipeline import PipelineOptions, run_pipeline
from app.ocr_cache import copy_uploaded_ocr_artifact, resolve_or_create_ocr_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Run clean PSD-like Python pipeline on one image.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--ocr", default="")
    parser.add_argument("--model-evidence", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--run-ocr", action="store_true", help="Run configured OCR provider when --ocr is absent.")
    parser.add_argument("--ocr-cache-dir", default="", help="Override service OCR cache directory.")
    parser.add_argument("--require-ocr", action="store_true", help="Fail when no OCR artifact can be produced.")
    parser.add_argument("--allow-missing-ocr", action="store_true", help="Allow degraded no-text output when OCR is missing.")
    parser.add_argument("--tile-size", type=int, default=8)
    args = parser.parse_args()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    if args.ocr_cache_dir:
        settings = replace(settings, ocr_cache_dir=Path(args.ocr_cache_dir).expanduser().resolve())

    ocr_path = Path(args.ocr).expanduser().resolve() if args.ocr else None
    ocr_diagnostics: dict = {}
    if ocr_path is not None:
        resolved = copy_uploaded_ocr_artifact(ocr_path, out_dir / "input.ocr_blocks.v1.json")
        ocr_path = resolved.path
        ocr_diagnostics = resolved.diagnostics
    elif args.run_ocr:
        resolved = resolve_or_create_ocr_artifact(
            image_path=Path(args.image).expanduser().resolve(),
            task_ocr_path=out_dir / "input.ocr_blocks.v1.json",
            settings=settings,
            require_ocr=args.require_ocr,
        )
        ocr_path = resolved.path
        ocr_diagnostics = resolved.diagnostics
    elif args.require_ocr:
        raise SystemExit("--require-ocr needs either --ocr or --run-ocr")

    allow_missing_ocr = args.allow_missing_ocr and not args.require_ocr
    result = run_pipeline(
        image_path=Path(args.image),
        ocr_path=ocr_path,
        out_dir=out_dir,
        allow_missing_ocr=allow_missing_ocr,
        options=PipelineOptions(tile_size=args.tile_size),
        model_evidence_path=Path(args.model_evidence) if args.model_evidence else None,
        ocr_diagnostics=ocr_diagnostics,
    )
    d = result.diagnostics
    print(
        "PSD-like Python service: "
        f"text={d.get('textLayerCount', 0)} raster={d.get('rasterLayerCount', 0)} "
        f"shape={d.get('shapeLayerCount', 0)} missing_assets={d.get('missingAssetCount', 0)} "
        f"ocr_provider={d.get('ocrProvider', '')} ocr_cache_hit={d.get('ocrCacheHit', '')} "
        f"ocr_text={d.get('ocrTextCount', 0)} "
        f"out={result.out_dir}"
    )
    if ocr_diagnostics:
        print(json.dumps({"ocrDiagnostics": ocr_diagnostics}, ensure_ascii=False))


if __name__ == "__main__":
    main()
