from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import get_settings
from ..project_builder import discover_inputs, export_project
from ..types import ExportRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export one or more images to a Pencil project ZIP.")
    parser.add_argument("--input", action="append", default=[], type=Path, help="Image file or image directory. Repeatable.")
    parser.add_argument("--manifest", action="append", default=[], type=Path, help="JSON manifest with pages[].path or cases[].sourcePath.")
    parser.add_argument("--out", required=True, type=Path, help="Output directory.")
    parser.add_argument("--project-name", default="Pencil Project")
    parser.add_argument("--mode", choices=("all", "clean-editable", "visual-fidelity", "visual-ocr"), default="all")
    parser.add_argument("--columns", default="auto")
    parser.add_argument("--include-debug", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--ocr-provider", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = discover_inputs(args.input, args.manifest)
    if not inputs:
        raise SystemExit("no input images found")
    settings = get_settings()
    manifest = export_project(
        ExportRequest(
            inputs=inputs,
            out_dir=args.out.expanduser().resolve(),
            project_name=args.project_name,
            mode=args.mode,
            columns=args.columns,
            include_debug=args.include_debug,
            ocr_provider=args.ocr_provider,
        ),
        settings,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
