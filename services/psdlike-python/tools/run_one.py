#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.pipeline import PipelineOptions, run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run clean PSD-like Python pipeline on one image.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--ocr", default="")
    parser.add_argument("--model-evidence", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--allow-missing-ocr", action="store_true", default=True)
    parser.add_argument("--tile-size", type=int, default=8)
    args = parser.parse_args()
    result = run_pipeline(
        image_path=Path(args.image),
        ocr_path=Path(args.ocr) if args.ocr else None,
        out_dir=Path(args.out),
        allow_missing_ocr=args.allow_missing_ocr,
        options=PipelineOptions(tile_size=args.tile_size),
        model_evidence_path=Path(args.model_evidence) if args.model_evidence else None,
    )
    d = result.diagnostics
    print(
        "PSD-like Python service: "
        f"text={d.get('textLayerCount', 0)} raster={d.get('rasterLayerCount', 0)} "
        f"shape={d.get('shapeLayerCount', 0)} missing_assets={d.get('missingAssetCount', 0)} "
        f"out={result.out_dir}"
    )


if __name__ == "__main__":
    main()
