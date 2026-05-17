from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ui_visual_extraction import DEFAULT_CHECKPOINT, DEFAULT_SOURCE_IMAGE, M28ExtractionOptions
from app.ui_visual_extraction import extract_m28_ui_visual_objects


def main() -> int:
    args = parse_args()
    output_dir = resolve_output_dir(Path(args.output_dir), overwrite=args.overwrite)
    document = extract_m28_ui_visual_objects(
        M28ExtractionOptions(
            source_image=Path(args.input),
            checkpoint=Path(args.checkpoint),
            output_dir=output_dir,
            quality=args.quality,
            model_cfg=args.model_cfg,
            device=args.device,
            max_image_edge=args.max_image_edge,
            points_per_side=args.points_per_side,
            points_per_batch=args.points_per_batch,
            max_masks=args.max_masks,
        )
    )
    print(f"Wrote {Path(document.previewSheetPath or '').resolve()}")
    print(f"Wrote {Path(document.overlayPath or '').resolve()}")
    print(
        "M28 counts: icons={icons} imageAssets={images} controls={controls} blocked={blocked} rawMasks={raw} inferMs={infer} postMs={post} device={device}".format(
            icons=document.meta["iconCount"],
            images=document.meta["imageAssetCount"],
            controls=document.meta["controlCount"],
            blocked=document.meta["blockedCount"],
            raw=document.sam.rawMaskCount,
            infer=document.sam.inferenceMs,
            post=document.sam.postprocessMs,
            device=document.sam.device,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M28 single-image SAM2 UI visual extraction.")
    parser.add_argument("--input", default=str(DEFAULT_SOURCE_IMAGE))
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--output-dir", default="storage/m28_single_visual_extraction")
    parser.add_argument("--quality", choices=["default", "high"], default="default")
    parser.add_argument("--model-cfg", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-image-edge", type=int, default=1280)
    parser.add_argument("--points-per-side", type=int, default=None)
    parser.add_argument("--points-per-batch", type=int, default=64)
    parser.add_argument("--max-masks", type=int, default=500)
    parser.add_argument("--overwrite", action="store_true", help="Write into --output-dir even when it already exists.")
    return parser.parse_args()


def resolve_output_dir(path: Path, *, overwrite: bool) -> Path:
    resolved = path.expanduser().resolve()
    if overwrite or not resolved.exists():
        return resolved
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolved.with_name(f"{resolved.name}_{suffix}")


if __name__ == "__main__":
    raise SystemExit(main())
