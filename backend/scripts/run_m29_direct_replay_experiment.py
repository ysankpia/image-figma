from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.m29_direct_replay import M29DirectReplayOptions, build_m29_direct_replay_dsl
from app.text_masked_media_audit import text_boxes_from_ocr_document
from app.visual_primitive_graph import M29VisualPrimitiveOptions, extract_m29_visual_primitive_graph


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    output_dir = resolve_output_dir(Path(args.output_dir), overwrite=args.overwrite)
    source_png = source.read_bytes()

    ocr_document = read_json(Path(args.ocr_json).expanduser().resolve()) if args.ocr_json else None
    m29_document = read_json(Path(args.m29_json).expanduser().resolve()) if args.m29_json else None
    if m29_document is None:
        text_boxes = []
        if ocr_document is not None:
            text_boxes, warnings = text_boxes_from_ocr_document(ocr_document)
            for warning in warnings:
                print(f"OCR warning: {warning}")
        m29_output = output_dir / "m29"
        m29_document = extract_m29_visual_primitive_graph(
            png_data=source_png,
            source_image=str(source),
            output_dir=m29_output,
            options=M29VisualPrimitiveOptions(),
            text_boxes=text_boxes,
        ).to_dict()
        m29_document["sourceM29NodesJson"] = str((m29_output / "nodes.json").resolve())
    else:
        m29_document["sourceM29NodesJson"] = str(Path(args.m29_json).expanduser().resolve())

    result = build_m29_direct_replay_dsl(
        source_png=source_png,
        source_image_path=str(source),
        m29_document=m29_document,
        ocr_document=ocr_document,
        output_dir=output_dir,
        options=M29DirectReplayOptions(max_total_visible_nodes=args.max_total_visible_nodes),
        task_id=args.task_id,
    )
    print(f"Wrote {output_dir / 'm29_direct_replay_dsl.json'}")
    print(f"Wrote {output_dir / 'm29_direct_replay_report.json'}")
    summary = result.report["summary"]
    print(
        "M29 direct replay: text={replayedTextCount} image={replayedImageCount} "
        "symbol={replayedSymbolCount} shape={replayedShapeCount} visible={visibleNodeCount} "
        "fallbackErased={fallbackErasedBBoxCount}".format(**summary)
    )
    if result.report.get("warnings"):
        print("Warnings: " + ", ".join(result.report["warnings"]))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run branch-only M29 direct replay experiment.")
    parser.add_argument("--input", required=True, help="Source PNG path.")
    parser.add_argument("--output-dir", default="storage/m29_direct_replay")
    parser.add_argument("--m29-json", default="", help="Optional existing M29 nodes.json.")
    parser.add_argument("--ocr-json", default="", help="Optional OCR ocr.json.")
    parser.add_argument("--task-id", default="m29_direct_replay")
    parser.add_argument("--max-total-visible-nodes", type=int, default=M29DirectReplayOptions.max_total_visible_nodes)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def resolve_output_dir(path: Path, *, overwrite: bool) -> Path:
    resolved = path.expanduser().resolve()
    if overwrite or not resolved.exists():
        return resolved
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolved.with_name(f"{resolved.name}_{suffix}")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
