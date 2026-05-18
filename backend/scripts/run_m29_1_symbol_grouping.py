from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.symbol_fragment_grouping import M291Options, extract_m291_symbol_fragment_grouping


DEFAULT_SOURCE_IMAGE = Path("/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png")


def main() -> int:
    args = parse_args()
    m29_output = Path(args.m29_output).expanduser().resolve()
    nodes_path = m29_output / "nodes.json"
    source = Path(args.input).expanduser().resolve()
    output_dir = resolve_output_dir(m29_output / "m29_1", overwrite=args.overwrite)
    options = M291Options(
        neighbor_search_radius=args.neighbor_search_radius,
        accepted_edge_threshold=args.accepted_edge_threshold,
        accepted_group_threshold=args.accepted_group_threshold,
    )
    document = extract_m291_symbol_fragment_grouping(
        m29_document=json.loads(nodes_path.read_text(encoding="utf-8")),
        m29_nodes_json_path=str(nodes_path),
        png_data=source.read_bytes(),
        source_image=str(source),
        output_dir=output_dir,
        options=options,
    )
    print(f"Wrote {output_dir / 'group_nodes.json'}")
    print(f"Wrote {output_dir / 'preview_sheet.png'}")
    print(
        "M29.1 counts: candidates={candidates} edges={edges} groups={groups} acceptedGroups={acceptedGroups} uncertainGroups={uncertainGroups} rejectedGroups={rejectedGroups}".format(
            **document.meta["counts"]
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.1 symbol fragment grouping harness.")
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--input", default=str(DEFAULT_SOURCE_IMAGE))
    parser.add_argument("--overwrite", action="store_true", help="Write into m29_1 even when it already exists.")
    parser.add_argument("--neighbor-search-radius", type=int, default=M291Options.neighbor_search_radius)
    parser.add_argument("--accepted-edge-threshold", type=float, default=M291Options.accepted_edge_threshold)
    parser.add_argument("--accepted-group-threshold", type=float, default=M291Options.accepted_group_threshold)
    return parser.parse_args()


def resolve_output_dir(path: Path, *, overwrite: bool) -> Path:
    resolved = path.expanduser().resolve()
    if overwrite or not resolved.exists():
        return resolved
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolved.with_name(f"{resolved.name}_{suffix}")


if __name__ == "__main__":
    raise SystemExit(main())
