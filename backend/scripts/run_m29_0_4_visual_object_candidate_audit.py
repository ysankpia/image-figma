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

from app.visual_object_candidate_audit import M2904Options, M2904SourceExpansionRefs, extract_visual_object_candidate_audit


DEFAULT_SOURCE_IMAGE = Path("/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png")


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    m29_output = Path(args.m29_output).expanduser().resolve()
    m2903_output = Path(args.m2903_output).expanduser().resolve() if args.m2903_output else resolve_latest_output(m29_output, "m29_0_3", "visual_evidence.json")
    m2902_output = Path(args.m2902_output).expanduser().resolve() if args.m2902_output else resolve_latest_output(m29_output, "m29_0_2", "text_masked_media_audit.json")
    m2903_json = m2903_output / "visual_evidence.json"
    m2902_json = m2902_output / "text_masked_media_audit.json"
    if not m2903_json.exists():
        raise FileNotFoundError(f"M29.0.3 visual evidence JSON not found: {m2903_json}")
    if not m2902_json.exists():
        raise FileNotFoundError(f"M29.0.2 audit JSON not found: {m2902_json}")
    output_dir = resolve_output_dir(m29_output / "m29_0_4", overwrite=args.overwrite)
    document = extract_visual_object_candidate_audit(
        png_data=source.read_bytes(),
        source_image=str(source),
        m2903_document=json.loads(m2903_json.read_text(encoding="utf-8")),
        m2903_visual_evidence_json_path=str(m2903_json),
        m2902_document=json.loads(m2902_json.read_text(encoding="utf-8")),
        m2902_audit_json_path=str(m2902_json),
        output_dir=output_dir,
        source_expansion_refs=M2904SourceExpansionRefs(
            m29_nodes_json=str(Path(args.m29_nodes_json).expanduser().resolve()) if args.m29_nodes_json else None,
            m291_group_nodes_json=str(Path(args.m291_group_nodes_json).expanduser().resolve()) if args.m291_group_nodes_json else None,
            m2902_media_evidence_json=str(m2902_json),
        ),
        options=M2904Options(
            edge_threshold=args.edge_threshold,
            weak_edge_threshold=args.weak_edge_threshold,
            max_object_members=args.max_object_members,
            output_preview_max_thumb=args.output_preview_max_thumb,
        ),
    )
    print(f"Resolved M29.0.3 visual evidence: {m2903_json}")
    print(f"Resolved M29.0.2 audit: {m2902_json}")
    print(f"Wrote {output_dir / 'visual_object_candidates.json'}")
    print(f"Wrote {output_dir / 'edge_audit.json'}")
    print(f"Wrote {output_dir / 'preview_visual_objects.png'}")
    print(
        "M29.0.4 counts: "
        f"nodes={len(document.evidence_nodes)} edges={len(document.evidence_edges)} "
        f"objects={len(document.objects)} sets={len(document.sets)}"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.0.4 generic visual object candidate audit.")
    parser.add_argument("--input", default=str(DEFAULT_SOURCE_IMAGE))
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--m2903-output", default="")
    parser.add_argument("--m2902-output", default="")
    parser.add_argument("--m29-nodes-json", default="")
    parser.add_argument("--m291-group-nodes-json", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--edge-threshold", type=float, default=M2904Options.edge_threshold)
    parser.add_argument("--weak-edge-threshold", type=float, default=M2904Options.weak_edge_threshold)
    parser.add_argument("--max-object-members", type=int, default=M2904Options.max_object_members)
    parser.add_argument("--output-preview-max-thumb", type=int, default=M2904Options.output_preview_max_thumb)
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
