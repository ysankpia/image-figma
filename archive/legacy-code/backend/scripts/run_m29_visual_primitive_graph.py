from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.visual_primitive_graph import M29TextBox, M29VisualPrimitiveOptions
from app.visual_primitive_graph import extract_m29_visual_primitive_graph


DEFAULT_SOURCE_IMAGE = Path("/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png")


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    output_dir = resolve_output_dir(Path(args.output_dir), overwrite=args.overwrite)
    options = M29VisualPrimitiveOptions(
        min_component_area=args.min_component_area,
        max_component_area_ratio=args.max_component_area_ratio,
    )
    text_boxes = load_text_boxes(Path(args.text_boxes_json).expanduser().resolve()) if args.text_boxes_json else []
    document = extract_m29_visual_primitive_graph(
        png_data=source.read_bytes(),
        source_image=str(source),
        output_dir=output_dir,
        options=options,
        text_boxes=text_boxes,
    )
    print(f"Wrote {output_dir / 'nodes.json'}")
    print(f"Wrote {output_dir / 'preview_sheet.png'}")
    print(
        "M29 counts: text={text} shape={shape} image={image} symbol={symbol} unknown={unknown} blocked={blocked}".format(
            **document.meta["counts"]
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29 PNG -> visual primitive graph harness.")
    parser.add_argument("--input", default=str(DEFAULT_SOURCE_IMAGE))
    parser.add_argument("--output-dir", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--overwrite", action="store_true", help="Write into --output-dir even when it already exists.")
    parser.add_argument("--text-boxes-json", default="")
    parser.add_argument("--min-component-area", type=int, default=M29VisualPrimitiveOptions.min_component_area)
    parser.add_argument("--max-component-area-ratio", type=float, default=M29VisualPrimitiveOptions.max_component_area_ratio)
    return parser.parse_args()


def resolve_output_dir(path: Path, *, overwrite: bool) -> Path:
    resolved = path.expanduser().resolve()
    if overwrite or not resolved.exists():
        return resolved
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolved.with_name(f"{resolved.name}_{suffix}")


def load_text_boxes(path: Path) -> list[M29TextBox]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    boxes = payload.get("textBoxes", payload if isinstance(payload, list) else [])
    return [
        M29TextBox(
            id=str(item.get("id") or f"text_{index + 1:03d}"),
            bbox=[int(value) for value in item["bbox"]],
            text=item.get("text"),
            confidence=float(item.get("confidence", 1.0)),
            source=item.get("source", "manual"),
            kind=item.get("kind", "unknown"),
        )
        for index, item in enumerate(boxes)
        if isinstance(item, dict) and isinstance(item.get("bbox"), list) and len(item["bbox"]) == 4
    ]


if __name__ == "__main__":
    raise SystemExit(main())
