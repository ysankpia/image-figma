from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.ocr import extract_ocr
from app.png_tools import read_png_metadata
from app.text_masked_media_audit import (
    MediaAuditRegion,
    TextMaskedMediaAuditOptions,
    extract_text_masked_media_audit,
    text_boxes_from_ocr_document,
)
from app.visual_primitive_graph import M29TextBox


DEFAULT_SOURCE_IMAGE = Path("/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png")


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    png_data = source.read_bytes()
    output_dir = resolve_output_dir(resolve_m2902_output_dir(Path(args.m29_output)), overwrite=args.overwrite)
    m29_document, m29_nodes_path = load_optional_m29(Path(args.m29_output).expanduser().resolve())
    m291_document, m291_path = load_optional_m291(Path(args.m29_output).expanduser().resolve())
    text_boxes, text_source, warnings = load_text_source(args, source, png_data)
    regions = load_regions(Path(args.media_audit_region_json).expanduser().resolve()) if args.media_audit_region_json else None
    document = extract_text_masked_media_audit(
        png_data=png_data,
        source_image=str(source),
        output_dir=output_dir,
        text_boxes=text_boxes,
        text_source=text_source,
        m29_document=m29_document,
        m29_nodes_json_path=str(m29_nodes_path) if m29_nodes_path else None,
        m291_document=m291_document,
        m291_group_nodes_json_path=str(m291_path) if m291_path else None,
        regions=regions,
        options=TextMaskedMediaAuditOptions(
            text_padding=args.text_padding,
            min_media_like_area=args.min_media_like_area,
        ),
        warnings=warnings,
    )
    print(f"Wrote {output_dir / 'text_masked_media_audit.json'}")
    print(f"Wrote {output_dir / 'preview_text_masked_media_audit.png'}")
    print(
        "M29.0.2 counts: textBoxes={textBoxCount} evidence={evidenceCount}".format(
            **document.meta
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.0.2 text-masked visual media audit.")
    parser.add_argument("--input", default=str(DEFAULT_SOURCE_IMAGE))
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--text-boxes-json", default="")
    parser.add_argument("--ocr-json", default="")
    parser.add_argument("--ocr-provider", choices=["", "baidu_ppocrv5"], default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--text-padding", type=int, default=TextMaskedMediaAuditOptions.text_padding)
    parser.add_argument("--min-media-like-area", type=int, default=TextMaskedMediaAuditOptions.min_media_like_area)
    parser.add_argument("--media-audit-region-json", default="")
    return parser.parse_args()


def resolve_m2902_output_dir(m29_output: Path) -> Path:
    return m29_output.expanduser().resolve() / "m29_0_2"


def resolve_output_dir(path: Path, *, overwrite: bool) -> Path:
    resolved = path.expanduser().resolve()
    if overwrite or not resolved.exists():
        return resolved
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolved.with_name(f"{resolved.name}_{suffix}")


def load_optional_m29(m29_output: Path) -> tuple[dict | None, Path | None]:
    nodes_path = m29_output / "nodes.json"
    if not nodes_path.exists():
        return None, None
    return json.loads(nodes_path.read_text(encoding="utf-8")), nodes_path


def load_optional_m291(m29_output: Path) -> tuple[dict | None, Path | None]:
    group_path = m29_output / "m29_1" / "group_nodes.json"
    if not group_path.exists():
        return None, None
    return json.loads(group_path.read_text(encoding="utf-8")), group_path


def load_text_source(args: argparse.Namespace, source: Path, png_data: bytes) -> tuple[list[M29TextBox], str, list[str]]:
    if args.text_boxes_json:
        return load_text_boxes(Path(args.text_boxes_json).expanduser().resolve()), "text_boxes_json", []
    if args.ocr_json:
        payload = json.loads(Path(args.ocr_json).expanduser().resolve().read_text(encoding="utf-8"))
        boxes, warnings = text_boxes_from_ocr_document(payload)
        return boxes, "ocr_json", warnings
    if args.ocr_provider == "baidu_ppocrv5":
        metadata = read_png_metadata(png_data)
        if metadata is None:
            raise ValueError("source PNG metadata is unreadable")
        settings = replace(get_settings(), ocr_provider=args.ocr_provider)
        document = extract_ocr(task_id="m29_0_2_smoke", image=metadata, settings=settings, source_path=source)
        boxes, warnings = text_boxes_from_ocr_document(document.to_dict())
        return boxes, f"ocr_provider:{document.provider}:{document.status}", warnings + [warning.code for warning in document.warnings]
    return [], "none", ["no_text_source_provided"]


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


def load_regions(path: Path) -> list[MediaAuditRegion]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("regions", payload if isinstance(payload, list) else [])
    regions: list[MediaAuditRegion] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("bbox"), list) or len(item["bbox"]) != 4:
            continue
        regions.append(MediaAuditRegion(str(item.get("name") or f"region_{index + 1:03d}"), [int(value) for value in item["bbox"]]))
    return regions


if __name__ == "__main__":
    raise SystemExit(main())
