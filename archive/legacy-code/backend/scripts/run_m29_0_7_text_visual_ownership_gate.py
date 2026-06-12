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

from app.text_visual_ownership_gate import M2907Options, extract_text_visual_ownership_gate  # noqa: E402


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"source image not found: {source}")
    m29_output = Path(args.m29_output).expanduser().resolve()
    m2903_output = Path(args.m2903_output).expanduser().resolve() if args.m2903_output else resolve_latest_output(m29_output, "m29_0_3", "visual_evidence.json")
    m2902_output = Path(args.m2902_output).expanduser().resolve() if args.m2902_output else resolve_latest_output(m29_output, "m29_0_2", "text_masked_media_audit.json")
    m2903_json = m2903_output / "visual_evidence.json"
    m2902_json = m2902_output / "text_masked_media_audit.json"
    for path in [m2903_json, m2902_json]:
        if not path.exists():
            raise FileNotFoundError(f"required M29 input not found: {path}")
    output_dir = resolve_output_dir(m29_output / "m29_0_7", overwrite=args.overwrite)
    document = extract_text_visual_ownership_gate(
        png_data=source.read_bytes(),
        source_image=str(source),
        m2903_document=json.loads(m2903_json.read_text(encoding="utf-8")),
        m2903_visual_evidence_json_path=str(m2903_json),
        m2902_document=json.loads(m2902_json.read_text(encoding="utf-8")),
        m2902_audit_json_path=str(m2902_json),
        output_dir=output_dir,
        options=M2907Options(
            text_owned_overlap_min=args.text_owned_overlap_min,
            text_owned_text_covered_min=args.text_owned_text_covered_min,
            ocr_confidence_min=args.ocr_confidence_min,
            visual_candidate_high_text_overlap=args.visual_candidate_high_text_overlap,
            text_preview_max_chars=args.text_preview_max_chars,
            output_preview_max_thumb=args.output_preview_max_thumb,
            max_examples_per_kind=args.max_examples_per_kind,
        ),
    )
    print(f"Resolved M29.0.3 visual evidence: {m2903_json}")
    print(f"Resolved M29.0.2 audit: {m2902_json}")
    print(f"Wrote {output_dir / 'text_visual_ownership_gate.json'}")
    print(f"Wrote {output_dir / 'preview_text_visual_ownership_gate.png'}")
    print(
        "M29.0.7 counts: "
        f"decisions={len(document.ownership_decisions)} "
        f"ownership={document.meta.get('ownershipCounts', {})}"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.0.7 text visual ownership gate.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--m2903-output", default="")
    parser.add_argument("--m2902-output", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--text-owned-overlap-min", type=float, default=M2907Options.text_owned_overlap_min)
    parser.add_argument("--text-owned-text-covered-min", type=float, default=M2907Options.text_owned_text_covered_min)
    parser.add_argument("--ocr-confidence-min", type=float, default=M2907Options.ocr_confidence_min)
    parser.add_argument("--visual-candidate-high-text-overlap", type=float, default=M2907Options.visual_candidate_high_text_overlap)
    parser.add_argument("--text-preview-max-chars", type=int, default=M2907Options.text_preview_max_chars)
    parser.add_argument("--output-preview-max-thumb", type=int, default=M2907Options.output_preview_max_thumb)
    parser.add_argument("--max-examples-per-kind", type=int, default=M2907Options.max_examples_per_kind)
    return parser.parse_args()


def resolve_latest_output(m29_output: Path, prefix: str, filename: str) -> Path:
    candidates = [path for path in m29_output.glob(f"{prefix}*") if path.is_dir() and (path / filename).exists()]
    if not candidates:
        raise FileNotFoundError(f"No {prefix} output found under {m29_output}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


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
