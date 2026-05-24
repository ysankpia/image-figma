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

from app.mixed_symbol_text_conflict_audit import M2913Options, build_batch_summary, extract_mixed_symbol_text_conflict_audit  # noqa: E402


def main() -> int:
    args = parse_args()
    if args.batch_root:
        return run_batch(args)
    document, output_dir = run_single(args, Path(args.m29_output).expanduser().resolve(), explicit_input=args.input)
    print_single_result(document, output_dir)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    batch_root = Path(args.batch_root).expanduser().resolve()
    input_root = Path(args.input_root).expanduser().resolve() if args.input_root else None
    if not batch_root.exists():
        raise FileNotFoundError(f"batch root not found: {batch_root}")
    image_documents = []
    m2905_by_image = {}
    for image_dir in sorted(path for path in batch_root.glob("image_*") if path.is_dir()):
        source = resolve_batch_source(image_dir, input_root)
        print(f"== {image_dir.name} == {source}")
        document, output_dir = run_single(args, image_dir, explicit_input=str(source))
        print_single_result(document, output_dir)
        image_documents.append((image_dir.name, document))
        if m2905_json := resolve_optional_json(args.m2905_output, image_dir, "m29_0_5", "refined_visual_objects.json", required=False):
            m2905_by_image[image_dir.name] = load_json(m2905_json) or {}
    build_batch_summary(image_documents, batch_root, m2905_by_image=m2905_by_image)
    print(f"Wrote {batch_root / 'm29_1_3_batch_summary.json'}")
    print(f"Wrote {batch_root / 'm29_1_3_batch_summary.csv'}")
    return 0


def run_single(args: argparse.Namespace, m29_output: Path, *, explicit_input: str) -> tuple[object, Path]:
    if not explicit_input:
        raise ValueError("--input is required unless --batch-root is used")
    source = Path(explicit_input).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"source image not found: {source}")
    m2903_json = resolve_optional_json(args.m2903_output, m29_output, "m29_0_3", "visual_evidence.json", required=True)
    m2907_json = resolve_optional_json(args.m2907_output, m29_output, "m29_0_7", "text_visual_ownership_gate.json", required=False)
    m291_json = resolve_optional_json(args.m291_output, m29_output, "m29_1", "group_nodes.json", required=False)
    m2902_json = resolve_optional_json(args.m2902_output, m29_output, "m29_0_2", "text_masked_media_audit.json", required=False)
    output_dir = resolve_output_dir(m29_output / "m29_1_3", overwrite=args.overwrite)
    document = extract_mixed_symbol_text_conflict_audit(
        png_data=source.read_bytes(),
        source_image=str(source),
        m2903_document=load_json(m2903_json) or {},
        m2903_visual_evidence_json_path=str(m2903_json),
        output_dir=output_dir,
        m2907_document=load_json(m2907_json),
        m2907_ownership_json_path=str(m2907_json) if m2907_json else None,
        m291_document=load_json(m291_json),
        m291_group_nodes_json_path=str(m291_json) if m291_json else None,
        m2911_document=None,
        m2911_lineage_audit_json_path=None,
        m2902_document=load_json(m2902_json),
        m2902_audit_json_path=str(m2902_json) if m2902_json else None,
        options=M2913Options(
            full_ocr_coverage_min=args.full_ocr_coverage_min,
            partial_ocr_overlap_min=args.partial_ocr_overlap_min,
            text_like_aspect_min=args.text_like_aspect_min,
            compact_max_edge=args.compact_max_edge,
            compact_max_area=args.compact_max_area,
            repeated_alignment_tolerance=args.repeated_alignment_tolerance,
            label_adjacency_max_gap=args.label_adjacency_max_gap,
            duplicate_iou_min=args.duplicate_iou_min,
            max_examples_per_classification=args.max_examples_per_classification,
        ),
    )
    return document, output_dir


def print_single_result(document: object, output_dir: Path) -> None:
    print(f"Resolved M29.0.3 visual evidence: {document.source_m2903_visual_evidence_json}")
    print(f"Wrote {output_dir / 'mixed_symbol_text_conflict_audit.json'}")
    print(f"Wrote {output_dir / 'overlay_mixed_symbol_text_conflicts.png'}")
    print(f"M29.1.3 conflicts: {document.summary.get('byClassification', {})}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.1.3 mixed symbol/text conflict classification audit.")
    parser.add_argument("--input", default="")
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--batch-root", default="")
    parser.add_argument("--input-root", default="")
    parser.add_argument("--m2903-output", default="")
    parser.add_argument("--m2907-output", default="")
    parser.add_argument("--m291-output", default="")
    parser.add_argument("--m2902-output", default="")
    parser.add_argument("--m2905-output", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--full-ocr-coverage-min", type=float, default=M2913Options.full_ocr_coverage_min)
    parser.add_argument("--partial-ocr-overlap-min", type=float, default=M2913Options.partial_ocr_overlap_min)
    parser.add_argument("--text-like-aspect-min", type=float, default=M2913Options.text_like_aspect_min)
    parser.add_argument("--compact-max-edge", type=int, default=M2913Options.compact_max_edge)
    parser.add_argument("--compact-max-area", type=int, default=M2913Options.compact_max_area)
    parser.add_argument("--repeated-alignment-tolerance", type=int, default=M2913Options.repeated_alignment_tolerance)
    parser.add_argument("--label-adjacency-max-gap", type=int, default=M2913Options.label_adjacency_max_gap)
    parser.add_argument("--duplicate-iou-min", type=float, default=M2913Options.duplicate_iou_min)
    parser.add_argument("--max-examples-per-classification", type=int, default=M2913Options.max_examples_per_classification)
    return parser.parse_args()


def resolve_optional_json(arg_value: str, m29_output: Path, prefix: str, filename: str, *, required: bool) -> Path | None:
    if arg_value:
        path = Path(arg_value).expanduser().resolve()
        candidate = path / filename if path.is_dir() else path
        if not candidate.exists():
            raise FileNotFoundError(f"required M29 input not found: {candidate}")
        return candidate
    candidates = [path for path in m29_output.glob(f"{prefix}*") if path.is_dir() and (path / filename).exists()]
    if not candidates:
        if required:
            raise FileNotFoundError(f"No {prefix} output found under {m29_output}")
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


def resolve_batch_source(image_dir: Path, input_root: Path | None) -> Path:
    for relative in [
        Path("m29_0_3") / "visual_evidence.json",
        Path("m29_1") / "group_nodes.json",
        Path("nodes.json"),
    ]:
        source_json = image_dir / relative
        if not source_json.exists():
            continue
        value = (load_json(source_json) or {}).get("sourceImage")
        if not value:
            continue
        path = Path(str(value).split("#", 1)[0]).expanduser()
        if path.exists():
            return path.resolve()
        if input_root is not None:
            candidate = input_root / path.name
            if candidate.exists():
                return candidate.resolve()
    if input_root is not None:
        index = int(image_dir.name.split("_")[-1])
        matches = sorted(input_root.glob(f"*({index}).png"))
        if matches:
            return matches[0].resolve()
    raise FileNotFoundError(f"cannot resolve source image for {image_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
