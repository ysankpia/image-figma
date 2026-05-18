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

from app.visual_evidence_normalization import VisualEvidenceOptions, extract_visual_evidence_normalization


DEFAULT_SOURCE_IMAGE = Path("/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png")


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    m29_output = Path(args.m29_output).expanduser().resolve()
    m2902_output = Path(args.m2902_output).expanduser().resolve() if args.m2902_output else resolve_latest_m2902_output(m29_output)
    m2902_json = m2902_output / "text_masked_media_audit.json"
    if not m2902_json.exists():
        raise FileNotFoundError(f"M29.0.2 audit JSON not found: {m2902_json}")
    output_dir = resolve_output_dir(m29_output / "m29_0_3", overwrite=args.overwrite)
    document = extract_visual_evidence_normalization(
        png_data=source.read_bytes(),
        source_image=str(source),
        m2902_document=json.loads(m2902_json.read_text(encoding="utf-8")),
        m2902_audit_json_path=str(m2902_json),
        output_dir=output_dir,
        options=VisualEvidenceOptions(
            text_noise_overlap_threshold=args.text_noise_overlap_threshold,
            media_candidate_text_overlap_max=args.media_candidate_text_overlap_max,
            icon_candidate_text_overlap_max=args.icon_candidate_text_overlap_max,
            media_candidate_min_area=args.media_candidate_min_area,
            output_preview_max_thumb=args.output_preview_max_thumb,
        ),
    )
    print(f"Resolved M29.0.2 audit: {m2902_json}")
    print(f"Wrote {output_dir / 'visual_evidence.json'}")
    print(f"Wrote {output_dir / 'preview_visual_evidence.png'}")
    print(f"M29.0.3 counts: items={document.meta['itemCount']} buckets={document.meta['bucketCounts']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.0.3 visual evidence normalization.")
    parser.add_argument("--input", default=str(DEFAULT_SOURCE_IMAGE))
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--m2902-output", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--text-noise-overlap-threshold", type=float, default=VisualEvidenceOptions.text_noise_overlap_threshold)
    parser.add_argument("--media-candidate-text-overlap-max", type=float, default=VisualEvidenceOptions.media_candidate_text_overlap_max)
    parser.add_argument("--icon-candidate-text-overlap-max", type=float, default=VisualEvidenceOptions.icon_candidate_text_overlap_max)
    parser.add_argument("--media-candidate-min-area", type=int, default=VisualEvidenceOptions.media_candidate_min_area)
    parser.add_argument("--output-preview-max-thumb", type=int, default=VisualEvidenceOptions.output_preview_max_thumb)
    return parser.parse_args()


def resolve_latest_m2902_output(m29_output: Path) -> Path:
    candidates = [
        path
        for path in m29_output.glob("m29_0_2*")
        if path.is_dir() and (path / "text_masked_media_audit.json").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"No M29.0.2 output found under {m29_output}")
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
