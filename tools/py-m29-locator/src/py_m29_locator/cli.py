from __future__ import annotations

import argparse
from pathlib import Path

from .locator import OUTPUT_NAME, locate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Locate M29.0 foreground regions in one PNG.")
    parser.add_argument("--input", required=True, help="Path to input PNG.")
    parser.add_argument("--out", required=True, help="Output directory.")
    args = parser.parse_args(argv)

    doc = locate(Path(args.input), Path(args.out))
    print(f"wrote {Path(args.out) / OUTPUT_NAME} ({len(doc['items'])} items)")
    return 0
