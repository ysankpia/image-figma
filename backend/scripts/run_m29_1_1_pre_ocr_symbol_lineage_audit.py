from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pre_ocr_symbol_lineage_audit import PreOcrSymbolLineageAuditOptions, extract_pre_ocr_symbol_lineage_audit  # noqa: E402


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"source image not found: {source}")
    m29_output = Path(args.m29_output).expanduser().resolve()
    m29_nodes_json = Path(args.m29_nodes_json).expanduser().resolve() if args.m29_nodes_json else m29_output / "nodes.json"
    if not m29_nodes_json.exists():
        raise FileNotFoundError(f"M29 nodes JSON not found: {m29_nodes_json}")
    m291_json = resolve_optional_json(args.m291_output, m29_output, "m29_1", "group_nodes.json")
    m2902_json = resolve_optional_json(args.m2902_output, m29_output, "m29_0_2", "text_masked_media_audit.json")
    m2903_json = resolve_optional_json(args.m2903_output, m29_output, "m29_0_3", "visual_evidence.json")
    m2907_json = resolve_optional_json(args.m2907_output, m29_output, "m29_0_7", "text_visual_ownership_gate.json")
    output_dir = resolve_output_dir(m29_output / "m29_1_1", overwrite=args.overwrite)
    document = extract_pre_ocr_symbol_lineage_audit(
        png_data=source.read_bytes(),
        source_image=str(source),
        m29_document=json.loads(m29_nodes_json.read_text(encoding="utf-8")),
        m29_nodes_json_path=str(m29_nodes_json),
        output_dir=output_dir,
        m291_document=load_json(m291_json),
        m291_group_nodes_json_path=str(m291_json) if m291_json else None,
        m2902_document=load_json(m2902_json),
        m2902_audit_json_path=str(m2902_json) if m2902_json else None,
        m2903_document=load_json(m2903_json),
        m2903_visual_evidence_json_path=str(m2903_json) if m2903_json else None,
        m2907_document=load_json(m2907_json),
        m2907_ownership_json_path=str(m2907_json) if m2907_json else None,
        options=PreOcrSymbolLineageAuditOptions(
            match_iou_min=args.match_iou_min,
            max_examples_per_kind=args.max_examples_per_kind,
        ),
    )
    print(f"Resolved M29 nodes: {m29_nodes_json}")
    if m291_json:
        print(f"Resolved M29.1 groups: {m291_json}")
    if m2903_json:
        print(f"Resolved M29.0.3 visual evidence: {m2903_json}")
    if m2907_json:
        print(f"Resolved M29.0.7 ownership: {m2907_json}")
    print(f"Wrote {output_dir / 'pre_ocr_symbol_lineage_audit.json'}")
    print(f"Wrote {output_dir / 'overlay_pre_ocr_symbol_lineage.png'}")
    print(f"M29.1.1 findings: {document.summary.get('byFindingKind', {})}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.1.1 pre-OCR symbol lineage audit.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--m29-nodes-json", default="")
    parser.add_argument("--m291-output", default="")
    parser.add_argument("--m2902-output", default="")
    parser.add_argument("--m2903-output", default="")
    parser.add_argument("--m2907-output", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--match-iou-min", type=float, default=PreOcrSymbolLineageAuditOptions.match_iou_min)
    parser.add_argument("--max-examples-per-kind", type=int, default=PreOcrSymbolLineageAuditOptions.max_examples_per_kind)
    return parser.parse_args()


def resolve_optional_json(arg_value: str, m29_output: Path, prefix: str, filename: str) -> Path | None:
    if arg_value:
        path = Path(arg_value).expanduser().resolve()
        candidate = path / filename if path.is_dir() else path
        if not candidate.exists():
            raise FileNotFoundError(f"required M29 input not found: {candidate}")
        return candidate
    candidates = [path for path in m29_output.glob(f"{prefix}*") if path.is_dir() and (path / filename).exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime) / filename


def load_json(path: Path | None) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path is not None else None


def resolve_output_dir(path: Path, *, overwrite: bool) -> Path:
    resolved = path.expanduser().resolve()
    if overwrite:
        if resolved.exists():
            shutil.rmtree(resolved)
        return resolved
    if not resolved.exists():
        return resolved
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolved.with_name(f"{resolved.name}_{suffix}")


if __name__ == "__main__":
    raise SystemExit(main())
